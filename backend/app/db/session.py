"""DB接続（SQLite）。PostgreSQL移行時はここの URL/接続だけ差し替える。"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# backend/game.db
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(_BACKEND_DIR, 'game.db')}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

if engine.dialect.name == "sqlite":
    # OPEN-007のアクションログ再生でリクエストごとの書き込みが増える分、
    # 読み取りをブロックしないよう WAL mode にする（ファイルDB前提。in-memoryテスト用engineは
    # 各テストが個別に create_engine するためここには含まれない）。
    @event.listens_for(engine, "connect")
    def _set_sqlite_wal(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
