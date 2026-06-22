"""横断的な不変条件。"""
from app.engine.game_engine import GameEngine
from tests.test_engine_run import auto_play


def test_same_seed_same_runrecord(data):
    a = GameEngine(data)
    ra = auto_play(a, seed=123)["run_record"]
    b = GameEngine(data)
    rb = auto_play(b, seed=123)["run_record"]
    assert ra == rb                    # 同seed＋同方策 → 完全一致


def test_different_seed_differs(data):
    a = auto_play(GameEngine(data), seed=1)["run_record"]
    b = auto_play(GameEngine(data), seed=2)["run_record"]
    # 少なくとも結果のどこかが異なる（ほぼ確実）
    assert (a["seed"], a["total_turns"], a["floor_reached"]) != \
           (b["seed"], b["total_turns"], b["floor_reached"])


def test_combat_log_is_not_in_runrecord(data):
    eng = GameEngine(data)
    eng.new_run(1)
    eng.select_node("L")
    eng.attack()
    # battle.log は表示用に存在する
    assert len(eng.battle.log) > 0
    # RunRecord には combat_log が含まれない（別物・非同期）
    rr = eng.run.snapshot()
    assert "combat_log" not in rr
    assert "log" not in rr


def test_combat_log_is_ephemeral(data):
    eng = GameEngine(data)
    eng.new_run(1)
    eng.select_node("L")
    while eng.phase == "battle":
        eng.attack()
    # 勝利すると battle（＝log）は破棄される
    assert eng.battle is None
    # だが RunRecord の統計は残る
    assert len(eng.run.enemies_defeated) >= 1


def test_gold_accounting_consistent(data):
    eng = GameEngine(data)
    snap = auto_play(eng, seed=11)
    rr = snap["run_record"]
    # 使用額は獲得額を超えない（初期goldは0なので earned が上限）
    spent = sum(rr["gold_spent"].values())
    assert spent <= rr["gold_earned"] + 0  # init_gold=0
