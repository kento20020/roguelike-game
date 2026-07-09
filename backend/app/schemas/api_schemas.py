"""API の Pydantic I/O。レスポンスは engine.snapshot() と同形（完全状態）。

route では `GameStateResponse(session_id=sid, **engine.snapshot())` で構築する。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── requests ──
class NewRunRequest(BaseModel):
    # seed は SFC32 の定義域 [0, 2^32-1] に制限（§17.3。範囲外の暗黙丸めを入口で拒否）
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    bot_type: str = "human"


class SelectNodeRequest(BaseModel):
    node_id: str


class SinkRequest(BaseModel):
    sink_type: str


class UpgradeRequest(BaseModel):
    upgrade_type: str


class SideBet(BaseModel):
    """サイドベット『読み宣言』: 次の敵行動(behavior)への任意ベット。
    既存のstream2(behavior_roll)の結果をそのまま使う。新規RNG消費はしない。"""
    behavior: str
    amount: int


class CombatActionRequest(BaseModel):
    """attack/guard の共通リクエストボディ。side_bet は任意（賭けない状態がデフォルト）。"""
    side_bet: Optional[SideBet] = None


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
    # 受けの使用回数（ジャストガードの重ねがけ減衰の現在段・戦闘毎リセット・v1.8）。
    # UIが「次の受けの効き」を表示するための公開状態。
    guard_uses: int = 0
    scout_hint: Optional[str] = None
    preview: Optional[str] = None
    next_action: Optional[str] = None  # 先読みが公開した確定の次手の種別
    log: list[LogLine]
    side_bet_total: int = 0  # サイドベット『読み宣言』の戦闘あたり累計額（per_battle_cap 可視化用）
    side_bet_result: Optional[dict[str, Any]] = None  # 直近ターンのサイドベット結果（次ターンでクリア）
    last_turn: Optional[dict[str, Any]] = None  # 直近ターンの実現結果 {action, guard}（ログ表示済みの公開情報のみ）
    side_bet: Optional[dict[str, Any]] = None  # サイドベット表示規則（正本 config.json side_bet の該当キーのみ）
    # テル（行動の前兆）試作: 気配信頼度ラベル。フラグOFF/非公開ターンは None。
    # engine.snapshot() は生成していたが本スキーマに無くレスポンスから欠落していた（型契約の破れを修復）。
    tell_reliability: Optional[str] = None


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
    # OPEN-024/025 テレメトリ（旧レコードは既定値で埋まる）
    data_version: str = ""
    strategy_version: Optional[str] = None
    sink_use_counts: dict[str, int] = {}
    gate_results: list[dict] = []
    action_counts: dict[str, int] = {}


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


class EnemyCatalogItem(BaseModel):
    """敵の表示用カタログ（enemies.json 由来・id/name/experienceのみ。weight/behaviorsは含めない）。"""
    id: str
    name: str
    experience: str


# ── dealer dossier（個人観測統計・Wilson信頼区間。真のweightは非開示）──
class DossierBehaviorOut(BaseModel):
    behavior: str
    count: int
    n_total: int
    ci_low: float
    ci_high: float


class DossierEnemyOut(BaseModel):
    enemy_id: str
    behaviors: list[DossierBehaviorOut]
    n_total: int
