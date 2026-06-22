"""戦闘1ターンの解決（戦闘の心臓部）。GDD §8.2 準拠・データ駆動。

不変条件:
- 与ダメは必ず `attack × multiplier`（stance × attack_boost）。attack を直接使わない。
- ramp_value(n) = ramp_base_initial + eff_increment*(n-1)。
- combat_log は表示専用（ここで battle.log に追記）。RunRecord は engine 側で別管理。
- mod の post_damage 順序: 重装甲(軽減) → player被弾 → 反射(counter) → 好機(heavy追撃)。
  これにより「反射×重装甲」synergy（軽減後の被弾を受けつつ反射を返す）が自然成立する。
"""
from __future__ import annotations

from typing import Optional

from app.data.loader import GameData
from app.engine.rng import Sfc32
from app.schemas.models import (
    HANSHA,
    JUSO,
    KASOKU,
    KOUKI,
    MIKIRI,
    YOMI,
    Battle,
    Player,
)

# 行動タイプ
NONE = "none"
COUNTER = "counter"
HEAVY = "heavy_blow"
EVADE = "evade"
RAMP_HIT = "ramp_hit"

_SCOUT_HINT = {
    COUNTER: "反撃の構え。受けに回っている。",
    HEAVY: "大振りの予兆。重い一撃が来やすい。",
    NONE: "隙が大きい。空振りが多そうだ。",
    RAMP_HIT: "刻む手が速い。蓄積に注意。",
    EVADE: "身をかわす気配。",
}


# ── mod 値の解決（1枚=value_1 / 2枚以上=value_stack）──
def mod_value(player: Player, data: GameData, mod_id: str,
              key1: str = "value_1", key_stack: str = "value_stack",
              default: Optional[float] = None):
    count = player.mod_count(mod_id)
    if count == 0:
        return default
    m = data.mod(mod_id)
    return m[key1] if count == 1 else m[key_stack]


def _kasoku_factor(player: Player, data: GameData) -> float:
    return mod_value(player, data, KASOKU, default=1.0)


def _mikiri_factor_from_mods(player: Player) -> float:
    """見切り係数（1枚=0.5 / 2枚以上=0）。data 不要で mods から直接判定。"""
    count = player.mod_count(MIKIRI)
    if count == 0:
        return 1.0
    return 0.5 if count == 1 else 0.0


def effective_behaviors(player: Player, enemy) -> list[tuple[str, float]]:
    """見切りで evade weight を補正した実効行動テーブル。

    カオス敵の behaviors は floor_generator がラン別 weight で構築済み。
    """
    mik = _mikiri_factor_from_mods(player)
    return [(t, w * mik if t == EVADE else w) for t, w in enemy.behaviors]


def roll_behavior(behaviors: list[tuple[str, float]], stream: Sfc32) -> str:
    types = [t for t, _ in behaviors]
    weights = [w for _, w in behaviors]
    if sum(weights) <= 0:
        return NONE
    return types[stream.weighted_index(weights)]


def top_behavior(enemy) -> str:
    """最も weight の高い行動（スカウトの示唆用）。"""
    if not enemy.behaviors:
        return NONE
    return max(enemy.behaviors, key=lambda tw: tw[1])[0]


def scout_hint_for(enemy) -> str:
    return _SCOUT_HINT.get(top_behavior(enemy), "気配を読めない。")


def prepare_preview(battle: Battle, player: Player, data: GameData, stream: Sfc32) -> None:
    """先読み（yomi）: 公開対象ターンなら次行動を先引きして battle に保持。"""
    if battle.pending_action is not None:
        return
    preview_turns = mod_value(player, data, YOMI, default=0) or 0
    if battle.turns < preview_turns:  # turn1..preview_turns を公開
        action = roll_behavior(effective_behaviors(player, battle.enemy), stream)
        battle.pending_action = action
        battle.preview = _SCOUT_HINT.get(action, "")


