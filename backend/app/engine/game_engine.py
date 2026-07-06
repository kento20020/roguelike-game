"""ゲームエンジン — 状態機械＋経済。API と bot が共通で呼ぶ唯一の窓口。

各公開アクションは破壊的にゲーム状態を更新し、`snapshot()`（完全な状態）を返す。
combat_log（表示専用）と RunRecord（統計専用）は別管理で同期しない。
"""
from __future__ import annotations

from typing import Any, Optional

from app.data.loader import GameData, get_data
from app.engine import chaos_weights as cw
from app.engine import combat_resolver as cr
from app.engine import gate_resolver as gr
from app.engine import tells
from app.engine.floor_generator import build_enemy_instance, generate_floor
from app.engine.rng import (
    STREAM_CHAOS,
    STREAM_GATE,
    STREAM_GENERAL,
    STREAM_HEAL,
    STREAM_TREASURE,
    STREAM_BEHAVIOR,
    GameRNG,
)
from app.schemas.models import (
    HANSHA,
    PHASE_BATTLE,
    PHASE_CLEARED,
    PHASE_DEAD,
    PHASE_EXPLORING,
    PHASE_GATE_PREVIEW,
    PHASE_HEAL,
    PHASE_NEXT_FLOOR,
    PHASE_TREASURE_OPENED,
    PHASE_TREASURE_PREVIEW,
    Battle,
    EnemyInstance,
    Floor,
    Node,
    Player,
    RunRecord,
)

MOD_POOL = ["mikiri", "kasoku_dome", "juso", "hansha", "yomi", "kouki"]
MAX_FLOOR = 5


class IllegalAction(RuntimeError):
    """不正操作の基底。"""


class WrongPhase(IllegalAction):
    """その phase では許されない操作（API では HTTP 409）。"""


class InvalidMove(IllegalAction):
    """合法でない操作: ロックnode選択・チップ不足・満タン回復・未知sink等（HTTP 400）。"""


