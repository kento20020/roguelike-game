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
        for key in ("row1_pool", "row2_pool", "row3_pool"):
            for eid in fl.get(key, []):
                assert eid in data._enemies_by_id


def test_unlock_parent_arity(data: GameData):
    # multi=2親 / single=1親、を全フロアで確認
    def check(umap, who):
        for k, spec in umap.items():
            if spec["type"] == "multi":
                assert len(spec["parents"]) == 2, f"{who} {k}"
            else:
                assert len(spec["parents"]) == 1, f"{who} {k}"

    for fl in data.floors:
        if fl.get("fixed_layout"):
            check(fl["nodes_layout"]["row2"], "1F")
        elif fl["floor_number"] == 5:
            check(fl["unlock_map"]["row1_to_row2"], "5F r1->r2")
            check(fl["unlock_map"]["row2_to_row3"], "5F r2->r3")
        else:
            check(fl["unlock_map"], f"{fl['floor_number']}F")


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
    # tier 2: 45 * (1 + 0.15*1) = 51.75 -> 52
    assert data.scaled_hp(e, 2) == round(45 * 1.15)
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
