"""FastAPI エントリポイント。 起動: uvicorn main:app --reload

エラー対応: WrongPhase→409 / InvalidMove→400 / UpgradeError→400。
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.db import models  # noqa: F401  (テーブル登録のため import)
from app.db.crud import UpgradeError
from app.db.session import Base, engine
from app.engine.game_engine import IllegalAction, InvalidMove, WrongPhase

app = FastAPI(title="カジノタワー ローグライト API", version="1.0")

# テーブル作成（SQLite）
Base.metadata.create_all(bind=engine)

# 将来のフロント（Vite dev server 等）用に CORS を許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(WrongPhase)
async def _wrong_phase(_: Request, exc: WrongPhase):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidMove)
async def _invalid_move(_: Request, exc: InvalidMove):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(UpgradeError)
async def _upgrade_error(_: Request, exc: UpgradeError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(IllegalAction)
async def _illegal_action(_: Request, exc: IllegalAction):
    # WrongPhase/InvalidMove に該当しない基底例外のフォールバック
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
