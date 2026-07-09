"""依存性モジュール。routes.py と共有する2つの責務を置く。

- get_engine_or_404: アクティブランの取得（無ければ404・キャッシュミスなら再生で復元）
- finalize_run: 終局ランを確定する保存本体（ライブ経路 routes._finalize_if_ended と
  復元経路 get_engine_or_404 の双方から呼ばれる。routes.py に置くと復元経路からの
  呼び出しが循環importになるため、両方の呼び出し元より下位のここに置く）

DB は app.db.session.get_db を直接使う。
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import get_db
from app.engine.game_engine import PHASE_CLEARED, PHASE_DEAD, GameEngine
from app.engine.replay import rebuild_engine
from app.session_store import store
from app.simulation.bots import STRATEGY_VERSION

logger = logging.getLogger("casino_tower.deps")


# ── 保存責務: 終局ランの確定 ──
def finalize_run(db: Session, session_id: str, eng: GameEngine) -> None:
    """終局ランを RunRecord 等へ確定する保存本体（ガードは呼び出し側の責務）。

    ライブ経路（routes._finalize_if_ended）と復元経路（get_engine_or_404）で共有する。
    復元経路から呼ぶのは「ライブで終局アクションは記録されたが finalize 前にプロセスが
    落ちた」クラッシュ窓の回復のため（OPEN-007 観点2）。二重確定防止のガードは各呼び出し側で行う
    （ライブは store.is_finalized、復元は crud.run_record_exists）。
    """
    sv = None if eng.run.bot_type == "human" else STRATEGY_VERSION
    crud.save_run_record(db, eng.run.snapshot(), strategy_version=sv)
    crud.save_run_actions(db, eng.run.run_id, eng.run.turn_history)
    if eng.phase == PHASE_CLEARED:
        pts = eng.data.config["permanent_upgrades"]["points_per_clear"]
        crud.award_points(db, pts)
    elif eng.phase == PHASE_DEAD and eng._postmortem:
        crud.save_postmortem(
            db, eng.run.run_id, eng.run.turn_history,
            eng._postmortem["fatal_turn_index"], eng._postmortem,
        )
    store.mark_finalized(session_id)


# ── 取得責務: アクティブランの取得（無ければ404） ──
def get_engine_or_404(session_id: str, db: Session = Depends(get_db)) -> GameEngine:
    # 永続の正本は ActiveSessionRow。行が無い（TTL掃除済み等）セッションは、エンジンが
    # インメモリに残っていても「存在しない」扱いにする。キャッシュヒットで進めてしまうと
    # record_action が無記録（黙ってNone）になり、エンジンだけ進んでログが進まない乖離が起きる（観点1）。
    row = crud.load_active_session(db, session_id)
    if row is None:
        store.drop(session_id)  # ゾンビエンジンの掃除（以後の再起動時404と挙動を揃える）
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")

    eng = store.get(session_id)
    if eng is not None:
        return eng

    # インメモリキャッシュミス（再起動 or LRU追い出し直後）: DBのアクションログから再構築する。
    # 壊れた/未知仕様のログは 500（詳細はサーバログ）。生の例外を素通しすると IllegalAction 系が
    # 409/400 に誤マッピングされ、GET が「phase不整合」を返す混乱した応答になるため明示的に包む（観点3）。
    try:
        eng = rebuild_engine(row)
    except Exception as err:
        logger.exception("failed to rebuild session %s from action log", session_id)
        raise HTTPException(status_code=500,
                            detail=f"failed to restore session {session_id} from action log") from err
    store.restore(session_id, eng)

    # クラッシュ窓の回復（OPEN-007 観点2）: ライブで終局したが finalize 未達のまま再起動した行は、
    # GET しても finalize されず・POST は WrongPhase になるため RunRecord が永久に確定されない。
    # 復元時に終局phaseなら確定する。RunRecord が既にあれば二重確定しない（冪等）。
    if eng.phase in (PHASE_CLEARED, PHASE_DEAD) and not crud.run_record_exists(db, eng.run.run_id):
        finalize_run(db, session_id, eng)
    return eng
