"""mod寄与の ablation 検証（GDD §18.2 Phase3・OPEN-023）。

宝箱抽選プール（game_engine.MOD_POOL）から特定modを除外した世界と通常世界を
CRN（共通乱数・同一seed群）で比較し、単体寄与とペア交互作用を測る。
- 測るだけ。data/*.json・エンジンは不変（プール差し替えは実行中のみ・finallyで復元）。
- 判定は §18.4 の非対称運用（死にmodは潰す・壊れmodは残す）に従い人間に返す＝厳格failなし。
- hansha は 1F 確定配置（floors.json content 経由・MOD_POOL 非経由）が全コホートに残るため、
  測れるのは「確定1枚を超える追加取得の寄与」（semantics フラグで明示）。

CRN の要点: full / 各 ablated コホートを同じ seed 群 0..n-1 で回すので、seed ごとの
対標本差 d_i = clear(full)_i − clear(ablated)_i を取れる（分散低減）。単体は McNemar
e-process、ペア交互作用は [-2,2] 指標を [0,1] へ写像した Bernoulli 信頼系列で判定する。

実行: python -m app.simulation.mod_ablation --n 1000 --profile mid --out baselines/mod_ablation_result.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import app.engine.game_engine as ge
from app.data.loader import GameData
from app.engine.game_engine import GameEngine
from app.simulation import balance_stats as bs
from app.simulation import bots
from app.simulation.phase12_harness import PROFILES

FIXED_MODS: frozenset[str] = frozenset({"hansha"})  # 1F確定配置（floors.json content 由来）
DEFAULT_DELTA_SINGLE = 0.08   # §18.1 単体寄与 ±8pt
DEFAULT_W_PAIR = 0.10         # §18.1 ペア交互作用 ±W=10pt（v1.11 事前登録）
DEFAULT_DEAD_HI = 0.01        # dead: CI上限 < +1pt
DEFAULT_BROKEN_LO = 0.08      # broken: CI下限 > +8pt


# ─────────────────────── pool ablation（実行中のみ差し替え） ───────────────────────
@contextmanager
def _ablated_pool(excluded: frozenset[str]) -> Iterator[None]:
    """game_engine.MOD_POOL から excluded を除いたプールを yield 中だけ有効化する。

    treasure_open は bare 名 `MOD_POOL` を参照するため、モジュールグローバルの再代入で
    差し替わる（`from ... import MOD_POOL` はリポジトリに存在しない）。finally で必ず復元。
    """
    orig = ge.MOD_POOL
    missing = excluded - set(orig)
    if missing:
        raise ValueError(f"unknown mods for ablation: {sorted(missing)}")
    ablated = [m for m in orig if m not in excluded]
    if not ablated:
        raise ValueError("ablated pool is empty")
    ge.MOD_POOL = ablated
    try:
        yield
    finally:
        ge.MOD_POOL = orig


def _resolve_profile(name: str) -> dict[str, int]:
    """"base"/"mid"/"maxed" を PROFILES のキー先頭一致で解決する。"""
    for key, up in PROFILES.items():
        if key.startswith(name):
            return dict(up)
    raise ValueError(f"unknown profile: {name!r} (expected base/mid/maxed)")


# ─────────────────────── cohort（RunRecord は保持しない・指標のみ） ───────────────────────
def _run_cohort_indicators(eng: GameEngine, n: int, upgrades: dict[str, int]) -> dict:
    """seed 0..n-1 の strong bot を回し、seed昇順のクリア指標列＋要約を返す。

    records を貯めず clears（0/1 列）だけ保持する（22 コホート×n を軽く保つため）。
    """
    clears: list[int] = []
    cleared = 0
    floor_sum = 0
    death_floor: Counter[int] = Counter()
    for seed in range(n):
        rr = bots.play_strong(eng, seed=seed, upgrades=upgrades)
        c = 1 if rr["cleared"] else 0
        clears.append(c)
        cleared += c
        floor_sum += rr["floor_reached"]
        if not rr["cleared"] and rr["death_floor"] is not None:
            death_floor[rr["death_floor"]] += 1
    return {
        "clears": clears,
        "cleared": cleared,
        "rate": cleared / n if n else 0.0,
        "avg_floor": floor_sum / n if n else 0.0,
        "death_floor": dict(sorted(death_floor.items())),
    }


# ─────────────────────── 単体寄与（CRN 対標本） ───────────────────────
def _single_stats(f: Sequence[int], wo: Sequence[int], delta: float, alpha: float) -> dict:
    """full（f）と ablated（wo）の対標本差から単体寄与・同等性・McNemar e値を出す。

    d_i = f_i − wo_i ∈ {-1,0,1}。contribution = E[d] = clear%(full) − clear%(ablated)。
    """
    d = [fi - wi for fi, wi in zip(f, wo)]
    contribution = sum(d) / len(d) if d else 0.0
    t = bs.tost_cs(d, delta, alpha=alpha)           # back-transform 済み CI＋同等性 bool
    mc = bs.mcnemar_eprocess(list(zip(f, wo)), alpha=alpha)
    return {
        "contribution": contribution,
        "ci": t["ci"],
        "within_pm_delta": t["equivalent"],
        "mcnemar": mc,
        "evalue": mc["evalue"],                     # H0:寄与0 の anytime-valid e値（e-BH 入力）
    }


# ─────────────────────── ペア交互作用 ───────────────────────
def _interaction_stats(f: Sequence[int], x: Sequence[int], y: Sequence[int],
                       xy: Sequence[int], w: float, alpha: float, boot_seed: int) -> dict:
    """純交互作用 I を CRN 指標列から測る。

    g_i = x_i + y_i − f_i − xy_i ∈ [-2,2]。E[g] を展開すると
      E[g] = (E[f]−E[xy]) − (E[f]−E[x]) − (E[f]−E[y]) = Δ_XY − Δ_X − Δ_Y = I
    （Δ_X = E[f]−E[woX] は X の単体寄与）。よって interaction = mean(g) が I の不偏推定。
    符号解釈: I<0 = 相補（両方揃って初めて効く synergy）／I>0 = 冗長・逓減（substitute）。
    """
    g = [xi + yi - fi - xyi for fi, xi, yi, xyi in zip(f, x, y, xy)]
    interaction = sum(g) / len(g) if g else 0.0
    gp = [(v + 2.0) / 4.0 for v in g]               # [-2,2] -> [0,1] へ写像（有界CS入力）
    clo, chi = bs.bernoulli_cs(gp, alpha)
    ci = (4.0 * clo - 2.0, 4.0 * chi - 2.0)         # [0,1] CI を [-2,2] へ戻す
    evalue = bs.bernoulli_evalue(gp, 0.5, alpha=alpha)  # H0:E[g]=0 <=> E[gp]=0.5
    ci_boot = bs.bootstrap_ci(g, alpha=alpha, seed=boot_seed)  # 副次クロスチェック
    within_w = bs.equivalence_check(ci, w)
    sign = "synergy" if ci[1] < 0 else ("substitute" if ci[0] > 0 else "none")
    return {
        "interaction": interaction,
        "ci": ci,
        "evalue": evalue,
        "ci_bootstrap": ci_boot,
        "within_w": within_w,
        "sign": sign,
    }


def _classify_single(ci: tuple[float, float], dead_hi: float, broken_lo: float) -> str:
    """単体寄与 CI から §18.4 の分類札を出す（判定は人間・厳格failにはしない）。"""
    lo, hi = ci
    if hi < 0.0:
        return "trap"
    if hi < dead_hi:
        return "dead"
    if lo > broken_lo:
        return "broken"
    if lo > 0.0:
        return "healthy"
    return "inconclusive"


# ─────────────────────── レポート組み立て ───────────────────────
def build_report(n: int = 1000, profile: str = "mid", alpha: float = 0.05,
                 delta_single: float = DEFAULT_DELTA_SINGLE, w_pair: float = DEFAULT_W_PAIR,
                 dead_hi: float = DEFAULT_DEAD_HI, broken_lo: float = DEFAULT_BROKEN_LO,
                 boot_seed: int = 0) -> dict:
    """full / 単体×6 / ペア×15 を CRN で回し、寄与・交互作用・e-BH を JSON dict で返す。"""
    data = GameData.load()                          # get_data キャッシュ非依存（フレッシュ正本）
    upgrades = _resolve_profile(profile)
    eng = GameEngine(data)
    pool = list(ge.MOD_POOL)                        # 差し替え前スナップショット（全ループの基準）

    # full（全mod在中）→ 単体（1除外）→ ペア（2除外）の順に指標を採る
    full = _run_cohort_indicators(eng, n, upgrades)
    single_co: dict[str, dict] = {}
    for m in pool:
        with _ablated_pool(frozenset({m})):
            single_co[m] = _run_cohort_indicators(eng, n, upgrades)
    pair_keys = list(itertools.combinations(pool, 2))
    pair_co: dict[tuple[str, str], dict] = {}
    for x, y in pair_keys:
        with _ablated_pool(frozenset({x, y})):
            pair_co[(x, y)] = _run_cohort_indicators(eng, n, upgrades)

    f = full["clears"]

    # 単体統計
    singles: dict[str, dict] = {}
    for m in pool:
        co = single_co[m]
        st = _single_stats(f, co["clears"], delta_single, alpha)
        singles[m] = {
            "cohort": {"cleared": co["cleared"], "rate": co["rate"],
                       "avg_floor": co["avg_floor"], "death_floor": co["death_floor"]},
            "contribution": st["contribution"],
            "ci": st["ci"],
            "within_pm_delta": st["within_pm_delta"],
            "mcnemar": st["mcnemar"],
            "evalue": st["evalue"],
            "verdict": _classify_single(st["ci"], dead_hi, broken_lo),
            "semantics": ("incremental_beyond_fixed_1F" if m in FIXED_MODS
                          else "presence_vs_absence"),
        }

    # ペア統計（結合寄与は _single_stats を delta=w_pair で再利用＝joint_*）
    pairs: dict[str, dict] = {}
    for x, y in pair_keys:
        co = pair_co[(x, y)]
        joint = _single_stats(f, co["clears"], w_pair, alpha)
        inter = _interaction_stats(f, single_co[x]["clears"], single_co[y]["clears"],
                                   co["clears"], w_pair, alpha, boot_seed)
        pairs[f"{x}|{y}"] = {
            "cohort": {"cleared": co["cleared"], "rate": co["rate"],
                       "avg_floor": co["avg_floor"], "death_floor": co["death_floor"]},
            "joint_contribution": joint["contribution"],
            "joint_ci": joint["ci"],
            "joint_evalue": joint["evalue"],
            "interaction": inter["interaction"],
            "interaction_ci": inter["ci"],
            "interaction_evalue": inter["evalue"],
            "interaction_ci_bootstrap": inter["ci_bootstrap"],
            "within_w": inter["within_w"],
            "sign": inter["sign"],
            "confounded_by_fixed_1F": (x in FIXED_MODS or y in FIXED_MODS),
        }

    # e-BH ファミリ1: 単体6 + ペア結合15（固定順: pool順 → combinations順）で FDR 制御
    direct_meta: list[tuple[str, str]] = ([("single", m) for m in pool]
                                          + [("pair", f"{x}|{y}") for x, y in pair_keys])
    direct_evalues = ([singles[m]["evalue"] for m in pool]
                      + [pairs[f"{x}|{y}"]["joint_evalue"] for x, y in pair_keys])
    direct_rejected = set(bs.ebh_fdr(direct_evalues, alpha=alpha))
    family_direct_rejected: list[str] = []
    for i, (kind, key) in enumerate(direct_meta):
        sig = i in direct_rejected
        if kind == "single":
            singles[key]["fdr_significant"] = sig
        else:
            pairs[key]["joint_fdr_significant"] = sig
        if sig:
            family_direct_rejected.append(key)

    # e-BH ファミリ2: ペア交互作用15（combinations順）
    inter_keys = [f"{x}|{y}" for x, y in pair_keys]
    inter_evalues = [pairs[k]["interaction_evalue"] for k in inter_keys]
    inter_rejected = set(bs.ebh_fdr(inter_evalues, alpha=alpha))
    family_interaction_rejected: list[str] = []
    for i, k in enumerate(inter_keys):
        sig = i in inter_rejected
        pairs[k]["interaction_fdr_significant"] = sig
        if sig:
            family_interaction_rejected.append(k)

    flo, fhi = bs.wilson(full["cleared"], n)
    power_note = ("" if 0.15 <= full["rate"] <= 0.85
                  else "floor/ceiling で検出力低下（full rate が [0.15,0.85] 外）")

    # verdict: 単体に trap/dead/broken、または「同等でない×交互作用FDR有意」ペアがあれば warn
    warn = (any(s["verdict"] in ("trap", "dead", "broken") for s in singles.values())
            or any((not p["within_w"]) and p["interaction_fdr_significant"]
                   for p in pairs.values()))

    return {
        "n": n,
        "profile": profile,
        "upgrades": upgrades,
        "alpha": alpha,
        "pool": pool,
        "thresholds": {
            "delta_single": delta_single,
            "w_pair": w_pair,
            "dead_hi": dead_hi,
            "broken_lo": broken_lo,
        },
        "full": {
            "cleared": full["cleared"],
            "rate": full["rate"],
            "ci_wilson": (flo, fhi),
            "avg_floor": full["avg_floor"],
            "death_floor": full["death_floor"],
            "power_note": power_note,
        },
        "singles": singles,
        "pairs": pairs,
        "fdr": {
            "family_direct_rejected": family_direct_rejected,
            "family_interaction_rejected": family_interaction_rejected,
        },
        "verdict": "warn" if warn else "pass",
        "_comment": ("mod寄与 ablation（GDD §18.2 Phase3・OPEN-023）。プール差し替えは実行中のみで "
                     "data/*.json・エンジンは不変。分類は §18.4 の非対称運用でデザイナー（人間）判断＝"
                     "厳格ゲートなし・Goodhart回避。hansha は 1F 確定分を除いた追加取得寄与を測る。"),
    }


# ─────────────────────── 出力 ───────────────────────
def _pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def _print_summary(rep: dict) -> None:
    print(f"=== mod ablation (N={rep['n']}, profile={rep['profile']}, "
          f"verdict={rep['verdict']}) ===")
    fu = rep["full"]
    print(f"full pool: {rep['pool']}")
    print(f"  clear {_pct(fu['rate'])}  CI[{_pct(fu['ci_wilson'][0])},{_pct(fu['ci_wilson'][1])}]  "
          f"avg_floor={fu['avg_floor']:.2f}  deaths={fu['death_floor']}")
    if fu["power_note"]:
        print(f"  power: {fu['power_note']}")

    print("\nSINGLES  Δ=寄与(pt)=clear%(full)-clear%(ablated)  * = e-BH FDR 有意:")
    hdr = f"  {'mod':>12} {'Δ(pt)':>7} {'CI(pt)':>18} {'verdict':>12} {'FDR':>3}  semantics"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for m in rep["pool"]:
        s = rep["singles"][m]
        lo, hi = s["ci"]
        fdr = "*" if s["fdr_significant"] else ""
        print(f"  {m:>12} {s['contribution'] * 100:>+6.1f} "
              f"[{lo * 100:>+6.1f},{hi * 100:>+6.1f}] {s['verdict']:>12} {fdr:>3}  {s['semantics']}")

    print("\nPAIRS  I=交互作用=結合寄与-単体寄与和  I<0=synergy I>0=substitute  * = FDR 有意  1F=交絡:")
    hdr2 = f"  {'pair':>20} {'I(pt)':>7} {'CI(pt)':>18} {'sign':>11} {'FDR':>3} {'cnf':>3}"
    print(hdr2)
    print("  " + "-" * (len(hdr2) - 2))
    for k, p in rep["pairs"].items():
        lo, hi = p["interaction_ci"]
        fdr = "*" if p["interaction_fdr_significant"] else ""
        conf = "1F" if p["confounded_by_fixed_1F"] else ""
        print(f"  {k:>20} {p['interaction'] * 100:>+6.1f} "
              f"[{lo * 100:>+6.1f},{hi * 100:>+6.1f}] {p['sign']:>11} {fdr:>3} {conf:>3}")

    fd = rep["fdr"]
    print(f"\nFDR rejected  direct:      {fd['family_direct_rejected'] or 'なし'}")
    print(f"FDR rejected  interaction: {fd['family_interaction_rejected'] or 'なし'}")
    print("（判定はデザイナー＝人間。死にmodは潰す・壊れmodは残す非対称運用・§18.4。数値JSONは不変）")


def main() -> None:
    ap = argparse.ArgumentParser(description="mod寄与 ablation 検証（GDD §18.2 Phase3・OPEN-023）")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--profile", type=str, default="mid", choices=("base", "mid", "maxed"))
    ap.add_argument("--out", type=str, default=None, help="JSON 出力先")
    args = ap.parse_args()
    rep = build_report(n=args.n, profile=args.profile)
    _print_summary(rep)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fp:
            json.dump(rep, fp, ensure_ascii=False, indent=2)
        print("wrote", args.out)
    # 観察専用ツール: 厳格ゲートなし＝終了コードは常に 0（balance_report と違い sys.exit しない）


if __name__ == "__main__":
    main()
