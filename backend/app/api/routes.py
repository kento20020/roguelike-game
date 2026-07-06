"""§25 エンドポイント。gameplay は engine を駆動し完全状態を返す。
ラン終了で RunRecord 保存＋（cleared なら）恒久強化ポイント付与。
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import finalize_run, get_engine_or_404
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

router = APIRouter(prefix="/api")

# ディーラー調書の観測データ世代札（バランス改定等で分けたい場合に上げる。config.jsonとは無関係）。
DOSSIER_DATA_VERSION = "prototype-v1"


def _state(session_id: str, eng: GameEngine) -> GameStateResponse:
    return GameStateResponse(session_id=session_id, **eng.snapshot())


def _finalize_if_ended(db: Session, session_id: str, eng: GameEngine) -> None:
    # ライブ経路の二重確定防止は store.is_finalized（プロセス内・セッション単位）で行う。
    # 保存本体は復元経路と共有する finalize_run（app.api.deps）。
    if eng.phase in (PHASE_CLEARED, PHASE_DEAD) and not store.is_finalized(session_id):
        finalize_run(db, session_id, eng)


# ── catalog（静的データ・効果文の正本）──
@router.get("/catalog/mods", response_model=list[ModCatalogItem])
def catalog_mods() -> list[dict]:
    data = get_data()
    return [
        {"id": m["id"], "name": m["name"], "effect_1": m["effect_1"], "effect_stack": m["effect_stack"]}
        for m in data.mods
    ]


@router.get("/catalog/enemies", response_model=list[EnemyCatalogItem])
def catalog_enemies() -> list[dict]:
    """敵名表示用の軽量カタログ。weight/behaviorsなど生データは含めない（開示不変条件）。"""
    data = get_data()
    return [{"id": e["id"], "name": e["name"], "experience": e["experience"]} for e in data.enemies]


# ── run lifecycle ──
@router.post("/run/new", response_model=GameStateResponse)
def new_run(req: NewRunRequest, db: Session = Depends(get_db)) -> GameStateResponse:
    seed = req.seed if req.seed is not None else secrets.randbits(32)
    profile = crud.get_or_create_profile(db)
    upgrades = crud.profile_levels(profile)
    eng = GameEngine()
    eng.new_run(seed, upgrades=upgrades, bot_type=req.bot_type)
    session_id = store.create(eng)
    crud.create_active_session(db, session_id, seed, req.bot_type, upgrades)
    return _state(session_id, eng)


@router.get("/run/{session_id}", response_model=GameStateResponse)
def get_run(session_id: str, db: Session = Depends(get_db)) -> GameStateResponse:
    return _state(session_id, get_engine_or_404(session_id, db))


@router.post("/run/{session_id}/select-node", response_model=GameStateResponse)
def select_node(session_id: str, req: SelectNodeRequest, db: Session = Depends(get_db)) -> GameStateResponse:
    eng = get_engine_or_404(session_id, db)
    eng.select_node(req.node_id)
    crud.record_action(db, session_id, {"type": "select_node", "node_id": req.node_id})
    _finalize_if_ended(db, session_id, eng)
    return _state(session_id, eng)


def _drain_observations(db: Session, eng: GameEngine) -> None:
    """戦闘ターンで蓄積された (enemy_id, behavior) 観測をディーラー調書に反映する。"""
    for enemy_id, behavior in eng.drain_observations():
        crud.increment_observation(db, enemy_id, behavior, data_version=DOSSIER_DATA_VERSION)


@router.post("/run/{session_id}/attack", response_model=GameStateResponse)
def attack(session_id: str, req: CombatActionRequest = CombatActionRequest(),
           db: Session = Depends(get_db)) -> GameStateResponse:
    eng = get_engine_or_404(session_id, db)
    side_bet = req.side_bet.model_dump() if req.side_bet else None
    eng.attack(side_bet=side_bet)
    crud.record_action(db, session_id, {"type": "attack", "side_bet": side_bet})
    _drain_observations(db, eng)
    _finalize_if_ended(db, session_id, eng)
    return _state(session_id, eng)


@router.post("/run/{session_id}/guard", response_model=GameStateResponse)
def guard(session_id: str, req: CombatActionRequest = CombatActionRequest(),
          db: Session = Depends(get_db)) -> GameStateResponse:
    eng = get_engine_or_404(session_id, db)
    side_bet = req.side_bet.model_dump() if req.side_bet else None
    eng.guard(side_bet=side_bet)
    crud.record_action(db, session_id, {"type": "guard", "side_bet": side_bet})
    _drain_observations(db, eng)
    _finalize_if_ended(db, session_id, eng)
    return _state(session_id, eng)


@router.post("/run/{session_id}/sink", response_model=GameStateResponse)
def sink(session_id: str, req: SinkRequest, db: Session = Depends(get_db)) -> GameStateResponse:
    eng = get_engine_or_404(session_id, db)
    eng.use_sink(req.sink_type)
    crud.record_action(db, session_id, {"type": "use_sink", "sink_type": req.sink_type})
    return _state(session_id, eng)


@router.post("/run/{session_id}/treasure/open", response_model=GameStateResponse)
def treasure_open(session_id: str, db: Session = Depends(get_db)) -> GameStateResponse:
    eng = get_engine_or_404(session_id, db)
    eng.treasure_open()
    crud.record_action(db, session_id, {"type": "treasure_open"})
    return _state(session_id, eng)


@router.post("/run/{session_id}/treasure/reroll", response_model=GameStateResponse)
def treasure_reroll(session_id: str, db: Session = Depends(get_db)) -> GameStateResponse:
    eng = get_engine_or_404(session_id, db)
    eng.treasure_reroll()
    crud.record_action(db, session_id, {"type": "treasure_reroll"})
    return _state(session_id, eng)


@router.post("/run/{session_id}/gate/resolve", response_model=GameStateResponse)
def gate_resolve(session_id: str, db: Session = Depends(get_db)) -> GameStateResponse:
    eng = get_engine_or_404(session_id, db)
    eng.gate_resolve()
    crud.record_action(db, session_id, {"type": "gate_resolve"})
    _finalize_if_ended(db, session_id, eng)
    return _state(session_id, eng)


@router.post("/run/{session_id}/continue", response_model=GameStateResponse)
def continue_(session_id: str, db: Session = Depends(get_db)) -> GameStateResponse:
    """モーダルphase（treasure_opened/heal）を閉じて exploring へ（§25補完）。"""
    eng = get_engine_or_404(session_id, db)
    eng.dismiss()
    crud.record_action(db, session_id, {"type": "dismiss"})
    return _state(session_id, eng)


@router.get("/run/{session_id}/postmortem", response_model=PostmortemResponse)
def postmortem(session_id: str, db: Session = Depends(get_db)) -> PostmortemResponse:
    """検死レポート＋リプレイ（戦闘死のみ。ゲート死は致命ターンが無いため対象外）。"""
    eng = get_engine_or_404(session_id, db)
    row = crud.get_postmortem(db, eng.run.run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="postmortem not available for this run")
    return PostmortemResponse(**row.to_dict())


# ── meta progression ──
@router.get("/profile/upgrades", response_model=UpgradeStateResponse)
def profile_upgrades(db: Session = Depends(get_db)) -> UpgradeStateResponse:
    """現在の恒久強化状態（残ポイント・各Lv・上限）。ClearedPage の初期表示用。"""
    p = crud.get_or_create_profile(db)
    return UpgradeStateResponse(
        points=p.points, levels=crud.profile_levels(p), maxes=crud.upgrade_maxes())


@router.post("/run/{session_id}/upgrade", response_model=UpgradeStateResponse)
def upgrade(session_id: str, req: UpgradeRequest, db: Session = Depends(get_db)) -> UpgradeStateResponse:
    get_engine_or_404(session_id, db)  # session 妥当性のみ確認
    p = crud.allocate_upgrade(db, req.upgrade_type)  # UpgradeError -> 400
    return UpgradeStateResponse(
        points=p.points, levels=crud.profile_levels(p), maxes=crud.upgrade_maxes())


@router.get("/profile/dossier", response_model=list[DossierEnemyOut])
def profile_dossier(data_version: str = DOSSIER_DATA_VERSION, db: Session = Depends(get_db)) -> list[DossierEnemyOut]:
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
