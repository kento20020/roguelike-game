"""エンジンの状態モデル（dataclass）。

API 段で Pydantic I/O に変換するが、エンジン内部はこの軽量 dataclass を使う。
`GameState.snapshot()` が「完全なゲーム状態」の dict を返す（CLAUDE.md: 各レスポンス
は完全な状態を返す／フロントに差分計算させない）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# ── mod id 定数（mods.json と一致）──
MIKIRI = "mikiri"      # 見切り
KASOKU = "kasoku_dome" # 加速止め
JUSO = "juso"          # 重装甲
HANSHA = "hansha"      # 反射
YOMI = "yomi"          # 先読み
KOUKI = "kouki"        # 好機

# ── phase 定数 ──
PHASE_EXPLORING = "exploring"
PHASE_BATTLE = "battle"
PHASE_TREASURE_PREVIEW = "treasure_preview"
PHASE_TREASURE_OPENED = "treasure_opened"
PHASE_HEAL = "heal"
PHASE_GATE_PREVIEW = "gate_preview"
PHASE_GATE_RESOLVE = "gate_resolve"
PHASE_NEXT_FLOOR = "next_floor"
PHASE_CLEARED = "cleared"
PHASE_DEAD = "dead"


@dataclass
class Player:
    hp: int
    max_hp: int
    attack: int
    chips: int
    mods: list[str] = field(default_factory=list)  # mod id。スタックは重複で表現
    stance_multiplier: float = 1.0                  # フェーズB予約（現在1.0固定）
    attack_boost_pending: bool = False              # 次の1撃のみ ×boost

    def mod_count(self, mod_id: str) -> int:
        return self.mods.count(mod_id)

    def has_mod(self, mod_id: str) -> bool:
        return mod_id in self.mods

    def snapshot(self) -> dict[str, Any]:
        return {
            "hp": self.hp, "max_hp": self.max_hp, "attack": self.attack,
            "chips": self.chips, "mods": list(self.mods),
            "stance_multiplier": self.stance_multiplier,
            "attack_boost_pending": self.attack_boost_pending,
        }


@dataclass
class EnemyInstance:
    """戦闘にインスタンス化された敵（tier補正済みHP）。"""
    id: str
    name: str
    experience: str
    max_hp: int
    hp: int
    attack: int
    difficulty: int
    gold_base: int
    chaos: bool
    behaviors: list[tuple[str, float]]   # 実効行動テーブル（カオスはラン別weight）
    ramp_increment: int = 0
    heavy_factor: float = 1.8
    counter_factor: float = 1.0
    is_strong: bool = False

    @property
    def has_ramp(self) -> bool:
        # レース系（ramp_hit を持つ）か、カオスで ramp_hit を引き得る
        return self.chaos or any(t == "ramp_hit" for t, _ in self.behaviors)

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "experience": self.experience,
            "hp": self.hp, "max_hp": self.max_hp, "attack": self.attack,
            "difficulty": self.difficulty, "is_strong": self.is_strong,
            "chaos": self.chaos,
        }


@dataclass
class Node:
    """フロアツリーの1ノード。"""
    id: str               # 'L','M','R','A','B','C','D','E','X','Y','Z','GATE'
    kind: str             # 'enemy' | 'treasure' | 'heal' | 'gate'
    row: int              # 1,2,3
    parents: list[str]
    parent_type: str      # 'single' | 'multi' | 'root'
    enemy_id: Optional[str] = None
    resolved: bool = False
    # 宝箱の事前抽選値（生成時に親の強敵性込みで確定）
    treasure_roll: Optional[float] = None
    has_treasure: Optional[bool] = None
    fixed_mod: Optional[str] = None      # 1F確定宝箱の mod id（hansha）

    def snapshot(self, state: str) -> dict[str, Any]:
        # resolved は engine 側の解決状態（state）から導出する。
        # Node.resolved 属性はエンジンが更新しないため state を正とする。
        return {
            "id": self.id, "kind": self.kind, "row": self.row,
            "parents": list(self.parents), "parent_type": self.parent_type,
            "resolved": state == "resolved", "state": state,
        }


@dataclass
class Battle:
    enemy: EnemyInstance
    node_id: str
    floor: int
    turns: int = 0                       # 経過ターン
    ramp_value: int = 0                  # 現在の蓄積ダメージ（レース）
    scout_hint: Optional[str] = None
    preview: Optional[str] = None        # 先読みで公開した次行動（表示用文言）
    pending_action: Optional[str] = None # 先読みで先引きした次行動（消費される）
    kouki_cooldown: int = 0              # 好機の残クールダウン
    log: list[dict] = field(default_factory=list)  # 表示専用・使い捨て
    side_bet_total: int = 0              # サイドベット『読み宣言』累計額（per_battle_cap 判定用）
    side_bet_result: Optional[dict] = None  # 直近ターンの的中/払戻（表示専用・次ターンでクリア）
    last_action: Optional[str] = None    # 直近ターンで実現した敵の行動（ログ表示済みの公開結果・表示契約用）
    last_guard: Optional[bool] = None    # 直近ターンに受けを選んだか（表示契約用）

    def add_log(self, text: str, kind: str = "info") -> None:
        self.log.append({"t": text, "k": kind})


@dataclass
class RunRecord:
    """統計専用・永続。combat_log とは別物（同期しない）。"""
    run_id: str
    seed: int
    bot_type: str = "human"
    cleared: bool = False
    floor_reached: int = 1
    total_turns: int = 0
    final_hp: int = 0
    mods_acquired: list[str] = field(default_factory=list)
    gold_earned: int = 0
    gold_spent: dict[str, int] = field(default_factory=lambda: {
        "scout": 0, "heal_small": 0, "heal_large": 0,
        "attack_boost": 0, "gate_guarantee": 0, "treasure_reroll": 0,
    })
    enemies_defeated: list[dict] = field(default_factory=list)
    death_cause: Optional[str] = None
    death_floor: Optional[int] = None
    permanent_upgrades_state: dict[str, int] = field(default_factory=dict)
    gate_guarantee_stacks: int = 0  # ゲート保証の重ねがけ回数（ラン合計・GDD §19.1 v0.9追加）
    turn_history: list[dict] = field(default_factory=list)  # 検死/リプレイ用（ターン開始前スナップショット付き）。snapshot()には含めない（内部専用）。

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id, "seed": self.seed, "bot_type": self.bot_type,
            "cleared": self.cleared, "floor_reached": self.floor_reached,
            "total_turns": self.total_turns, "final_hp": self.final_hp,
            "mods_acquired": list(self.mods_acquired),
            "gold_earned": self.gold_earned, "gold_spent": dict(self.gold_spent),
            "enemies_defeated": list(self.enemies_defeated),
            "death_cause": self.death_cause, "death_floor": self.death_floor,
            "permanent_upgrades_state": dict(self.permanent_upgrades_state),
            "gate_guarantee_stacks": self.gate_guarantee_stacks,
        }


@dataclass
class Floor:
    """生成済みフロア（ノードグラフ）。"""
    floor_number: int
    name: str
    nodes: dict[str, Node]            # id -> Node
    gate_result_table: dict[str, float]
    floor_multiplier: float

    def node(self, node_id: str) -> Node:
        return self.nodes[node_id]
