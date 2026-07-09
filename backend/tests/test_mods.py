"""6mod の効果・スタック・3 interactions。"""
from app.engine import combat_resolver as cr
from app.engine.rng import Sfc32
from app.schemas.models import (
    HANSHA,
    JUSO,
    KASOKU,
    KOUKI,
    MIKIRI,
    YOMI,
    Battle,
    EnemyInstance,
    Player,
)

DUMMY = Sfc32(0)


def make_enemy(hp=50, attack=10, behaviors=None, heavy_factor=1.8,
               counter_factor=1.0, ramp_increment=0, chaos=False):
    return EnemyInstance(
        id="t", name="敵", experience="grind", max_hp=hp, hp=hp, attack=attack,
        difficulty=2, gold_base=10, chaos=chaos,
        behaviors=behaviors if behaviors is not None else [("counter", 100)],
        ramp_increment=ramp_increment, heavy_factor=heavy_factor,
        counter_factor=counter_factor, is_strong=False,
    )


def mk(enemy, hp=100, attack=15, mods=None):
    p = Player(hp=hp, max_hp=100, attack=attack, chips=50, mods=list(mods or []))
    b = Battle(enemy=enemy, node_id="L", floor=2)
    return p, b


# ── 重装甲 (juso) ──
def test_juso_reduces_counter(data):
    e = make_enemy(attack=20)
    p, b = mk(e, mods=[JUSO])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER)
    # base 20, cap=20*0.5=10, reduction=min(4,10)=4 → incoming 16
    assert r["reduction"] == 4
    assert r["incoming"] == 16


def test_juso_stack_reduces_more(data):
    e = make_enemy(attack=20)
    p, b = mk(e, mods=[JUSO, JUSO])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER)
    # value_stack 8, cap 10 → reduction 8 → incoming 12
    assert r["reduction"] == 8
    assert r["incoming"] == 12


def test_juso_capped_at_half_base(data):
    e = make_enemy(attack=6)                 # counter base 6
    p, b = mk(e, mods=[JUSO])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER)
    # cap = 6*0.5 = 3 → reduction min(4,3)=3 → incoming 3
    assert r["reduction"] == 3
    assert r["incoming"] == 3


def test_juso_does_not_apply_to_ramp(data):
    e = make_enemy(attack=10, behaviors=[("ramp_hit", 100)], ramp_increment=2)
    p, b = mk(e, mods=[JUSO])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.RAMP_HIT)
    assert r["reduction"] == 0               # ramp_hit は軽減対象外


# ── 反射 (hansha) ──
def test_hansha_reflects_on_counter(data):
    e = make_enemy(hp=50, attack=10)
    p, b = mk(e, mods=[HANSHA])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER)
    # enemy.hp 50 - dealt 15 - reflect 5 = 30
    assert r["reflect"] == 5
    assert e.hp == 30


def test_hansha_stack(data):
    e = make_enemy(hp=50, attack=10)
    p, b = mk(e, mods=[HANSHA, HANSHA])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER)
    assert r["reflect"] == 10
    assert e.hp == 25


def test_hansha_can_kill(data):
    e = make_enemy(hp=18, attack=10)         # 18 - 15 = 3, reflect 5 → dead
    p, b = mk(e, mods=[HANSHA])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER)
    assert r["enemy_dead"] is True
    assert e.hp == 0


def test_hansha_not_on_heavy(data):
    e = make_enemy(hp=50, attack=10)
    p, b = mk(e, mods=[HANSHA])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY)
    assert r["reflect"] == 0                  # counter 限定


# ── 見切り (mikiri) ──
def test_mikiri_halves_evade_weight(data):
    e = make_enemy(behaviors=[("evade", 60), ("counter", 40)])
    p = Player(hp=100, max_hp=100, attack=15, chips=50, mods=[MIKIRI])
    eff = cr.effective_behaviors(p, e)
    assert dict(eff)["evade"] == 30           # 60 * 0.5
    assert dict(eff)["counter"] == 40


def test_mikiri_stack_zeroes_evade(data):
    e = make_enemy(behaviors=[("evade", 60), ("counter", 40)])
    p = Player(hp=100, max_hp=100, attack=15, chips=50, mods=[MIKIRI, MIKIRI])
    eff = cr.effective_behaviors(p, e)
    assert dict(eff)["evade"] == 0
    # 実際にロールしても evade は出ない
    for i in range(50):
        assert cr.roll_behavior(eff, Sfc32(i)) != "evade"


