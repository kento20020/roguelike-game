"""アクションログ再生（OPEN-007）。

GameEngine は (seed, upgrades, 操作列) の純粋関数として振る舞う（同一seed→同一結果の
不変条件・CLAUDE.md）。そのため永続化すべきは「状態」ではなく「状態を再現するのに
十分な入力」でよい。ここでは ActiveSessionRow に貯めたアクション列を、実際の
GameEngine メソッド呼び出しとして再適用することで状態を復元する。

app.simulation.bots._apply の {"type": ..., ...} dict ディスパッチと同じ規約を踏襲し、
guard/side_bet 対応を加えて拡張したもの。

再生は GameEngine の状態を作るためだけに行う。_drain_observations（調書カウント）や
_finalize_if_ended（RunRecord確定）はライブプレイ時に既に実行・DB反映済みのため、
ここでは呼ばない（呼ぶと二重計上になる）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.engine.game_engine import GameEngine

if TYPE_CHECKING:
    from app.db.models import ActiveSessionRow


def apply_action(eng: GameEngine, action: dict) -> None:
    t = action["type"]
    if t == "select_node":
        eng.select_node(action["node_id"])
    elif t == "attack":
        eng.attack(side_bet=action.get("side_bet"))
    elif t == "guard":
        eng.guard(side_bet=action.get("side_bet"))
    elif t == "use_sink":
        eng.use_sink(action["sink_type"])
    elif t == "treasure_open":
        eng.treasure_open()
    elif t == "treasure_reroll":
        eng.treasure_reroll()
    elif t == "dismiss":
        eng.dismiss()
    elif t == "gate_resolve":
        eng.gate_resolve()
    else:
        raise ValueError(f"unknown replay action type: {t!r}")


def rebuild_engine(row: "ActiveSessionRow") -> GameEngine:
    eng = GameEngine()
    eng.new_run(row.seed, upgrades=row.upgrades_json, bot_type=row.bot_type)
    for action in row.actions_json:
        apply_action(eng, action)
    return eng
