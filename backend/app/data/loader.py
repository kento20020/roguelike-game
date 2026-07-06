"""データローダ＋検証。

4つのJSON（config / enemies / floors / mods）を読み、検証し、
エンジン全体に「正本データ」を提供する唯一の入口。

CLAUDE.md 原則:
- データファイルが正本。コードに数値を埋め込まない。
- 係数は必ず fallback 経由: `enemy.get(key, config[...])`。
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any

_DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# config["combat"] にある全敵共通の既定係数。敵が個別値を持てば優先。
_COMBAT_FALLBACK_KEYS = ("counter_factor", "heavy_factor")


def _read_bytes(name: str) -> bytes:
    with open(os.path.join(_DATA_DIR, name), "rb") as f:
        return f.read()


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
    # 4つの正本JSONの内容ハッシュ（12hex）。統計を数値世代でフィルタする札（OPEN-024）。
    data_version: str = ""

    # ── construction ──────────────────────────────────────────────
    @classmethod
    def load(cls, validate: bool = True) -> "GameData":
        names = ("config.json", "enemies.json", "floors.json", "mods.json")
        raw = {name: _read_bytes(name) for name in names}
        config = json.loads(raw["config.json"])
        floors_doc = json.loads(raw["floors.json"])
        mods_doc = json.loads(raw["mods.json"])
        enemies_doc = json.loads(raw["enemies.json"])
        enemies_by_id = {e["id"]: e for e in enemies_doc["enemies"]}
        mods_by_id = {m["id"]: m for m in mods_doc["mods"]}
        floors_by_num = {f["floor_number"]: f for f in floors_doc["floors"]}
        h = hashlib.sha256()
        for name in names:
            h.update(raw[name])
        gd = cls(
            config=config,
            floors_doc=floors_doc,
            mods_doc=mods_doc,
            enemies_doc=enemies_doc,
            _enemies_by_id=enemies_by_id,
            _mods_by_id=mods_by_id,
            _floors_by_num=floors_by_num,
            data_version=h.hexdigest()[:12],
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
    def scaled_hp(self, enemy: dict, tier: int, row: int = 1) -> int:
        """tier補正＋row深度補正後の最大HP。
        hp × (1 + tier_factor×(tier-1)) × (1 + hp_per_row×(row-1))。乗算合成（attack×multiplier と同形）。"""
        factor = self.config["scaling"]["enemy_hp_tier_factor"]
        hp = enemy["hp"] * (1.0 + factor * (tier - 1))
        ds = self.config.get("depth_scaling", {})
        hp *= 1.0 + ds.get("hp_per_row", 0.0) * (row - 1)
        return round(hp)

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

        # floors: pool ID が enemies に存在 / レイアウト・生成パラメータの整合
        for fl in self.floors:
            pools = []
            for key in ("row1_pool", "row2_pool", "row3_pool", "enemy_pool"):
                pools += fl.get(key, [])
            for eid in pools:
                if eid not in self._enemies_by_id:
                    errs.append(f"floor {fl['floor_number']}: unknown enemy id {eid}")
            self._validate_floor_def(fl, errs)

        # mod_interactions が実在 mod を参照
        for inter in self.mod_interactions:
            for mid in inter["mods"]:
                if mid not in self._mods_by_id:
                    errs.append(f"mod_interaction references unknown mod {mid}")

        # ゲート出目テーブル: キー4種・確率合計1.0（OPEN-013）
        outcomes = {"unhurt", "minor", "major", "special"}
        for fl in self.floors:
            t = fl.get("gate_result_table", {})
            if set(t) != outcomes:
                errs.append(f"floor {fl['floor_number']}: gate_result_table keys {sorted(t)} != {sorted(outcomes)}")
            elif abs(sum(t.values()) - 1.0) > 1e-9:
                errs.append(f"floor {fl['floor_number']}: gate_result_table sum {sum(t.values())} != 1.0")

        # experience は romaji 正準キーのみ（OPEN-012 受入条件: 日本語がAPI/統計キーに出ない）
        exp_keys = {"grind", "gamble", "race", "dodge", "chaos"}
        for e in self.enemies:
            if e["experience"] not in exp_keys:
                errs.append(f"{e['id']}: experience '{e['experience']}' not in {sorted(exp_keys)}")

        if errs:
            raise DataError("; ".join(errs))

    def _validate_floor_def(self, fl: dict, errs: list[str]) -> None:
        """フロア定義の検証。
        fixed_layout: 静的レイアウトの多親=2/単親=1/親実在。
        生成フロア: depth・enemy_pool・generation パラメータの妥当性
        （接続そのものはランタイム生成なので floor_generator.validate_floor が生成毎に検証する）。"""
        fn = fl["floor_number"]
        if fl.get("fixed_layout"):
            for node_key, spec in fl["nodes_layout"]["row2"].items():
                parents, ntype = spec["parents"], spec["type"]
                if ntype == "multi" and len(parents) != 2:
                    errs.append(f"floor {fn} row2 {node_key}: multi must have 2 parents")
                if ntype == "single" and len(parents) != 1:
                    errs.append(f"floor {fn} row2 {node_key}: single must have 1 parent")
                for p in parents:
                    if p not in {"L", "M", "R"}:
                        errs.append(f"floor {fn} row2 {node_key}: unknown parent {p}")
            return

        depth = fl.get("depth")
        if not isinstance(depth, int) or depth < 2:
            errs.append(f"floor {fn}: depth must be int >= 2")
        pool = fl.get("enemy_pool", [])
        if not pool:
            errs.append(f"floor {fn}: enemy_pool must not be empty")
        elif all(self._enemies_by_id.get(e, {}).get("chaos") for e in pool if e in self._enemies_by_id):
            errs.append(f"floor {fn}: enemy_pool needs at least one non-chaos enemy")
        gen = fl.get("generation", {})
        lo, hi = gen.get("main_width_min"), gen.get("main_width_max")
        if not (isinstance(lo, int) and isinstance(hi, int) and 2 <= lo <= hi <= 3):
            errs.append(f"floor {fn}: generation main_width must satisfy 2 <= min <= max <= 3")
        if gen.get("dead_ends_max_per_row", 0) < 0:
            errs.append(f"floor {fn}: dead_ends_max_per_row must be >= 0")


# モジュールレベルのキャッシュ（プロセス内で1回ロード）
_CACHED: GameData | None = None


def get_data() -> GameData:
    global _CACHED
    if _CACHED is None:
        _CACHED = GameData.load()
    return _CACHED
