"""カオス敵のラン別行動分布（stream#8）。

GDD §9.2: ラン開始時、各カオス敵について {counter, heavy_blow, evade, ramp_hit}
の比率をシードから決定（Dirichlet風）。ラン内一貫・ラン間変動。

合計100の整数 weight で返す（behaviors と同じ形式: list[(type, weight)]）。
"""
from __future__ import annotations

from app.engine.rng import Sfc32

CHAOS_TYPES = ["counter", "heavy_blow", "evade", "ramp_hit"]


def generate_one(stream: Sfc32) -> list[tuple[str, int]]:
    """4種に合計100の整数weightを配分（各種 最低5 を保証して退化を防ぐ）。"""
    # 一様値を引いて正規化（Dirichlet(1,1,1,1) 近似）
    raw = [stream.random() + 1e-9 for _ in CHAOS_TYPES]
    total = sum(raw)
    # 最低保証 5pt を確保したうえで残り80ptを比率配分
    floor_pt = 5
    remaining = 100 - floor_pt * len(CHAOS_TYPES)  # 80
    weights = [floor_pt + int(remaining * (r / total)) for r in raw]
    # 端数で 100 に満たない分を最大weightに足す
    diff = 100 - sum(weights)
    weights[weights.index(max(weights))] += diff
    return list(zip(CHAOS_TYPES, weights))


def generate_all(stream: Sfc32, chaos_ids: list[str]) -> dict[str, list[tuple[str, int]]]:
    """全カオス敵idぶんの分布を生成。idの順で stream を消費（決定論）。"""
    return {eid: generate_one(stream) for eid in sorted(chaos_ids)}
