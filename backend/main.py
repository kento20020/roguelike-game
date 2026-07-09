"""FastAPI エントリポイント。 起動: uvicorn main:app --reload

エラー対応: WrongPhase→409 / InvalidMove→400 / UpgradeError→400。
運用設定は環境変数（.env.example 参照）: ALLOWED_ORIGINS / LOG_LEVEL / DATABASE_URL。
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.db import models  # noqa: F401  (テーブル登録のため import)
from app.db.crud import UpgradeError
from app.db.session import Base, SessionLocal, engine
from app.engine.game_engine import IllegalAction, InvalidMove, WrongPhase
from app.logging_setup import request_id_var, setup_logging
from app.maintenance import periodic_session_cleanup

setup_logging()
logger = logging.getLogger("casino_tower")

# active_sessions TTL 掃除の周期タスク設定（.env.example 参照）。
# TTL は crud.delete_stale_active_sessions の既定（7日=168h）に一致させる。
_SESSION_TTL_HOURS = int(os.environ.get("SESSION_TTL_HOURS", "168"))
_SESSION_CLEANUP_INTERVAL_HOURS = float(os.environ.get("SESSION_CLEANUP_INTERVAL_HOURS", "24"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """起動時に active_sessions TTL 掃除の周期タスクを立ち上げ、停止時に確実に片付ける。

    NOTE: TestClient をコンテキストマネージャ無し（`TestClient(app)`）で使う既存テストでは
    lifespan は発火しない。`with TestClient(app) as client:` を使ったときのみ起動する。
    """
    task = asyncio.create_task(
        periodic_session_cleanup(
            SessionLocal,
            interval_hours=_SESSION_CLEANUP_INTERVAL_HOURS,
            ttl_hours=_SESSION_TTL_HOURS,
        )
    )
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # 正常なシャットダウン（周期タスクのキャンセルは想定内）

app = FastAPI(title="カジノタワー ローグライト API", version="1.0", lifespan=lifespan)

# テーブル作成（SQLite・開発/テスト用フォールバック）。
# スキーマ変更の正規手段は Alembic（docs/runbook.md）。create_all は既存テーブルに列追加をしない。
Base.metadata.create_all(bind=engine)

# CORS: 既定は Vite dev server のみ。公開時は ALLOWED_ORIGINS（カンマ区切り）で明示する。
_origins = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """リクエストID採番（X-Request-ID）。障害調査時にログとレスポンスを突き合わせる足がかり。

    call_next の前に request_id_var へ set し、finally で reset することで、call_next 内側で
    走る全ログレコード（RequestIdFilter 経由）へ request_id が自動付与される。手動での
    req_id 引数埋め込みは不要になったのでメッセージから外した。
    """
    req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    token = request_id_var.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        if response.status_code >= 400:
            logger.warning("%s %s -> %d", request.method, request.url.path,
                           response.status_code)
        return response
    finally:
        request_id_var.reset(token)


@app.exception_handler(WrongPhase)
async def _wrong_phase(_: Request, exc: WrongPhase):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


# InvalidMove（不正操作） / UpgradeError（強化不可） / IllegalAction（WrongPhase/InvalidMove に
# 該当しない基底例外のフォールバック）はいずれも同じ 400 レスポンスを返す。
@app.exception_handler(InvalidMove)
@app.exception_handler(UpgradeError)
@app.exception_handler(IllegalAction)
async def _bad_request(_: Request, exc: Exception):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    # 想定外の 500 はスタックトレースを必ずサーバログへ残す（クライアントには詳細を返さない）
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
