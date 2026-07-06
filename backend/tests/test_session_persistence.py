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


def _get_live_then_replayed(client, sid: str) -> tuple[dict, dict]:
    """現在のGETを記録した後 store.clear() で復元を強制し、再度GETした結果を返す。

    (live, replayed) の等価性が「決定論的リプレイ」不変条件そのもの（観点1/6）。
    """
    live = client.get(f"/api/run/{sid}").json()
    store.clear()
    replayed = client.get(f"/api/run/{sid}").json()
    return live, replayed


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


# ── エンジン成功後の record_action 無記録（乖離）を塞ぐ: 行が消えたセッションは 404（観点1） ──
# active_sessions 行が TTL 掃除（crud.delete_stale_active_sessions）等で消えた後も、エンジンが
# インメモリに残っていると従来はリクエストが成功し続け、record_action は黙って None を返す
# （＝エンジンだけ進んでログは進まない）。永続の正本は ActiveSessionRow なので、行が無い
# セッションは「もう存在しない」として、エンジンを進める前に 404 で拒否するべき。
def test_request_after_row_deleted_is_404_and_engine_not_advanced(api):
    client, TestSession = api
    sid = _new(client, seed=1)["session_id"]
    client.post(f"/api/run/{sid}/select-node", json={"node_id": "L"})
    eng = store.get(sid)
    assert eng is not None and eng.phase == "battle"
    turns_before = eng.run.total_turns

    with TestSession() as db:  # TTL掃除相当（行だけ消える・エンジンはキャッシュに残る）
        db.delete(db.get(ActiveSessionRow, sid))
        db.commit()

    r = client.post(f"/api/run/{sid}/attack")
    assert r.status_code == 404               # 黙って成功（＝無記録の乖離）させない
    assert eng.run.total_turns == turns_before  # エンジンも進んでいない
    assert store.get(sid) is None               # ゾンビエンジンはキャッシュからも破棄される


# ── 拒否されたサイドベットで live と replay が乖離しない（観点1/6） ──
# 従来の engine は「戦闘ターンを解決した後に」side_bet を検証して InvalidMove を投げていた。
# その場合 API は 400 を返し record_action は呼ばれないが、live エンジンは1ターン進んでしまって
# いる（RNG消費・total_turns・敵HP）。ログに無いターンは再生されないため、キャッシュ喪失後の
# 復元結果が live と食い違う＝純粋関数不変条件の破れ。拒否されるリクエストは状態を一切
# 進めてはならない（検証はターン解決の前）。
def test_rejected_side_bet_does_not_diverge_live_from_replay(api):
    client, _ = api
    sid = _new(client, seed=1)["session_id"]
    client.post(f"/api/run/{sid}/select-node", json={"node_id": "L"})

    # max_amount(20) 超の額は常に InvalidMove → 400
    r = client.post(f"/api/run/{sid}/attack",
                    json={"side_bet": {"behavior": "counter", "amount": 999}})
    assert r.status_code == 400

    live, replayed = _get_live_then_replayed(client, sid)
    assert replayed == live  # 400 のリクエストは live 側も一切進んでいないこと


# ── 有効なサイドベットは記録され、再生でも bit-for-bit 同一（観点6） ──
def test_valid_side_bet_replays_identically(api):
    client, _ = api
    sid = _new(client, seed=1)["session_id"]
    state = client.post(f"/api/run/{sid}/select-node", json={"node_id": "L"}).json()
    # 最初の敵を倒してチップを稼ぐ（seed固定なので決定論的）
    for _ in range(50):
        if state["phase"] != "battle":
            break
        state = client.post(f"/api/run/{sid}/attack").json()
    while state["phase"] in ("treasure_preview", "treasure_opened", "heal"):
        path = "treasure/open" if state["phase"] == "treasure_preview" else "continue"
        state = client.post(f"/api/run/{sid}/{path}").json()
    assert state["phase"] == "exploring", "テスト前提: 最初の戦闘を生き延びる seed であること"
    assert state["player"]["chips"] >= 5, "テスト前提: min_amount 以上のチップを稼げていること"

    nodes = state["floor"]["nodes"]
    enemy = next(nid for nid, n in nodes.items()
                 if n["state"] == "available" and n["kind"] == "enemy")
    state = client.post(f"/api/run/{sid}/select-node", json={"node_id": enemy}).json()
    assert state["phase"] == "battle"
    r = client.post(f"/api/run/{sid}/attack",
                    json={"side_bet": {"behavior": "none", "amount": 5}})
    assert r.status_code == 200

    live, replayed = _get_live_then_replayed(client, sid)
    assert replayed == live


