"""ゲート（胴元の関門）判定と保証 sink。

- gate_result_table はフロア別（floors.json）。stream#5 で抽選。
- 被ダメ: minor=max_hp×0.10 / major=max_hp×0.25 / unhurt・special=0。
- ゲート保証 n回目: コスト=50×1.5^(n-1)、major削減=0.25×0.5^(n-1)。
  削減分は unhurt/minor へ半々、special は維持、重ねがけ可。
"""
from __future__ import annotations

from app.data.loader import GameData
from app.engine.rng import Sfc32

OUTCOMES = ["unhurt", "minor", "major", "special"]


def apply_guarantee(table: dict[str, float], times: int, data: GameData) -> dict[str, float]:
    """times 回ぶんの保証を適用した確率テーブルを返す（重ねがけ）。"""
    s = data.config["sinks"]
    rule = data.floors_doc["gate_guarantee_rule"]
    t = dict(table)
    for n in range(1, times + 1):
        reduction = s["gate_guarantee_base_reduction"] * (s["gate_guarantee_reduction_decay"] ** (n - 1))
        removed = min(t["major"], reduction)
        t["major"] -= removed
        t["unhurt"] += removed * rule["split_to_unhurt"]
        t["minor"] += removed * rule["split_to_minor"]
        # special は維持（preserve_special）
    return t


def guarantee_cost(times: int, data: GameData) -> int:
    """times 回目の保証コスト（=これまで n=1..times のうち最新回のコスト）。"""
    s = data.config["sinks"]
    n = times  # 1-indexed: times 回目のコスト
    return round(s["gate_guarantee_base_cost"] * (s["gate_guarantee_cost_growth"] ** (n - 1)))


def roll_gate(table: dict[str, float], stream: Sfc32) -> str:
    weights = [table[o] for o in OUTCOMES]
    return OUTCOMES[stream.weighted_index(weights)]


def gate_damage(outcome: str, max_hp: int, data: GameData) -> int:
    ratio = data.floors_doc["gate_damage"][outcome]
    return round(max_hp * ratio)
