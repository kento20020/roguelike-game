"""依存性: アクティブランの取得（404）。DB は app.db.session.get_db を直接使う。"""
from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import get_db
from app.engine.game_engine import GameEngine
from app.engine.replay import rebuild_engine
from app.session_store import store


def get_engine_or_404(session_id: str, db: Session = Depends(get_db)) -> GameEngine:
    eng = store.get(session_id)
    if eng is not None:
        return eng

    # インメモリキャッシュミス（再起動 or LRU追い出し直後）: DBのアクションログから再構築する。
    row = crud.load_active_session(db, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    eng = rebuild_engine(row)
    store.restore(session_id, eng)
    return eng