# ── 加速止め (kasoku) ──
def test_kasoku_halves_ramp_increment(data):
    e = make_enemy(attack=10, behaviors=[("ramp_hit", 100)], ramp_increment=4)
    p, b = mk(e, mods=[KASOKU])
    cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.RAMP_HIT)   # turn1 = 5
    r2 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.RAMP_HIT)  # turn2
    # eff_inc = 4*0.5 = 2 → ramp = 5 + 2 = 7
    assert r2["ramp_value"] == 7


def test_kasoku_stack_zeroes_growth(data):
    e = make_enemy(attack=10, behaviors=[("ramp_hit", 100)], ramp_increment=4)
    p, b = mk(e, mods=[KASOKU, KASOKU])
    cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.RAMP_HIT)
    r2 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.RAMP_HIT)
    assert r2["ramp_value"] == 5               # 増えない


# ── 好機 (kouki) ──
def test_kouki_extra_attack_on_heavy(data):
    e = make_enemy(hp=100, attack=10)
    p, b = mk(e, mods=[KOUKI])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY)
    assert r["extra"] == 15                    # 追撃 = attack
    assert e.hp == 100 - 15 - 15               # dealt + extra


def test_kouki_single_has_cooldown(data):
    e = make_enemy(hp=300, attack=10)
    p, b = mk(e, mods=[KOUKI])
    r1 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY)
    assert r1["extra"] == 15
    r2 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY)
    assert r2["extra"] == 0                    # CD 中
    r3 = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY)
    assert r3["extra"] == 15                    # 1ターン空けて再発


def test_kouki_stack_no_cooldown(data):
    e = make_enemy(hp=400, attack=10)
    p, b = mk(e, mods=[KOUKI, KOUKI])
    for _ in range(3):
        r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY)
        assert r["extra"] == 15                # 毎ターン発動


def test_kouki_extra_can_kill(data):
    e = make_enemy(hp=25, attack=10)           # 25 -15(dealt) -15(extra) < 0
    p, b = mk(e, mods=[KOUKI])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY)
    assert r["enemy_dead"] is True


# ── 先読み (yomi) ──
def test_yomi_pre_rolls_and_consumes(data):
    e = make_enemy(behaviors=[("counter", 100)])
    p, b = mk(e, mods=[YOMI])
    stream = Sfc32(5)
    cr.prepare_preview(b, p, data, stream)
    assert b.pending_action == "counter"
    assert b.preview is not None
    r = cr.resolve_turn(b, p, data, DUMMY)     # pending を消費（DUMMYは使われない）
    assert r["action"] == "counter"
    assert b.pending_action is None


def test_yomi_single_only_turn1(data):
    """yomi 1枚は本来turn1のみ公開。tell_system フラグは「常に先引き」する試作仕様なので、
    このテストの意図（1枚ならturn2は非公開）を保つには明示的にOFFにして検証する。
    """
    prev_flag = data.config.get("feature_flags", {}).get("tell_system")
    data.config.setdefault("feature_flags", {})["tell_system"] = False
    try:
        e = make_enemy(behaviors=[("counter", 100)])
        p, b = mk(e, mods=[YOMI])
        cr.prepare_preview(b, p, data, Sfc32(5))
        cr.resolve_turn(b, p, data, DUMMY)         # turn1 完了
        cr.prepare_preview(b, p, data, Sfc32(5))   # turn2: 公開しない
        assert b.pending_action is None
    finally:
        data.config["feature_flags"]["tell_system"] = prev_flag


def test_yomi_stack_two_turns(data):
    e = make_enemy(behaviors=[("counter", 100)])
    p, b = mk(e, mods=[YOMI, YOMI])
    cr.prepare_preview(b, p, data, Sfc32(5))
    assert b.pending_action == "counter"
    cr.resolve_turn(b, p, data, DUMMY)
    cr.prepare_preview(b, p, data, Sfc32(5))   # turn2 も公開
    assert b.pending_action == "counter"


