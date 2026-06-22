"""アクティブラン（進行中ゲーム）のメモリ保持。

session_id → GameEngine をプロセス内 dict で保持。DBは結果（RunRecord/Profile）のみ。
退避/TTLなし（dev 用・単一プロセス前提）。再起動で進行中ランは失われる（仕様: NOTES参照）。
マルチワーカー/再起動対応が必要なら engine の全状態シリアライズ（rng含む）が前提となる。
"""
from __future__ import annotations

import uuid
from typing import Optional

from app.engine.game_engine import GameEngine


class SessionStore:
    def __init__(self) -> None:
        self._engines: dict[str, GameEngine] = {}
        self._finalized: set[str] = set()

    def create(self, engine: GameEngine) -> str:
        sid = uuid.uuid4().hex
        self._engines[sid] = engine
        return sid

    def get(self, sid: str) -> Optional[GameEngine]:
        return self._engines.get(sid)

    def mark_finalized(self, sid: str) -> None:
        self._finalized.add(sid)

    def is_finalized(self, sid: str) -> bool:
        return sid in self._finalized

    def clear(self) -> None:
        self._engines.clear()
        self._finalized.clear()


# プロセス内シングルトン
store = SessionStore()
