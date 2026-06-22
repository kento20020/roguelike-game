"""SFC32 RNG: golden vector（決定論凍結）・ストリーム独立・再現性。

GOLDEN_* は現行 Python 実装の出力を凍結したもの。将来 TS 版を作るときは
同じ値を出すこと。アルゴリズムを変えたらこのテストが落ちる（＝意図しない変更検知）。
"""
from app.engine.rng import (
    GameRNG,
    STREAM_BEHAVIOR,
    STREAM_FLOOR,
    STREAM_GENERAL,
    Sfc32,
)

GOLDEN_SEED0_GENERAL = [2291109118, 1894794987, 1601370244, 2251310239, 3702085430]
GOLDEN_SEED0_BEHAVIOR = [3307213865, 3192491242, 2027800550, 1904777129, 2806491785]
GOLDEN_SEED12345_FLOOR = [3125131349, 1683531783, 939887584, 3420846517, 951097526]


def test_golden_vectors():
    r = GameRNG(0)
    assert [r.stream(STREAM_GENERAL).next_u32() for _ in range(5)] == GOLDEN_SEED0_GENERAL
    r2 = GameRNG(0)
    assert [r2.stream(STREAM_BEHAVIOR).next_u32() for _ in range(5)] == GOLDEN_SEED0_BEHAVIOR
    r3 = GameRNG(12345)
    assert [r3.stream(STREAM_FLOOR).next_u32() for _ in range(5)] == GOLDEN_SEED12345_FLOOR


def test_same_seed_same_sequence():
    a = GameRNG(99)
    b = GameRNG(99)
    for sid in range(GameRNG.NUM_STREAMS):
        sa = [a.stream(sid).next_u32() for _ in range(20)]
        sb = [b.stream(sid).next_u32() for _ in range(20)]
        assert sa == sb


def test_streams_are_independent():
    # ストリームBの出力は、先にストリームAを引いても変わらない
    base = GameRNG(123)
    b_only = [base.stream(STREAM_BEHAVIOR).next_u32() for _ in range(10)]

    mixed = GameRNG(123)
    # 先に floor を大量に引く
    for _ in range(50):
        mixed.stream(STREAM_FLOOR).next_u32()
    b_after = [mixed.stream(STREAM_BEHAVIOR).next_u32() for _ in range(10)]
    assert b_only == b_after


def test_different_streams_differ():
    r = GameRNG(0)
    g = [r.stream(STREAM_GENERAL).next_u32() for _ in range(5)]
    b = [r.stream(STREAM_BEHAVIOR).next_u32() for _ in range(5)]
    assert g != b


def test_different_seeds_differ():
    a = [GameRNG(1).stream(STREAM_GENERAL).next_u32() for _ in range(5)]
    b = [GameRNG(2).stream(STREAM_GENERAL).next_u32() for _ in range(5)]
    assert a != b


def test_stream_id_bounds():
    r = GameRNG(0)
    for bad in (-1, 9, 100):
        try:
            r.stream(bad)
            assert False, "expected ValueError"
        except ValueError:
            pass


def test_random_in_unit_interval():
    s = Sfc32(7)
    for _ in range(10000):
        v = s.random()
        assert 0.0 <= v < 1.0


def test_randint_bounds_inclusive():
    s = Sfc32(3)
    seen = set()
    for _ in range(5000):
        v = s.randint(2, 5)
        assert 2 <= v <= 5
        seen.add(v)
    assert seen == {2, 3, 4, 5}  # 全値が出る


def test_weighted_index_respects_zero_weight():
    s = Sfc32(11)
    # index 1 は weight 0 → 絶対に選ばれない
    for _ in range(5000):
        assert s.weighted_index([50, 0, 50]) in (0, 2)


def test_weighted_index_distribution_approx():
    s = Sfc32(42)
    n = 60000
    cnt = [0, 0]
    for _ in range(n):
        cnt[s.weighted_index([70, 30])] += 1
    ratio0 = cnt[0] / n
    assert abs(ratio0 - 0.70) < 0.02  # 70%±2pt


def test_shuffle_is_permutation_and_deterministic():
    s1 = Sfc32(5)
    s2 = Sfc32(5)
    a = s1.shuffle(list(range(10)))
    b = s2.shuffle(list(range(10)))
    assert sorted(a) == list(range(10))  # 要素保存
    assert a == b  # 同 seed → 同結果
