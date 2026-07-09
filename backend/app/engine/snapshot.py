"""スナップショット/ノードビュー構築 — GameEngine の状態を API/bot 向け dict に直列化する表示層。

RNG を一切消費しない純粋なシリアライザ。キー名・値・構造は GameEngine.snapshot() の契約そのもの
（各レスポンスは完全なゲーム状態を返す＝フロントに差分計算をさせない）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.engine import tells
from app.schemas.models import PHASE_CLEARED, PHASE_DEAD, Node

if TYPE_CHECKING:
    from app.engine.game_engine import GameEngine


def build_node_view(engine: GameEngine, node: Node) -> dict:
    """ノードの表示用 dict。敵ノードは L2（体験タイプ・強敵）を常時開示し、
    L3（名前・最大HP）はインタラクト後（resolved／戦闘中の当該ノード）のみ付す（§5・OPEN-015）。
    確率テーブルの数値は出さない（暗黙知型・GDD §5）。"""
    state = engine.node_state(node)
    d = node.snapshot(state)
    if node.kind == "enemy" and node.enemy_id:
        e = engine.data.enemy(node.enemy_id)
        d["experience"] = e["experience"]
        d["is_strong"] = engine.data.is_strong(e)
        interacted = state == "resolved" or (
            engine.battle is not None and engine.battle.node_id == node.id)
        if interacted:
            d["name"] = e["name"]
            d["max_hp"] = engine.data.scaled_hp(e, engine.current_floor, node.row)
    return d


def _build_floor_state(engine: GameEngine) -> dict:
    return {
        "floor_number": engine.current_floor,
        "nodes": {nid: build_node_view(engine, n) for nid, n in engine.floor.nodes.items()},
    }


def _build_battle_state(engine: GameEngine) -> dict:
    b = engine.battle
    battle_state = {
        "enemy": b.enemy.snapshot(),
        "turns": b.turns, "ramp_value": b.ramp_value,
        # 受けの使用回数（重ねがけ減衰の現在段）。UIが「次の受けの効き」を示せるよう公開する。
        "guard_uses": b.guard_uses,
        # 次に受けた場合の軽減量スケール = stack_decay ** guard_uses（1.0→0.5→0.25…）。
        # 減衰の計算はここ（Python）で確定させる。フロントは表示のみで一切計算しない（アーキ原則1）。
        "guard_next_scale": engine.data.config["combat"]["guard"]["stack_decay"] ** b.guard_uses,
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
        "side_bet": {k: engine.data.config["side_bet"][k]
                     for k in ("min_amount", "max_amount", "payout_multiplier", "per_battle_cap")},
    }
    # テル（行動の前兆）システム試作: フラグON時のみ、次手が公開されているターンに
    # 敵ごとの固定「気配信頼度」ラベルを添える（新規RNG消費なし・既存next_actionと同じ条件）。
    if engine.data.config.get("feature_flags", {}).get("tell_system") and b.pending_action is not None:
        battle_state["tell_reliability"] = tells.tell_reliability(b.enemy.id)
    else:
        battle_state["tell_reliability"] = None
    return battle_state


def build_snapshot(engine: GameEngine) -> dict:
    """完全なゲーム状態 dict を組み立てて返す。floor→battle→available_actions の順に評価する
    （いずれも副作用なし・RNG非消費なので評価順は挙動に影響しない）。"""
    return {
        "phase": engine.phase,
        "current_floor": engine.current_floor,
        "player": engine.player.snapshot() if engine.player else None,
        "floor": _build_floor_state(engine) if engine.floor else None,
        "battle": _build_battle_state(engine) if engine.battle else None,
        "pending": dict(engine.pending),
        "available_actions": engine.available_actions(),
        # §17.3 seed非露出: RunRecord は seed を含むため終端（dead/cleared）でのみ開示（seed-scum防止）。
        "run_record": (engine.run.snapshot()
                       if engine.run and engine.phase in (PHASE_DEAD, PHASE_CLEARED) else None),
    }
