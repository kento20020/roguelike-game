"""ディーラー調書（個人観測統計）のテスト。

- increment_observation の集計が正しいこと
- wilson() の CI 計算が妥当な範囲であること
- dossier API のレスポンスJSONに真のweight/probability系のキーが一切含まれないこと
  （開示不変条件。プレイヤーは「自分が観測した頻度」しか見えてはいけない）
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from app.db import crud
from app.db.session import Base, get_db
from app.session_store import store
from app.simulation.balance_stats import wilson

# ── 共有 fixture（test_api.py と同じ隔離パターン: in-memory SQLite + TestClient） ──


@pytest.fixture
def api():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    TestSession = sessionmaker(bind=eng, autoflush=False, autocommit=False)

    def _override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = _override
    store.clear()
    client = TestClient(main.app)
    yield client, TestSession
    main.app.dependency_overrides.clear()
    store.clear()


def _new(client, seed=1):
    r = client.post("/api/run/new", json={"seed": seed})
    assert r.status_code == 200
    return r.json()


# 戦闘だけを何ターンか進める（select-node で敵ノードへ入り、attack を繰り返す）。
def _fight_some_turns(client, sid, state, max_turns=200):
    nodes = state["floor"]["nodes"]
    avail = [nid for nid, n in nodes.items() if n["state"] == "available" and n["kind"] == "enemy"]
    assert avail, "テスト用フロアに敵ノードが無い"
    state = client.post(f"/api/run/{sid}/select-node", json={"node_id": avail[0]}).json()
    assert state["phase"] == "battle"
    turns = 0
    while state["phase"] == "battle" and turns < max_turns:
        state = client.post(f"/api/run/{sid}/attack").json()
        turns += 1
    return state


# ───────────── crud.increment_observation ─────────────
def test_increment_observation_aggregates(api):
    _, TestSession = api
    with TestSession() as db:
        crud.increment_observation(db, "f1_fixed_a", "counter", data_version="v1")
        crud.increment_observation(db, "f1_fixed_a", "counter", data_version="v1")
        crud.increment_observation(db, "f1_fixed_a", "none", data_version="v1")
        crud.increment_observation(db, "f1_fixed_b", "heavy_blow", data_version="v1")

        rows = {(r.enemy_id, r.behavior): r.count for r in crud.get_dossier(db, "v1")}
        assert rows[("f1_fixed_a", "counter")] == 2
        assert rows[("f1_fixed_a", "none")] == 1
        assert rows[("f1_fixed_b", "heavy_blow")] == 1


def test_increment_observation_separates_data_version(api):
    _, TestSession = api
    with TestSession() as db:
        crud.increment_observation(db, "f1_fixed_a", "counter", data_version="v1")
        crud.increment_observation(db, "f1_fixed_a", "counter", data_version="v2")
        v1_rows = crud.get_dossier(db, "v1")
        v2_rows = crud.get_dossier(db, "v2")
        assert len(v1_rows) == 1 and v1_rows[0].count == 1
        assert len(v2_rows) == 1 and v2_rows[0].count == 1


# ───────────── wilson() の妥当性 ─────────────
def test_wilson_ci_reasonable_range():
    lo, hi = wilson(42, 100)  # observed 42%
    assert 0.0 <= lo < 0.42 < hi <= 1.0
    # n=0 は退避値
    assert wilson(0, 0) == (0.0, 0.0)
    # サンプル数が増えるほど CI 幅は狭くなる（同じ観測比率で）
    lo_small, hi_small = wilson(4, 10)
    lo_big, hi_big = wilson(400, 1000)
    assert (hi_big - lo_big) < (hi_small - lo_small)


# ───────────── dossier API: 集計の正しさ ─────────────
def test_dossier_api_aggregates_from_real_battles(api):
    client, _ = api
    sid = _new(client, seed=123)["session_id"]
    state = client.get(f"/api/run/{sid}").json()
    _fight_some_turns(client, sid, state)

    r = client.get("/api/profile/dossier")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and len(body) >= 1
    for enemy in body:
        total_from_behaviors = sum(b["count"] for b in enemy["behaviors"])
        assert total_from_behaviors == enemy["n_total"]
        for b in enemy["behaviors"]:
            assert b["n_total"] == enemy["n_total"]
            lo, hi = wilson(b["count"], b["n_total"])
            assert b["ci_low"] == pytest.approx(lo)
            assert b["ci_high"] == pytest.approx(hi)


def test_dossier_api_empty_when_no_observations(api):
    client, _ = api
    r = client.get("/api/profile/dossier")
    assert r.status_code == 200
    assert r.json() == []


def test_dossier_api_data_version_query_param(api):
    client, _ = api
    sid = _new(client, seed=5)["session_id"]
    state = client.get(f"/api/run/{sid}").json()
    _fight_some_turns(client, sid, state)

    # 別の data_version には何も無い
    other = client.get("/api/profile/dossier", params={"data_version": "some-other-version"})
    assert other.status_code == 200
    assert other.json() == []


# ───────────── 開示不変条件: 真のweight/probabilityは絶対に出さない ─────────────
_FORBIDDEN_SUBSTRINGS = (
    "weight", "probability", "prob", "chaos", "tier_range", "gold_base", "ramp_increment",
)


def _collect_keys(obj, acc: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            _collect_keys(v, acc)
    elif isinstance(obj, list):
        for item in obj:
            _collect_keys(item, acc)


def test_dossier_response_never_exposes_true_weights_or_raw_enemy_data(api):
    client, _ = api
    sid = _new(client, seed=99)["session_id"]
    state = client.get(f"/api/run/{sid}").json()
    _fight_some_turns(client, sid, state)

    r = client.get("/api/profile/dossier")
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1  # テストとして意味があるためには非空である必要がある

    keys: set[str] = set()
    _collect_keys(body, keys)
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert not any(forbidden in k.lower() for k in keys), (
            f"dossier response leaked a forbidden-looking key containing '{forbidden}': {keys}"
        )

    # レスポンス形状も固定（新規フィールドが紛れ込んだら気付けるように）
    for enemy in body:
        assert set(enemy.keys()) == {"enemy_id", "behaviors", "n_total"}
        for b in enemy["behaviors"]:
            assert set(b.keys()) == {"behavior", "count", "n_total", "ci_low", "ci_high"}


def test_catalog_enemies_never_exposes_weights(api):
    """/api/catalog/enemies も id/name/experience のみ（weight/behaviors非開示）。"""
    client, _ = api
    r = client.get("/api/catalog/enemies")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    for e in items:
        assert set(e.keys()) == {"id", "name", "experience"}
