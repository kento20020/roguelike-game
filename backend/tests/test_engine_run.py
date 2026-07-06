"""エンジンの状態機械・経済・1ラン通し。"""
import pytest

from app.engine.game_engine import GameEngine, IllegalAction


def auto_play(eng: GameEngine, seed: int, upgrades=None, max_steps=4000) -> dict:
    """常に攻撃／ゲート優先の単純プレイで終端まで進める。"""
    eng.new_run(seed, upgrades=upgrades, bot_type="auto")
    for _ in range(max_steps):
        ph = eng.phase
        if ph in ("cleared", "dead"):
            break
        if ph == "battle":
            eng.attack()
        elif ph == "exploring":
            avail = eng.available_nodes()
            gate = [n for n in avail if eng.floor.nodes[n].kind == "gate"]
            enemies = [n for n in avail if eng.floor.nodes[n].kind == "enemy"]
            routes = [n for n in avail if eng.floor.nodes[n].kind == "gate_route"]
            pick = (gate or enemies or routes or avail)[0]
            eng.select_node(pick)
        elif ph == "treasure_preview":
            eng.treasure_open()
        elif ph in ("treasure_opened", "heal", "next_floor"):
            eng.dismiss()
        elif ph == "gate_preview":
            eng.gate_resolve()
        else:
            break
    return eng.snapshot()


def test_new_run_initial_state(data):
    eng = GameEngine(data)
    snap = eng.new_run(42)
    assert snap["phase"] == "exploring"
    assert snap["current_floor"] == 1
    assert snap["player"]["hp"] == 100
    assert snap["player"]["attack"] == 15
    assert snap["player"]["chips"] == 0
    assert snap["player"]["mods"] == []


def test_root_nodes_available(data):
    eng = GameEngine(data)
    eng.new_run(1)
    avail = set(eng.available_nodes())
    assert {"L", "M", "R"} <= avail
    # dead-end A (parent L) は最初ロック
    assert "A" not in avail


def test_upgrades_applied(data):
    eng = GameEngine(data)
    snap = eng.new_run(1, upgrades={"max_hp": 2, "attack": 3, "init_gold": 1})
    assert snap["player"]["max_hp"] == 100 + 10 * 2
    assert snap["player"]["attack"] == 15 + 2 * 3
    assert snap["player"]["chips"] == 0 + 15 * 1


def test_defeating_enemy_unlocks_and_rewards(data):
    eng = GameEngine(data)
    eng.new_run(1)
    eng.select_node("L")
    assert eng.phase == "battle"
    chips_before = eng.player.chips
    for _ in range(50):
        if eng.phase != "battle":
            break
        eng.attack()
    assert eng.resolved.get("L") is True
    assert eng.player.chips > chips_before          # チップ獲得
    # L 撃破で A（宝箱）と B が available に
    avail = set(eng.available_nodes())
    assert "A" in avail and "B" in avail


def test_floor1_treasure_gives_hansha(data):
    eng = GameEngine(data)
    eng.new_run(1)
    eng.select_node("L")
    while eng.phase == "battle":
        eng.attack()
    eng.dismiss()  # victory pending(なくてもno-op)
    eng.select_node("A")
    assert eng.phase == "treasure_preview"
    eng.treasure_open()
    assert eng.phase == "treasure_opened"
    assert "hansha" in eng.player.mods


def test_illegal_action_raises(data):
    eng = GameEngine(data)
    eng.new_run(1)
    with pytest.raises(IllegalAction):
        eng.attack()                                  # exploring 中に attack 不可
    with pytest.raises(IllegalAction):
        eng.gate_resolve()


def test_full_run_terminates(data):
    eng = GameEngine(data)
    snap = auto_play(eng, seed=7)
    assert snap["phase"] in ("cleared", "dead")
    rr = snap["run_record"]
    assert rr["total_turns"] > 0
    assert rr["floor_reached"] >= 1
    assert len(rr["enemies_defeated"]) >= 1
    # 死亡/クリア画面の「強敵撃破数」表示用（GDD §15.1）: 各撃破記録は is_strong を持つ
    assert all("is_strong" in d for d in rr["enemies_defeated"])


def test_snapshot_completeness(data):
    eng = GameEngine(data)
    snap = eng.new_run(1)
    for key in ("phase", "current_floor", "player", "floor", "battle",
                "pending", "available_actions", "run_record"):
        assert key in snap


