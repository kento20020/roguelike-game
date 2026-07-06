"""OPEN-024/025 — data_version・strategy_version・テレメトリ列・run_actions 永続化。"""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.data.loader import GameData
from app.db import crud
from app.db.models import RunActionsRow
from app.db.session import Base
from app.engine.game_engine import GameEngine
from tests.test_engine_run import auto_play


def _mem_db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    return sessionmaker(bind=eng, autoflush=False, autocommit=False)()


def test_data_version_is_stable_content_hash(data):
    v1 = GameData.load().data_version
    v2 = GameData.load().data_version
    assert v1 == v2, "同じデータからは同じ世代札"
    assert len(v1) == 12 and all(c in "0123456789abcdef" for c in v1)


def test_run_record_collects_action_and_gate_telemetry(data):
    eng = GameEngine(data)
    snap = auto_play(eng, seed=7)
    rr = snap["run_record"]
    assert rr["action_counts"].get("attack", 0) > 0
    assert isinstance(rr["sink_use_counts"], dict)
    if rr["floor_reached"] >= 2:
        first = rr["gate_results"][0]
        assert first["floor"] == 1
        assert first["outcome"] in ("unhurt", "minor", "major", "special")


def test_guard_and_sink_use_counts(data):
    eng = GameEngine(data)
    eng.new_run(1)
    eng.player.chips = 999
    eng.select_node("L")
    eng.guard()
    assert eng.run.action_counts.get("guard", 0) >= 1
    if eng.phase == "battle":
        eng.use_sink("scout")
        assert eng.run.sink_use_counts["scout"] == 1


def test_save_run_record_stamps_versions(data):
    db = _mem_db()
    g = GameEngine(data)
    auto_play(g, seed=11)
    row = crud.save_run_record(db, g.run.snapshot(), strategy_version=None)
    assert row.data_version == GameData.load().data_version
    assert row.strategy_version is None
    row2 = crud.save_run_record(db, g.run.snapshot(), strategy_version="strong-v1")
    assert row2.strategy_version == "strong-v1"
    # API 出力（to_dict）にも載る
    d = row.to_dict()
    assert d["data_version"] and isinstance(d["sink_use_counts"], dict)


def test_save_run_actions_persists_full_history(data):
    db = _mem_db()
    g = GameEngine(data)
    auto_play(g, seed=11)
    ra = crud.save_run_actions(db, g.run.run_id, g.run.turn_history)
    assert ra.run_id == g.run.run_id
    assert len(ra.actions_json) == g.run.total_turns  # 全ターンが残る（クリア/死亡を問わない）
    got = db.execute(select(RunActionsRow).where(RunActionsRow.run_id == g.run.run_id)).scalars().first()
    assert got is not None and got.actions_json[0]["player_move"] in ("attack", "guard", "heal_small", "heal_large")
