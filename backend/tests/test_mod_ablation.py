"""mod_ablation の検証（GDD §18.2 Phase3・OPEN-023）。

- プール差し替え(_ablated_pool)の成功/例外時の復元保証と入力検証（ValueError）
- 除外modが宝箱抽選（MOD_POOL経由）から出ないこと／hansha は1F確定配置（floors.json content
  経由・MOD_POOL非経由）なので除外しても残ること
- build_report の決定論（同一n・profileなら dict 完全一致）
- 推定量（_single_stats / _interaction_stats / _classify_single）の代数をエンジン不要の
  人工データで検証
- hansha の semantics フラグ・confounded_by_fixed_1F フラグ

build_report(n=12) は実行コストがあるため、本ファイル全体で最大2回まで（決定論テストの
2回のみ）。module-scope fixture `report_pair` で決定論テストと hansha フラグテストが
同じ結果を使い回す。
"""
import pytest

import app.engine.game_engine as ge
from app.engine.game_engine import GameEngine
from app.simulation import bots
from app.simulation import mod_ablation as ma


# ─────────────────────── (a) プール復元 ───────────────────────
def test_ablated_pool_removes_mod_and_restores_after_success():
    orig = list(ge.MOD_POOL)
    with ma._ablated_pool(frozenset({"juso"})):
        assert "juso" not in ge.MOD_POOL
        assert len(ge.MOD_POOL) == len(orig) - 1
    assert ge.MOD_POOL == orig


def test_ablated_pool_restores_after_exception():
    orig = list(ge.MOD_POOL)
    with pytest.raises(RuntimeError):
        with ma._ablated_pool(frozenset({"juso"})):
            raise RuntimeError("boom")
    assert ge.MOD_POOL == orig


def test_ablated_pool_unknown_mod_raises_value_error():
    with pytest.raises(ValueError):
        with ma._ablated_pool(frozenset({"nope"})):
            pass  # pragma: no cover - 到達しない（enterで例外）


def test_ablated_pool_all_excluded_raises_value_error():
    with pytest.raises(ValueError):
        with ma._ablated_pool(frozenset(ge.MOD_POOL)):
            pass  # pragma: no cover - 到達しない（enterで例外）


# ─────────────────────── (b) 除外modが宝箱から出ない ───────────────────────
def test_ablated_juso_never_acquired(data):
    eng = GameEngine(data)
    with ma._ablated_pool(frozenset({"juso"})):
        for seed in range(40):
            rr = bots.play_strong(eng, seed=seed)
            assert "juso" not in rr["mods_acquired"]


def test_ablated_hansha_still_appears_via_fixed_1f(data):
    # hansha は 1F 確定配置（floors.json content 経由）で MOD_POOL を通らないため、
    # 宝箱抽選プールから除外しても 1F 固定分は残る（ablation で測れるのは
    # 「確定1枚を超える追加取得」の寄与のみ、という設計を裏付ける）。
    eng = GameEngine(data)
    with ma._ablated_pool(frozenset({"hansha"})):
        appeared = any(
            "hansha" in bots.play_strong(eng, seed=seed)["mods_acquired"]
            for seed in range(40)
        )
    assert appeared


# ─────────────────────── (c)(e) build_report: 決定論 + hansha フラグ ───────────────────────
@pytest.fixture(scope="module")
def report_pair():
    """build_report(n=12) を2回呼び、決定論テストと hansha フラグテストで共有する
    （このファイル全体での build_report 呼び出し回数を2回に最小化するため）。"""
    rep1 = ma.build_report(n=12, profile="mid")
    rep2 = ma.build_report(n=12, profile="mid")
    return rep1, rep2


def test_build_report_deterministic(report_pair):
    rep1, rep2 = report_pair
    assert rep1 == rep2


def test_hansha_semantics_and_confounding_flag(report_pair):
    rep, _ = report_pair
    assert rep["singles"]["hansha"]["semantics"] == "incremental_beyond_fixed_1F"
    assert rep["pairs"], "pairs が空では confounded フラグを検証できない"
    for key, p in rep["pairs"].items():
        x, y = key.split("|")
        expected = "hansha" in (x, y)
        assert p["confounded_by_fixed_1F"] is expected


# ─────────────────────── (d) 推定量の代数（エンジン不要・人工データ） ───────────────────────
def test_single_stats_contribution_algebra():
    st = ma._single_stats([1, 1, 1, 0], [1, 0, 0, 0], delta=0.08, alpha=0.05)
    assert st["contribution"] == 0.5


def test_interaction_stats_matches_delta_decomposition():
    f = [1, 1, 1, 1]
    x = [1, 1, 0, 0]
    y = [1, 0, 1, 0]
    xy = [0, 0, 0, 0]
    inter = ma._interaction_stats(f, x, y, xy, w=0.10, alpha=0.05, boot_seed=0)

    def mean(s):
        return sum(s) / len(s)

    delta_x = mean(f) - mean(x)
    delta_y = mean(f) - mean(y)
    delta_xy = mean(f) - mean(xy)
    expected = delta_xy - delta_x - delta_y
    assert abs(inter["interaction"] - expected) < 1e-12

    lo, hi = inter["ci"]
    assert -2.0 <= lo <= hi <= 2.0


@pytest.mark.parametrize("ci,expected", [
    ((-0.2, -0.05), "trap"),
    ((-0.005, 0.005), "dead"),
    ((0.10, 0.20), "broken"),
    ((0.02, 0.06), "healthy"),
    ((-0.03, 0.05), "inconclusive"),
])
def test_classify_single_boundaries(ci, expected):
    assert ma._classify_single(ci, dead_hi=0.01, broken_lo=0.08) == expected
