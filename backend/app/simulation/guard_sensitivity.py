"""ジャストガード感度分析ハーネス（OPEN-018 数値確定用）。

v1.8 で再設計した受け（ジャストガード＋重ねがけ減衰）の軽減率・減衰係数を最終確定するため、
`config["combat"]["guard"]` を **インメモリで** 振りながら strong bot のクリア率等を計測する。
config.json ファイルは一切変更しない（フレッシュな GameData.load() の config dict を
その場で書き換えるだけ。モジュールキャッシュ get_data() にも触れない）。

グリッド: heavy_mitigation ∈ {0.7, 0.8, 0.9} × stack_decay ∈ {0.4, 0.5, 0.7}（計9combo）。
         counter/ramp_hit=0.5 固定・count_whiff=true 固定・deal_factor=0.5 固定。

各 combo で maxed 恒久強化プロファイルの strong bot を guard_policy 3種で N seeds 実行:
  smart  = 現行方策（公開済みの次手にのみ受ける）
  never  = 一切受けない（旧 strong-v1 相当の行動空間）
  always = 毎ターン受ける（旧仕様で支配戦略だった「常時受け」の再現）
CRN: 全 policy/combo で同一 seed 群 0..N-1 を使う。

導出指標:
  skill_expression = clear%(smart) − clear%(never)  … 受けを「読んで使える」ことの寄与
  dominance        = clear%(always) − clear%(never) … 正なら常時受けがまだ得＝支配戦略が残存

実行: python -m app.simulation.guard_sensitivity [N]   （既定 N=400）
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

from app.data.loader import GameData
from app.engine.game_engine import GameEngine
from app.simulation import bots
from app.simulation.phase12_harness import PROFILES

# グリッド（heavy 以外は叩き台のまま固定）
HEAVY_MITIGATIONS = (0.7, 0.8, 0.9)
STACK_DECAYS = (0.4, 0.5, 0.7)
FIXED_COUNTER = 0.5
FIXED_RAMP_HIT = 0.5
FIXED_DEAL_FACTOR = 0.5
FIXED_COUNT_WHIFF = True

OUT_PATH = os.path.join(os.path.dirname(__file__), "baselines", "guard_sensitivity_result.json")


def _maxed_profile() -> dict:
    """balance_report._maxed_profile と同一: 恒久強化の合計が最大＝maxed を選ぶ。"""
    return max(PROFILES.values(), key=lambda u: sum(u.values()) if u else 0)


def _guard_config(heavy_mit: float, stack_decay: float) -> dict:
    """config.json combat.guard と同一構造の dict（インメモリ書き換え用）。"""
    return {
        "deal_factor": FIXED_DEAL_FACTOR,
        "mitigation_by_action": {
            "heavy_blow": heavy_mit,
            "counter": FIXED_COUNTER,
            "ramp_hit": FIXED_RAMP_HIT,
        },
        "stack_decay": stack_decay,
        "count_whiff": FIXED_COUNT_WHIFF,
    }


def _run_policy(eng: GameEngine, n: int, upgrades: dict, guard_policy: str) -> dict:
    """1 policy を n seeds（0..n-1・CRN）回して集計（phase12_harness.run_cohort を踏襲）。"""
    cleared = 0
    death_floor: Counter[int] = Counter()
    floor_sum = 0
    guard_sum = 0
    for seed in range(n):
        rr = bots.play_strong(eng, seed=seed, upgrades=upgrades, guard_policy=guard_policy)
        floor_sum += rr["floor_reached"]
        guard_sum += rr["action_counts"].get("guard", 0)  # RunRecord.action_counts の受け回数
        if rr["cleared"]:
            cleared += 1
        elif rr["death_floor"] is not None:
            death_floor[rr["death_floor"]] += 1
    return {
        "n": n,
        "cleared": cleared,
        "clear_rate": cleared / n,
        "avg_floor": floor_sum / n,
        "avg_guard": guard_sum / n,
        "death_floor": dict(sorted(death_floor.items())),
    }


def run(n: int = 400) -> dict:
    # モジュールキャッシュ（get_data）とは独立のフレッシュな正本データを読む。
    # 以降 data.config["combat"]["guard"] をインメモリで差し替える（frozen dataclass の dict は可変）。
    data = GameData.load()
    upgrades = _maxed_profile()
    eng = GameEngine(data=data)

    # never は guard 係数に非依存 → 全 combo で同一。1回だけ測って使い回す（時間節約）。
    never = _run_policy(eng, n, upgrades, "never")

    combos: list[dict] = []
    for heavy_mit in HEAVY_MITIGATIONS:
        for stack_decay in STACK_DECAYS:
            # ★config.json ファイルは触らない。読み込み済み config dict のみ差し替える。
            data.config["combat"]["guard"] = _guard_config(heavy_mit, stack_decay)
            smart = _run_policy(eng, n, upgrades, "smart")
            always = _run_policy(eng, n, upgrades, "always")
            combos.append({
                "heavy_mitigation": heavy_mit,
                "stack_decay": stack_decay,
                "smart": smart,
                "always": always,
                "skill_expression": smart["clear_rate"] - never["clear_rate"],
                "dominance": always["clear_rate"] - never["clear_rate"],
            })

    return {
        "n": n,
        "profile": dict(upgrades),
        "fixed": {
            "counter": FIXED_COUNTER,
            "ramp_hit": FIXED_RAMP_HIT,
            "deal_factor": FIXED_DEAL_FACTOR,
            "count_whiff": FIXED_COUNT_WHIFF,
        },
        "grid": {
            "heavy_mitigation": list(HEAVY_MITIGATIONS),
            "stack_decay": list(STACK_DECAYS),
        },
        "never": never,
        "combos": combos,
        "_comment": ("ジャストガード感度分析（OPEN-018 数値確定用・インメモリで係数を振る観測値）。"
                     "config.json は不変。数値の最終確定はデザイナー（人間）判断・Goodhart回避。"),
    }


def _pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def _print_table(rep: dict) -> None:
    n = rep["n"]
    nv = rep["never"]
    print(f"=== Guard Sensitivity (N={n}, maxed profile, CRN) ===")
    print(f"profile={rep['profile']}")
    fx = rep["fixed"]
    print(f"fixed: counter={fx['counter']:.2f} ramp_hit={fx['ramp_hit']:.2f} "
          f"deal_factor={fx['deal_factor']:.2f} count_whiff={fx['count_whiff']}")
    print(f"NEVER baseline: clear {_pct(nv['clear_rate'])}  avg_floor={nv['avg_floor']:.2f}  "
          f"guard/run={nv['avg_guard']:.2f}  deaths={nv['death_floor']}")
    print()
    header = (f"{'heavy':>5} {'decay':>5} | {'smart%':>7} {'never%':>7} {'always%':>8} | "
              f"{'skill_exp':>9} {'dominance':>9} | {'g/run(sm)':>9} {'g/run(al)':>9} | "
              f"{'floor(sm)':>9}")
    print(header)
    print("-" * len(header))
    for c in rep["combos"]:
        sm, al = c["smart"], c["always"]
        print(f"{c['heavy_mitigation']:>5.2f} {c['stack_decay']:>5.2f} | "
              f"{_pct(sm['clear_rate']):>7} {_pct(nv['clear_rate']):>7} {_pct(al['clear_rate']):>8} | "
              f"{c['skill_expression'] * 100:>+8.1f}p {c['dominance'] * 100:>+8.1f}p | "
              f"{sm['avg_guard']:>9.2f} {al['avg_guard']:>9.2f} | {sm['avg_floor']:>9.2f}")
    print()
    # 気づき: 支配戦略が残る combo（dominance>0）と skill_expression 最大 combo。
    dom = [c for c in rep["combos"] if c["dominance"] > 0]
    best = max(rep["combos"], key=lambda c: c["skill_expression"])
    print(f"dominance>0 (常時受けがまだ得): "
          f"{[(c['heavy_mitigation'], c['stack_decay']) for c in dom] or 'なし'}")
    print(f"skill_expression 最大: heavy={best['heavy_mitigation']} decay={best['stack_decay']} "
          f"({best['skill_expression'] * 100:+.1f}pt)")


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    rep = run(n)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    _print_table(rep)
    print("\nwrote", OUT_PATH)


if __name__ == "__main__":
    main()
