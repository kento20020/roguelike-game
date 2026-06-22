"""Phase1/2 ハーネス — strong/random を多数 seed で回しクリア率を計測。

CRN（共通乱数）: strong と random は同じゲーム seed 群（0..N-1）でプレイ。
合格条件: strong クリア率 25〜40%、random は概ね 1〜5%、CI が重ならない（スキル幅）。
帯域外なら JSON 数値を人間が調整（Goodhart回避）。

実行: python -m app.simulation.phase12_harness [N]
"""
from __future__ import annotations

import sys
from collections import Counter

from app.engine.game_engine import GameEngine
from app.simulation import bots
from app.simulation.balance_stats import wilson  # 単一ソース（再エクスポート: test_simulation 互換）


def run_cohort(play, n: int, **kw) -> dict:
    """コホートを回し集計＋各 RunRecord snapshot を records に保持して返す。
    records は balance_report / balance_analysis / fun_metrics の入力になる。"""
    eng = GameEngine()
    cleared = 0
    death_floor = Counter()
    total_turns = 0
    records = []
    for seed in range(n):
        rr = play(eng, seed=seed, **kw)
        records.append(rr)
        total_turns += rr["total_turns"]
        if rr["cleared"]:
            cleared += 1
        elif rr["death_floor"] is not None:
            death_floor[rr["death_floor"]] += 1
    lo, hi = wilson(cleared, n)
    return {
        "n": n, "cleared": cleared, "rate": cleared / n,
        "ci": (lo, hi), "death_floor": dict(sorted(death_floor.items())),
        "avg_turns": total_turns / n, "records": records,
    }


# 恒久強化プロファイル（win-to-progress: クリアを重ねるほど有利）
PROFILES = {
    "base (fresh acct)": {},
    "mid (~6 clears)": {"max_hp": 2, "attack": 2, "init_gold": 2, "gold_drop": 1, "sink_cost": 1},
    "maxed (26 clears)": {"max_hp": 5, "attack": 5, "init_gold": 5, "gold_drop": 3, "sink_cost": 3},
}


def main(n: int = 1000) -> None:
    def pct(x):
        return f"{x * 100:.1f}%"

    print(f"=== Phase1/2 harness  (N={n} seeds, CRN) ===")
    rnd = run_cohort(bots.play_random, n, bot_seed=1234)
    print(f"RANDOM  clear {pct(rnd['rate'])}  CI[{pct(rnd['ci'][0])},{pct(rnd['ci'][1])}]  "
          f"avg_turns={rnd['avg_turns']:.1f}  deaths={rnd['death_floor']}")

    print("STRONG by 恒久強化プロファイル:")
    band_hit = False
    for name, up in PROFILES.items():
        s = run_cohort(bots.play_strong, n, upgrades=up)
        in_band = 0.25 <= s["rate"] <= 0.40
        gap = s["ci"][0] > rnd["ci"][1]
        band_hit = band_hit or in_band
        tag = "  <= 25-40% PASS" if in_band else ""
        print(f"  {name:20s} clear {pct(s['rate']):>6}  CI[{pct(s['ci'][0])},{pct(s['ci'][1])}]  "
              f"skill_gap={'Y' if gap else 'n'}  deaths={s['death_floor']}{tag}")

    print("--- verdict ---")
    if band_hit:
        print("いずれかのプロファイルで強プレイ 25-40% を達成（システムはクリア可能・健全）。")
    print("base が帯域外なのは想定内: data/*.json は『叩き台』。fresh acct も帯域へ寄せたい場合は")
    print("方策ではなく backend/app/data/*.json の数値を人間が調整する（Goodhart回避・要レビュー）。")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    main(n)
