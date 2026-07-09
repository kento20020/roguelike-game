"""API（FastAPI）テスト。各テストは隔離した in-memory SQLite を使う。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from app.db import crud
from app.db.session import Base, get_db
from app.session_store import store


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


# HTTPだけでランを終端まで進める（やや賢いドライバ）
def _drive(client, state, max_steps=3000):
    for _ in range(max_steps):
        sid = state["session_id"]
        ph = state["phase"]
        if ph in ("cleared", "dead"):
            break
        if ph == "battle":
            p = state["player"]
            sinks = [a["sink"] for a in state["available_actions"] if a["type"] == "use_sink"]
            # OPEN-020 で戦闘中回復は1ターン消費するため、緊急時（35%未満）のみ回復する
            if p["hp"] < p["max_hp"] * 0.35 and "heal_large" in sinks:
                state = client.post(f"/api/run/{sid}/sink", json={"sink_type": "heal_large"}).json()
                continue
            state = client.post(f"/api/run/{sid}/attack").json()
        elif ph == "exploring":
            p = state["player"]
            sinks = [a["sink"] for a in state["available_actions"] if a["type"] == "use_sink"]
            # 探索中の回復はターン消費なし（OPEN-020 の battle 中とは違う）ので積極的に使う
            if p["hp"] < p["max_hp"] * 0.7 and "heal_large" in sinks:
                state = client.post(f"/api/run/{sid}/sink", json={"sink_type": "heal_large"}).json()
                continue
            nodes = state["floor"]["nodes"]
            avail = [nid for nid, n in nodes.items() if n["state"] == "available"]
            free = [n for n in avail if nodes[n]["kind"] in ("treasure", "heal", "gate_route")]
            gate = [n for n in avail if nodes[n]["kind"] == "gate"]
            enemies = [n for n in avail if nodes[n]["kind"] == "enemy"]
            pick = free[0] if free else (gate[0] if gate else
                   (max(enemies, key=lambda n: nodes[n]["row"]) if enemies else avail[0]))
            state = client.post(f"/api/run/{sid}/select-node", json={"node_id": pick}).json()
        elif ph == "treasure_preview":
            state = client.post(f"/api/run/{sid}/treasure/open").json()
        elif ph in ("treasure_opened", "heal", "next_floor"):
            state = client.post(f"/api/run/{sid}/continue").json()
        elif ph == "gate_preview":
            state = client.post(f"/api/run/{sid}/gate/resolve").json()
        else:
            break
    return state


# ── basics ──
def test_new_run_and_get(api):
    client, _ = api
    j = _new(client, seed=42)
    assert j["phase"] == "exploring"
    assert j["current_floor"] == 1
    assert j["player"]["hp"] == 100
    sid = j["session_id"]
    g = client.get(f"/api/run/{sid}")
    assert g.status_code == 200
    assert g.json()["session_id"] == sid


def test_unknown_session_404(api):
    client, _ = api
    assert client.get("/api/run/does-not-exist").status_code == 404
    assert client.post("/api/run/nope/attack").status_code == 404


def test_random_seed_when_omitted(api):
    client, _ = api
    r = client.post("/api/run/new", json={})
    assert r.status_code == 200
    assert r.json()["phase"] == "exploring"


# ── gameplay + errors ──
def test_select_battle_then_attack(api):
    client, _ = api
    sid = _new(client)["session_id"]
    r = client.post(f"/api/run/{sid}/select-node", json={"node_id": "L"})
    assert r.status_code == 200 and r.json()["phase"] == "battle"
    # 戦闘が終わるまで攻撃
    state = r.json()
    while state["phase"] == "battle":
        state = client.post(f"/api/run/{sid}/attack").json()
    assert state["floor"]["nodes"]["L"]["resolved"] is True


def test_attack_in_exploring_409(api):
    client, _ = api
    sid = _new(client)["session_id"]
    assert client.post(f"/api/run/{sid}/attack").status_code == 409


def test_select_locked_node_400(api):
    client, _ = api
    sid = _new(client)["session_id"]
    # GATE は最初ロック
    assert client.post(f"/api/run/{sid}/select-node", json={"node_id": "GATE"}).status_code == 400
    # 未知ノードも 400
    assert client.post(f"/api/run/{sid}/select-node", json={"node_id": "ZZZ"}).status_code == 400


def test_full_run_persists_record_and_history(api):
    client, TestSession = api
    state = _drive(client, _new(client, seed=7))
    assert state["phase"] in ("cleared", "dead")
    hist = client.get("/api/stats/history").json()
    assert len(hist) >= 1
    assert hist[0]["total_turns"] > 0
    # OPEN-024: 世代札が刻印される（human ランは strategy_version=NULL）
    assert hist[0]["data_version"]
    assert hist[0]["strategy_version"] is None
    # 操作履歴（run_actions）が全ランで永続化される
    from sqlalchemy import select

    from app.db.models import RunActionsRow
    with TestSession() as db:
        rows = list(db.execute(select(RunActionsRow)).scalars())
    assert len(rows) == 1 and len(rows[0].actions_json) > 0


# ── meta progression ──
def test_meta_levels_feed_new_run(api):
    client, TestSession = api
    with TestSession() as db:
        p = crud.get_or_create_profile(db)
        p.attack = 5
        p.max_hp = 3
        db.commit()
    j = _new(client, seed=1)
    assert j["player"]["attack"] == 15 + 2 * 5      # 25
    assert j["player"]["max_hp"] == 100 + 10 * 3    # 130


def test_profile_upgrades_get(api):
    client, TestSession = api
    # 初期は全Lv0・points0・maxesは config 由来
    r = client.get("/api/profile/upgrades")
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == 0
    assert body["levels"] == {"max_hp": 0, "attack": 0, "init_gold": 0, "gold_drop": 0, "sink_cost": 0}
    assert body["maxes"]["max_hp"] == 5 and body["maxes"]["gold_drop"] == 3
    # ポイント付与→割り振り後に GET が反映する
    with TestSession() as db:
        crud.award_points(db, 2)
    sid = _new(client)["session_id"]
    client.post(f"/api/run/{sid}/upgrade", json={"upgrade_type": "max_hp"})
    body2 = client.get("/api/profile/upgrades").json()
    assert body2["levels"]["max_hp"] == 1 and body2["points"] == 1


def test_upgrade_allocation_and_errors(api):
    client, TestSession = api
    sid = _new(client)["session_id"]
    # ポイント無し → 400
    assert client.post(f"/api/run/{sid}/upgrade", json={"upgrade_type": "attack"}).status_code == 400
    # 3pt 付与して割り振り
    with TestSession() as db:
        crud.award_points(db, 3)
    r = client.post(f"/api/run/{sid}/upgrade", json={"upgrade_type": "attack"})
    assert r.status_code == 200
    body = r.json()
    assert body["levels"]["attack"] == 1
    assert body["points"] == 2
    # 未知項目 → 400
    assert client.post(f"/api/run/{sid}/upgrade", json={"upgrade_type": "nope"}).status_code == 400


def test_upgrade_respects_max_level(api):
    client, TestSession = api
    sid = _new(client)["session_id"]
    with TestSession() as db:
        crud.award_points(db, 20)
    # sink_cost は max_level 3
    for _ in range(3):
        assert client.post(f"/api/run/{sid}/upgrade", json={"upgrade_type": "sink_cost"}).status_code == 200
    assert client.post(f"/api/run/{sid}/upgrade", json={"upgrade_type": "sink_cost"}).status_code == 400


def test_clear_awards_point(api):
    """クリア到達時のポイント付与・履歴記録の API 経路を検証する。
    クリア率そのもの（バランス）は bot ハーネス（§18）の管轄なので、
    ここではエンジンを直接強化して決定的にクリアさせる。"""
    client, TestSession = api
    state = _new(client, seed=1)
    sid = state["session_id"]
    eng = store.get(sid)
    eng.player.attack = 9999                      # 全戦闘を1ターンで終える
    eng.player.max_hp = eng.player.hp = 99999     # 道中の被弾で死なない
    for _ in range(3000):
        if state["phase"] in ("cleared", "dead"):
            break
        if state["phase"] == "gate_preview":
            # ゲート死を排除（出目テーブルはフロア生成物なのでテスト内で無傷固定）
            eng.floor.gate_result_table = {"unhurt": 1.0, "minor": 0.0, "major": 0.0, "special": 0.0}
        state = _drive(client, state, max_steps=1)
    assert state["phase"] == "cleared"
    # クリアで 1pt 付与
    with TestSession() as db:
        assert crud.get_or_create_profile(db).points >= 1
    # 履歴に cleared が残る
    hist = client.get("/api/stats/history").json()
    assert any(h["cleared"] for h in hist)


def test_catalog_mods(api):
    client, _ = api
    r = client.get("/api/catalog/mods")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 6
    assert {m["id"] for m in items} == {"mikiri", "kasoku_dome", "juso", "hansha", "yomi", "kouki"}
    for m in items:
        assert m["effect_1"] and m["effect_stack"]


def test_guard_available_and_usable(api):
    client, _ = api
    sid = _new(client)["session_id"]
    r = client.post(f"/api/run/{sid}/select-node", json={"node_id": "L"})
    assert r.json()["phase"] == "battle"
    types = {a["type"] for a in r.json()["available_actions"]}
    assert "guard" in types and "attack" in types
    assert r.json()["battle"]["guard_uses"] == 0  # 契約: 減衰段を戦闘開始から公開
    assert r.json()["battle"]["guard_next_scale"] == 1.0  # 契約: 戦闘開始時は受けフル効き
    g = client.post(f"/api/run/{sid}/guard")
    assert g.status_code == 200
    assert g.json()["battle"]["guard_uses"] == 1  # 受け1回で加算（BattleOut契約の破れ防止）
    assert g.json()["battle"]["guard_next_scale"] == 0.5  # 契約: 受け1回で次の効きが半減（BattleOut欠落防止）


def test_guard_wrong_phase_409(api):
    client, _ = api
    sid = _new(client)["session_id"]
    assert client.post(f"/api/run/{sid}/guard").status_code == 409
