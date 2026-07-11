"""正本データの不変条件テスト。データが壊れたら最初にここで落ちる。"""
import pytest

from app.data.loader import DataError, GameData


def test_load_passes_validation():
    # validate=True で例外なくロードできること
    GameData.load(validate=True)


def test_counts(data: GameData):
    assert len(data.enemies) == 36
    assert len(data.mods) == 6
    assert len(data.floors) == 5


def test_enemy_ids_unique(data: GameData):
    ids = [e["id"] for e in data.enemies]
    assert len(ids) == len(set(ids))


def test_nonchaos_behaviors_sum_100(data: GameData):
    for e in data.enemies:
        if e.get("chaos"):
            continue
        total = sum(b["weight"] for b in e["behaviors"])
        assert total == 100, f"{e['id']} weight sum {total}"


def test_chaos_enemies_empty_and_flagged(data: GameData):
    chaos = [e for e in data.enemies if e.get("chaos")]
    assert len(chaos) == 4  # f3_r2_e, f4_r2_e, f5_r2_d, f5_r3_c
    for e in chaos:
        assert e["behaviors"] == []
        assert e["experience"] == "chaos"


def test_race_enemies_have_ramp_increment(data: GameData):
    for e in data.enemies:
        if any(b["type"] == "ramp_hit" for b in e.get("behaviors", [])):
            assert "ramp_increment" in e


def test_floor_pools_reference_real_enemies(data: GameData):
    for fl in data.floors:
        for key in ("row1_pool", "row2_pool", "row3_pool", "enemy_pool"):
            for eid in fl.get(key, []):
                assert eid in data._enemies_by_id


def test_floor_definitions_valid(data: GameData):
    """1F=静的レイアウトの親数、2F以降=可変深度の生成パラメータ（接続はランタイム生成なので
    floor_generator.validate_floor が生成毎に検証する）。"""
    depths = {}
    for fl in data.floors:
        if fl.get("fixed_layout"):
            for k, spec in fl["nodes_layout"]["row2"].items():
                want = 2 if spec["type"] == "multi" else 1
                assert len(spec["parents"]) == want, f"1F {k}"
        else:
            assert fl["depth"] >= 2
            depths[fl["floor_number"]] = fl["depth"]
            g = fl["generation"]
            assert 2 <= g["main_width_min"] <= g["main_width_max"] <= 3
            assert fl["enemy_pool"]
    # 深度カーブ（デザイナー決定の叩き台: 2F=3 / 3F=4 / 4F=5 / 5F=6）
    assert depths == {2: 3, 3: 4, 4: 5, 5: 6}


def test_coeff_fallback_uses_config_default(data: GameData):
    # 個別 heavy_factor を持たない敵 → config 既定 1.8
    e = data.enemy("f2_r1_a")  # 削り合い、heavy_factor 未指定
    assert "heavy_factor" not in e
    assert data.coeff(e, "heavy_factor") == data.config["combat"]["heavy_factor"] == 1.8
    assert data.coeff(e, "counter_factor") == 1.0


def test_coeff_fallback_prefers_enemy_override():
    e = {"heavy_factor": 2.5}
    gd = GameData.load()
    assert gd.coeff(e, "heavy_factor") == 2.5


def test_scaled_hp_formula(data: GameData):
    e = data.enemy("f2_r1_a")  # base hp 45
    # tier 2: 45 * (1 + 0.10*1) = 49.5 -> 50（round=銀行丸め）
    assert data.scaled_hp(e, 2) == round(45 * 1.10)
    assert data.scaled_hp(e, 1) == 45


def test_is_strong_threshold(data: GameData):
    assert data.is_strong(data.enemy("f3_r2_b")) is True   # difficulty 4
    assert data.is_strong(data.enemy("f2_r1_a")) is False  # difficulty 2


def test_validation_catches_bad_weights():
    gd = GameData.load()
    # behaviors を壊して再検証 → DataError
    bad = dict(gd.enemies_doc)
    import copy
    bad = copy.deepcopy(gd.enemies_doc)
    bad["enemies"][0]["behaviors"] = [{"type": "counter", "weight": 50}]  # 合計50
    broken = GameData(
        config=gd.config, floors_doc=gd.floors_doc, mods_doc=gd.mods_doc,
        enemies_doc=bad,
        _enemies_by_id={e["id"]: e for e in bad["enemies"]},
        _mods_by_id=gd._mods_by_id, _floors_by_num=gd._floors_by_num,
    )
    with pytest.raises(DataError):
        broken.validate()


def test_tutorial_guaranteed_mod_is_hansha(data: GameData):
    tut = data.mods_doc["tutorial_guaranteed"]
    assert tut["mod_id"] == "hansha"
    assert tut["floor"] == 1


def test_upgrade_max_levels_total_is_21(data: GameData):
    """恒久強化の上限Lv合計=21（data_model.md §20 合格条件・OPEN-013）。意図的に変えるなら docs も更新。"""
    items = data.config["permanent_upgrades"]["items"]
    assert sum(v["max_level"] for v in items.values()) == 21


def test_gate_result_tables_sum_to_one(data: GameData):
    """全フロアのゲート出目テーブルはキー4種・合計1.0（OPEN-013。loader.validate でも強制）。"""
    for fl in data.floors:
        t = fl["gate_result_table"]
        assert set(t) == {"unhurt", "minor", "major", "special"}
        assert abs(sum(t.values()) - 1.0) < 1e-9
