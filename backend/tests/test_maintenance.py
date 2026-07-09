"""active_sessions TTL 掃除の周期タスク（FastAPI lifespan 起動）のテスト。

test_telemetry.py の _mem_db() / test_session_persistence.py の ActiveSessionRow 直接操作の
作法に合わせる。lifespan は `with TestClient(app) as client:` の形でのみ発火する
（既存 test_api.py の api fixture は `with` 無しで生成しているため影響を受けない）。
"""
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from app.db.models import ActiveSessionRow
from app.db.session import Base
from app.maintenance import cleanup_stale_sessions_once


def _mem_session_factory():
    """テスト専用の隔離した in-memory SQLite セッションファクトリを返す。"""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    return sessionmaker(bind=eng, autoflush=False, autocommit=False)


def _naive_utc_now() -> datetime:
    """crud._naive_utc_now と同じ「SQLite CURRENT_TIMESTAMP 互換の naive UTC」。"""
    return datetime.now(UTC).replace(tzinfo=None)


def test_cleanup_removes_only_stale_rows():
    factory = _mem_session_factory()
    now = _naive_utc_now()
    with factory() as db:
        # 8日前 = 既定TTL(7日=168h)超過 → 掃除対象
        db.add(ActiveSessionRow(session_id="stale", seed=1, bot_type="human",
                                upgrades_json={}, actions_json=[],
                                last_seen_at=now - timedelta(days=8)))
        # 現在時刻 = TTL内 → 残す
        db.add(ActiveSessionRow(session_id="fresh", seed=2, bot_type="human",
                                upgrades_json={}, actions_json=[],
                                last_seen_at=now))
        db.commit()

    deleted = cleanup_stale_sessions_once(factory, ttl_hours=168)
    assert deleted == 1  # 戻り値は削除件数

    with factory() as db:
        remaining = [r.session_id for r in db.execute(select(ActiveSessionRow)).scalars()]
    assert remaining == ["fresh"]  # 古い行だけ消え、新しい行は残る


def test_lifespan_starts_and_stops_cleanly():
    # コンテキストマネージャ構文が lifespan（startup/shutdown）を実際に発火させる。
    # startup で周期タスクが立ち上がり、shutdown で例外なくキャンセルされることを確認。
    with TestClient(main.app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
