"""セッション永続化（OPEN-007・アクションログ再生方式）のテスト。

GameEngine は (seed, upgrades, 操作列) の純粋関数（同一seed→同一結果）なので、
「インメモリキャッシュを飛ばして再生させたラン」と「一度も飛ばさなかったラン」は
同一seed・同一操作列であれば bit-for-bit 同じ結果になるはず、というのが検証の軸。
"""
from sqlalchemy import select

from app.db import crud
from app.db.models import ActiveSessionRow, ObservationRow
from app.engine.replay import rebuild_engine
from app.session_store import store
from tests.test_api import _drive, _new, api  # noqa: F401  (api は fixture として再利用)


def _strip_session_id(state: dict) -> dict:
    return {k: v for k, v in state.items() if k != "session_id"}


# ── active_sessions の記録そのもの ──
def test_active_session_row_created_and_records_actions(api):
    client, TestSession = api
    state = _new(client, seed=1)
    sid = state["session_id"]

    with TestSession() as db:
        row = crud.load_active_session(db, sid)
        assert row is not None
        assert row.seed == 1
        assert row.bot_type == "human"
        assert row.actions_json == []

    r = client.post(f"/api/run/{sid}/select-node", json={"node_id": "L"})
    assert r.status_code == 200
    client.post(f"/api/run/{sid}/attack")

    with TestSession() as db:
        row = crud.load_active_session(db, sid)
        assert [a["type"] for a in row.actions_json] == ["select_node", "attack"]
        assert row.actions_json[0]["node_id"] == "L"


# ── 中断（インメモリキャッシュ喪失）を挟んでも結果が同一 ──
def test_resume_after_cache_loss_matches_uninterrupted_run(api):
    client, _ = api
    actions = [
        ("select-node", {"node_id": "L"}),
        ("attack", None),
        ("attack", None),
        ("attack", None),
    ]

    # A: 毎回 store.clear() でインメモリを飛ばし、都度DBから再生させる
    sid_a = _new(client, seed=1)["session_id"]
    final_a = None
    for path, body in actions:
        store.clear()
        r = client.post(f"/api/run/{sid_a}/{path}", json=body) if body is not None \
            else client.post(f"/api/run/{sid_a}/{path}")
        assert r.status_code == 200
        final_a = r.json()

    # B: 同一seed・同一操作列だが一度も飛ばさない
    sid_b = _new(client, seed=1)["session_id"]
    final_b = None
    for path, body in actions:
        r = client.post(f"/api/run/{sid_b}/{path}", json=body) if body is not None \
            else client.post(f"/api/run/{sid_b}/{path}")
        assert r.status_code == 200
        final_b = r.json()

    assert _strip_session_id(final_a) == _strip_session_id(final_b)


# ── LRU上限超過 → 追い出されたセッションもDBから透過的に復元できる ──
def test_lru_eviction_falls_back_to_db_replay(api):
    client, _ = api
    original_max = store._max_sessions
    store._max_sessions = 1
    try:
        state_a = _new(client, seed=2)
        sid_a = state_a["session_id"]
        client.post(f"/api/run/{sid_a}/select-node", json={"node_id": "L"})
        expected = client.get(f"/api/run/{sid_a}").json()

        # 2件目を作ると上限1のため sid_a はインメモリから追い出される
        _new(client, seed=3)
        assert store.get(sid_a) is None  # 追い出し済みであることの確認

        r = client.get(f"/api/run/{sid_a}")
        assert r.status_code == 200
        assert _strip_session_id(r.json()) == _strip_session_id(expected)
    finally:
        store._max_sessions = original_max


# ── 終局（cleared/dead）直後にキャッシュを飛ばしても GET は404にならない（当初案の訂正の回帰） ──
# 注意: 終局を強制するのに engine を直接書き換える cheat（test_api.py::test_clear_awards_point 方式）は
# ここでは使えない。その cheat はアクションログに記録されない生の状態変更なので、再生（replay）が
# 発生した瞬間にライブ結果と乖離してしまう（決定論が壊れる）。そのため通常プレイと同じ _drive で
# 正規の操作列のみを使い、cleared/dead どちらの終局でもよいものとして検証する。
def test_get_after_terminal_survives_cache_loss(api):
    client, TestSession = api
    state = _new(client, seed=7)
    sid = state["session_id"]
    final_state = _drive(client, state)
    assert final_state["phase"] in ("cleared", "dead")

    with TestSession() as db:
        assert crud.load_active_session(db, sid) is not None  # 終局後も即削除しない

    store.clear()
    r = client.get(f"/api/run/{sid}")
    assert r.status_code == 200
    assert r.json()["phase"] == final_state["phase"]


# ── 再生は調書観測（ObservationRow）に一切書き込まない（二重計上防止） ──
def test_replay_does_not_touch_observations(api):
    client, TestSession = api
    sid = _new(client, seed=1)["session_id"]
    client.post(f"/api/run/{sid}/select-node", json={"node_id": "L"})
    client.post(f"/api/run/{sid}/attack")

    with TestSession() as db:
        row = db.get(ActiveSessionRow, sid)
        count_before = len(db.execute(select(ObservationRow)).scalars().all())
        rebuild_engine(row)  # 純粋な再生。DBに触れないはず
        count_after = len(db.execute(select(ObservationRow)).scalars().all())
    assert count_before == count_after
