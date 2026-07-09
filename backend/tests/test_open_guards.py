"""OPEN-016/017/019/020/021 — 異常系ガードと sink 挙動（docs/operations.md の方針準拠）。"""
import pytest

from app.engine import combat_resolver as cr
from app.engine.game_engine import GameEngine, InvalidMove
from app.engine.rng import STREAM_BEHAVIOR
from tests.test_engine_run import _drive_to_gate_preview

MAXED = {"max_hp": 5, "attack": 5, "init_gold": 5, "gold_drop": 3, "sink_cost": 3}


def _enter_battle(data, seed=1):
    eng = GameEngine(data)
    eng.new_run(seed)
    eng.select_node("L")
    return eng


# ── OPEN-016: ゲート保証は大ダメ0%到達後の重ねがけ不可（400＋非提示） ──

def test_gate_guarantee_blocked_when_major_zero(data):
    eng = _drive_to_gate_preview(data, MAXED)
    assert eng is not None, "20 seed 内で gate_preview に到達できるはず"
    eng.player.chips = 99999
    # 1F は major=0.15 なので保証1回（削減0.25）で 0 に到達する
    eng.use_sink("gate_guarantee")
    assert eng.pending["table"]["major"] <= 1e-9
    with pytest.raises(InvalidMove):
        eng.use_sink("gate_guarantee")
    acts = eng.available_actions()
    assert not any(a.get("sink") == "gate_guarantee" for a in acts)
    # 保証の失敗はカウントされない（状態を汚さない）
    assert eng.gate_guarantee_uses == 1
    assert eng.run.gate_guarantee_stacks == 1


# ── OPEN-017: 確定mod宝箱（1F反射）はリロール不可（400＋非提示） ──

def test_fixed_mod_treasure_cannot_reroll(data):
    eng = GameEngine(data)
    eng.new_run(1)
    eng.select_node("L")
    while eng.phase == "battle":
        eng.attack()
    eng.dismiss()
    eng.select_node("A")  # 1F A = 反射確定宝箱
    assert eng.phase == "treasure_preview"
    eng.player.chips = 9999
    chips_before = eng.player.chips
    with pytest.raises(InvalidMove):
        eng.treasure_reroll()
    assert eng.player.chips == chips_before  # 30G の空費なし
    assert not any(a["type"] == "treasure_reroll" for a in eng.available_actions())
    eng.treasure_open()
    assert "hansha" in eng.player.mods


# ── OPEN-019: sink コストの下限は 1（割引で無料化しない） ──

def test_sink_cost_never_zero(data):
    eng = GameEngine(data)
    eng.new_run(1, upgrades=MAXED)  # sink_cost Lv3 の割引で scout(15G) が 0 になり得た
    assert eng._sink_cost(data.config["sinks"]["scout"]) >= 1


# ── OPEN-021: attack_boost の二重課金禁止＋evade時の持越し ──

def test_attack_boost_double_purchase_rejected(data):
    eng = _enter_battle(data)
    eng.player.chips = 9999
    eng.use_sink("attack_boost")
    assert eng.player.attack_boost_pending is True
    chips_after_buy = eng.player.chips
    with pytest.raises(InvalidMove):
        eng.use_sink("attack_boost")
    assert eng.player.chips == chips_after_buy  # 二重課金なし


def test_attack_boost_carries_over_on_evade(data):
    eng = _enter_battle(data)
    eng.player.chips = 9999
    eng.use_sink("attack_boost")
    b = eng.battle
    b.pending_action = None  # 先読み分を無効化し forced で evade を強制
    res = cr.resolve_turn(b, eng.player, data, eng.rng.stream(STREAM_BEHAVIOR),
                          forced_action="evade")
    assert res["action"] == "evade"
    # 空振りでは消費しない（持越し）— 30G 丸損の禁止
    assert eng.player.attack_boost_pending is True


# ── OPEN-020: battle 中の回復 sink は1ターン消費（敵が動く） ──

def test_heal_in_battle_consumes_turn(data):
    eng = _enter_battle(data)
    eng.player.chips = 9999
    eng.player.hp = 50
    turns_before = eng.battle.turns
    total_before = eng.run.total_turns
    eng.use_sink("heal_small")
    if eng.phase == "battle":
        assert eng.battle.turns == turns_before + 1
    assert eng.run.total_turns == total_before + 1
    last = eng.run.turn_history[-1]
    assert last["player_move"] == "heal_small"
    assert last["dealt"] == 0  # 攻撃は放棄している


def test_heal_in_exploring_does_not_consume_turn(data):
    eng = GameEngine(data)
    eng.new_run(1)
    eng.player.chips = 9999
    eng.player.hp = 50
    total_before = eng.run.total_turns
    eng.use_sink("heal_small")
    assert eng.run.total_turns == total_before
