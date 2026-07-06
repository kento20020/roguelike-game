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


def _all_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_keys(v)


def test_seed_not_exposed_while_running(data):
    """§17.3 seed非露出: 進行中は run_record=null・seed/rng_streams/chaos_weights を出さない（seed-scum防止）。"""
    eng = GameEngine(data)
    snap = eng.new_run(5)
    assert snap["run_record"] is None
    keys = set(_all_keys(snap))
    assert "seed" not in keys and "rng_streams" not in keys and "chaos_weights" not in keys
    eng.select_node("L")
    snap2 = eng.snapshot()
    assert snap2["run_record"] is None
    keys2 = set(_all_keys(snap2))
    assert "seed" not in keys2 and "rng_streams" not in keys2 and "chaos_weights" not in keys2


def test_run_record_disclosed_only_at_terminal(data):
    snap = auto_play(GameEngine(data), seed=3)
    assert snap["phase"] in ("cleared", "dead")
    assert snap["run_record"]["seed"] == 3


def test_victory_never_leaves_player_at_zero_hp(data):
    """OPEN-010: 相打ち（勝利優先）でHP0のまま生存しない（勝利時 hp=max(1,hp)）。"""
    from app.engine import combat_resolver as cr
    from app.engine.rng import STREAM_BEHAVIOR

    eng = GameEngine(data)
    eng.new_run(1)
    eng.select_node("L")
    b = eng.battle
    b.enemy.hp = 1      # 次の一撃で確実に倒せる
    eng.player.hp = 1   # 反撃を受ければ 0 以下になる
    res = cr.resolve_turn(b, eng.player, data, eng.rng.stream(STREAM_BEHAVIOR),
                          forced_action="counter")
    assert res["enemy_dead"] is True
    assert res["player_dead"] is False
    assert eng.player.hp >= 1
