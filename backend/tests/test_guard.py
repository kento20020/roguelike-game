"""ジャストガード＋重ねがけ減衰（OPEN-018 再設計・docs/proposals/guard_redesign.md）。

- 軽減率は敵の実際の行動に連動: heavy 90% / counter 50% / ramp_hit 50% / none·evade 0%（空振り）
- 同一戦闘内で使うたび軽減量が stack_decay(0.5) 倍に減衰（ゲート保証の重ねがけ半減と同哲学）
- 空振りも減衰カウントに含める（count_whiff=true）
- 与ダメ側（deal_factor 0.5・boost 非消費）と「重装甲→guard」の適用順は従来仕様を維持
"""

from app.engine import combat_resolver as cr
from app.engine.rng import Sfc32
from app.schemas.models import HANSHA, JUSO, KOUKI, Battle, EnemyInstance, Player


def make_enemy(hp=100, attack=20, behaviors=None, heavy_factor=1.8,
               counter_factor=1.0, ramp_increment=0, chaos=False):
    return EnemyInstance(
        id="t", name="敵", experience="grind", max_hp=hp, hp=hp, attack=attack,
        difficulty=2, gold_base=10, chaos=chaos,
        behaviors=behaviors if behaviors is not None else [("counter", 100)],
        ramp_increment=ramp_increment, heavy_factor=heavy_factor,
        counter_factor=counter_factor, is_strong=False,
    )


def make_player(hp=100, attack=20, mods=None, chips=50):
    return Player(hp=hp, max_hp=100, attack=attack, chips=chips, mods=list(mods or []))


def make_battle(enemy):
    return Battle(enemy=enemy, node_id="L", floor=2)


DUMMY = Sfc32(0)


# ── ジャストガード: 行動連動の軽減率 ──
def test_just_guard_heavy_90pct(data):
    e = make_enemy(attack=20)                   # heavy: 20*1.8 = 36
    p = make_player()
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY, guard=True)
    assert r["incoming"] == 4                   # round(36 * (1-0.9)) = round(3.6)
    assert p.hp == 96
    assert r["dealt"] == 10                     # 与ダメ 20*0.5（据え置き）
    assert b.guard_uses == 1


def test_just_guard_counter_50pct(data):
    e = make_enemy(attack=20)                   # counter: 20*1.0 = 20
    p = make_player()
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER, guard=True)
    assert r["incoming"] == 10                  # round(20 * 0.5)
    assert p.hp == 90


def test_just_guard_ramp_50pct(data):
    e = make_enemy(behaviors=[("ramp_hit", 100)], ramp_increment=2)
    p = make_player()
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.RAMP_HIT, guard=True)
    assert r["ramp_value"] == 5                 # turn1: base_initial
    assert r["incoming"] == 2                   # round(5 * 0.5) = round(2.5) = 2（偶数丸め）


def test_guard_whiff_none_costs_deal_only(data):
    # 空振り: 軽減対象なし・与ダメ半減のコストだけ払う。減衰カウントには含まれる。
    e = make_enemy()
    p = make_player()
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.NONE, guard=True)
    assert r["incoming"] == 0
    assert r["dealt"] == 10
    assert b.guard_uses == 1


# ── 重ねがけ減衰 ──
def test_stack_decay_second_use_halves_mitigation(data):
    e = make_enemy(hp=1000, attack=20)
    p = make_player(hp=100)
    b = make_battle(e)
    r1 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY, guard=True)
    assert r1["incoming"] == 4                  # 1回目: 軽減90%
    r2 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY, guard=True)
    assert r2["incoming"] == 20                 # 2回目: 軽減45% → round(36*0.55) = round(19.8)
    assert b.guard_uses == 2


def test_whiff_counts_toward_decay(data):
    # 空振り(none)の後の guard は2回目扱い（count_whiff=true）
    e = make_enemy(hp=1000, attack=20)
    p = make_player(hp=100)
    b = make_battle(e)
    cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.NONE, guard=True)
    r2 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY, guard=True)
    assert r2["incoming"] == 20                 # 軽減45%


def test_decay_resets_between_battles(data):
    p = make_player(hp=100)
    b1 = make_battle(make_enemy(hp=1000, attack=20))
    cr.resolve_turn(b1, p, data, DUMMY, forced_action=cr.HEAVY, guard=True)
    cr.resolve_turn(b1, p, data, DUMMY, forced_action=cr.HEAVY, guard=True)
    b2 = make_battle(make_enemy(hp=1000, attack=20))  # 新しい戦闘 → カウンタ 0 から
    r = cr.resolve_turn(b2, p, data, DUMMY, forced_action=cr.HEAVY, guard=True)
    assert r["incoming"] == 4                   # 軽減90%に戻る


def test_attack_turns_do_not_increment_guard_uses(data):
    e = make_enemy(attack=20)
    p = make_player()
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY, guard=False)
    assert b.guard_uses == 0
    assert r["incoming"] == 36                  # 非guardは従来どおり素通し


# ── 既存メカニクスとの相互作用（従来仕様の維持） ──
def test_juso_applies_before_guard(data):
    # 重装甲(-4)の軽減後に guard 軽減率を乗算
    e = make_enemy(attack=20)                   # heavy 36
    p = make_player(mods=[JUSO])
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY, guard=True)
    # base 36 - juso 4 = 32 → round(32 * 0.1) = 3
    assert r["reduction"] == 4
    assert r["incoming"] == 3


def test_reflect_fires_under_guard(data):
    e = make_enemy(hp=100, attack=20)
    p = make_player(mods=[HANSHA])
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER, guard=True)
    assert r["reflect"] == 5                    # counter 被弾時の反射は guard 中も発動
    assert e.hp == 100 - 10 - 5                 # dealt 10 + 反射 5


def test_kouki_fires_under_guard(data):
    # 「heavy をジャストで受けつつ好機の追撃」は読み勝ちの意図的シナジー
    e = make_enemy(hp=100, attack=20)
    p = make_player(mods=[KOUKI])
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY, guard=True)
    assert r["extra"] == 20                     # 追撃はフル火力（deal_factor が乗らない）


def test_guard_does_not_consume_boost(data):
    e = make_enemy()
    p = make_player()
    p.attack_boost_pending = True
    b = make_battle(e)
    cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.NONE, guard=True)
    assert p.attack_boost_pending is True
