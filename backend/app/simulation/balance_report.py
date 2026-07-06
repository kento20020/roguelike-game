"""バランス検証オーケストレータ（GDD §18.2 Phase1-4 を1コマンドで）。

§18.1 の各合格条件を pass/warn/fail で判定し JSON 出力する。
- 厳格 fail は「スキル幅」のみ（回帰の厳格ゲートは test_balance_regression が担当）。
- 他の条件は warn（帯域内はデザイナー判断／JSONは人間が触る・Goodhart回避・§18.4）。
- fun_metrics（面白さ代理指標）も併記する（測るだけ・合否にしない）。

実行: python -m app.simulation.balance_report --n 1000 --out report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from app.simulation import balance_analysis as ba
from app.simulation import balance_stats as bs
from app.simulation import bots
from app.simulation import fun_metrics as fm
from app.simulation.phase12_harness import PROFILES, run_cohort

BAND_LO, BAND_HI = 0.25, 0.40           # §18.1 強プレイ
RAND_LO, RAND_HI = 0.01, 0.05           # §18.1 ランダム（暫定）
FIRST_MOVE_NODES = ("L", "M", "R")      # 初手（row1 の3枠）


def _check(name: str, status: str, spec: str, detail: dict) -> dict:
    return {"name": name, "status": status, "spec": spec, "detail": detail}


def _maxed_profile() -> dict:
    return max(PROFILES.values(), key=lambda u: sum(u.values()) if u else 0)


def _indicators(records: Sequence[dict]) -> list[int]:
    return [1 if r.get("cleared") else 0 for r in records]


def build_report(n: int = 1000, n_first_move: int | None = None, alpha: float = 0.05,
                 random_bot_seed: int = 1234) -> dict:
    n_fm = n_first_move if n_first_move is not None else min(n, 300)
    maxed_up = _maxed_profile()

    # コホート（CRN: strong/random は同一ゲーム seed 群 0..n-1）
    strong = {name: run_cohort(bots.play_strong, n, upgrades=up) for name, up in PROFILES.items()}
    rnd = run_cohort(bots.play_random, n, bot_seed=random_bot_seed)
    maxed_co = next(co for name, co in strong.items() if PROFILES[name] is maxed_up)
    all_strong = [r for co in strong.values() for r in co["records"]]

    checks: list[dict] = []

    # Phase1: 強クリア率 25-40%（いずれかのプロファイルで帯域内 → pass、無ければ warn=JSON調整事項）
    bands = {name: bs.band_test(_indicators(co["records"]), BAND_LO, BAND_HI, alpha)
             for name, co in strong.items()}
    any_in = any(v == "in" for v in bands.values())
    checks.append(_check(
        "強クリア率25-40%", "pass" if any_in else "warn", "§18.1",
        {"band_test": bands, "rates": {name: co["rate"] for name, co in strong.items()},
         "note": "" if any_in else "帯域外はコード非責＝data/*.jsonの数値調整事項（人間）"}))

    # random 1-5%（暫定指標 → warn）
    r_band = bs.band_test(_indicators(rnd["records"]), RAND_LO, RAND_HI, alpha)
    checks.append(_check("random1-5%", "pass" if r_band == "in" else "warn", "§18.1(暫定)",
                         {"band_test": r_band, "rate": rnd["rate"]}))

    # Phase2: スキル幅（唯一の厳格ゲート）。CRN対標本 McNemar ＋ Wilson 非重なりで確認
    pairs = [(a, b) for a, b in zip(_indicators(maxed_co["records"]), _indicators(rnd["records"]))]
    mc = bs.mcnemar_eprocess(pairs, alpha=alpha)
    mlo, mhi = bs.wilson(maxed_co["cleared"], maxed_co["n"])
    rlo, rhi = bs.wilson(rnd["cleared"], rnd["n"])
    nonoverlap = mlo > rhi
    gap = (mc["reject"] and mc["direction"] == 1) or nonoverlap
    checks.append(_check("スキル幅(CIが0をまたがない)", "pass" if gap else "fail",
                         "§18.1 ★厳格ゲート",
                         {"mcnemar": mc, "maxed_wilson": (mlo, mhi), "random_wilson": (rlo, rhi),
                          "nonoverlap": nonoverlap}))

    # Phase2: 初手別クリア率差 ±5pt ＆ 選択感度（forced_first_node で正規実験・maxed）
    fm_cohort = {nd: run_cohort(bots.play_strong, n_fm, upgrades=maxed_up, forced_first_node=nd)["records"]
                 for nd in FIRST_MOVE_NODES}
    fms = ba.first_move_sensitivity(fm_cohort, delta=0.05, alpha=alpha)
    checks.append(_check("初手別クリア率差±5pt", "pass" if fms["within_5pt"] else "warn", "§18.1",
                         {"clear_rates": fms["clear_rates"], "spread": fms["spread"]}))
    checks.append(_check("選択感度(有意な差)", "pass" if fms["sensitive"] else "warn", "§18.1",
                         {"pairs": fms["pairs"]}))

    # 死亡フロア分布が集中しない
    dfc = ba.death_floor_concentration(all_strong, threshold=0.5, alpha=alpha)
    checks.append(_check("死亡フロア集中しない", "warn" if dfc["concentrated"] else "pass", "§18.1",
                         {"counts": dfc["counts"], "max_share": dfc["max_share"], "mode": dfc["mode"]}))

    # Phase3: 単一mod寄与 ±8pt（平均寄与のみ）。±8pt超は要レビュー（壊れ/死にmod・非対称運用でwarn）
    modc = ba.mod_marginal_contribution(all_strong, delta=0.08, alpha=alpha)
    broken = sorted(m for m, v in modc.items() if v["broken_or_dead"])
    checks.append(_check("単一mod寄与±8pt", "warn" if broken else "pass", "§18.1(平均寄与のみ・観察的)",
                         {"broken_or_dead": broken,
                          "per_mod": {m: {"contribution": v["contribution"], "ci": v["ci"]} for m, v in modc.items()}}))

    # Phase4: 経済（sink ROI 観察値・hoarder）＝記述（warnにもしない・参考）
    roi = ba.sink_roi_observational(all_strong, alpha=alpha)
    hoard = ba.hoarder_detection(all_strong)

    verdict = "fail" if any(c["status"] == "fail" for c in checks) else \
              ("warn" if any(c["status"] == "warn" for c in checks) else "pass")

    return {
        "n": n, "n_first_move": n_fm, "alpha": alpha,
        "clear_rates": {name: co["rate"] for name, co in strong.items()},
        "random_rate": rnd["rate"],
        "checks": checks,
        "economy": {"sink_roi_observational": roi, "hoarder": hoard},
        "fun_metrics": fm.compute(maxed_co["records"]),
        "verdict": verdict,
    }


def regression_snapshot(n: int = 120) -> dict:
    """Phase5 回帰CI 用の決定論スナップショット（bot は同一 seed→同一結果）。
    data/*.json の数値変更でこれらがズレたら回帰として検出する。"""
    strong = {name: run_cohort(bots.play_strong, n, upgrades=up) for name, up in PROFILES.items()}
    rnd = run_cohort(bots.play_random, n, bot_seed=1234)

    def depth(co: dict) -> int:
        return sum(int(k) * v for k, v in co["death_floor"].items()) + co["cleared"] * 6

    maxed_up = _maxed_profile()
    maxed_co = next(co for name, co in strong.items() if PROFILES[name] is maxed_up)
    return {
        "n": n,
        "clear_counts": {name: co["cleared"] for name, co in strong.items()},
        "random_clear_count": rnd["cleared"],
        "maxed_death_floor": maxed_co["death_floor"],
        "strong_depth_gt_random": depth(maxed_co) > depth(rnd),
    }


def _print_summary(rep: dict) -> None:
    icon = {"pass": "PASS", "warn": "warn", "fail": "FAIL"}
    print(f"=== balance_report (N={rep['n']}, verdict={rep['verdict']}) ===")
    print("clear rates:", {k: round(v, 3) for k, v in rep["clear_rates"].items()},
          "| random:", round(rep["random_rate"], 3))
    for c in rep["checks"]:
        print(f"  [{icon[c['status']]:4}] {c['name']}  ({c['spec']})")
    fmx = rep["fun_metrics"]
    print("fun: close_win_rate=", fmx["close_win_rate"],
          " mod_diversity(norm)=", (fmx["mod_diversity"]["normalized"]),
          " gate_guarantee_used=", fmx["gate_guarantee_dependence"]["used_rate"])


def main() -> None:
    ap = argparse.ArgumentParser(description="§18 バランス検証レポート")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--first-move-n", type=int, default=None)
    ap.add_argument("--out", type=str, default=None, help="JSON 出力先")
    args = ap.parse_args()
    rep = build_report(n=args.n, n_first_move=args.first_move_n)
    _print_summary(rep)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        print("wrote", args.out)
    # 厳格ゲート失敗時は非ゼロ終了（CIで使えるよう）
    sys.exit(1 if rep["verdict"] == "fail" else 0)


if __name__ == "__main__":
    main()