def test_progression_and_termination(data):
    # 単純プレイ（回復・スカウトなし）は弱いので必ずクリアはしないが、
    # フロア進行（ゲート通過→次フロア）と死亡判定の両方が機能することを確認。
    # クリア率の検証は phase12_harness（強ボット）の役割。
    eng = GameEngine(data)
    max_floor = 0
    outcomes = set()
    for seed in range(40):
        snap = auto_play(eng, seed=seed)
        outcomes.add(snap["phase"])
        max_floor = max(max_floor, snap["run_record"]["floor_reached"])
    assert max_floor >= 2          # ゲート通過→次フロアが機能する
    assert "dead" in outcomes      # 死亡判定も通る（状態機械が両分岐を踏む）


def test_snapshot_exposes_enemy_preview(data):
    """L2（体験タイプ・強敵）は常時開示、L3（名前・最大HP）はインタラクト後のみ（§5・OPEN-015）。
    確率（behaviors weight）は常に非公開。"""
    eng = GameEngine(data)
    eng.new_run(7)
    nodes = eng.snapshot()["floor"]["nodes"]
    enemies = [n for n in nodes.values() if n["kind"] == "enemy"]
    assert enemies, "1F に敵ノードがあるはず"
    for n in enemies:
        assert isinstance(n["experience"], str) and n["experience"]
        assert isinstance(n["is_strong"], bool)
        assert "name" not in n and "max_hp" not in n       # L3 は未インタラクトでは伏せる
        assert "behaviors" not in n and "weight" not in n  # 確率は伏せる
    for n in [n for n in nodes.values() if n["kind"] != "enemy"]:
        assert n.get("experience") is None
    # 戦闘コミット（インタラクト）で L3 開示
    eng.select_node("L")
    view = eng.snapshot()["floor"]["nodes"]["L"]
    assert view["name"] and view["max_hp"] > 0
    # 撃破後（resolved）も開示継続
    while eng.phase == "battle":
        eng.attack()
    view2 = eng.snapshot()["floor"]["nodes"]["L"]
    assert view2["name"] and view2["max_hp"] > 0


def test_gate_preview_pending_has_table_and_damage(data):
    """関門ギミック: gate_preview の pending は確率テーブルと被ダメ実値を持つ（React に計算させない）。"""
    MAXED = {"max_hp": 5, "attack": 5, "init_gold": 5, "gold_drop": 3, "sink_cost": 3}
    reached = None
    for seed in range(20):
        eng = GameEngine(data)
        eng.new_run(seed, upgrades=MAXED)
        for _ in range(4000):
            ph = eng.phase
            if ph == "gate_preview":
                reached = eng
                break
            if ph in ("dead", "cleared"):
                break
            if ph == "battle":
                eng.attack()
            elif ph == "exploring":
                avail = eng.available_nodes()
                gate = [n for n in avail if eng.floor.nodes[n].kind == "gate"]
                enemies = [n for n in avail if eng.floor.nodes[n].kind == "enemy"]
                routes = [n for n in avail if eng.floor.nodes[n].kind == "gate_route"]
                eng.select_node((gate or enemies or routes or avail)[0])
            elif ph == "treasure_preview":
                eng.treasure_open()
            elif ph in ("treasure_opened", "heal", "next_floor"):
                eng.dismiss()
            else:
                break
        if reached:
            break
    assert reached is not None, "20 seed 内で gate_preview に到達できるはず"
    pend = reached.snapshot()["pending"]
    assert set(pend["table"]) == {"unhurt", "minor", "major", "special"}
    assert set(pend["damage"]) == {"unhurt", "minor", "major", "special"}
    assert all(v >= 0 for v in pend["damage"].values())
    assert pend["damage"]["unhurt"] == 0 and pend["damage"]["special"] == 0
    assert pend["damage"]["major"] >= pend["damage"]["minor"] > 0


def test_enemy_drop_routes_to_treasure(data):
    """撃破ドロップ: 多親敵を倒すと treasure_preview(source=enemy) になり、開封で mod を得る。"""
    MAXED = {"max_hp": 5, "attack": 5, "init_gold": 5, "gold_drop": 3, "sink_cost": 3}
    found = False
    for seed in range(40):
        eng = GameEngine(data)
        eng.new_run(seed, upgrades=MAXED)
        for _ in range(4000):
            ph = eng.phase
            if ph in ("dead", "cleared"):
                break
            if ph == "battle":
                before = len(eng.run.mods_acquired)
                eng.attack()
                if eng.phase == "treasure_preview" and eng.pending.get("source") == "enemy":
                    eng.treasure_open()
                    assert eng.phase == "treasure_opened"
                    assert len(eng.run.mods_acquired) == before + 1
                    found = True
                    break
            elif ph == "exploring":
                av = eng.available_nodes()
                en = [n for n in av if eng.floor.nodes[n].kind == "enemy"]
                rt = [n for n in av if eng.floor.nodes[n].kind == "gate_route"]
                g = [n for n in av if eng.floor.nodes[n].kind == "gate"]
                eng.select_node((en or rt or g or av)[0])  # 敵優先で戦う
            elif ph == "treasure_preview":
                eng.treasure_open()
            elif ph in ("treasure_opened", "heal", "next_floor"):
                eng.dismiss()
            elif ph == "gate_preview":
                eng.gate_resolve()
            else:
                break
        if found:
            break
    assert found, "撃破ドロップ→treasure_preview(source=enemy) が発生するはず"


