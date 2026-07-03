"""API の Pydantic I/O。レスポンスは engine.snapshot() と同形（完全状態）。

route では `GameStateResponse(session_id=sid, **engine.snapshot())` で構築する。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ── requests ──
class NewRunRequest(BaseModel):
    seed: Optional[int] = None
    bot_type: str = "human"


class SelectNodeRequest(BaseModel):
    node_id: str


class SinkRequest(BaseModel):
    sink_type: str


class UpgradeRequest(BaseModel):
    upgrade_type: str


# ── state sub-models ──
class PlayerOut(BaseModel):
    hp: int
    max_hp: int
    attack: int
    chips: int
    mods: list[str]
    stance_multiplier: float
    attack_boost_pending: bool


class NodeOut(BaseModel):
    id: str
    kind: str
    row: int
    parents: list[str]
    parent_type: str
    resolved: bool
    state: str
    # 敵ノードのみ（L2/L3 開示・GDD §5）。確率は含めない。
    experience: Optional[str] = None
    name: Optional[str] = None
    is_strong: Optional[bool] = None
    max_hp: Optional[int] = None


class FloorOut(BaseModel):
    floor_number: int
    nodes: dict[str, NodeOut]


class EnemyOut(BaseModel):
    id: str
    name: str
    experience: str
    hp: int
    max_hp: int
    attack: int
    difficulty: int
    is_strong: bool
    chaos: bool


class LogLine(BaseModel):
    t: str
    k: str


class BattleOut(BaseModel):
    enemy: EnemyOut
    turns: int
    ramp_value: int
    scout_hint: Optional[str] = None
    preview: Optional[str] = None
    next_action: Optional[str] = None  # 先読みが公開した確定の次手の種別
    log: list[LogLine]


class ActionItem(BaseModel):
    type: str
    node: Optional[str] = None
    sink: Optional[str] = None
    cost: Optional[int] = None  # use_sink / treasure_reroll の実コスト（メタ強化反映済み）


class RunRecordOut(BaseModel):
    model_config = ConfigDict(extra="allow")  # DB行の id/created_at も許容
    run_id: str
    seed: int
    bot_type: str
    cleared: bool
    floor_reached: int
    total_turns: int
    final_hp: int
    mods_acquired: list[str]
    gold_earned: int
    gold_spent: dict[str, int]
    enemies_defeated: list[dict]
    death_cause: Optional[str] = None
    death_floor: Optional[int] = None
    permanent_upgrades_state: dict[str, int]
    gate_guarantee_stacks: int = 0


# ── responses ──
class GameStateResponse(BaseModel):
    session_id: str
    phase: str
    current_floor: int
    player: Optional[PlayerOut] = None
    floor: Optional[FloorOut] = None
    battle: Optional[BattleOut] = None
    pending: dict[str, Any] = {}
    available_actions: list[ActionItem] = []
    run_record: Optional[RunRecordOut] = None


class PostmortemResponse(BaseModel):
    """検死レポート＋リプレイ（GET /run/{sid}/postmortem）。turn_history/counterfactual は
    engineが計算した軽量dictをそのまま透過する（WinModel等の未実装インフラには依存しない）。"""
    model_config = ConfigDict(extra="allow")
    run_id: str
    turn_history: list[dict[str, Any]]
    fatal_turn_index: int
    counterfactual: dict[str, Any]
    created_at: Optional[str] = None


class UpgradeStateResponse(BaseModel):
    points: int
    levels: dict[str, int]
    maxes: dict[str, int]


class ModCatalogItem(BaseModel):
    """技(mod)の表示用カタログ（mods.json 由来・効果文の正本）。"""
    id: str
    name: str
    effect_1: str
    effect_stack: str