def resolve_turn(battle: Battle, player: Player, data: GameData,
                 behavior_stream: Sfc32, *, forced_action: Optional[str] = None,
                 guard: bool = False) -> dict:
    """1ターン解決。battle/player を破壊的更新し、結果 dict を返す。

    guard=True（受け）: 与ダメ ×guard.deal_factor（boost は消費しない）、
    被ダメ ×guard.incoming_factor（重装甲の軽減後にさらに乗算）。先読みを活かす攻防の選択。
    """
    enemy = battle.enemy
    cfg = data.config

    # 1. ramp 更新（レース系/カオス）
    battle.turns += 1
    n = battle.turns
    if enemy.has_ramp:
        base_initial = cfg["combat"]["ramp_base_initial"]
        eff_inc = enemy.ramp_increment * _kasoku_factor(player, data)
        battle.ramp_value = round(base_initial + eff_inc * (n - 1))

    # 2. 与ダメ = attack × multiplier（stance × boost）。受けは deal_factor 倍・boost 非消費。
    if guard:
        gcfg = cfg["combat"]["guard"]
        dealt = round(player.attack * player.stance_multiplier * gcfg["deal_factor"])
    else:
        boost_mult = cfg["attack_boost"]["multiplier"] if player.attack_boost_pending else 1.0
        multiplier = player.stance_multiplier * boost_mult
        dealt = round(player.attack * multiplier)
        if player.attack_boost_pending:
            player.attack_boost_pending = False
    enemy.hp -= dealt
    battle.add_log(f"{'受け · ' if guard else ''}{enemy.name} に {dealt} ダメージ", "hit")
    enemy_dead = enemy.hp <= 0

    # 3. 行動ロール（先読みで先引き済みなら消費）
    if forced_action is not None:
        action = forced_action
    elif battle.pending_action is not None:
        action = battle.pending_action
        battle.pending_action = None
    else:
        action = roll_behavior(effective_behaviors(player, enemy), behavior_stream)
    battle.preview = None

    # 4. 被ダメ算出
    base_inc = 0
    if action == NONE:
        battle.add_log("相手は動かなかった（被ダメ 0）", "calm")
    elif action == COUNTER:
        base_inc = round(enemy.attack * enemy.counter_factor)
    elif action == HEAVY:
        base_inc = round(enemy.attack * enemy.heavy_factor)
    elif action == RAMP_HIT:
        base_inc = battle.ramp_value
    elif action == EVADE:
        # 与ダメを取り消す（空振り）
        enemy.hp += dealt
        enemy_dead = enemy.hp <= 0  # 戻したので基本 False
        battle.add_log("見切られた — 攻撃が空を切った", "calm")

    # 5. post_damage フック
    incoming = base_inc
    reduction = 0
    if action in (COUNTER, HEAVY):
        juso = mod_value(player, data, JUSO)  # 4 or 8 or None
        if juso:
            cap_ratio = data.mod(JUSO).get("cap_ratio", 0.5)
            cap = base_inc * cap_ratio
            reduction = int(min(juso, cap))
            incoming = max(0, base_inc - reduction)
            if reduction > 0:
                battle.add_log(f"重装甲 — 被ダメ {reduction} 軽減", "mod")
    # b. player 被弾（受けは重装甲の軽減後にさらに incoming_factor 倍）
    if guard and incoming > 0:
        incoming = round(incoming * cfg["combat"]["guard"]["incoming_factor"])
        battle.add_log("受け — 被ダメを大きく抑えた", "mod")
    player.hp -= incoming
    if action == COUNTER:
        battle.add_log(f"反撃 — {incoming} ダメージを受けた", "hurt")
    elif action == HEAVY:
        battle.add_log(f"強打 — {incoming} ダメージを受けた", "hurt")
    elif action == RAMP_HIT:
        battle.add_log(f"時を刻む一撃 — {incoming} ダメージ（蓄積）", "hurt")

    # c. 反射（counter 被弾時、敵へ固定ダメ）
    reflect = 0
    if action == COUNTER and not enemy_dead:
        refl = mod_value(player, data, HANSHA)  # 5 or 10 or None
        if refl:
            enemy.hp -= refl
            reflect = refl
            battle.add_log(f"反射 — {enemy.name} に {refl} の追加ダメージ", "mod")
            enemy_dead = enemy.hp <= 0

    # d. 好機（heavy 被弾時、追撃1回。CD は「発動しなかったターン末」に減衰）
    extra = 0
    kouki_fired = False
    if action == HEAVY and not enemy_dead and player.has_mod(KOUKI) and battle.kouki_cooldown == 0:
        extra = round(player.attack * player.stance_multiplier)  # boost は乗らない
        enemy.hp -= extra
        battle.add_log(f"好機 — 追撃 {extra} ダメージ", "mod")
        enemy_dead = enemy.hp <= 0
        cd = mod_value(player, data, KOUKI, key1="cooldown_1", key_stack="cooldown_stack", default=0)
        battle.kouki_cooldown = int(cd)
        kouki_fired = True
    if not kouki_fired and battle.kouki_cooldown > 0:
        battle.kouki_cooldown -= 1

    # 6. 判定（敵が先に死ねば勝利優先）
    if enemy.hp < 0:
        enemy.hp = 0
    player_dead = player.hp <= 0 and not enemy_dead
    if player.hp < 0:
        player.hp = 0

    battle.scout_hint = None  # スカウト示唆は1ターン限り
    return {
        "action": action,
        "dealt": dealt,
        "base_incoming": base_inc,
        "reduction": reduction,
        "incoming": incoming,
        "reflect": reflect,
        "extra": extra,
        "enemy_dead": enemy_dead,
        "player_dead": player_dead,
        "ramp_value": battle.ramp_value,
    }