def test_heal_amounts_are_fixed_not_percent(data):
    """回復量は固定値（GDD §7.3/§13.2 v0.9確定）。max_hp を強化しても +15/+30 固定。
    %方式なら max_hp=150 で 22/45 になるため、それと区別する。"""
    from app.schemas.models import Node

    # max_hp 強化 (+50 → 150) で固定値であることを確認
    eng = GameEngine(data)
    eng.new_run(1, upgrades={"max_hp": 5})
    assert eng.player.max_hp == 150

    # 回復ノード: 大小いずれでも config の固定値（15 or 30）。max_hp比なら 22/45。
    eng.player.hp = 50
    node = Node(id="H", kind="heal", row=2, parents=["L"], parent_type="single")
    eng._resolve_heal(node)
    amt = eng.pending["heal"]
    expected = 30 if eng.pending["big"] else 15
    assert amt == expected, f"回復ノードは固定値であるべき: got {amt}"
    assert amt not in (22, 45), "max_hp の % になっている（固定値違反）"

    # 回復sink（小=+15固定 / 大=+30固定）
    eng2 = GameEngine(data)
    eng2.new_run(1, upgrades={"max_hp": 5})
    eng2.player.chips = 9999
    eng2.player.hp = 50
    eng2.use_sink("heal_small")
    assert eng2.player.hp == 65, "小回復は +15 固定であるべき"
    eng2.player.hp = 50
    eng2.use_sink("heal_large")
    assert eng2.player.hp == 80, "大回復は +30 固定であるべき"


def _drive_to_gate_preview(data, upgrades):
    """gate_preview に到達したエンジンを返す（保証は使わない）。"""
    for seed in range(20):
        e = GameEngine(data)
        e.new_run(seed, upgrades=upgrades)
        for _ in range(4000):
            ph = e.phase
            if ph == "gate_preview":
                return e
            if ph in ("dead", "cleared"):
                break
            if ph == "battle":
                e.attack()
            elif ph == "exploring":
                av = e.available_nodes()
                gate = [n for n in av if e.floor.nodes[n].kind == "gate"]
                en = [n for n in av if e.floor.nodes[n].kind == "enemy"]
                rt = [n for n in av if e.floor.nodes[n].kind == "gate_route"]
                e.select_node((gate or en or rt or av)[0])
            elif ph == "treasure_preview":
                e.treasure_open()
            elif ph in ("treasure_opened", "heal", "next_floor"):
                e.dismiss()
            else:
                break
    return None


def test_gate_special_bonus_and_next_floor_phase(data):
    """特殊通過＝無傷＋ボーナスチップ（GDD §7.4）。次フロアは next_floor phase を経て exploring へ（GDD §6.1）。"""
    MAXED = {"max_hp": 5, "attack": 5, "init_gold": 5, "gold_drop": 3, "sink_cost": 3}
    eng = _drive_to_gate_preview(data, MAXED)
    assert eng is not None, "20 seed 内で gate_preview に到達できるはず"
    assert eng.current_floor < 5, "1F想定（次フロアがある）"

    # 特殊を強制
    eng.floor.gate_result_table = {"unhurt": 0.0, "minor": 0.0, "major": 0.0, "special": 1.0}
    chips_before = eng.player.chips
    hp_before = eng.player.hp
    floor_before = eng.current_floor
    bonus = data.config["gate_special"]["bonus_gold"]

    snap = eng.gate_resolve()
    assert snap["phase"] == "next_floor"                       # 演出 phase を発行
    assert snap["pending"]["advanced_to"] == floor_before + 1
    assert snap["pending"]["special_bonus"] == bonus
    assert eng.player.chips == chips_before + bonus            # ボーナスチップ
    assert eng.player.hp == hp_before                          # 無傷（ダメージ0）
    assert any(a["type"] == "dismiss" for a in snap["available_actions"])

    # continue（dismiss）で exploring へ
    snap2 = eng.dismiss()
    assert snap2["phase"] == "exploring"
    assert eng.current_floor == floor_before + 1


