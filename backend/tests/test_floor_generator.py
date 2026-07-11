"""フロア生成（可変深度×あみだくじ型格子）— 生成規則の不変条件・敵割当・宝箱/回復配置・tier/深度補正・カオスweight。

形状決め打ちテストは廃止し、ランダム接続でも常に成立すべき不変条件をseed横断で検証する。
"""
import pytest

from app.engine import chaos_weights as cw
from app.engine.floor_generator import (
    _multi_drop_chance,
    build_enemy_instance,
    generate_floor,
    validate_floor,
)
from app.engine.rng import STREAM_CHAOS, GameRNG


def gen(floor_number, seed=0):
    return generate_floor(floor_number, _DATA, GameRNG(seed))


@pytest.fixture(autouse=True)
def _bind(data):
    global _DATA
    _DATA = data


def _mains_by_row(fl):
    rows: dict[int, list] = {}
    for n in fl.nodes.values():
        if n.kind == "enemy":
            rows.setdefault(n.row, []).append(n)
    return rows


# ── 1F 固定レイアウト ──
def test_floor1_fixed_layout(data):
    fl = gen(1)
    assert fl.node("L").enemy_id == "f1_fixed_a"
    assert fl.node("M").enemy_id == "f1_fixed_b"
    assert fl.node("R").enemy_id == "f1_fixed_c"
    # A = 反射確定宝箱
    a = fl.node("A")
    assert a.kind == "treasure"
    assert a.has_treasure is True
    assert a.fixed_mod == "hansha"
    # B,C は gate_route
    assert fl.node("B").kind == "gate_route"
    assert fl.node("C").kind == "gate_route"
    # 回復なし
    assert not any(n.kind == "heal" for n in fl.nodes.values())


# ── 生成規則の不変条件 ──
def test_generated_floor_depth_matches_config(data):
    for fn in (2, 3, 4, 5):
        fl = gen(fn, seed=fn)
        depth = data.floor(fn)["depth"]
        rows = _mains_by_row(fl)
        assert max(rows) == depth
        assert fl.node("GATE").row == depth + 1


def test_row_widths_within_bounds(data):
    for seed in range(20):
        fl = gen(4, seed=seed)
        rows = {r: len(ns) for r, ns in _mains_by_row(fl).items()}
        assert rows[1] == 3  # 開幕は3択固定
        widths = [rows[r] for r in sorted(rows)]
        for r, w in rows.items():
            if r > 1:
                assert 2 <= w <= 3
        for a, b in zip(widths, widths[1:]):
            assert abs(a - b) <= 1  # 幅の変化は±1（分岐/合流の格子）
        assert widths[-1] >= 2      # 最終rowは≥2＝GATEへ最低2本


def test_multi_parents_are_adjacent_lattice(data):
    # 多親は「1つ前のrowの隣接2ノード」＝あみだくじの窓
    for seed in range(20):
        fl = gen(3, seed=seed)
        for n in fl.nodes.values():
            if n.kind == "enemy" and n.parent_type == "multi":
                rows = {int(p.split("_")[0][1:]) for p in n.parents}
                cols = sorted(int(p.split("_")[1]) for p in n.parents)
                assert rows == {n.row - 1}
                assert cols[1] == cols[0] + 1


def test_unlock_arity_multi_single(data):
    for fn in (2, 3, 4, 5):
        fl = gen(fn, seed=fn)
        for n in fl.nodes.values():
            if n.parent_type == "multi" and n.id != "GATE":
                assert len(n.parents) == 2
            elif n.parent_type == "single":
                assert len(n.parents) == 1


def test_dead_end_always_single(data):
    for fn in (1, 2, 3, 4, 5):
        fl = gen(fn, seed=fn)
        for n in fl.nodes.values():
            if n.kind in ("treasure", "heal") and n.parents:
                assert n.parent_type == "single"


def test_all_nodes_reachable_and_valid(data):
    # validate_floor は生成のたびに呼ばれるが、明示的にも全フロア×複数seedで検証
    for fn in (1, 2, 3, 4, 5):
        for seed in range(10):
            validate_floor(gen(fn, seed=seed), data)


def test_gate_parents_are_final_row_mains(data):
    fl = gen(4, seed=9)
    depth = data.floor(4)["depth"]
    finals = {n.id for n in fl.nodes.values() if n.kind == "enemy" and n.row == depth}
    assert set(fl.node("GATE").parents) == finals
    assert len(finals) >= 2


def test_topology_varies_between_seeds(data):
    sigs = set()
    for seed in range(12):
        fl = gen(5, seed=seed)
        sigs.add(tuple(sorted((n.id, tuple(n.parents)) for n in fl.nodes.values())))
    assert len(sigs) > 1  # 接続（エッジ）そのものが毎回同じ形にならない


def test_deterministic_same_seed(data):
    a = gen(4, seed=42)
    b = gen(4, seed=42)
    sig = lambda fl: {k: (n.kind, n.enemy_id, tuple(n.parents)) for k, n in fl.nodes.items()}
    assert sig(a) == sig(b)


