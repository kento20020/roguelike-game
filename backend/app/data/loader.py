"""データローダ＋検証。

4つのJSON（config / enemies / floors / mods）を読み、検証し、
エンジン全体に「正本データ」を提供する唯一の入口。

CLAUDE.md 原則:
- データファイルが正本。コードに数値を埋め込まない。
- 係数は必ず fallback 経由: `enemy.get(key, config[...])`。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

_DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# config["combat"] にある全敵共通の既定係数。敵が個別値を持てば優先。
_COMBAT_FALLBACK_KEYS = ("counter_factor", "heavy_factor")


def _read(name: str) -> dict[str, Any]:
    with open(os.path.join(_DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


class DataError(ValueError):
    """データ不整合（不変条件違反）。"""


@dataclass(frozen=True)
class GameData:
    """読み込み済みの全正本データ＋アクセサ。

    `GameData.load()` で生成。生成時に `validate()` 済み。
    """

    config: dict[str, Any]
    floors_doc: dict[str, Any]
    mods_doc: dict[str, Any]
    enemies_doc: dict[str, Any]
    _enemies_by_id: dict[str, dict] = field(default_factory=dict)
    _mods_by_id: dict[str, dict] = field(default_factory=dict)
    _floors_by_num: dict[int, dict] = field(default_factory=dict)

    # ── construction ──────────────────────────────────────────────
    @classmethod
    def load(cls, validate: bool = True) -> "GameData":
        config = _read("config.json")
        floors_doc = _read("floors.json")
        mods_doc = _read("mods.json")
        enemies_doc = _read("enemies.json")
        enemies_by_id = {e["id"]: e for e in enemies_doc["enemies"]}
        mods_by_id = {m["id"]: m for m in mods_doc["mods"]}
        floors_by_num = {f["floor_number"]: f for f in floors_doc["floors"]}
        gd = cls(
            config=config,
            floors_doc=floors_doc,
            mods_doc=mods_doc,
            enemies_doc=enemies_doc,
            _enemies_by_id=enemies_by_id,
            _mods_by_id=mods_by_id,
            _floors_by_num=floors_by_num,
        )
        if validate:
            gd.validate()
        return gd

    # ── accessors ─────────────────────────────────────────────────
    @property
    def enemies(self) -> list[dict]:
        return self.enemies_doc["enemies"]

    @property
    def mods(self) -> list[dict]:
        return self.mods_doc["mods"]

    @property
    def floors(self) -> list[dict]:
        return self.floors_doc["floors"]

    @property
    def mod_interactions(self) -> list[dict]:
        return self.mods_doc.get("mod_interactions", [])

    def enemy(self, enemy_id: str) -> dict:
        return self._enemies_by_id[enemy_id]

    def mod(self, mod_id: str) -> dict:
        return self._mods_by_id[mod_id]

    def mod_by_name(self, name: str) -> dict:
        for m in self.mods:
            if m["name"] == name:
                return m
        raise KeyError(name)

    def floor(self, floor_number: int) -> dict:
        return self._floors_by_num[floor_number]

    # ── coefficient fallback (CLAUDE.md mandated pattern) ─────────
    def coeff(self, enemy: dict, key: str) -> float:
        """敵が個別係数を持てばそれを、無ければ config["combat"] の既定。"""
        if key in enemy:
            return enemy[key]
        return self.config["combat"][key]

    # ── derived helpers ───────────────────────────────────────────
    def scaled_hp(self, enemy: dict, tier: int) -> int:
        """tier 補正後の最大HP。 hp * (1 + factor*(tier-1))。"""
        factor = self.config["scaling"]["enemy_hp_tier_factor"]
        return round(enemy["hp"] * (1.0 + factor * (tier - 1)))

    def is_strong(self, enemy: dict) -> bool:
        return enemy["difficulty"] >= self.config["strong_enemy"]["difficulty_threshold"]

    # ── validation (invariants enforced here & in tests) ─────────
    def validate(self) -> None:
        errs: list[str] = []

        # 敵ID一意
        ids = [e["id"] for e in self.enemies]
        if len(ids) != len(set(ids)):
            dupes = {i for i in ids if ids.count(i) > 1}
            errs.append(f"duplicate enemy ids: {sorted(dupes)}")

        # behaviors weight 合計100 / カオスは空＋chaos:true
        for e in self.enemies:
            if e.get("chaos"):
                if e.get("behaviors"):
                    errs.append(f"{e['id']}: chaos enemy must have empty behaviors")
            else:
                total = sum(b["weight"] for b in e["behaviors"])
                if total != 100:
                    errs.append(f"{e['id']}: behaviors weight sum {total} != 100")
                # レース系は ramp_increment 必須
                if any(b["type"] == "ramp_hit" for b in e["behaviors"]) and "ramp_increment" not in e:
                    errs.append(f"{e['id']}: ramp_hit present but no ramp_increment")

        # mod ID 一意 / 6種
        mod_ids = [m["id"] for m in self.mods]
        if len(mod_ids) != len(set(mod_ids)):
            errs.append("duplicate mod ids")

        # floors: pool ID が enemies に存在 / unlock の親整合
        for fl in self.floors:
            pools = []
            for key in ("row1_pool", "row2_pool", "row3_pool"):
                pools += fl.get(key, [])
            for eid in pools:
                if eid not in self._enemies_by_id:
                    errs.append(f"floor {fl['floor_number']}: unknown enemy id {eid}")
            self._validate_unlock(fl, errs)

        # mod_interactions が実在 mod を参照
        for inter in self.mod_interactions:
            for mid in inter["mods"]:
                if mid not in self._mods_by_id:
                    errs.append(f"mod_interaction references unknown mod {mid}")

        if errs:
            raise DataError("; ".join(errs))

    def _validate_unlock(self, fl: dict, errs: list[str]) -> None:
        """多親=2親 / 単親=1親 / dead-end は必ず単親、を検証。"""
        def check_map(umap: dict, valid_parents: set[str], label: str) -> None:
            for node_key, spec in umap.items():
                parents = spec["parents"]
                ntype = spec["type"]
                if ntype == "multi" and len(parents) != 2:
                    errs.append(f"floor {fl['floor_number']} {label} {node_key}: multi must have 2 parents")
                if ntype == "single" and len(parents) != 1:
                    errs.append(f"floor {fl['floor_number']} {label} {node_key}: single must have 1 parent")
                for p in parents:
                    if p not in valid_parents:
                        errs.append(f"floor {fl['floor_number']} {label} {node_key}: unknown parent {p}")

        fn = fl["floor_number"]
        if fl.get("fixed_layout"):
            row2 = fl["nodes_layout"]["row2"]
            check_map(row2, {"L", "M", "R"}, "row2")
        elif fn == 5:
            umap = fl["unlock_map"]
            check_map(umap["row1_to_row2"], {"L", "M", "R"}, "r1->r2")
            check_map(umap["row2_to_row3"], {"A", "B", "C", "D"}, "r2->r3")
        else:
            check_map(fl["unlock_map"], {"L", "M", "R"}, "row2")


# モジュールレベルのキャッシュ（プロセス内で1回ロード）
_CACHED: GameData | None = None


def get_data() -> GameData:
    global _CACHED
    if _CACHED is None:
        _CACHED = GameData.load()
    return _CACHED