def test_gate_guarantee_stacks_recorded(data):
    """ゲート保証の重ねがけ回数がランレコードに累計される（GDD §19.1 v0.9）。"""
    MAXED = {"max_hp": 5, "attack": 5, "init_gold": 5, "gold_drop": 3, "sink_cost": 3}
    eng = None
    for seed in range(20):
        e = GameEngine(data)
        e.new_run(seed, upgrades=MAXED)
        for _ in range(4000):
            ph = e.phase
            if ph == "gate_preview":
                eng = e
                break
            if ph in ("dead", "cleared"):
                break
            if ph == "battle":
                e.attack()
            elif ph == "exploring":
                av = e.available_nodes()
                gate = [n for n in av if e.floor.nodes[n].kind == "gate"]
                en = [n for n in av if e.floor.nodes[n].kind == "enemy"]
                rt = [n for n in av if e.floor.nodes[n].kind == "gate_route"]
                e.select_node((gate or en or rt or av)[0])
            elif ph == "treasure_preview":
                e.treasure_open()
            elif ph in ("treasure_opened", "heal", "next_floor"):
                e.dismiss()
            else:
                break
        if eng:
            break
    assert eng is not None, "20 seed 内で gate_preview に到達できるはず"
    eng.player.chips = 99999
    # OPEN-016: major=0 到達後は重ねがけ不可のため、2回積める major を持つテーブルに差し替える
    eng.floor.gate_result_table = {"unhurt": 0.10, "minor": 0.25, "major": 0.60, "special": 0.05}
    assert eng.run.gate_guarantee_stacks == 0
    eng.use_sink("gate_guarantee")
    eng.use_sink("gate_guarantee")
    assert eng.run.gate_guarantee_stacks == 2
    # 進行中 snapshot は run_record 非露出（§17.3）のため内部 RunRecord 側で確認する
    assert eng.run.snapshot()["gate_guarantee_stacks"] == 2


def test_yomi_exposes_next_action_in_snapshot(data):
    """先読み所持なら戦闘突入時 snapshot に確定の次手(next_action)が載る。無しなら None。

    tell_system フラグはON時「yomi無しでも常に先引き」する試作仕様のため、
    このテストの意図（yomi無し→None）を保つには明示的にOFFにして検証する。
    """
    BEH = {"counter", "heavy_blow", "evade", "ramp_hit", "none"}
    prev_flag = data.config.get("feature_flags", {}).get("tell_system")
    data.config.setdefault("feature_flags", {})["tell_system"] = False
    try:
        eng = GameEngine(data)
        eng.new_run(1)
        eng.select_node("L")
        assert eng.snapshot()["battle"]["next_action"] is None      # yomi 無し
        eng2 = GameEngine(data)
        eng2.new_run(1)
        eng2.player.mods.append("yomi")
        s = eng2.select_node("L")
        assert s["battle"]["next_action"] in BEH                    # 確定の次手
    finally:
        data.config["feature_flags"]["tell_system"] = prev_flag


def test_tell_system_flag_forces_turn1_preview_without_yomi(data):
    """テル試作: フラグON時、yomi未所持でもturn1でpending_action(next_action)がセットされる。

    既存のroll_behavior呼び出しと同じコードパス・同じタイミングを使うだけで、
    新規のRNG消費箇所は増えない、という前提の確認。
    """
    prev_flag = data.config.get("feature_flags", {}).get("tell_system")
    data.config.setdefault("feature_flags", {})["tell_system"] = True
    try:
        eng = GameEngine(data)
        eng.new_run(1)
        s = eng.select_node("L")
        assert "yomi" not in eng.player.mods
        assert s["battle"]["next_action"] is not None
        assert s["battle"]["tell_reliability"] is not None

        # 回帰テスト: battle.turns基準の閾値を使うと「常に次ターンを公開」し続けてしまい、
        # yomi無しでも実質全ターン確定情報が見える＝暗黙知型ギャンブル性が壊れる致命的な
        # バグがあった（閾値をturn1固定の1にして修正）。turn2以降はNoneに戻ることを確認。
        s2 = eng.attack()
        if s2["phase"] == "battle":
            assert s2["battle"]["next_action"] is None
            assert s2["battle"]["tell_reliability"] is None
    finally:
        data.config["feature_flags"]["tell_system"] = prev_flag
