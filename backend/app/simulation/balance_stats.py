"""バランス検証の統計手法（GDD §18.3）。

2系統を統一提供する:
- **A（自前近似・stdlib＋numpy配列）**: Wilson区間 / ブートストラップCI / Holm補正 / 同等性判定。
- **B（e-value・anytime-valid）**: ベルヌーイ信頼系列 BernoulliCS（WSR hedged betting）、
  帯域判定、対標本 McNemar e-process、e値BH（FDR制御）、同等性CS（TOST）、集中e値、レーシング。

設計原則:
- エンジンはこのモジュールに依存しない（simulation/分析専用。numpy はここでのみ使用）。
- 全関数は決定論的（bootstrap は seed 引数で固定。CS/e-value は入力から一意）。
- 数値は「測るだけ」。バランス JSON は一切書き換えない（Goodhart回避・CLAUDE.md）。

anytime-valid の根拠: hedged capital K_t = ½∏(1+λ_i(x_i-m)) + ½∏(1-λ_i(x_i-m)) は
H0:μ=m の下で平均1の非負マルチンゲール（λ_i は予測可能）。Ville の不等式より
P(sup_t K_t ≥ 1/α) ≤ α。よって {m: sup_t K_t < 1/α} は被覆 ≥ 1-α の信頼系列。
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np


# ───────────────────────── A: 自前近似 ─────────────────────────
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """二項比率の Wilson スコア信頼区間。"""
    if n == 0:
        return (0.0, 0.0)
    phat = k / n
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def bootstrap_ci(data: Sequence[float], alpha: float = 0.05, B: int = 2000,
                 seed: int = 0, stat: Callable[[np.ndarray], float] = np.mean) -> tuple[float, float]:
    """パーセンタイル・ブートストラップ CI（既定は平均）。seed で再現性確保。"""
    a = np.asarray(data, dtype=float)
    if a.size == 0:
        return (0.0, 0.0)
    rng = _rng(seed)
    idx = rng.integers(0, a.size, size=(B, a.size))
    stats = np.array([stat(a[row]) for row in idx])
    return (float(np.quantile(stats, alpha / 2)), float(np.quantile(stats, 1 - alpha / 2)))


def diff_bootstrap_ci(a: Sequence[float], b: Sequence[float], alpha: float = 0.05,
                      B: int = 2000, seed: int = 0) -> tuple[float, float]:
    """mean(a) - mean(b) の差のブートストラップ CI（独立2群）。"""
    aa = np.asarray(a, dtype=float)
    bb = np.asarray(b, dtype=float)
    if aa.size == 0 or bb.size == 0:
        return (0.0, 0.0)
    rng = _rng(seed)
    ia = rng.integers(0, aa.size, size=(B, aa.size))
    ib = rng.integers(0, bb.size, size=(B, bb.size))
    diffs = aa[ia].mean(axis=1) - bb[ib].mean(axis=1)
    return (float(np.quantile(diffs, alpha / 2)), float(np.quantile(diffs, 1 - alpha / 2)))


def holm_adjust(pvals: Sequence[float]) -> list[float]:
    """Holm-Bonferroni 補正後 p 値。"""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj


def equivalence_check(ci: tuple[float, float], delta: float) -> bool:
    """CI が同等域 [-delta, delta] に収まるか（簡易TOST・ブートストラップCI版）。"""
    lo, hi = ci
    return lo >= -delta and hi <= delta


# ───────────────────────── B: e-value / anytime-valid ─────────────────────────
_LAMBDA_CAP = 0.5  # betting fraction 上限。factor=1±λ(x-m)≥1-0.5>0 を保証（x,m∈[0,1]）。


def _predictable_lambdas(xs: np.ndarray, alpha: float) -> np.ndarray:
    """WSR 予測可能プラグイン betting fraction（m 非依存・[0,_LAMBDA_CAP]）。
    λ_t は x_0..x_{t-1} のみに依存（予測可能）→ hedged capital がマルチンゲール。"""
    n = xs.size
    lams = np.empty(n)
    c = math.sqrt(2.0 * math.log(2.0 / alpha))
    mean_prev = 0.5
    m2 = 0.0
    cnt = 0
    for t in range(n):
        var_prev = (0.25 + m2) / (cnt + 1)              # σ̂²_{t-1}（1/4 で初期化）
        denom = var_prev * (t + 1) * math.log(t + 2)
        lam = c / math.sqrt(denom) if denom > 0 else _LAMBDA_CAP
        lams[t] = min(_LAMBDA_CAP, max(0.0, lam))
        # Welford 更新（x_t を取り込む。λ 決定の後＝予測可能性を保つ）
        cnt += 1
        d = xs[t] - mean_prev
        mean_prev += d / cnt
        m2 += d * (xs[t] - mean_prev)
    return lams


def bernoulli_cs(xs: Sequence[float], alpha: float = 0.05, grid: int = 1001) -> tuple[float, float]:
    """[0,1] 有界データの平均に対する two-sided 信頼系列（WSR hedged betting・anytime-valid）。"""
    x = np.asarray(xs, dtype=float)
    if x.size == 0:
        return (0.0, 1.0)
    ms = np.linspace(0.0, 1.0, grid)
    lams = _predictable_lambdas(x, alpha)
    thresh = 1.0 / alpha
    in_cs = np.ones(grid, dtype=bool)
    cap_p = np.ones(grid)
    cap_m = np.ones(grid)
    for t in range(x.size):
        diff = x[t] - ms
        cap_p *= (1.0 + lams[t] * diff)
        cap_m *= (1.0 - lams[t] * diff)
        hedged = 0.5 * cap_p + 0.5 * cap_m
        in_cs &= hedged < thresh                  # 一度でも 1/α を超えた m は棄却（running）
    if not in_cs.any():
        mu = float(x.mean())
        return (mu, mu)
    sel = ms[in_cs]
    return (float(sel.min()), float(sel.max()))


def bernoulli_evalue(xs: Sequence[float], m0: float, alpha: float = 0.05) -> float:
    """H0:μ=m0 に対する e-value（sup_t hedged capital）。e-BH への入力に使う。"""
    x = np.asarray(xs, dtype=float)
    if x.size == 0:
        return 1.0
    lams = _predictable_lambdas(x, alpha)
    cap_p = cap_m = 1.0
    mx = 0.0
    for t in range(x.size):
        d = x[t] - m0
        cap_p *= (1.0 + lams[t] * d)
        cap_m *= (1.0 - lams[t] * d)
        mx = max(mx, 0.5 * cap_p + 0.5 * cap_m)
    return mx


def band_test(xs: Sequence[float], lo: float, hi: float, alpha: float = 0.05, grid: int = 1001) -> str:
    """平均が帯域 [lo,hi] にあるかの anytime-valid 判定。
    'in'(CS⊆帯域) / 'below' / 'above' / 'undetermined'。"""
    clo, chi = bernoulli_cs(xs, alpha=alpha, grid=grid)
    if clo >= lo and chi <= hi:
        return "in"
    if chi < lo:
        return "below"
    if clo > hi:
        return "above"
    return "undetermined"


def tost_cs(diffs: Sequence[float], delta: float, alpha: float = 0.05, grid: int = 1001) -> dict:
    """対標本差 d_i∈[-1,1] の平均が [-delta,delta] に収まるか（同等性・CS版TOST）。"""
    d = np.asarray(diffs, dtype=float)
    if d.size == 0:
        return {"equivalent": False, "ci": (-1.0, 1.0)}
    y = (d + 1.0) / 2.0
    ylo, yhi = bernoulli_cs(y, alpha=alpha, grid=grid)
    dlo, dhi = 2 * ylo - 1, 2 * yhi - 1
    return {"equivalent": dlo >= -delta and dhi <= delta, "ci": (dlo, dhi)}


def mcnemar_eprocess(pairs: Sequence[tuple[int, int]], alpha: float = 0.05, grid: int = 1001) -> dict:
    """対標本（同一seedで条件A/B）の差の検定。discordant ペアの偏りを
    Bernoulli(0.5) からの逸脱として信頼系列で判定（CRN の分散低減を活用）。"""
    disc = [1 if a > b else 0 for a, b in pairs if a != b]
    if not disc:
        return {"reject": False, "direction": 0, "ci": (0.5, 0.5), "n_disc": 0, "evalue": 1.0}
    lo, hi = bernoulli_cs(disc, alpha=alpha, grid=grid)
    direction = 1 if lo > 0.5 else (-1 if hi < 0.5 else 0)
    return {"reject": direction != 0, "direction": direction, "ci": (lo, hi),
            "n_disc": len(disc), "evalue": bernoulli_evalue(disc, 0.5, alpha=alpha)}


def ebh_fdr(evalues: Sequence[float], alpha: float = 0.05) -> list[int]:
    """e値 Benjamini-Hochberg（FDR制御・任意依存に頑健）。棄却仮説の index を返す。"""
    e = np.asarray(evalues, dtype=float)
    m = e.size
    if m == 0:
        return []
    order = np.argsort(-e)
    sorted_e = e[order]
    for k in range(m, 0, -1):
        if sorted_e[k - 1] >= m / (k * alpha):
            return [int(i) for i in order[:k]]
    return []


def concentration_evalue(counts: dict, threshold: float = 0.5, alpha: float = 0.05) -> dict:
    """分布の集中検定（死亡フロア等）。最頻カテゴリのシェアが threshold を超えて
    集中しているかを、最頻=1 の指標列に対する信頼系列の下限で判定。"""
    total = sum(counts.values())
    if total == 0:
        return {"concentrated": False, "max_share": 0.0, "ci": (0.0, 0.0), "mode": None}
    mode = max(counts, key=counts.get)
    indicators = [1] * counts[mode] + [0] * (total - counts[mode])
    lo, hi = bernoulli_cs(indicators, alpha=alpha)
    return {"concentrated": lo > threshold, "max_share": counts[mode] / total,
            "ci": (lo, hi), "mode": mode}


def racing_compare(arms: dict, alpha: float = 0.05) -> dict:
    """各アーム（プロファイル/初手など）の信頼系列を計算し、支配関係（CSが重ならない）と
    最良アームを返す。anytime-valid な区間で「差が確定したか」を見るレーシング相当。"""
    cs = {k: bernoulli_cs(v, alpha=alpha) for k, v in arms.items()}
    best = None
    for k, (lo, _) in cs.items():
        if all(k == j or lo > hi_j for j, (_, hi_j) in cs.items()):
            best = k
            break
    keys = list(cs)
    separated = {}
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            (la, ha), (lb, hb) = cs[a], cs[b]
            separated[f"{a}|{b}"] = (ha < lb) or (hb < la)
    return {"cs": cs, "best": best, "separated": separated}
