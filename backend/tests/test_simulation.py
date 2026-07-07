"""bot/harness のスモークテスト（小Nで高速）。クリア率の帯域検証は手動実行
（python -m app.simulation.phase12_harness）で行う。"""
from app.engine.game_engine import GameEngine
from app.simulation import bots
from app.simulation.phase12_harness import run_cohort, wilson


def test_strong_bot_terminates(data):
    eng = GameEngine(data)
    rr = bots.play_strong(eng, seed=3)
    assert rr["bot_type"] == "strong"
    assert rr["total_turns"] > 0
    assert rr["cleared"] in (True, False)


def test_random_bot_terminates(data):
    eng = GameEngine(data)
    rr = bots.play_random(eng, seed=3, bot_seed=99)
    assert rr["bot_type"] == "random"


def test_strong_bot_deterministic(data):
    a = bots.play_strong(GameEngine(data), seed=5)
    b = bots.play_strong(GameEngine(data), seed=5)
    # run_id はラン識別用の一意IDであり、seedの決定論の対象外
    a, b = dict(a), dict(b)
    a.pop("run_id"), b.pop("run_id")
    assert a == b


def test_strong_beats_random_on_progression(data):
    # 小Nでも、強ボットは平均到達フロアでランダムを上回る
    s = run_cohort(bots.play_strong, 30)
    r = run_cohort(bots.play_random, 30, bot_seed=1)
    s_depth = sum(int(k) * v for k, v in s["death_floor"].items()) + s["cleared"] * 6
    r_depth = sum(int(k) * v for k, v in r["death_floor"].items()) + r["cleared"] * 6
    assert s_depth > r_depth


def test_maxed_upgrades_can_clear(data):
    # 恒久強化を積めばクリアできる＝システムが健全（クリア可能）
    up = {"max_hp": 5, "attack": 5, "init_gold": 5, "gold_drop": 3, "sink_cost": 3}
    r = run_cohort(bots.play_strong, 120, upgrades=up)
    assert r["cleared"] >= 1


def test_wilson_interval():
    lo, hi = wilson(40, 100)
    assert 0.0 <= lo < 0.40 < hi <= 1.0
