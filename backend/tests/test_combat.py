"""戦闘1ターンの各行動・ダメージ式・boost・ramp。forced_action で決定論的に検証。"""
import pytest

from app.engine import combat_resolver as cr
from app.engine.rng import Sfc32
from app.schemas.models import Battle, EnemyInstance, Player


def make_enemy(hp=50, attack=10, behaviors=None, heavy_factor=1.8,
               counter_factor=1.0, ramp_increment=0, chaos=False):
    return EnemyInstance(
        id="t", name="敵", experience="grind", max_hp=hp, hp=hp, attack=attack,
        difficulty=2, gold_base=10, chaos=chaos,
        behaviors=behaviors if behaviors is not None else [("counter", 100)],
        ramp_increment=ramp_increment, heavy_factor=heavy_factor,
        counter_factor=counter_factor, is_strong=False,
    )


def make_player(hp=100, attack=15, mods=None, chips=50, boost=False):
    return Player(hp=hp, max_hp=100, attack=attack, chips=chips,
                  mods=list(mods or []), attack_boost_pending=boost)


def make_battle(enemy):
    return Battle(enemy=enemy, node_id="L", floor=2)


DUMMY = Sfc32(0)


def test_none_action(data):
    e = make_enemy(hp=50, attack=10)
    p = make_player(attack=15)
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.NONE)
    assert e.hp == 35           # 50 - 15
    assert p.hp == 100          # 無被弾
    assert r["incoming"] == 0
    assert r["enemy_dead"] is False


def test_counter_uses_counter_factor(data):
    e = make_enemy(hp=50, attack=10, counter_factor=1.0)
    p = make_player(attack=15)
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER)
    assert e.hp == 35
    assert p.hp == 90           # 100 - round(10*1.0)
    assert r["incoming"] == 10


def test_heavy_uses_config_default_factor(data):
    e = make_enemy(hp=50, attack=10)            # heavy_factor 既定 1.8
    p = make_player(attack=15)
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY)
    assert r["incoming"] == round(10 * 1.8)     # 18
    assert p.hp == 82


def test_heavy_factor_override(data):
    e = make_enemy(hp=50, attack=10, heavy_factor=2.5)
    p = make_player(attack=15)
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY)
    assert r["incoming"] == 25


def test_evade_cancels_player_damage(data):
    e = make_enemy(hp=50, attack=10)
    p = make_player(attack=15)
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.EVADE)
    assert e.hp == 50           # 与ダメ取り消し
    assert p.hp == 100          # 被ダメ 0
    assert r["incoming"] == 0


def test_ramp_hit_formula(data):
    # base_initial=5, increment=2 → turn1=5, turn2=7
    e = make_enemy(hp=80, attack=10, behaviors=[("ramp_hit", 100)], ramp_increment=2)
    p = make_player(attack=15)
    b = make_battle(e)
    r1 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.RAMP_HIT)
    assert r1["ramp_value"] == 5
    assert r1["incoming"] == 5
    r2 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.RAMP_HIT)
    assert r2["ramp_value"] == 7
    assert r2["incoming"] == 7


def test_attack_boost_doubles_and_consumes(data):
    e = make_enemy(hp=100, attack=10)
    p = make_player(attack=15, boost=True)
    b = make_battle(e)
    r1 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.NONE)
    assert r1["dealt"] == 30                 # 15 * 2.0
    assert p.attack_boost_pending is False   # 消費
    r2 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.NONE)
    assert r2["dealt"] == 15                 # 元に戻る


def test_damage_is_attack_times_multiplier(data):
    # stance=1.0, boostなし → dealt == attack
    e = make_enemy(hp=100, attack=0)
    p = make_player(attack=23)
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.NONE)
    assert r["dealt"] == 23


def test_enemy_death_from_strike(data):
    e = make_enemy(hp=10, attack=10)
    p = make_player(attack=15)
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER)
    assert r["enemy_dead"] is True
    assert e.hp == 0
    # 敵が先に死ねば player_dead にはならない
    assert r["player_dead"] is False


def test_player_death(data):
    e = make_enemy(hp=100, attack=100)
    p = make_player(hp=10, attack=5)
    b = make_battle(e)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY)
    assert r["player_dead"] is True
    assert p.hp == 0


def test_roll_behavior_uses_stream(data):
    # weight [counter 100] → 常に counter
    e = make_enemy(behaviors=[("counter", 100)])
    p = make_player()
    acts = {cr.roll_behavior(e.behaviors, Sfc32(i)) for i in range(20)}
    assert acts == {"counter"}