class GameEngine:
    def __init__(self, data: Optional[GameData] = None):
        self.data: GameData = data or get_data()
        self.rng: GameRNG | None = None
        self.player: Player | None = None
        self.run: RunRecord | None = None
        self.current_floor: int = 1
        self.floor: Floor | None = None
        self.phase: str = PHASE_EXPLORING
        self.battle: Battle | None = None
        self.chaos_weights: dict = {}
        self.pending: dict[str, Any] = {}
        self.gate_guarantee_uses: int = 0
        self.resolved: dict[str, bool] = {}
        self._postmortem: Optional[dict] = None  # _die() で計算済みの検死レポート（致命ターンの反実仮想）
        # ディーラー調書用: (enemy_id, behavior) の観測イベント。API層がDBへ反映しdrainする。
        self._pending_observations: list[tuple[str, str]] = []

    # ─────────────────────────── new run ───────────────────────────
    def new_run(self, seed: int, upgrades: Optional[dict[str, int]] = None,
                bot_type: str = "human") -> dict:
        self.rng = GameRNG(seed)
        up = {"max_hp": 0, "attack": 0, "init_gold": 0, "gold_drop": 0, "sink_cost": 0}
        up.update(upgrades or {})
        cfg = self.data.config
        items = cfg["permanent_upgrades"]["items"]
        base_hp = cfg["player"]["base_hp"] + items["max_hp"]["per_level"] * up["max_hp"]
        attack = cfg["player"]["base_attack"] + items["attack"]["per_level"] * up["attack"]
        chips = cfg["player"]["base_gold"] + items["init_gold"]["per_level"] * up["init_gold"]
        self.player = Player(hp=base_hp, max_hp=base_hp, attack=attack, chips=chips, mods=[])
        self._upgrades = up

        chaos_ids = [e["id"] for e in self.data.enemies if e.get("chaos")]
        self.chaos_weights = cw.generate_all(self.rng.stream(STREAM_CHAOS), chaos_ids)

        self.current_floor = 1
        self.resolved = {}
        self.floor = generate_floor(1, self.data, self.rng)
        self.phase = PHASE_EXPLORING
        self.battle = None
        self.pending = {}
        self.gate_guarantee_uses = 0
        self.run = RunRecord(run_id=f"run-{seed}", seed=seed, bot_type=bot_type,
                             floor_reached=1, permanent_upgrades_state=dict(up))
        return self.snapshot()

    # ─────────────────────────── node state ───────────────────────────
    def node_state(self, node: Node) -> str:
        if self.resolved.get(node.id):
            return "resolved"
        if not node.parents:
            return "available"
        return "available" if any(self.resolved.get(p) for p in node.parents) else "locked"

    def available_nodes(self) -> list[str]:
        return [n.id for n in self.floor.nodes.values() if self.node_state(n) == "available"]

    # ─────────────────────────── select node ───────────────────────────
    def select_node(self, node_id: str) -> dict:
        self._require(PHASE_EXPLORING)
        node = self.floor.nodes.get(node_id)
        if node is None:
            raise InvalidMove(f"unknown node {node_id}")
        if self.node_state(node) != "available":
            raise InvalidMove(f"node {node_id} not available")

        if node.kind == "enemy":
            self._enter_battle(node)
        elif node.kind == "gate_route":
            self.resolved[node.id] = True          # 通過（無料）
        elif node.kind == "treasure":
            if node.has_treasure:
                self.phase = PHASE_TREASURE_PREVIEW
                self.pending = {"node": node.id}
            else:
                self.resolved[node.id] = True       # 空（何もなし）
                self.pending = {"empty_treasure": True}
        elif node.kind == "heal":
            self._resolve_heal(node)
        elif node.kind == "gate":
            self.phase = PHASE_GATE_PREVIEW
            # 出目テーブル＋被ダメ実値（React に計算させない・表示専用）。
            self.pending = {
                "table": self.floor.gate_result_table,
                "damage": {o: gr.gate_damage(o, self.player.max_hp, self.data) for o in gr.OUTCOMES},
            }
        return self.snapshot()

    # ─────────────────────────── battle ───────────────────────────
    def _enter_battle(self, node: Node) -> None:
        enemy = build_enemy_instance(node.enemy_id, self.current_floor, self.data, self.chaos_weights)
        self.battle = Battle(enemy=enemy, node_id=node.id, floor=self.current_floor)
        self.battle.add_log(f"{enemy.name} が席についた。", "info")
        self.phase = PHASE_BATTLE
        # 先読み（yomi）: turn1 の行動を先引き
        cr.prepare_preview(self.battle, self.player, self.data, self.rng.stream(STREAM_BEHAVIOR))

    def attack(self, side_bet: Optional[dict] = None) -> dict:
        return self._combat_turn(guard=False, side_bet=side_bet)

    def guard(self, side_bet: Optional[dict] = None) -> dict:
        """受け（ガード）: 与ダメ半減・被ダメ大幅軽減。先読みを活かす攻防の選択。"""
        return self._combat_turn(guard=True, side_bet=side_bet)

    def _combat_turn(self, guard: bool, side_bet: Optional[dict] = None) -> dict:
        self._require(PHASE_BATTLE)
        return self._resolve_battle_turn(guard=guard, side_bet=side_bet, player_attacks=True,
                                         player_move="guard" if guard else "attack")

    def _resolve_battle_turn(self, *, guard: bool, side_bet: Optional[dict],
                             player_attacks: bool, player_move: str) -> dict:
        b, p = self.battle, self.player
        pre_snapshot = self._pre_turn_snapshot()
        b.side_bet_result = None  # 前ターン分の表示をクリア
        res = cr.resolve_turn(b, p, self.data, self.rng.stream(STREAM_BEHAVIOR),
                              guard=guard, player_attacks=player_attacks)
        # 表示契約: 直近ターンの実現結果（この時点でログにも出力済みの公開情報）。
        # UIがログ文言を解析して演出分岐する文字列依存をさせないための構造化フィールド。
        b.last_action, b.last_guard = res["action"], guard
        self._pending_observations.append((b.enemy.id, res["action"]))
        self.run.total_turns += 1
        self.run.turn_history.append({
            "node_id": b.node_id, "enemy_id": b.enemy.id, "guard": guard,
            "action": res["action"], "dealt": res["dealt"], "incoming": res["incoming"],
            "player_move": player_move,
            "player_hp_before": pre_snapshot["player"]["hp"], "player_hp_after": p.hp,
            "enemy_hp_before": pre_snapshot["enemy"]["hp"], "enemy_hp_after": b.enemy.hp,
            "ramp_value": res["ramp_value"], "kouki_cooldown": b.kouki_cooldown,
            "pre_turn_snapshot": pre_snapshot,
        })

        # サイドベット『読み宣言』: stream2(behavior_roll) の既存結果(res["action"])で判定。
        # 新規RNG消費は一切しない（このメソッドはここまでで rng.stream() を追加で呼ばない）。
        if side_bet is not None:
            b.side_bet_result = self._settle_side_bet(b, p, side_bet, res["action"])

        if res["player_dead"]:
            self._die(cause=f"{b.enemy.id}:{res['action']}")
            return self.snapshot()
        if res["enemy_dead"]:
            self._victory(b)
            return self.snapshot()
        # 継続: 次ターンの先読み
        cr.prepare_preview(b, p, self.data, self.rng.stream(STREAM_BEHAVIOR))
        return self.snapshot()

    def _pre_turn_snapshot(self) -> dict:
        """ターン解決"直前"の player/battle/enemy の軽量スナップショット（検死の反実仮想用）。
        値はすべて不変（str/int/float/bool/tuple）なので list(...) で十分＝実オブジェクトとは無関係。"""
        p, b, e = self.player, self.battle, self.battle.enemy
        return {
            "player": {
                "hp": p.hp, "max_hp": p.max_hp, "attack": p.attack, "chips": p.chips,
                "mods": list(p.mods), "stance_multiplier": p.stance_multiplier,
                "attack_boost_pending": p.attack_boost_pending,
            },
            "battle": {
                "turns": b.turns, "ramp_value": b.ramp_value, "kouki_cooldown": b.kouki_cooldown,
                "node_id": b.node_id, "floor": b.floor,
            },
            "enemy": {
                "id": e.id, "name": e.name, "experience": e.experience, "max_hp": e.max_hp,
                "hp": e.hp, "attack": e.attack, "difficulty": e.difficulty, "gold_base": e.gold_base,
                "chaos": e.chaos, "behaviors": list(e.behaviors), "ramp_increment": e.ramp_increment,
                "heavy_factor": e.heavy_factor, "counter_factor": e.counter_factor,
                "is_strong": e.is_strong,
            },
        }

    def _settle_side_bet(self, battle: Battle, player: Player, side_bet: dict, action: str) -> dict:
        """サイドベット『読み宣言』の検証＋判定。

        検証: 賭け額が min/max 範囲内・チップ足りているか・per_battle_cap 超過なし。
        違反時は InvalidMove（HTTP 400）。的中は payout_multiplier 倍の差分を加算、外れは没収。
        """
        cfg = self.data.config["side_bet"]
        amount = side_bet.get("amount")
        behavior = side_bet.get("behavior")
        if not isinstance(amount, int) or not (cfg["min_amount"] <= amount <= cfg["max_amount"]):
            raise InvalidMove(f"invalid side bet amount: {amount}")
        if player.chips < amount:
            raise InvalidMove("not enough chips for side bet")
        if battle.side_bet_total + amount > cfg["per_battle_cap"]:
            raise InvalidMove("side bet per-battle cap exceeded")

        battle.side_bet_total += amount
        hit = behavior == action
        if hit:
            payout = round(amount * (cfg["payout_multiplier"] - 1))
            player.chips += payout
        else:
            payout = -amount
            player.chips -= amount
        return {"hit": hit, "payout": payout}

    def _victory(self, b: Battle) -> None:
        e = b.enemy
        bonus = self.data.config["strong_enemy"]["gold_bonus_multiplier"] if e.is_strong else 1.0
        gold_mult = 1.0 + self.data.config["permanent_upgrades"]["items"]["gold_drop"]["per_level"] * self._upgrades["gold_drop"]
        gold = round(e.gold_base * self.floor.floor_multiplier * bonus * gold_mult)
        self.player.chips += gold
        self.run.gold_earned += gold
        self.run.enemies_defeated.append({
            "enemy_id": e.id, "experience": e.experience, "floor": self.current_floor, "turns": b.turns,
            "is_strong": e.is_strong,
        })
        self.resolved[b.node_id] = True
        self.battle = None
        victory = {"enemy": e.name, "gold": gold, "turns": b.turns}
        # 撃破ドロップ（多親×enemy・GDD §11.4）: has_treasure なら宝箱を開く。
        node = self.floor.nodes[b.node_id]
        if node.has_treasure:
            self.phase = PHASE_TREASURE_PREVIEW
            self.pending = {"node": b.node_id, "source": "enemy", "victory": victory}
        else:
            self.phase = PHASE_EXPLORING
            self.pending = {"victory": victory}

    def _die(self, cause: str) -> None:
        self.player.hp = 0
        self._postmortem = self._compute_postmortem()
        self.battle = None
        self.phase = PHASE_DEAD
        self._finalize(cleared=False, death_cause=cause)

    def _compute_postmortem(self) -> dict:
        """致命ターン（turn_historyの最後）の反実仮想: guardを反転してforced_actionで再現。
        forced_action指定によりroll_behaviorは呼ばれずRNGストリームは一切消費しない。"""
        if not self.run.turn_history:
            return {}
        last = self.run.turn_history[-1]
        snap = last["pre_turn_snapshot"]
        p_snap, b_snap, e_snap = snap["player"], snap["battle"], snap["enemy"]

        player = Player(
            hp=p_snap["hp"], max_hp=p_snap["max_hp"], attack=p_snap["attack"], chips=p_snap["chips"],
            mods=list(p_snap["mods"]), stance_multiplier=p_snap["stance_multiplier"],
            attack_boost_pending=p_snap["attack_boost_pending"],
        )
        enemy = EnemyInstance(
            id=e_snap["id"], name=e_snap["name"], experience=e_snap["experience"],
            max_hp=e_snap["max_hp"], hp=e_snap["hp"], attack=e_snap["attack"],
            difficulty=e_snap["difficulty"], gold_base=e_snap["gold_base"], chaos=e_snap["chaos"],
            behaviors=list(e_snap["behaviors"]), ramp_increment=e_snap["ramp_increment"],
            heavy_factor=e_snap["heavy_factor"], counter_factor=e_snap["counter_factor"],
            is_strong=e_snap["is_strong"],
        )
        battle = Battle(
            enemy=enemy, node_id=b_snap["node_id"], floor=b_snap["floor"],
            turns=b_snap["turns"], ramp_value=b_snap["ramp_value"],
            kouki_cooldown=b_snap["kouki_cooldown"],
        )

        original_guard = last["guard"]
        flipped_guard = not original_guard
        res = cr.resolve_turn(battle, player, self.data, self.rng.stream(STREAM_BEHAVIOR),
                              forced_action=last["action"], guard=flipped_guard)

        if res["player_dead"]:
            category, avoidable = "unavoidable", False
            message = "あれは避けられなかった"
        elif not res["enemy_dead"]:
            avoidable = True
            if flipped_guard:  # 実際はguard=False致命 → 「ガードしていれば」
                category = "avoidable_guard"
                message = "ガードしていれば生存していた"
            else:  # 実際はguard=True致命 → 「攻撃していれば」
                category = "avoidable_attack"
                message = "ガードせず攻撃していれば生存していた"
        else:
            category, avoidable = "mutual_kill_victory", True
            message = "相打ちで敵を先に倒せていた"

        return {
            "fatal_turn_index": len(self.run.turn_history) - 1,
            "original_guard": original_guard,
            "counterfactual_guard": flipped_guard,
            "category": category,
            "avoidable": avoidable,
            "message": message,
            "counterfactual_result": {
                "action": res["action"], "dealt": res["dealt"], "incoming": res["incoming"],
                "player_hp": player.hp, "enemy_hp": enemy.hp,
                "enemy_dead": res["enemy_dead"], "player_dead": res["player_dead"],
            },
        }

    # ─────────────────────────── treasure ───────────────────────────
    def treasure_open(self) -> dict:
        self._require(PHASE_TREASURE_PREVIEW)
        node = self.floor.nodes[self.pending["node"]]
        if node.fixed_mod:
            mod_id = node.fixed_mod
        else:
            mod_id = MOD_POOL[self.rng.stream(STREAM_TREASURE).randint(0, len(MOD_POOL) - 1)]
        self.player.mods.append(mod_id)
        self.run.mods_acquired.append(mod_id)
        self.resolved[node.id] = True
        self.phase = PHASE_TREASURE_OPENED
        # count: スタック段階（1枚目/2枚目以降）を UI で出すため。
        self.pending = {"mod": mod_id, "count": self.player.mod_count(mod_id)}
        return self.snapshot()

    def treasure_reroll(self) -> dict:
        self._require(PHASE_TREASURE_PREVIEW)
        node = self.floor.nodes[self.pending["node"]]
        if node.fixed_mod:
            raise InvalidMove("fixed-mod treasure cannot be rerolled")  # OPEN-017: 30G空費防止
        cost = self._sink_cost(self.data.config["sinks"]["treasure_reroll"])
        if self.player.chips < cost:
            raise InvalidMove("not enough chips for reroll")
        self.player.chips -= cost
        self.run.gold_spent["treasure_reroll"] += cost
        # 中身を引き直す（stream を1回進める＝次の open が変わる）
        self.rng.stream(STREAM_TREASURE).next_u32()
        return self.snapshot()

    # ─────────────────────────── heal node ───────────────────────────
    def _resolve_heal(self, node: Node) -> None:
        big = self.rng.stream(STREAM_HEAL).random() < 0.45
        # 回復量は固定値（GDD §7.3 v0.9確定）: 大回復 +30固定 / 小回復 +15固定。
        # max_hp の % ではなく固定値（恒久強化で max_hp が増える終盤ほど相対的に薄くなる）。
        amt = self.data.config["heal"]["node_large" if big else "node_small"]
        self.player.hp = min(self.player.max_hp, self.player.hp + amt)
        self.resolved[node.id] = True
        self.phase = PHASE_HEAL
        self.pending = {"heal": amt, "big": big}

    # ─────────────────────────── gate ───────────────────────────
    def gate_resolve(self) -> dict:
        self._require(PHASE_GATE_PREVIEW)
        table = dict(self.floor.gate_result_table)
        if self.gate_guarantee_uses:
            table = gr.apply_guarantee(table, self.gate_guarantee_uses, self.data)
        outcome = gr.roll_gate(table, self.rng.stream(STREAM_GATE))
        dmg = gr.gate_damage(outcome, self.player.max_hp, self.data)
        self.player.hp = max(0, self.player.hp - dmg)
        gate_node = next(n for n in self.floor.nodes.values() if n.kind == "gate")
        self.resolved[gate_node.id] = True

        # 特殊(special)＝一発逆転の「当たり」: 無傷通過＋ボーナスチップ（GDD §7.4「次フロア強化等」）。
        special_bonus = 0
        if outcome == "special":
            special_bonus = self.data.config["gate_special"]["bonus_gold"]
            self.player.chips += special_bonus
            self.run.gold_earned += special_bonus

        if self.player.hp <= 0:
            self.phase = PHASE_DEAD
            self._finalize(cleared=False, death_cause=f"gate:{outcome}")
            return self.snapshot()

        if self.current_floor >= MAX_FLOOR:
            self.phase = PHASE_CLEARED
            self.pending = {"gate_outcome": outcome, "special_bonus": special_bonus}
            self._finalize(cleared=True)
            return self.snapshot()

        # 次フロアへ: next_floor 演出 phase を発行してから exploring へ（GDD §6.1 厳密型）。
        # フロアは生成済みで、continue（dismiss）で exploring に入る。
        self.current_floor += 1
        self.run.floor_reached = self.current_floor
        self.resolved = {}
        self.gate_guarantee_uses = 0
        self.floor = generate_floor(self.current_floor, self.data, self.rng)
        self.phase = PHASE_NEXT_FLOOR
        self.pending = {"gate_outcome": outcome, "advanced_to": self.current_floor,
                        "special_bonus": special_bonus}
        return self.snapshot()

    # ─────────────────────────── sinks ───────────────────────────
    def _sink_cost(self, base: float) -> int:
        disc = -self.data.config["permanent_upgrades"]["items"]["sink_cost"]["per_level"] * self._upgrades["sink_cost"]
        # OPEN-019: 割引で 0G（無料スパム）にしない。下限1。
        return max(1, round(base - disc))

    def use_sink(self, sink_type: str) -> dict:
        p = self.data.config
        if sink_type == "scout":
            self._require(PHASE_BATTLE)
            cost = self._sink_cost(p["sinks"]["scout"])
            self._spend(cost, "scout")
            self.battle.scout_hint = cr.scout_hint_for(self.battle.enemy)
        elif sink_type == "attack_boost":
            self._require_in(PHASE_BATTLE)
            if self.player.attack_boost_pending:
                raise InvalidMove("attack boost already pending")  # OPEN-021: 二重課金防止
            cost = self._sink_cost(p["attack_boost"]["cost"])
            self._spend(cost, "attack_boost")
            self.player.attack_boost_pending = True
        elif sink_type in ("heal_small", "heal_large"):
            self._require_in(PHASE_EXPLORING, PHASE_BATTLE)
            small = sink_type == "heal_small"
            base = p["heal"]["sink_small_base"] if small else p["heal"]["sink_large_base"]
            mult = p["heal"]["sink_floor_multiplier"][str(self.current_floor)]
            cost = self._sink_cost(base * mult)
            if self.player.hp >= self.player.max_hp:
                raise InvalidMove("already full hp")
            self._spend(cost, sink_type)
            # 回復量は固定値（GDD §13.2 v0.9確定）: 小回復 +15固定 / 大回復 +30固定。
            amt = p["heal"]["node_small" if small else "node_large"]
            self.player.hp = min(self.player.max_hp, self.player.hp + amt)
            # OPEN-020: battle 中の回復は1ターン消費（敵行動のみが解決される）。
            if self.phase == PHASE_BATTLE:
                return self._resolve_battle_turn(guard=False, side_bet=None,
                                                 player_attacks=False, player_move=sink_type)
        elif sink_type == "gate_guarantee":
            self._require(PHASE_GATE_PREVIEW)
            # OPEN-016: 大ダメ0%到達後の重ねがけは効果ゼロの課金なので拒否。
            eff = gr.apply_guarantee(dict(self.floor.gate_result_table),
                                     self.gate_guarantee_uses, self.data)
            if eff["major"] <= 1e-9:
                raise InvalidMove("gate guarantee has no effect: major already 0")
            self.gate_guarantee_uses += 1
            cost = gr.guarantee_cost(self.gate_guarantee_uses, self.data)
            cost = self._sink_cost(cost)
            if self.player.chips < cost:
                self.gate_guarantee_uses -= 1
                raise InvalidMove("not enough chips for guarantee")
            self.player.chips -= cost
            self.run.gold_spent["gate_guarantee"] += cost
            # ラン合計の重ねがけ回数（GDD §19.1）。gate_guarantee_uses は L266 でフロア毎にリセットされるため別管理。
            self.run.gate_guarantee_stacks += 1
            self.pending["table"] = gr.apply_guarantee(dict(self.floor.gate_result_table),
                                                       self.gate_guarantee_uses, self.data)
        else:
            raise InvalidMove(f"unknown sink {sink_type}")
        return self.snapshot()

    def _spend(self, cost: int, key: str) -> None:
        if self.player.chips < cost:
            raise InvalidMove(f"not enough chips for {key}")
        self.player.chips -= cost
        self.run.gold_spent[key] += cost

    # ─────────────────────────── dismiss modal ───────────────────────────
    def dismiss(self) -> dict:
        if self.phase in (PHASE_TREASURE_OPENED, PHASE_HEAL, PHASE_NEXT_FLOOR):
            self.phase = PHASE_EXPLORING
        self.pending = {}
        return self.snapshot()

    # ─────────────────────────── finalize ───────────────────────────
    def _finalize(self, cleared: bool, death_cause: Optional[str] = None) -> None:
        self.run.cleared = cleared
        self.run.final_hp = self.player.hp
        self.run.mods_acquired = list(self.player.mods)
        if not cleared:
            self.run.death_cause = death_cause
            self.run.death_floor = self.current_floor
        self.run.floor_reached = self.current_floor

    # ─────────────────────────── observations (dossier) ───────────────────────────
    def drain_observations(self) -> list[tuple[str, str]]:
        """蓄積した (enemy_id, behavior) 観測を取り出し内部バッファを空にする。DB書き込みはAPI層の責務。"""
        obs, self._pending_observations = self._pending_observations, []
        return obs

    # ─────────────────────────── guards ───────────────────────────
    def _require(self, phase: str) -> None:
        if self.phase != phase:
            raise WrongPhase(f"requires phase {phase}, in {self.phase}")

    def _require_in(self, *phases: str) -> None:
        if self.phase not in phases:
            raise WrongPhase(f"requires one of {phases}, in {self.phase}")

    # ─────────────────────────── available actions ───────────────────────────
    def available_actions(self) -> list[dict]:
        acts: list[dict] = []
        pl = self.player
        if self.phase == PHASE_EXPLORING:
            for nid in self.available_nodes():
                acts.append({"type": "select_node", "node": nid})
            self._add_heal_boost_sinks(acts, boost=False)
        elif self.phase == PHASE_BATTLE:
            acts.append({"type": "attack"})
            acts.append({"type": "guard"})
            scout_cost = self._sink_cost(self.data.config["sinks"]["scout"])
            if pl.chips >= scout_cost:
                acts.append({"type": "use_sink", "sink": "scout", "cost": scout_cost})
            self._add_heal_boost_sinks(acts, boost=True)
        elif self.phase == PHASE_TREASURE_PREVIEW:
            acts.append({"type": "treasure_open"})
            node = self.floor.nodes.get(self.pending.get("node", ""))
            reroll_cost = self._sink_cost(self.data.config["sinks"]["treasure_reroll"])
            # OPEN-017: 確定mod宝箱にはリロールを提示しない
            if (node is None or not node.fixed_mod) and pl.chips >= reroll_cost:
                acts.append({"type": "treasure_reroll", "cost": reroll_cost})
        elif self.phase in (PHASE_TREASURE_OPENED, PHASE_HEAL, PHASE_NEXT_FLOOR):
            acts.append({"type": "dismiss"})
        elif self.phase == PHASE_GATE_PREVIEW:
            acts.append({"type": "gate_resolve"})
            # OPEN-016: major=0 到達後は保証を提示しない
            eff = gr.apply_guarantee(dict(self.floor.gate_result_table),
                                     self.gate_guarantee_uses, self.data)
            nxt = self._sink_cost(gr.guarantee_cost(self.gate_guarantee_uses + 1, self.data))
            if eff["major"] > 1e-9 and pl.chips >= nxt:
                acts.append({"type": "use_sink", "sink": "gate_guarantee", "cost": nxt})
        return acts

    def _add_heal_boost_sinks(self, acts: list[dict], boost: bool) -> None:
        pl = self.player
        cfg = self.data.config
        if pl.hp < pl.max_hp:
            mult = cfg["heal"]["sink_floor_multiplier"][str(self.current_floor)]
            small = self._sink_cost(cfg["heal"]["sink_small_base"] * mult)
            large = self._sink_cost(cfg["heal"]["sink_large_base"] * mult)
            if pl.chips >= small:
                acts.append({"type": "use_sink", "sink": "heal_small", "cost": small})
            if pl.chips >= large:
                acts.append({"type": "use_sink", "sink": "heal_large", "cost": large})
        if boost:
            boost_cost = self._sink_cost(cfg["attack_boost"]["cost"])
            if not pl.attack_boost_pending and pl.chips >= boost_cost:
                acts.append({"type": "use_sink", "sink": "attack_boost", "cost": boost_cost})

    # ─────────────────────────── snapshot ───────────────────────────
    def _node_view(self, node) -> dict:
        """ノードの表示用 dict。敵ノードには L2/L3 開示（体験タイプ・強敵・名前・最大HP）を付す。
        確率テーブルの数値は出さない（暗黙知型・GDD §5）。"""
        d = node.snapshot(self.node_state(node))
        if node.kind == "enemy" and node.enemy_id:
            e = self.data.enemy(node.enemy_id)
            d["experience"] = e["experience"]
            d["name"] = e["name"]
            d["is_strong"] = self.data.is_strong(e)
            d["max_hp"] = self.data.scaled_hp(e, self.current_floor)
        return d

    def snapshot(self) -> dict:
        floor_state = None
        if self.floor:
            floor_state = {
                "floor_number": self.current_floor,
                "nodes": {nid: self._node_view(n) for nid, n in self.floor.nodes.items()},
            }
        battle_state = None
        if self.battle:
            b = self.battle
            battle_state = {
                "enemy": b.enemy.snapshot(),
                "turns": b.turns, "ramp_value": b.ramp_value,
                "scout_hint": b.scout_hint, "preview": b.preview,
                # 先読み(yomi)が公開した「確定の次手」の種別（counter/heavy_blow/...）。未公開は None。
                "next_action": b.pending_action,
                "log": list(b.log),
                # サイドベット『読み宣言』の戦闘あたり累計額（per_battle_cap 可視化用・UI表示専用）。
                "side_bet_total": b.side_bet_total,
                # サイドベット『読み宣言』の直近ターン結果（表示専用・次ターンでクリア）。
                "side_bet_result": b.side_bet_result,
                # 直近ターンの実現結果（ログに表示済みの公開情報のみ・非公開情報は含めない）。
                "last_turn": ({"action": b.last_action, "guard": b.last_guard}
                              if b.last_action is not None else None),
                # サイドベットの表示規則（正本 config.json side_bet。フロントに定数を複製させない）。
                "side_bet": {k: self.data.config["side_bet"][k]
                             for k in ("min_amount", "max_amount", "payout_multiplier", "per_battle_cap")},
            }
            # テル（行動の前兆）システム試作: フラグON時のみ、次手が公開されているターンに
            # 敵ごとの固定「気配信頼度」ラベルを添える（新規RNG消費なし・既存next_actionと同じ条件）。
            if self.data.config.get("feature_flags", {}).get("tell_system") and b.pending_action is not None:
                battle_state["tell_reliability"] = tells.tell_reliability(b.enemy.id)
            else:
                battle_state["tell_reliability"] = None
        return {
            "phase": self.phase,
            "current_floor": self.current_floor,
            "player": self.player.snapshot() if self.player else None,
            "floor": floor_state,
            "battle": battle_state,
            "pending": dict(self.pending),
            "available_actions": self.available_actions(),
            # §17.3 seed非露出: RunRecord は seed を含むため終端（dead/cleared）でのみ開示（seed-scum防止）。
            "run_record": (self.run.snapshot()
                           if self.run and self.phase in (PHASE_DEAD, PHASE_CLEARED) else None),
        }
