"""§25 エンドポイント。gameplay は engine を駆動し完全状態を返す。
ラン終了で RunRecord 保存＋（cleared なら）恒久強化ポイント付与。
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
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
    DossierBehaviorOut,
    DossierEnemyOut,
    EnemyCatalogItem,
    GameStateResponse,
    ModCatalogItem,
    NewRunRequest,
    PostmortemResponse,
    RunRecordOut,
    SelectNodeRequest,
    SinkRequest,
    UpgradeRequest,
    UpgradeStateResponse,
)
from app.session_store import store
from app.simulation.balance_stats import wilson
from app.simulation.bots import STRATEGY_VERSION

router = APIRouter(prefix="/api")

# ディーラー調書の観測データ世代札（バランス改定等で分けたい場合に上げる。config.jsonとは無関係）。
DOSSIER_DATA_VERSION = "prototype-v1"


def _state(session_id: str, eng: GameEngine) -> GameStateResponse:
    return GameStateResponse(session_id=session_id, **eng.snapshot())


def _finalize_if_ended(db: Session, session_id: str, eng: GameEngine) -> None:
    if eng.phase in (PHASE_CLEARED, PHASE_DEAD) and not store.is_finalized(session_id):
        # strategy_version は bot 方策の版（OPEN-024）。human ランは NULL。
        sv = None if eng.run.bot_type == "human" else STRATEGY_VERSION
        crud.save_run_record(db, eng.run.snapshot(), strategy_version=sv)
        # 全ラン共通の操作履歴（クリア時も保存＝検死専用の PostmortemRow とは別物）
        crud.save_run_actions(db, eng.run.run_id, eng.run.turn_history)
        if eng.phase == PHASE_CLEARED:
            pts = eng.data.config["permanent_upgrades"]["points_per_clear"]
            crud.award_points(db, pts)
        elif eng.phase == PHASE_DEAD and eng._postmortem:
            crud.save_postmortem(
                db, eng.run.run_id, eng.run.turn_history,
                eng._postmortem["fatal_turn_index"], eng._postmortem,
            )
        store.mark_finalized(session_id)


# ── catalog（静的データ・効果文の正本）──
@router.get("/catalog/mods", response_model=list[ModCatalogItem])
def catalog_mods():
    data = get_data()
    return [
        {"id": m["id"], "name": m["name"], "effect_1": m["effect_1"], "effect_stack": m["effect_stack"]}
        for m in data.mods
    ]


@router.get("/catalog/enemies", response_model=list[EnemyCatalogItem])
def catalog_enemies():
    """敵名表示用の軽量カタログ。weight/behaviorsなど生データは含めない（開示不変条件）。"""
    data = get_data()
    return [{"id": e["id"], "name": e["name"], "experience": e["experience"]} for e in data.enemies]


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


def _drain_observations(db: Session, eng: GameEngine) -> None:
    """戦闘ターンで蓄積された (enemy_id, behavior) 観測をディーラー調書に反映する。"""
    for enemy_id, behavior in eng.drain_observations():
        crud.increment_observation(db, enemy_id, behavior, data_version=DOSSIER_DATA_VERSION)


@router.post("/run/{session_id}/attack", response_model=GameStateResponse)
def attack(session_id: str, req: CombatActionRequest = CombatActionRequest(), db: Session = Depends(get_db)):
    eng = get_engine_or_404(session_id)
    eng.attack(side_bet=req.side_bet.model_dump() if req.side_bet else None)
    _drain_observations(db, eng)
    _finalize_if_ended(db, session_id, eng)
    return _state(session_id, eng)


@router.post("/run/{session_id}/guard", response_model=GameStateResponse)
def guard(session_id: str, req: CombatActionRequest = CombatActionRequest(), db: Session = Depends(get_db)):
    eng = get_engine_or_404(session_id)
    eng.guard(side_bet=req.side_bet.model_dump() if req.side_bet else None)
    _drain_observations(db, eng)
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


@router.get("/run/{session_id}/postmortem", response_model=PostmortemResponse)
def postmortem(session_id: str, db: Session = Depends(get_db)):
    """検死レポート＋リプレイ（戦闘死のみ。ゲート死は致命ターンが無いため対象外）。"""
    eng = get_engine_or_404(session_id)
    row = crud.get_postmortem(db, eng.run.run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="postmortem not available for this run")
    return PostmortemResponse(**row.to_dict())


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


@router.get("/profile/dossier", response_model=list[DossierEnemyOut])
def profile_dossier(data_version: str = DOSSIER_DATA_VERSION, db: Session = Depends(get_db)):
    """ディーラー調書: 自分が観測した行動頻度のみをWilson信頼区間つきで返す。

    真のweight/確率・enemies.jsonの生データは一切含めない（開示不変条件）。
    """
    rows = crud.get_dossier(db, data_version)
    by_enemy: dict[str, list] = {}
    for r in rows:
        by_enemy.setdefault(r.enemy_id, []).append(r)

    result: list[DossierEnemyOut] = []
    for enemy_id, rs in by_enemy.items():
        n_total = sum(r.count for r in rs)
        behaviors = []
        for r in rs:
            ci_low, ci_high = wilson(r.count, n_total)
            behaviors.append(DossierBehaviorOut(
                behavior=r.behavior, count=r.count, n_total=n_total,
                ci_low=ci_low, ci_high=ci_high,
            ))
        result.append(DossierEnemyOut(enemy_id=enemy_id, behaviors=behaviors, n_total=n_total))
    return result


# ── telemetry ──
@router.get("/stats/history", response_model=list[RunRecordOut])
def history(limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)):
    return [RunRecordOut(**r.to_dict()) for r in crud.list_run_records(db, limit)]
