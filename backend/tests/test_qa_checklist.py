"""QAチェックリスト（docs/operations.md §18.8）の自動化テスト。

§18.8 の Smoke/Regression のうち既存テストが担保していなかった項目を
API 経由の決定的テストで固定する（既存カバー分との対応表は §18.8 側に記載）。
test_api.py::test_clear_awards_point と同じく、到達性の確保はエンジンの直接
強化で行う（クリア率・数値バランスは §18 bot ハーネスの管轄）。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
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


def _buff(sid):
    """全戦闘を1ターンで終え道中被弾で死なない状態にする（到達性の確保専用）。"""
    eng = store.get(sid)
    eng.player.attack = 9999
    eng.player.max_hp = eng.player.hp = 99999
    eng.player.gold = 9999
    return eng


def _step(client, sid, state, *, safe_gate=False):
    """現 phase を1手だけ進める。safe_gate=True はゲート死を排除（無傷固定）。"""
    ph = state["phase"]
    if ph == "battle":
        return client.post(f"/api/run/{sid}/attack").json()
    if ph == "exploring":
        nodes = state["floor"]["nodes"]
        avail = [nid for nid, n in nodes.items() if n["state"] == "available"]
        # 宝箱・回復を優先して踏む（QA対象 phase へ早く到達するため）
        pref = [n for n in avail if nodes[n]["kind"] in ("treasure", "heal", "gate_route", "gate")]
        pick = pref[0] if pref else avail[0]
        return client.post(f"/api/run/{sid}/select-node", json={"node_id": pick}).json()
    if ph == "treasure_preview":
        return client.post(f"/api/run/{sid}/treasure/open").json()
    if ph in ("treasure_opened", "heal", "next_floor"):
        return client.post(f"/api/run/{sid}/continue").json()
    if ph == "gate_preview":
        if safe_gate:
            store.get(sid).floor.gate_result_table = {"unhurt": 1.0, "minor": 0.0, "major": 0.0, "special": 0.0}
        return client.post(f"/api/run/{sid}/gate/resolve").json()
    return state


def _drive_until(client, sid, state, cond, *, safe_gate=True, max_steps=3000):
    """cond(state) が真になるまで進める。到達できなければテスト失敗。"""
    for _ in range(max_steps):
        if cond(state):
            return state
        if state["phase"] in ("cleared", "dead"):
            break
        state = _step(client, sid, state, safe_gate=safe_gate)
    assert cond(state), f"目標状態に到達できない: phase={state['phase']}"
    return state


# ── Smoke 3: 戦闘死亡 → dead・run_record(cleared:false) ──
def test_battle_death_dead_phase_and_uncleared_record(api):
    client, _ = api
    state = _new(client, seed=1)
    sid = state["session_id"]
    eng = store.get(sid)
    eng.player.attack = 0                     # 敵を倒せない
    eng.player.max_hp = eng.player.hp = 1     # 最初の被弾で死ぬ
    state = client.post(f"/api/run/{sid}/select-node", json={"node_id": "L"}).json()
    assert state["phase"] == "battle"
    for _ in range(200):
        if state["phase"] == "dead":
            break
        state = client.post(f"/api/run/{sid}/attack").json()
    assert state["phase"] == "dead"
    assert state["run_record"] is not None and state["run_record"]["cleared"] is False
    # §18.8 Regression 8: dead 中の attack は 409
    assert client.post(f"/api/run/{sid}/attack").status_code == 409
    # §18.8 Smoke 9 前半: 戦闘死では検死レポートが返る
    assert client.get(f"/api/run/{sid}/postmortem").status_code == 200


# ── Smoke 9 後半: ゲート死では検死レポートが無い（404） ──
def test_gate_death_has_no_postmortem_404(api):
    client, _ = api
    state = _new(client, seed=1)
    sid = state["session_id"]
    eng = _buff(sid)
    state = _drive_until(client, sid, state, lambda s: s["phase"] == "gate_preview", safe_gate=False)
    eng.floor.gate_result_table = {"unhurt": 0.0, "minor": 0.0, "major": 1.0, "special": 0.0}
    eng.player.hp = 1                         # 大ダメで確実に死ぬ
    state = client.post(f"/api/run/{sid}/gate/resolve").json()
    assert state["phase"] == "dead"
    assert client.get(f"/api/run/{sid}/postmortem").status_code == 404


# ── Smoke 4 後半: 宝箱リロールはチップを消費し phase 不変 ──
def test_reroll_costs_chips_and_keeps_phase(api):
    client, _ = api
    state = _new(client, seed=1)
    sid = state["session_id"]
    _buff(sid)
    # 1F 確定宝箱（fixed_mod）はリロール不可のため、reroll が提示される宝箱まで進める
    def reroll_offered(s):
        return s["phase"] == "treasure_preview" and any(
            "reroll" in a["type"] for a in s["available_actions"]
        )
    state = _drive_until(client, sid, state, reroll_offered)
    chips_before = state["player"]["chips"]
    r = client.post(f"/api/run/{sid}/treasure/reroll")
    assert r.status_code == 200
    after = r.json()
    assert after["phase"] == "treasure_preview"          # phase 不変
    assert after["player"]["chips"] < chips_before        # コスト消費（額は config 正本）


# ── Regression 8: §25.4 phase 不整合マトリクスの残りセル ──
def test_select_node_in_battle_409(api):
    client, _ = api
    sid = _new(client, seed=1)["session_id"]
    state = client.post(f"/api/run/{sid}/select-node", json={"node_id": "L"}).json()
    assert state["phase"] == "battle"
    assert client.post(f"/api/run/{sid}/select-node", json={"node_id": "M"}).status_code == 409


def test_reroll_in_treasure_opened_409(api):
    client, _ = api
    state = _new(client, seed=1)
    sid = state["session_id"]
    _buff(sid)
    state = _drive_until(client, sid, state, lambda s: s["phase"] == "treasure_preview")
    state = client.post(f"/api/run/{sid}/treasure/open").json()
    assert state["phase"] == "treasure_opened"
    assert client.post(f"/api/run/{sid}/treasure/reroll").status_code == 409


def test_attack_after_cleared_409(api):
    client, _ = api
    state = _new(client, seed=1)
    sid = state["session_id"]
    _buff(sid)
    state = _drive_until(client, sid, state, lambda s: s["phase"] == "cleared")
    assert client.post(f"/api/run/{sid}/attack").status_code == 409


# ── Regression 9: 満タン回復 sink は 400・回復ノードは満タンでも自動解決 ──
def test_full_hp_heal_sink_400_but_heal_node_auto_resolves(api):
    client, _ = api
    state = _new(client, seed=1)
    sid = state["session_id"]
    # 初期状態は HP 満タン。exploring での回復 sink は 400（InvalidMove）
    assert state["player"]["hp"] == state["player"]["max_hp"]
    assert client.post(f"/api/run/{sid}/sink", json={"sink_type": "heal_small"}).status_code == 400
    # 回復ノードは満タンでも拒否せず自動解決される（§7.3）
    _buff(sid)  # 満タンのまま回復ノードへ到達させる
    state = client.get(f"/api/run/{sid}").json()
    state = _drive_until(
        client, sid, state,
        lambda s: s["phase"] == "exploring" and any(
            n["state"] == "available" and n["kind"] == "heal" for n in s["floor"]["nodes"].values()
        ),
    )
    heal_id = next(
        nid for nid, n in state["floor"]["nodes"].items()
        if n["state"] == "available" and n["kind"] == "heal"
    )
    r = client.post(f"/api/run/{sid}/select-node", json={"node_id": heal_id})
    assert r.status_code == 200
    assert r.json()["phase"] == "heal"


# ── Regression 10: チップ不足の sink は 400（409 ではない） ──
def test_insufficient_chips_sink_400(api):
    client, _ = api
    state = _new(client, seed=1)
    sid = state["session_id"]
    eng = store.get(sid)
    eng.player.hp = 10                        # 回復自体は正当（満タン拒否と区別）
    eng.player.gold = 0
    r = client.post(f"/api/run/{sid}/sink", json={"sink_type": "heal_large"})
    assert r.status_code == 400
