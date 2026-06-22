"""依存性: アクティブランの取得（404）。DB は app.db.session.get_db を直接使う。"""
from __future__ import annotations

from fastapi import HTTPException

from app.engine.game_engine import GameEngine
from app.session_store import store


def get_engine_or_404(session_id: str) -> GameEngine:
    eng = store.get(session_id)
    if eng is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    return eng
