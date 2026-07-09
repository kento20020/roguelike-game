"""バックグラウンド保守タスク。

`active_sessions` の TTL 掃除を FastAPI lifespan から起動する周期タスクで実行する
（新規インフラ・依存を増やさない最小フットプリント方針。APScheduler 等は不採用）。
DB 呼び出しは同期関数（SQLAlchemy）なので `asyncio.to_thread` でイベントループを
ブロックしないようにオフロードする。
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db import crud

logger = logging.getLogger("casino_tower.maintenance")


def cleanup_stale_sessions_once(session_factory: Callable[[], Session], ttl_hours: int) -> int:
    """TTL 超過した active_sessions 行を1回だけ削除し、削除件数を返す薄いラッパー。

    session_factory はテスト時に in-memory SQLite 用のファクトリを注入できるようにする
    ための引数（本番では app.db.session.SessionLocal を渡す）。DBセッションは必ず閉じる。
    """
    db = session_factory()
    try:
        return crud.delete_stale_active_sessions(db, max_age_hours=ttl_hours)
    finally:
        db.close()


async def periodic_session_cleanup(
    session_factory: Callable[[], Session], interval_hours: float, ttl_hours: int
) -> None:
    """一定間隔で cleanup_stale_sessions_once を実行し続ける（起動直後に1回実行）。

    一過性の DB エラーでタスクが死なないよう、掃除処理は try/except で包んで継続する
    （キャンセルは asyncio.CancelledError=BaseException なので Exception では捕捉されず、
    正常なシャットダウンとして呼び出し側へ伝播する）。掃除0件時はログを出さない
    （正常系ログを恒常ノイズにしないため。削除が発生したときのみ INFO で記録する）。
    """
    while True:
        try:
            deleted = await asyncio.to_thread(cleanup_stale_sessions_once, session_factory, ttl_hours)
            if deleted > 0:
                logger.info("cleaned up %d stale active_sessions (ttl=%dh)", deleted, ttl_hours)
        except Exception:
            logger.exception("periodic_session_cleanup failed; will retry after interval")
        await asyncio.sleep(interval_hours * 3600)
