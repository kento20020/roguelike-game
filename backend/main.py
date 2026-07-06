"""FastAPI エントリポイント。 起動: uvicorn main:app --reload

エラー対応: WrongPhase→409 / InvalidMove→400 / UpgradeError→400。
運用設定は環境変数（.env.example 参照）: ALLOWED_ORIGINS / LOG_LEVEL / DATABASE_URL。
"""
from __future__ import annotations

import logging
import os
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.db import models  # noqa: F401  (テーブル登録のため import)
from app.db.crud import UpgradeError
from app.db.session import Base, engine
from app.engine.game_engine import IllegalAction, InvalidMove, WrongPhase

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("casino_tower")

app = FastAPI(title="カジノタワー ローグライト API", version="1.0")

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
    """リクエストID採番（X-Request-ID）。障害調査時にログとレスポンスを突き合わせる足がかり。"""
    req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    if response.status_code >= 400:
        logger.warning("req=%s %s %s -> %d", req_id, request.method, request.url.path,
                       response.status_code)
    return response


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
