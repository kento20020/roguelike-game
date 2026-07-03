"""§25 エンドポイント。gameplay は engine を駆動し完全状態を返す。
ラン終了で RunRecord 保存＋（cleared なら）恒久強化ポイント付与。
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_engine_or_404
from app.data.loader import get_data
from app.db import crud
from app.db.session import get_db
from app.engine.game_engine import (
    PHASE_CLEARED,
    PHASE_DEAD,
    GameEngine,
)
from app.schemas.api_schemas import (
    CombatActionRequest,
    GameStateResponse,
    ModCatalogItem,
    NewRunRequest,
    RunRecordOut,
    SelectNodeRequest,
    SinkRequest,
    UpgradeRequest,
    UpgradeStateResponse,
)
from app.session_store import store

router = APIRouter(prefix="/api")


def _state(session_id: str, eng: GameEngine) -> GameStateResponse:
    return GameStateResponse(session_id=session_id, **eng.snapshot())


def _finalize_if_ended(db: Session, session_id: str, eng: GameEngine) -> None:
    if eng.phase in (PHASE_CLEARED, PHASE_DEAD) and not store.is_finalized(session_id):
        crud.save_run_record(db, eng.run.snapshot())
        if eng.phase == PHASE_CLEARED:
            pts = eng.data.config["permanent_upgrades"]["points_per_clear"]
            crud.award_points(db, pts)
        store.mark_finalized(session_id)


# ── catalog（静的データ・効果文の正本）──
@router.get("/catalog/mods", response_model=list[ModCatalogItem])
def catalog_mods():
    data = get_data()
    return [
        {"id": m["id"], "name": m["name"], "effect_1": m["effect_1"], "effect_stack": m["effect_stack"]}
        for m in data.mods
    ]


# ── run lifecycle ──
@router.post("/run/new", response_model=GameStateResponse)
def new_run(req: NewRunRequest, db: Session = Depends(get_db)):
    seed = req.seed if req.seed is not None else secrets.randbits(32)
    profile = crud.get_or_create_profile(db)
    eng = GameEngine()
    eng.new_run(seed, upgrades=crud.profile_levels(profile), bot_type=req.bot_type)
    session_id = store.create(eng)
    return _state(session_id, eng)


@router.get("/run/{session_id}", response_model=GameStateResponse)
def get_run(session_id: str):
    return _state(session_id, get_engine_or_404(session_id))


@router.post("/run/{session_id}/select-node", response_model=GameStateResponse)
def select_node(session_id: str, req: SelectNodeRequest, db: Session = Depends(get_db)):
    eng = get_engine_or_404(session_id)
    eng.select_node(req.node_id)
    _finalize_if_ended(db, session_id, eng)
    return _state(session_id, eng)


@router.post("/run/{session_id}/attack", response_model=GameStateResponse)
def attack(session_id: str, req: CombatActionRequest = CombatActionRequest(), db: Session = Depends(get_db)):
    eng = get_engine_or_404(session_id)
    eng.attack(side_bet=req.side_bet.model_dump() if req.side_bet else None)
    _finalize_if_ended(db, session_id, eng)
    return _state(session_id, eng)


@router.post("/run/{session_id}/guard", response_model=GameStateResponse)
def guard(session_id: str, req: CombatActionRequest = CombatActionRequest(), db: Session = Depends(get_db)):
    eng = get_engine_or_404(session_id)
    eng.guard(side_bet=req.side_bet.model_dump() if req.side_bet else None)
    _finalize_if_ended(db, session_id, eng)
    return _state(session_id, eng)


@router.post("/run/{session_id}/sink", response_model=GameStateResponse)
def sink(session_id: str, req: SinkRequest):
    eng = get_engine_or_404(session_id)
    eng.use_sink(req.sink_type)
    return _state(session_id, eng)


@router.post("/run/{session_id}/treasure/open", response_model=GameStateResponse)
def treasure_open(session_id: str):
    eng = get_engine_or_404(session_id)
    eng.treasure_open()
    return _state(session_id, eng)


@router.post("/run/{session_id}/treasure/reroll", response_model=GameStateResponse)
def treasure_reroll(session_id: str):
    eng = get_engine_or_404(session_id)
    eng.treasure_reroll()
    return _state(session_id, eng)


@router.post("/run/{session_id}/gate/resolve", response_model=GameStateResponse)
def gate_resolve(session_id: str, db: Session = Depends(get_db)):
    eng = get_engine_or_404(session_id)
    eng.gate_resolve()
    _finalize_if_ended(db, session_id, eng)
    return _state(session_id, eng)


@router.post("/run/{session_id}/continue", response_model=GameStateResponse)
def continue_(session_id: str):
    """モーダルphase（treasure_opened/heal）を閉じて exploring へ（§25補完）。"""
    eng = get_engine_or_404(session_id)
    eng.dismiss()
    return _state(session_id, eng)


# ── meta progression ──
@router.get("/profile/upgrades", response_model=UpgradeStateResponse)
def profile_upgrades(db: Session = Depends(get_db)):
    """現在の恒久強化状態（残ポイント・各Lv・上限）。ClearedPage の初期表示用。"""
    p = crud.get_or_create_profile(db)
    return UpgradeStateResponse(
        points=p.points, levels=crud.profile_levels(p), maxes=crud.upgrade_maxes())


@router.post("/run/{session_id}/upgrade", response_model=UpgradeStateResponse)
def upgrade(session_id: str, req: UpgradeRequest, db: Session = Depends(get_db)):
    get_engine_or_404(session_id)  # session 妥当性のみ確認
    p = crud.allocate_upgrade(db, req.upgrade_type)  # UpgradeError -> 400
    return UpgradeStateResponse(
        points=p.points, levels=crud.profile_levels(p), maxes=crud.upgrade_maxes())


# ── telemetry ──
@router.get("/stats/history", response_model=list[RunRecordOut])
def history(limit: int = 50, db: Session = Depends(get_db)):
    return [RunRecordOut(**r.to_dict()) for r in crud.list_run_records(db, limit)]
