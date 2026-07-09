"""balance_analysis の検証（合成 RunRecord）＋ bots.forced_first_node の挙動不変性。"""
from app.engine.game_engine import GameEngine
from app.simulation import balance_analysis as ba
from app.simulation import bots


def rec(cleared, mods=(), gold_spent=None, death_floor=None, gold_earned=0, init_lv=0):
    return {
        "cleared": cleared, "mods_acquired": list(mods),
        "gold_spent": gold_spent or {}, "death_floor": death_floor,
        "gold_earned": gold_earned, "permanent_upgrades_state": {"init_gold": init_lv},
        "final_hp": 50, "total_turns": 10, "enemies_defeated": [],
    }


def test_mod_marginal_contribution_detects_strong_mod():
    recs = [rec(True, ["a"]) for _ in range(20)] + [rec(False, ["b"]) for _ in range(20)]
    out = ba.mod_marginal_contribution(recs, delta=0.08, seed=1)
    assert out["a"]["contribution"] > 0.5
    assert out["a"]["significant"] is True
    assert out["a"]["within_pm_delta"] is False
    assert out["a"]["broken_or_dead"] is True


def test_first_move_sensitivity():
    cohort = {
        "X": [rec(True) for _ in range(30)],
        "Y": [rec(False) for _ in range(30)],
    }
    res = ba.first_move_sensitivity(cohort, delta=0.05)
    assert res["spread"] == 1.0
    assert res["within_5pt"] is False
    assert res["sensitive"] is True


def test_first_move_no_difference():
    cohort = {"X": [rec(True) for _ in range(30)], "Y": [rec(True) for _ in range(30)]}
    res = ba.first_move_sensitivity(cohort, delta=0.05)
    assert res["spread"] == 0.0 and res["within_5pt"] is True
    assert res["sensitive"] is False


def test_death_floor_concentration():
    recs = ([rec(False, death_floor=2) for _ in range(18)] +
            [rec(False, death_floor=3) for _ in range(1)] +
            [rec(False, death_floor=4) for _ in range(1)])
    res = ba.death_floor_concentration(recs, threshold=0.5)
    assert res["mode"] == 2 and res["concentrated"] is True
    spread = ([rec(False, death_floor=f) for f in (2, 3, 4, 5) for _ in range(15)])
    assert ba.death_floor_concentration(spread, threshold=0.5)["concentrated"] is False


def test_hoarder_detection():
    # 稼いだのに使わず死ぬ＝貯め込み
    recs = [rec(False, gold_earned=200, gold_spent={"scout": 10}) for _ in range(10)]
    h = ba.hoarder_detection(recs, hoard_frac=0.5)
    assert h["hoarder_rate"] == 1.0
    assert h["hoarder_rate_died"] == 1.0


def test_sink_roi_observational():
    recs = ([rec(True, gold_spent={"scout": 15}) for _ in range(20)] +
            [rec(False, gold_spent={}) for _ in range(20)])
    out = ba.sink_roi_observational(recs, seed=2)
    assert out["scout"]["roi_diff"] > 0.5
    assert out["scout"]["ci"][0] > 0


def test_forced_first_node_unchanged_when_none(data):
    """forced_first_node=None は従来挙動と完全一致（決定性）。"""
    a = bots.play_strong(GameEngine(data), seed=5)
    b = bots.play_strong(GameEngine(data), seed=5, forced_first_node=None)
    # run_id はラン識別用の一意IDであり、seedの決定論の対象外
    a, b = dict(a), dict(b)
    a.pop("run_id"), b.pop("run_id")
    assert a == b


def test_forced_first_node_runs(data):
    """初手を強制しても正常に終端まで進む。"""
    rr = bots.play_strong(GameEngine(data), seed=5, forced_first_node="L")
    assert rr["bot_type"] == "strong"
    assert rr["floor_reached"] >= 1
