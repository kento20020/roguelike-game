"""ボット方策 — strong / random。同じ GameEngine を駆動する。

strong: HP管理・脅威の低い敵選択・無料宝箱回収・危険時のゲート保証。
random: 合法手から一様抽選（独立 bot RNG）。
クリア率が帯域外なら方策ではなく JSON 数値を人間が調整（Goodhart回避）。
"""
from __future__ import annotations

import math

from app.engine import gate_resolver as gr
from app.engine.floor_generator import build_enemy_instance
from app.engine.game_engine import GameEngine
from app.engine.rng import Sfc32
from app.schemas.models import JUSO

MAX_STEPS = 8000

# bot方策の版（OPEN-024: RunRecord.strategy_version に刻印し統計を方策世代でフィルタする）。
# 方策ロジックを変えたらバンプする。human ランは NULL。
STRATEGY_VERSION = "strong-v1"


# ─────────────────────── threat estimation ───────────────────────
def _juso_reduction(eng: GameEngine) -> int:
    c = eng.player.mod_count(JUSO)
    if c == 0:
        return 0
    m = eng.data.mod(JUSO)
    return int(m["value_1"] if c == 1 else m["value_stack"])


def _expected_incoming(e, eng: GameEngine, ttk: int) -> float:
    total = sum(w for _, w in e.behaviors) or 1
    red = _juso_reduction(eng)
    acc = 0.0
    for t, w in e.behaviors:
        if t == "counter":
            d = max(0, e.attack * e.counter_factor - red)
        elif t == "heavy_blow":
            d = max(0, e.attack * e.heavy_factor - red)
        elif t == "ramp_hit":
            d = 5 + e.ramp_increment * (ttk / 2.0)  # 平均蓄積
        else:
            d = 0.0
        acc += (w / total) * d
    return acc


def _threat(eng: GameEngine, node_id: str) -> float:
    node = eng.floor.nodes[node_id]
    e = build_enemy_instance(node.enemy_id, eng.current_floor, eng.data, eng.chaos_weights,
                             row=node.row)
    ttk = max(1, math.ceil(e.max_hp / max(1, eng.player.attack)))
    return ttk * _expected_incoming(e, eng, ttk)


# ─────────────────────── strong bot ───────────────────────
def _try_heal(eng: GameEngine) -> bool:
    p = eng.player
    if p.hp >= p.max_hp:
        return False
    cfg = eng.data.config
    mult = cfg["heal"]["sink_floor_multiplier"][str(eng.current_floor)]
    large = eng._sink_cost(cfg["heal"]["sink_large_base"] * mult)
    small = eng._sink_cost(cfg["heal"]["sink_small_base"] * mult)
    if p.chips >= large:
        eng.use_sink("heal_large")
        return True
    if p.chips >= small:
        eng.use_sink("heal_small")
        return True
    return False


def _has_dead_end_child(eng: GameEngine, node_id: str) -> bool:
    """この敵を倒すと宝箱/回復 dead-end が解放されるか（同じ1戦でmod獲得）。"""
    for n in eng.floor.nodes.values():
        if n.kind in ("treasure", "heal") and node_id in n.parents:
            return True
    return False


def _explore(eng: GameEngine) -> None:
    p = eng.player
    nodes = eng.floor.nodes
    avail = eng.available_nodes()

    # 低HPなら回復（探索の合間が安全）
    if p.hp < p.max_hp * 0.55 and _try_heal(eng):
        return

    # 無料ノード（宝箱・回復・gate_route）は戦闘より先に消化。
    # gate_route を先に取らないと無駄な row1 戦闘を増やしてしまう（重要）。
    for nid in avail:
        if nodes[nid].kind in ("treasure", "heal", "gate_route"):
            eng.select_node(nid)
            return

    # ゲートが見えたら向かう
    for nid in avail:
        if nodes[nid].kind == "gate":
            eng.select_node(nid)
            return

    # ゲートへ最短で登る: (1)高い row=ゲートに近い (2)宝箱を解放する敵=同戦でmod
    # (3)脅威最小。これで戦闘数を抑えつつ防御mod（重装甲等）を拾う。
    enemies = [nid for nid in avail if nodes[nid].kind == "enemy"]
    if enemies:
        eng.select_node(min(enemies, key=lambda n: (
            -nodes[n].row, not _has_dead_end_child(eng, n), _threat(eng, n))))
        return

    eng.select_node(avail[0])


def _battle(eng: GameEngine) -> None:
    b, p = eng.battle, eng.player
    # 瀕死なら回復
    if p.hp < p.max_hp * 0.30 and _try_heal(eng):
        return
    # とどめ強化（このターン倒せて被弾を1回減らせる）
    if (not p.attack_boost_pending and p.attack < b.enemy.hp <= p.attack * 2):
        cost = eng._sink_cost(eng.data.config["attack_boost"]["cost"])
        if p.chips >= cost:
            eng.use_sink("attack_boost")
            return
    eng.attack()


def _gate(eng: GameEngine) -> None:
    p = eng.player
    if p.hp < p.max_hp * 0.5 and eng.gate_guarantee_uses < 1:
        nxt = gr.guarantee_cost(eng.gate_guarantee_uses + 1, eng.data)
        if p.chips >= eng._sink_cost(nxt):
            eng.use_sink("gate_guarantee")
            return
    eng.gate_resolve()


def play_strong(eng: GameEngine, seed: int, upgrades=None, max_steps: int = MAX_STEPS,
                forced_first_node: str | None = None) -> dict:
    """forced_first_node: 初手の探索選択だけ指定ノードに固定（初手別感度の実験用）。
    None なら従来挙動と完全一致（以降のターンは常に通常方策）。"""
    eng.new_run(seed, upgrades=upgrades, bot_type="strong")
    forced_used = False
    for _ in range(max_steps):
        ph = eng.phase
        if ph in ("cleared", "dead"):
            break
        if ph == "battle":
            _battle(eng)
        elif ph == "exploring":
            if forced_first_node and not forced_used and forced_first_node in eng.available_nodes():
                eng.select_node(forced_first_node)
                forced_used = True
            else:
                _explore(eng)
        elif ph == "treasure_preview":
            eng.treasure_open()
        elif ph in ("treasure_opened", "heal", "next_floor"):
            eng.dismiss()
        elif ph == "gate_preview":
            _gate(eng)
        else:
            break
    return eng.run.snapshot()


# ─────────────────────── random bot ───────────────────────
def _apply(eng: GameEngine, a: dict) -> None:
    t = a["type"]
    if t == "select_node":
        eng.select_node(a["node"])
    elif t == "attack":
        eng.attack()
    elif t == "use_sink":
        eng.use_sink(a["sink"])
    elif t == "treasure_open":
        eng.treasure_open()
    elif t == "treasure_reroll":
        eng.treasure_reroll()
    elif t == "dismiss":
        eng.dismiss()
    elif t == "gate_resolve":
        eng.gate_resolve()


def play_random(eng: GameEngine, seed: int, bot_seed: int = 0,
                upgrades=None, max_steps: int = MAX_STEPS) -> dict:
    eng.new_run(seed, upgrades=upgrades, bot_type="random")
    rng = Sfc32((bot_seed ^ seed) & 0xFFFFFFFF)
    for _ in range(max_steps):
        ph = eng.phase
        if ph in ("cleared", "dead"):
            break
        # ランダムでもゲートは抜ける（gate_preview を放置しない）
        acts = eng.available_actions()
        if not acts:
            break
        _apply(eng, acts[rng.randint(0, len(acts) - 1)])
    return eng.run.snapshot()