# ── テル試作 (feature_flags.tell_system) ──
def test_tell_system_flag_previews_turn1_without_yomi(data):
    """フラグON時、yomi未所持でもturn1でpending_actionがセットされる（既存roll_behaviorと同じ経路）。"""
    prev_flag = data.config.get("feature_flags", {}).get("tell_system")
    data.config.setdefault("feature_flags", {})["tell_system"] = True
    try:
        e = make_enemy(behaviors=[("counter", 100)])
        p, b = mk(e, mods=[])                      # yomi 無し
        cr.prepare_preview(b, p, data, Sfc32(5))
        assert b.pending_action == "counter"
        assert b.preview is not None
    finally:
        data.config["feature_flags"]["tell_system"] = prev_flag


def test_tell_system_flag_does_not_shrink_existing_yomi_preview(data):
    """フラグONでも既存yomi所持者のpreview_turnsは既存値以上になるだけ（縮まない）。

    yomi 2枚（preview_turns=2）保持時、フラグONでもturn1・turn2いずれも変わらず公開される。
    """
    prev_flag = data.config.get("feature_flags", {}).get("tell_system")
    data.config.setdefault("feature_flags", {})["tell_system"] = True
    try:
        e = make_enemy(behaviors=[("counter", 100)])
        p, b = mk(e, mods=[YOMI, YOMI])
        cr.prepare_preview(b, p, data, Sfc32(5))
        assert b.pending_action == "counter"
        cr.resolve_turn(b, p, data, DUMMY)
        cr.prepare_preview(b, p, data, Sfc32(5))   # turn2 も公開（yomi 2枚分は維持）
        assert b.pending_action == "counter"
    finally:
        data.config["feature_flags"]["tell_system"] = prev_flag


# ── interactions ──
def test_hansha_juso_synergy_both_apply(data):
    # counter: 重装甲で軽減しつつ反射も返す
    e = make_enemy(hp=50, attack=20)
    p, b = mk(e, mods=[HANSHA, JUSO])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER)
    assert r["reduction"] == 4                 # 重装甲
    assert r["incoming"] == 16
    assert r["reflect"] == 5                    # 反射
    assert e.hp == 50 - 15 - 5


def test_mikiri_yomi_cancel_never_reveals_evade(data):
    # 見切り×先読み: evade weight 0 なので先読みは evade を出さない
    e = make_enemy(behaviors=[("evade", 80), ("counter", 20)])
    p = Player(hp=100, max_hp=100, attack=15, chips=50, mods=[MIKIRI, MIKIRI, YOMI])
    for i in range(40):
        b = Battle(enemy=make_enemy(behaviors=[("evade", 80), ("counter", 20)]),
                   node_id="L", floor=2)
        cr.prepare_preview(b, p, data, Sfc32(i))
        assert b.pending_action != "evade"


def test_mikiri_kouki_coexist(data):
    # 見切り×好機: 共存し、heavy で好機が発動する
    e = make_enemy(hp=100, attack=10, behaviors=[("evade", 50), ("heavy_blow", 50)])
    p, b = mk(e, mods=[MIKIRI, KOUKI])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.HEAVY)
    assert r["extra"] == 15


# ── ガード（受け・ジャストガード）──
def test_guard_reduces_incoming_and_dealt(data):
    e = make_enemy(hp=100, attack=20)
    p, b = mk(e, attack=20)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER, guard=True)
    assert e.hp == 90                       # dealt 20*0.5 = 10
    assert r["incoming"] == 10              # counter 20 → 軽減50% = 10
    assert p.hp == 90


def test_guard_does_not_consume_boost(data):
    e = make_enemy(hp=100, attack=10)
    p, b = mk(e, attack=20)
    p.attack_boost_pending = True
    cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.NONE, guard=True)
    assert p.attack_boost_pending is True   # ガードでは消費しない


def test_guard_none_action_no_incoming(data):
    e = make_enemy(hp=100, attack=10)
    p, b = mk(e, attack=20)
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.NONE, guard=True)
    assert r["incoming"] == 0
    assert e.hp == 90                       # dealt 20*0.5


def test_guard_with_juso_stacks(data):
    # 重装甲(-4)後に guard 軽減率（counter 50%）を乗算
    e = make_enemy(hp=100, attack=20)
    p, b = mk(e, attack=20, mods=[JUSO])
    r = cr.resolve_turn(b, p, data, DUMMY, forced_action=cr.COUNTER, guard=True)
    # base 20 - juso 4 = 16 → ×0.5 = 8
    assert r["incoming"] == 8