# ── 敵割当 ──
def test_enemies_from_merged_pool(data):
    for fn in (2, 5):
        fl = gen(fn, seed=1)
        pool = set(data.floor(fn)["enemy_pool"])
        for n in fl.nodes.values():
            if n.kind == "enemy":
                assert n.enemy_id in pool


def test_no_duplicate_enemy_within_row(data):
    # プール枯渇時はフロア内の重複再登場を許すが、同一row内では重複しない
    for seed in range(20):
        for fn in (2, 5):
            for ids in ((
                [n.enemy_id for n in ns]) for ns in _mains_by_row(gen(fn, seed=seed)).values()):
                assert len(ids) == len(set(ids))


def test_row_experience_constraint_all_rows(data):
    for seed in range(30):
        fl = gen(3, seed=seed)
        for ns in _mains_by_row(fl).values():
            exps = [data.enemy(n.enemy_id)["experience"] for n in ns]
            for ex in set(exps):
                assert exps.count(ex) <= 2


def test_final_row_has_non_chaos(data):
    for seed in range(30):
        fl = gen(5, seed=seed)
        depth = data.floor(5)["depth"]
        last = [n for n in fl.nodes.values() if n.kind == "enemy" and n.row == depth]
        assert any(not data.enemy(n.enemy_id).get("chaos") for n in last)


# ── 回復配置 ──
def test_heal_exactly_one_on_heal_floors(data):
    f1 = gen(1)
    assert sum(1 for n in f1.nodes.values() if n.kind == "heal") == 0
    for fn in (2, 3, 4):
        for seed in range(10):
            fl = gen(fn, seed=seed)
            assert sum(1 for n in fl.nodes.values() if n.kind == "heal") == 1
    for seed in range(10):
        f5 = gen(5, seed=seed)
        assert sum(1 for n in f5.nodes.values() if n.kind == "heal") == 0


# ── tier/深度 補正 ──
def test_tier_hp_scaling(data):
    inst = build_enemy_instance("f2_r1_a", 2, data)  # base 45, tier2, row1
    assert inst.max_hp == round(45 * 1.10)
    inst5 = build_enemy_instance("f5_r1_a", 5, data)  # base 100, tier5
    assert inst5.max_hp == round(100 * (1 + 0.10 * 4))


def test_depth_scaled_hp(data):
    per = data.config["depth_scaling"]["hp_per_row"]
    deep = build_enemy_instance("f2_r1_a", 2, data, row=3)
    assert deep.max_hp == round(45 * 1.10 * (1 + per * 2))


def test_strong_flag(data):
    assert build_enemy_instance("f3_r2_b", 3, data).is_strong is True
    assert build_enemy_instance("f2_r1_a", 2, data).is_strong is False


# ── カオス weight ──
def test_chaos_weights_sum_100(data):
    rng = GameRNG(11)
    weights = cw.generate_all(rng.stream(STREAM_CHAOS), ["f3_r2_e", "f5_r2_d"])
    for eid, dist in weights.items():
        assert sum(w for _, w in dist) == 100
        assert all(w >= 5 for _, w in dist)
        assert {t for t, _ in dist} == set(cw.CHAOS_TYPES)


def test_chaos_consistent_within_run_varies_between(data):
    w1 = cw.generate_all(GameRNG(1).stream(STREAM_CHAOS), ["f3_r2_e"])
    w1b = cw.generate_all(GameRNG(1).stream(STREAM_CHAOS), ["f3_r2_e"])
    w2 = cw.generate_all(GameRNG(2).stream(STREAM_CHAOS), ["f3_r2_e"])
    assert w1 == w1b              # 同seed→同分布
    assert w1 != w2              # 別seed→別分布（ほぼ確実）


def test_chaos_enemy_instance_uses_weights(data):
    rng = GameRNG(3)
    weights = cw.generate_all(rng.stream(STREAM_CHAOS), ["f3_r2_e"])
    inst = build_enemy_instance("f3_r2_e", 3, data, weights)
    assert inst.chaos is True
    assert sum(w for _, w in inst.behaviors) == 100


# ── 撃破ドロップ（多親×enemy・GDD §11.4）──
def test_multi_parent_enemy_drop_floor2(data):
    drops = total = 0
    saw_true = saw_false = False
    for seed in range(120):
        fl = gen(2, seed)
        for n in fl.nodes.values():
            if n.kind == "enemy" and n.parent_type == "multi":
                total += 1
                if n.has_treasure:
                    drops += 1
                    saw_true = True
                else:
                    saw_false = True
    assert saw_true and saw_false           # 確率機構として両方起きる
    rate = drops / total
    assert 0.18 < rate < 0.45               # 2F敵は非強敵 → 約30%


def test_no_multi_drop_on_floor1(data):
    # 1F は固定宝箱(A)のみ。多親enemyドロップは発生しない。
    for seed in range(20):
        fl = gen(1, seed)
        treasured = sorted(k for k, n in fl.nodes.items() if n.has_treasure)
        assert treasured == ["A"]


def test_strong_enemy_higher_drop_chance(data):
    # 強敵は +20pt（rate比較は接続ランダム化で不安定になるため確率値そのものを検証）
    assert _multi_drop_chance("f3_r2_b", data) == pytest.approx(
        _multi_drop_chance("f2_r1_a", data) + 0.20)
