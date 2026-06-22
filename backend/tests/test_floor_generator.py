"""フロア生成・アンロック・敵割当・宝箱/回復配置・tier補正・カオスweight。"""
import pytest

from app.engine import chaos_weights as cw
from app.engine.floor_generator import build_enemy_instance, generate_floor
from app.engine.rng import STREAM_CHAOS, GameRNG


def gen(floor_number, seed=0):
    return generate_floor(floor_number, _DATA, GameRNG(seed))


@pytest.fixture(autouse=True)
def _bind(data):
    global _DATA
    _DATA = data


# ── 構造 ──
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
    # B,C は gate_route（row2_pool 空）
    assert fl.node("B").kind == "gate_route"
    assert fl.node("C").kind == "gate_route"
    # 回復なし
    assert not any(n.kind == "heal" for n in fl.nodes.values())


def test_floor2_shape_A(data):
    fl = gen(2, seed=3)
    # L/M/R 敵、B/C 敵（gate route）、A/D は dead-end
    assert fl.node("B").kind == "enemy"
    assert fl.node("C").kind == "enemy"
    for k in ("A", "D"):
        assert fl.node(k).parent_type == "single"
        assert fl.node(k).kind in ("treasure", "heal")
    # GATE 親は B,C
    assert set(fl.node("GATE").parents) == {"B", "C"}


def test_unlock_arity_multi_single(data):
    for fn in (2, 3, 4, 5):
        fl = gen(fn, seed=fn)
        for n in fl.nodes.values():
            if n.parent_type == "multi" and n.id != "GATE":
                assert len(n.parents) == 2
            elif n.parent_type == "single":
                assert len(n.parents) == 1


def test_dead_end_always_single(data):
    # treasure/heal ノードは必ず単親
    for fn in (1, 2, 3, 4, 5):
        fl = gen(fn, seed=fn)
        for n in fl.nodes.values():
            if n.kind in ("treasure", "heal"):
                assert n.parent_type == "single"


def test_heal_at_most_one_and_not_floor1(data):
    f1 = gen(1)
    assert sum(1 for n in f1.nodes.values() if n.kind == "heal") == 0
    for fn in (2, 3, 4):
        fl = gen(fn, seed=fn)
        assert sum(1 for n in fl.nodes.values() if n.kind == "heal") <= 1
    # 5F は heal なし
    f5 = gen(5, seed=5)
    assert sum(1 for n in f5.nodes.values() if n.kind == "heal") == 0


def test_floor5_shape_D(data):
    fl = gen(5, seed=7)
    for k in ("X", "Y", "Z"):
        assert fl.node(k).kind == "enemy"
        assert fl.node(k).row == 3
    # GATE 親は row3 の multi（X,Y,Z）
    assert set(fl.node("GATE").parents) == {"X", "Y", "Z"}


def test_row2_experience_constraint(data):
    # row2 enemy の同一体験は2体以下（複数 seed で確認）
    for seed in range(30):
        fl = gen(3, seed=seed)
        exps = [data.enemy(n.enemy_id)["experience"]
                for n in fl.nodes.values() if n.row == 2 and n.kind == "enemy"]
        for ex in set(exps):
            assert exps.count(ex) <= 2


def test_row1_enemies_from_pool(data):
    fl = gen(3, seed=1)
    pool = set(data.floor(3)["row1_pool"])
    assert {fl.node(k).enemy_id for k in ("L", "M", "R")} == pool


def test_deterministic_same_seed(data):
    a = gen(4, seed=42)
    b = gen(4, seed=42)
    sig = lambda fl: {k: (n.kind, n.enemy_id) for k, n in fl.nodes.items()}
    assert sig(a) == sig(b)


# ── tier 補正 ──
def test_tier_hp_scaling(data):
    inst = build_enemy_instance("f2_r1_a", 2, data)  # base 45, tier2
    assert inst.max_hp == round(45 * 1.15)
    inst5 = build_enemy_instance("f5_r1_a", 5, data)  # base 100, tier5
    assert inst5.max_hp == round(100 * (1 + 0.15 * 4))


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


def test_strong_multi_enemy_higher_drop(data):
    # 5F row3 は difficulty 5 の強敵のみ → ドロップ率は 50% 寄り。
    drops = total = 0
    for seed in range(120):
        fl = gen(5, seed)
        for k in ("X", "Y", "Z"):
            n = fl.nodes.get(k)
            if n and n.kind == "enemy" and n.parent_type == "multi":
                total += 1
                if n.has_treasure:
                    drops += 1
    assert total > 0
    assert drops / total > 0.30
