"""balance_stats の検証。e-value/CS は被覆率(type-I制御)と決定性を黄金テストで担保。"""
import numpy as np
import pytest

from app.simulation import balance_stats as bs


# ───────────── A: 自前近似 ─────────────
def test_wilson_basic():
    lo, hi = bs.wilson(50, 100)
    assert lo < 0.5 < hi
    assert bs.wilson(0, 0) == (0.0, 0.0)


def test_bootstrap_ci_deterministic_and_brackets_mean():
    data = [0, 1] * 50  # 平均0.5
    ci1 = bs.bootstrap_ci(data, seed=42, B=500)
    ci2 = bs.bootstrap_ci(data, seed=42, B=500)
    assert ci1 == ci2                       # 同seed→同結果
    assert ci1[0] < 0.5 < ci1[1]


def test_diff_bootstrap_ci_detects_difference():
    a = [1] * 80 + [0] * 20   # 0.8
    b = [1] * 20 + [0] * 80   # 0.2
    lo, hi = bs.diff_bootstrap_ci(a, b, seed=1, B=500)
    assert lo > 0             # 差(0.6)のCIが0を含まない


def test_holm_adjust_monotone():
    adj = bs.holm_adjust([0.01, 0.04, 0.03])
    assert all(0.0 <= p <= 1.0 for p in adj)
    assert adj[0] >= 0.01 * 3 - 1e-9        # 最小pは×m


def test_equivalence_check():
    assert bs.equivalence_check((-0.03, 0.03), 0.05) is True
    assert bs.equivalence_check((-0.03, 0.08), 0.05) is False


# ───────────── B: e-value / CS ─────────────
@pytest.mark.parametrize("p", [0.2, 0.5, 0.8])
def test_bernoulli_cs_coverage(p):
    """anytime-valid CS は真の平均 p を被覆率 ≥ 1-α で含む（保守的なので実際は高い）。"""
    alpha = 0.1
    rng = np.random.default_rng(7)
    M, n = 120, 200
    covered = 0
    for _ in range(M):
        xs = (rng.random(n) < p).astype(float)
        lo, hi = bs.bernoulli_cs(xs, alpha=alpha, grid=201)
        if lo <= p <= hi:
            covered += 1
    assert covered / M >= 1 - alpha          # 被覆率が名目を下回らない


def test_bernoulli_cs_deterministic():
    xs = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]
    assert bs.bernoulli_cs(xs, grid=201) == bs.bernoulli_cs(xs, grid=201)


def test_band_test_classifies():
    rng = np.random.default_rng(3)
    low = (rng.random(400) < 0.05).astype(float)    # 平均~0.05
    high = (rng.random(400) < 0.6).astype(float)    # 平均~0.6
    mid = (rng.random(400) < 0.32).astype(float)    # 帯域内~0.32
    assert bs.band_test(low, 0.25, 0.40) == "below"
    assert bs.band_test(high, 0.25, 0.40) == "above"
    # mid は帯域 [0.25,0.40] 周辺。in か undetermined（CS が帯域に収まるとは限らない）
    assert bs.band_test(mid, 0.25, 0.40) in ("in", "undetermined")


def test_tost_cs_equivalence():
    eq = bs.tost_cs([0] * 400, delta=0.05)           # 差ゼロ→同等
    assert eq["equivalent"] is True
    neq = bs.tost_cs([1] * 200 + [0] * 200, delta=0.05)  # 平均差0.5→非同等
    assert neq["equivalent"] is False


def test_mcnemar_eprocess_direction():
    pairs = [(1, 0)] * 60 + [(0, 0)] * 40            # discordant は全て A>B
    res = bs.mcnemar_eprocess(pairs)
    assert res["reject"] is True and res["direction"] == 1
    none = bs.mcnemar_eprocess([(1, 1), (0, 0)] * 20)  # discordant なし
    assert none["reject"] is False and none["n_disc"] == 0


def test_ebh_fdr_selects_strong_evalues():
    # 大きな e値が棄却される。e=100 が4つ、e=1 が6つ
    ev = [100.0] * 4 + [1.0] * 6
    rej = set(bs.ebh_fdr(ev, alpha=0.05))
    assert {0, 1, 2, 3} <= rej
    assert bs.ebh_fdr([1.0] * 10, alpha=0.05) == []   # 弱いe値は棄却なし


def test_concentration_evalue():
    conc = bs.concentration_evalue({2: 180, 3: 10, 4: 10}, threshold=0.5)
    assert conc["concentrated"] is True and conc["mode"] == 2
    spread = bs.concentration_evalue({2: 50, 3: 50, 4: 50, 5: 50}, threshold=0.5)
    assert spread["concentrated"] is False


def test_racing_compare_finds_best():
    arms = {
        "maxed": [1] * 70 + [0] * 30,    # 0.7
        "mid": [1] * 30 + [0] * 70,      # 0.3
        "base": [1] * 5 + [0] * 95,      # 0.05
    }
    res = bs.racing_compare(arms)
    assert res["best"] == "maxed"
    assert res["separated"]["maxed|base"] is True
