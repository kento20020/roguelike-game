"""ゲート判定テーブル・被ダメ・保証 decay。"""
import math

from app.engine import gate_resolver as gr
from app.engine.rng import Sfc32


def test_gate_damage_ratios(data):
    assert gr.gate_damage("unhurt", 100, data) == 0
    assert gr.gate_damage("minor", 100, data) == 10
    assert gr.gate_damage("major", 100, data) == 25
    assert gr.gate_damage("special", 100, data) == 0
    assert gr.gate_damage("minor", 120, data) == 12


def test_roll_distribution_approx(data):
    table = data.floor(2)["gate_result_table"]  # 0.25/0.45/0.25/0.05
    s = Sfc32(1)
    cnt = {o: 0 for o in gr.OUTCOMES}
    n = 40000
    for _ in range(n):
        cnt[gr.roll_gate(table, s)] += 1
    assert abs(cnt["minor"] / n - 0.45) < 0.02
    assert abs(cnt["major"] / n - 0.25) < 0.02


def test_guarantee_reduces_major_splits_evenly(data):
    table = {"unhurt": 0.25, "minor": 0.45, "major": 0.25, "special": 0.05}
    g = gr.apply_guarantee(table, 1, data)
    # 削減 0.25、major 0.25→0.00、unhurt/minor へ 0.125 ずつ
    assert math.isclose(g["major"], 0.0, abs_tol=1e-9)
    assert math.isclose(g["unhurt"], 0.25 + 0.125)
    assert math.isclose(g["minor"], 0.45 + 0.125)
    assert math.isclose(g["special"], 0.05)             # special 維持
    assert math.isclose(sum(g.values()), 1.0)


def test_guarantee_caps_at_available_major(data):
    table = {"unhurt": 0.4, "minor": 0.4, "major": 0.1, "special": 0.1}
    g = gr.apply_guarantee(table, 1, data)
    # major は 0.1 しかない → 0.1 だけ削れる
    assert math.isclose(g["major"], 0.0, abs_tol=1e-9)
    assert math.isclose(g["unhurt"], 0.4 + 0.05)
    assert math.isclose(g["minor"], 0.4 + 0.05)
    assert math.isclose(sum(g.values()), 1.0)


def test_guarantee_stacking_halves_reduction(data):
    table = {"unhurt": 0.10, "minor": 0.30, "major": 0.40, "special": 0.20}
    g = gr.apply_guarantee(table, 2, data)
    # n=1: 削減0.25、n=2: 削減0.125 → 合計0.375 を major から
    assert math.isclose(g["major"], 0.40 - 0.375)
    assert math.isclose(sum(g.values()), 1.0)
    assert math.isclose(g["special"], 0.20)


def test_guarantee_cost_growth(data):
    assert gr.guarantee_cost(1, data) == 50
    assert gr.guarantee_cost(2, data) == round(50 * 1.5)   # 75
    assert gr.guarantee_cost(3, data) == round(50 * 1.5 ** 2)  # 113


def test_guaranteed_table_rolls_less_major(data):
    table = data.floor(4)["gate_result_table"]  # major 0.35
    g = gr.apply_guarantee(table, 1, data)
    s = Sfc32(9)
    n = 40000
    major = sum(1 for _ in range(n) if gr.roll_gate(g, s) == "major")
    assert major / n < 0.15  # 大幅減（0.35 → 0.10）