# ── 復元後の調書観測の二重計上防止（観点4/5） ──
# 再生中も engine は _pending_observations に観測を積む。ライブ時に既に調書へ反映済みの分を
# 復元後の最初の戦闘ターンでまとめて drain してしまうと二重計上になるため、rebuild_engine は
# 再生で積まれた観測を破棄しなければならない。
def test_restored_engine_does_not_double_count_observations(api):
    client, TestSession = api
    sid = _new(client, seed=1)["session_id"]
    client.post(f"/api/run/{sid}/select-node", json={"node_id": "L"})
    r = client.post(f"/api/run/{sid}/attack")  # ライブ1ターン → 観測1件は調書反映済み
    assert r.json()["phase"] == "battle", "テスト前提: 1ターンで決着しないこと"

    def _total(db):
        return sum(row.count for row in db.execute(select(ObservationRow)).scalars())

    with TestSession() as db:
        total_before = _total(db)
    assert total_before == 1

    store.clear()
    assert client.get(f"/api/run/{sid}").status_code == 200  # 再生（攻撃1ターン分を再適用）

    r = client.post(f"/api/run/{sid}/attack")  # 復元後の新規1ターン
    assert r.status_code == 200
    with TestSession() as db:
        # 新規1件だけ増える。再生分（1件）が残っていると +2 になる
        assert _total(db) == total_before + 1


# ── 再生失敗（壊れた/未知のアクションログ）は明示エラー＋ログ（観点3） ──
def test_corrupt_action_log_returns_explicit_500(api):
    client, TestSession = api
    with TestSession() as db:
        db.add(ActiveSessionRow(session_id="corrupt-sid", seed=1, bot_type="human",
                                upgrades_json={}, actions_json=[{"type": "no_such_action"}]))
        db.commit()

    r = client.get("/api/run/corrupt-sid")
    assert r.status_code == 500
    assert "restore" in r.json()["detail"]  # 生の例外ではなく明示メッセージであること


# ── 終局→finalize直前クラッシュ窓: 復元時に RunRecord を取りこぼさない（OPEN-007 観点2）──
# 状況の再現: ライブで終局アクションは actions_json に記録されたが、直後の finalize（RunRecord確定）が
# 走らないままプロセスが落ちた。これを store.mark_finalized で「finalize を丸ごとスキップさせた」状態で
# 忠実に再現する（＝アクションは全記録・RunRecord は未保存）。再起動（store.clear）後の初回アクセスで
# RunRecord が永続化されなければ、そのランの統計は永久に失われる。
def test_terminal_before_finalize_crash_is_recovered_on_resume(api):
    client, TestSession = api
    state = _new(client, seed=7)
    sid = state["session_id"]

    store.mark_finalized(sid)  # 以降の _finalize_if_ended を全スキップ＝finalize未達をエミュレート
    final_state = _drive(client, state)
    assert final_state["phase"] in ("cleared", "dead")

    # クラッシュ窓の前提: アクションは記録済みだが RunRecord は未保存
    with TestSession() as db:
        assert crud.load_active_session(db, sid) is not None
        assert not any(r.run_id == "run-7" for r in crud.list_run_records(db))

    store.clear()  # 再起動相当（インメモリと _finalized を破棄）
    r = client.get(f"/api/run/{sid}")
    assert r.status_code == 200
    assert r.json()["phase"] == final_state["phase"]

    # 復元経路が finalize 相当を実行し、RunRecord が確定していること
    with TestSession() as db:
        assert any(r.run_id == "run-7" for r in crud.list_run_records(db))


# ── 復元時 finalize が二重確定しない（既に確定済みのランを再開しても RunRecord/ポイントを増やさない）──
def test_resume_of_finalized_run_does_not_double_finalize(api):
    client, TestSession = api
    state = _new(client, seed=7)
    sid = state["session_id"]
    final_state = _drive(client, state)  # ライブで正規に finalize 済み
    assert final_state["phase"] in ("cleared", "dead")

    with TestSession() as db:
        recs_before = [r for r in crud.list_run_records(db) if r.run_id == "run-7"]
        pts_before = crud.get_or_create_profile(db).points
    assert len(recs_before) == 1  # ライブで1回だけ確定済み

    store.clear()  # 再起動相当
    assert client.get(f"/api/run/{sid}").status_code == 200

    with TestSession() as db:
        recs_after = [r for r in crud.list_run_records(db) if r.run_id == "run-7"]
        pts_after = crud.get_or_create_profile(db).points
    assert len(recs_after) == 1          # 二重に RunRecord を作らない
    assert pts_after == pts_before        # ポイント二重付与もしない
