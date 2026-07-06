"""検死レポート（致命ターンの反実仮想）: GameEngine._compute_postmortem の3分類を検証。

既存 test_combat.py のヘルパーパターン（make_enemy/make_player/make_battle, DUMMY）を踏襲。
forced_action により roll_behavior は呼ばれず RNG ストリームは消費されない前提を利用し、
player.hp/enemy.hp/enemy.attack を調整して各パターンを意図的に再現する。

3パターン:
  (a) unavoidable        — guard反転しても死は避けられない
  (b) avoidable_guard     — 元guard=False致命 → guard=Trueなら生存していた（enemyも生存）
  (c) mutual_kill_victory — 元guard=True致命 → guard=Falseなら相打ちで敵を先に倒せていた
      （"ガードせず攻撃していれば生存していた"側＝guard=True→Falseで敵が生存したまま自分も生存、
      は本ダメージ式では guard を外すと incoming が必ず増加方向のため到達不能。GDDのヒント
      「guard=True→False反転はenemy_deadに転じるmutual_killになる」と整合的なため、テストは
      到達可能な3パターンのみを扱う）。
"""
from app.engine import combat_resolver as cr
from app.engine.game_engine import GameEngine
from app.engine.rng import GameRNG, Sfc32
from app.schemas.models import Battle, EnemyInstance, Player, RunRecord


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


def _make_engine(data, player, battle):
    eng = GameEngine(data)
    eng.rng = GameRNG(0)
    eng.player = player
    eng.battle = battle
    eng.run = RunRecord(run_id="test-run", seed=0)
    return eng


def _play_fatal_turn(eng, guard, action):
    """GameEngine._combat_turn の記録ロジックを模倣: 実ターンを解決し pre_turn_snapshot 付きで
    turn_history に1エントリ積む。"""
    battle, player = eng.battle, eng.player
    pre_snapshot = eng._pre_turn_snapshot()
    res = cr.resolve_turn(battle, player, eng.data, DUMMY, forced_action=action, guard=guard)
    eng.run.turn_history.append({
        "node_id": battle.node_id, "enemy_id": battle.enemy.id, "guard": guard,
        "action": res["action"], "dealt": res["dealt"], "incoming": res["incoming"],
        "player_hp_before": pre_snapshot["player"]["hp"], "player_hp_after": player.hp,
        "enemy_hp_before": pre_snapshot["enemy"]["hp"], "enemy_hp_after": battle.enemy.hp,
        "ramp_value": res["ramp_value"], "kouki_cooldown": battle.kouki_cooldown,
        "pre_turn_snapshot": pre_snapshot,
    })
    return res


def test_postmortem_unavoidable(data):
    # 敵攻撃力が桁違いに高く、guardを反転(False→True)しても被ダメが致死圏内のまま。
    e = make_enemy(hp=1000, attack=1000, heavy_factor=1.8)
    p = make_player(hp=100, attack=15)
    b = make_battle(e)
    eng = _make_engine(data, p, b)

    res = _play_fatal_turn(eng, guard=False, action=cr.HEAVY)
    assert res["player_dead"] is True  # 実際に致命ターンだったことのサニティチェック

    pm = eng._compute_postmortem()
    assert pm["category"] == "unavoidable"
    assert pm["avoidable"] is False
    assert pm["message"] == "あれは避けられなかった"
    assert pm["original_guard"] is False
    assert pm["counterfactual_guard"] is True
    cf = pm["counterfactual_result"]
    assert cf["player_dead"] is True
    assert cf["enemy_dead"] is False


def test_postmortem_avoidable_guard(data):
    # guard=False致命ターン。guard=True(受け)なら被ダメが1/4になり生存でき、敵も倒れない。
    e = make_enemy(hp=500, attack=50, heavy_factor=1.8)
    p = make_player(hp=80, attack=15)
    b = make_battle(e)
    eng = _make_engine(data, p, b)

    res = _play_fatal_turn(eng, guard=False, action=cr.HEAVY)
    assert res["player_dead"] is True

    pm = eng._compute_postmortem()
    assert pm["category"] == "avoidable_guard"
    assert pm["avoidable"] is True
    assert pm["message"] == "ガードしていれば生存していた"
    assert pm["original_guard"] is False
    assert pm["counterfactual_guard"] is True
    cf = pm["counterfactual_result"]
    assert cf["player_dead"] is False
    assert cf["enemy_dead"] is False
    assert cf["player_hp"] == 58  # 80 - round(round(50*1.8)*0.25) = 80 - 22


def test_postmortem_mutual_kill_victory(data):
    # guard=True致命ターン（受けても被ダメが致死）。guard=Falseなら与ダメが倍増し、
    # enemy_dead優先ルールにより「player_dead=False」＝相打ちで敵を先に倒せていた、に転じる。
    e = make_enemy(hp=20, attack=200, heavy_factor=1.8)
    p = make_player(hp=50, attack=30)
    b = make_battle(e)
    eng = _make_engine(data, p, b)

    res = _play_fatal_turn(eng, guard=True, action=cr.HEAVY)
    assert res["player_dead"] is True
    assert res["enemy_dead"] is False  # 実ターンでは敵は生き残った（受けで与ダメ半減のため）

    pm = eng._compute_postmortem()
    assert pm["category"] == "mutual_kill_victory"
    assert pm["avoidable"] is True
    assert pm["message"] == "相打ちで敵を先に倒せていた"
    assert pm["original_guard"] is True
    assert pm["counterfactual_guard"] is False
    cf = pm["counterfactual_result"]
    assert cf["player_dead"] is False
    assert cf["enemy_dead"] is True


def test_postmortem_empty_when_no_turn_history(data):
    e = make_enemy()
    p = make_player()
    b = make_battle(e)
    eng = _make_engine(data, p, b)
    assert eng._compute_postmortem() == {}
