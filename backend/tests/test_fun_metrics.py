"""fun_metrics の検証（合成 RunRecord で期待値・空入力安全性）。"""
from app.simulation import fun_metrics as fm


def rec(cleared, final_hp, mods, max_hp_lv=0, stacks=0, enemies=None, total_turns=10):
    return {
        "cleared": cleared, "final_hp": final_hp, "mods_acquired": list(mods),
        "permanent_upgrades_state": {"max_hp": max_hp_lv}, "gate_guarantee_stacks": stacks,
        "enemies_defeated": enemies or [], "total_turns": total_turns,
    }


def test_close_win_rate():
    # max_hp_lv=0 → max_hp=100。final_hp<=15 が僅差勝ち。
    recs = [rec(True, 10, ["a"]), rec(True, 80, ["a"]), rec(False, 0, ["a"])]
    assert fm.close_win_rate(recs) == 0.5      # cleared 2件中 1件が僅差
    assert fm.close_win_rate([]) is None
    assert fm.close_win_rate([rec(False, 0, [])]) is None  # クリアなし


def test_close_win_rate_respects_maxhp_upgrade():
    # max_hp_lv=5 → max_hp=150。閾値15%=22.5。final_hp=20 は僅差、final_hp=40 は非僅差。
    recs = [rec(True, 20, ["a"], max_hp_lv=5), rec(True, 40, ["a"], max_hp_lv=5)]
    assert fm.close_win_rate(recs) == 0.5


def test_clear_turn_stats():
    recs = [rec(True, 50, ["a"], total_turns=10), rec(True, 50, ["a"], total_turns=20),
            rec(False, 0, ["a"], total_turns=5)]
    s = fm.clear_turn_stats(recs)
    assert s["n"] == 2 and s["mean"] == 15.0 and s["stdev"] == 5.0


def test_mod_diversity_entropy():
    # a,b が均等 → 1 bit、normalized 1.0
    recs = [rec(True, 50, ["a"]), rec(True, 50, ["b"])]
    d = fm.mod_diversity_entropy(recs)
    assert abs(d["entropy_bits"] - 1.0) < 1e-9
    assert abs(d["normalized"] - 1.0) < 1e-9
    assert fm.mod_diversity_entropy([])["entropy_bits"] is None


def test_mod_marginal_clear_rates():
    recs = [rec(True, 50, ["a"]), rec(False, 0, ["b"]), rec(True, 50, ["a"]), rec(False, 0, ["b"])]
    r = fm.mod_marginal_clear_rates(recs)
    assert r["per_mod"]["a"] == 1.0 and r["per_mod"]["b"] == 0.0
    assert r["spread"] == 1.0


def test_gate_guarantee_dependence():
    recs = [rec(True, 50, ["a"], stacks=2), rec(True, 50, ["a"], stacks=0)]
    g = fm.gate_guarantee_dependence(recs)
    assert g["mean_stacks"] == 1.0 and g["used_rate"] == 0.5


def test_race_avg_turns():
    recs = [rec(True, 50, ["a"], enemies=[
        {"experience": "race", "turns": 6}, {"experience": "grind", "turns": 3}])]
    r = fm.race_avg_turns(recs)
    assert r["avg_turns"] == 6.0 and r["n"] == 1
    assert fm.race_avg_turns([])["avg_turns"] is None


def test_compute_returns_all_keys():
    recs = [rec(True, 10, ["a", "b"], stacks=1, enemies=[{"experience": "race", "turns": 5}])]
    out = fm.compute(recs)
    for k in ("close_win_rate", "clear_turns", "mod_diversity",
              "mod_marginal_clear_rates", "gate_guarantee_dependence", "race_avg_turns"):
        assert k in out
