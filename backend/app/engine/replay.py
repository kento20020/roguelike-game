"""アクションログ再生（OPEN-007）。

GameEngine は (seed, upgrades, 操作列) の純粋関数として振る舞う（同一seed→同一結果の
不変条件・CLAUDE.md）。そのため永続化すべきは「状態」ではなく「状態を再現するのに
十分な入力」でよい。ここでは ActiveSessionRow に貯めたアクション列を、実際の
GameEngine メソッド呼び出しとして再適用することで状態を復元する。

app.simulation.bots._apply の {"type": ..., ...} dict ディスパッチと同じ規約を踏襲し、
guard/side_bet 対応を加えて拡張したもの。

再生は GameEngine の状態を作るためだけに行う。調書カウント（ObservationRow）や
_finalize_if_ended（RunRecord確定）はライブプレイ時に既に実行・DB反映済みのため、
ここではDBへ書かない（書くと二重計上になる）。再生中に engine 内部へ蓄積される
_pending_observations も同じ理由で復元前に破棄する（残すと復元後の最初の戦闘ターンの
drain でまとめてDBへ書かれ二重計上になる）。
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


def rebuild_engine(row: ActiveSessionRow) -> GameEngine:
    eng = GameEngine()
    eng.new_run(row.seed, upgrades=row.upgrades_json, bot_type=row.bot_type)
    # new_run() は呼ぶたびに新しいrun_id（uuid4）を発行するため、再構築のたびに変わってしまうと
    # 既存のRunRecord/postmortemの参照キーとズレる。ライブ生成時に確定したrun_idへ上書きする
    # （旧行でrun_id未保存＝Noneの場合のみ、new_run()が発行した値をそのまま使う）。
    if row.run_id is not None:
        eng.run.run_id = row.run_id
    for action in row.actions_json:
        apply_action(eng, action)
    # 再生で蓄積した調書観測はライブ時に反映済み。破棄しないと、復元後の最初の戦闘ターンの
    # _drain_observations で新規分と一緒にDBへ書かれ、二重計上になる。
    eng.drain_observations()
    return eng
