"""検死レポート（postmortem）— 致命ターンの反実仮想（counterfactual）解析。

致命ターン（turn_history の最後）の pre_turn_snapshot から状態を復元し、guard を反転して
同じ敵行動（forced_action）で再解決する。「ガード/攻撃を逆にしていたら生存できたか」を判定する。
forced_action 指定により roll_behavior は呼ばれず RNG ストリームを一切消費しない（決定論・再現安全）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.engine import combat_resolver as cr
from app.engine.rng import STREAM_BEHAVIOR
from app.schemas.models import Battle, EnemyInstance, Player

if TYPE_CHECKING:
    from app.engine.game_engine import GameEngine


def compute_postmortem(engine: "GameEngine") -> dict:
    if not engine.run.turn_history:
        return {}
    last = engine.run.turn_history[-1]
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
    res = cr.resolve_turn(battle, player, engine.data, engine.rng.stream(STREAM_BEHAVIOR),
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
        "fatal_turn_index": len(engine.run.turn_history) - 1,
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
