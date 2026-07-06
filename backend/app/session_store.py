"""アクティブラン（進行中ゲーム）のメモリ保持（LRUキャッシュ）。

session_id → GameEngine をプロセス内 OrderedDict で保持し、上限を超えたら最古を
追い出す（第一級の永続先ではない・単なるホットキャッシュ）。真の永続化は
ActiveSessionRow（app.db.models）が担い、キャッシュミス時は
app.engine.replay.rebuild_engine() で再構築できる（app.api.deps.get_engine_or_404）。
そのため追い出し・プロセス再起動があっても進行中ランは失われない（OPEN-007）。
"""
from __future__ import annotations

import uuid
from collections import OrderedDict
from typing import Optional

from app.engine.game_engine import GameEngine

MAX_SESSIONS = 500  # インメモリに保持する上限。超過分は最古から追い出す（DBから復元可能）。


class SessionStore:
    def __init__(self, max_sessions: int = MAX_SESSIONS) -> None:
        self._engines: OrderedDict[str, GameEngine] = OrderedDict()
        self._finalized: set[str] = set()
        self._max_sessions = max_sessions

    def _evict_if_over_capacity(self) -> None:
        while len(self._engines) > self._max_sessions:
            oldest_sid, _ = self._engines.popitem(last=False)
            self._finalized.discard(oldest_sid)

    def create(self, engine: GameEngine) -> str:
        sid = uuid.uuid4().hex
        self._engines[sid] = engine
        self._evict_if_over_capacity()
        return sid

    def restore(self, sid: str, engine: GameEngine) -> None:
        """既知の session_id を維持したまま（DBから再構築した）engine を登録する。"""
        self._engines[sid] = engine
        self._evict_if_over_capacity()

    def get(self, sid: str) -> Optional[GameEngine]:
        eng = self._engines.get(sid)
        if eng is not None:
            self._engines.move_to_end(sid)
        return eng

    def drop(self, sid: str) -> None:
        """セッションをキャッシュから破棄する（DB行が消えたゾンビエンジンの掃除用）。"""
        self._engines.pop(sid, None)
        self._finalized.discard(sid)

    def mark_finalized(self, sid: str) -> None:
        self._finalized.add(sid)

    def is_finalized(self, sid: str) -> bool:
        return sid in self._finalized

    def clear(self) -> None:
        self._engines.clear()
        self._finalized.clear()


# プロセス内シングルトン
store = SessionStore()
