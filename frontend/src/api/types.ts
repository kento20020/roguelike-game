// バックエンド app/schemas/api_schemas.py と同形（GDD §25.5: 型を共有）。
// 将来は OpenAPI から自動生成も可。

export type Phase =
  | "exploring"
  | "battle"
  | "treasure_preview"
  | "treasure_opened"
  | "heal"
  | "gate_preview"
  | "gate_resolve"
  | "next_floor"
  | "cleared"
  | "dead";

export type NodeKind = "enemy" | "treasure" | "heal" | "gate" | "gate_route";
export type NodeState = "locked" | "available" | "resolved";
export type SinkType =
  | "scout"
  | "heal_small"
  | "heal_large"
  | "attack_boost"
  | "gate_guarantee"
  | "treasure_reroll";
export type ActionType =
  | "select_node"
  | "attack"
  | "guard"
  | "use_sink"
  | "treasure_open"
  | "treasure_reroll"
  | "dismiss"
  | "gate_resolve";

export interface Player {
  hp: number;
  max_hp: number;
  attack: number;
  chips: number;
  mods: string[];
  stance_multiplier: number;
  attack_boost_pending: boolean;
}

export interface FloorNode {
  id: string;
  kind: NodeKind;
  row: number;
  parents: string[];
  parent_type: string;
  resolved: boolean;
  state: NodeState;
  // 敵ノードのみ（L2/L3 開示）。確率は含まれない。
  experience?: string | null;
  name?: string | null;
  is_strong?: boolean | null;
  max_hp?: number | null;
}

export interface Floor {
  floor_number: number;
  nodes: Record<string, FloorNode>;
}

export interface Enemy {
  id: string;
  name: string;
  experience: string;
  hp: number;
  max_hp: number;
  attack: number;
  difficulty: number;
  is_strong: boolean;
  chaos: boolean;
}

export interface LogLine {
  t: string;
  k: string;
}

export interface Battle {
  enemy: Enemy;
  turns: number;
  ramp_value: number;
  scout_hint: string | null;
  preview: string | null;
  next_action?: string | null; // 先読みが公開した確定の次手の種別
  log: LogLine[];
}

export interface ActionItem {
  type: ActionType;
  node?: string | null;
  sink?: SinkType | null;
  cost?: number | null;
}

export interface RunRecord {
  run_id: string;
  seed: number;
  bot_type: string;
  cleared: boolean;
  floor_reached: number;
  total_turns: number;
  final_hp: number;
  mods_acquired: string[];
  gold_earned: number;
  gold_spent: Record<string, number>;
  enemies_defeated: Array<Record<string, unknown>>;
  death_cause: string | null;
  death_floor: number | null;
  permanent_upgrades_state: Record<string, number>;
  [extra: string]: unknown;
}

export interface GameState {
  session_id: string;
  phase: Phase;
  current_floor: number;
  player: Player | null;
  floor: Floor | null;
  battle: Battle | null;
  pending: Record<string, unknown>;
  available_actions: ActionItem[];
  run_record: RunRecord | null;
}

export interface UpgradeState {
  points: number;
  levels: Record<string, number>;
  maxes: Record<string, number>;
}

// 技(mod)の表示用カタログ（バックエンド /api/catalog/mods・mods.json 由来）。
export interface ModCatalogItem {
  id: string;
  name: string;
  effect_1: string;
  effect_stack: string;
}

// 検死レポート＋リプレイ（GET /run/{sid}/postmortem）。致命ターン1つの反実仮想＋ターンリプレイ。
export interface TurnPreSnapshot {
  player: { hp: number; max_hp: number; [extra: string]: unknown };
  battle: { turns: number; ramp_value: number; kouki_cooldown: number; node_id: string; floor: number };
  enemy: { hp: number; max_hp: number; [extra: string]: unknown };
}

export interface TurnHistoryEntry {
  node_id: string;
  enemy_id: string;
  guard: boolean;
  action: string;
  dealt: number;
  incoming: number;
  player_hp_before: number;
  player_hp_after: number;
  enemy_hp_before: number;
  enemy_hp_after: number;
  ramp_value: number;
  kouki_cooldown: number;
  pre_turn_snapshot: TurnPreSnapshot;
  [extra: string]: unknown;
}

export interface PostmortemCounterfactualResult {
  action: string;
  dealt: number;
  incoming: number;
  player_hp: number;
  enemy_hp: number;
  enemy_dead: boolean;
  player_dead: boolean;
}

export interface PostmortemCounterfactual {
  fatal_turn_index: number;
  original_guard: boolean;
  counterfactual_guard: boolean;
  category: "unavoidable" | "avoidable_guard" | "avoidable_attack" | "mutual_kill_victory";
  avoidable: boolean | null;
  message: string;
  counterfactual_result: PostmortemCounterfactualResult;
}

export interface PostmortemResponse {
  run_id: string;
  turn_history: TurnHistoryEntry[];
  fatal_turn_index: number;
  counterfactual: PostmortemCounterfactual;
  created_at?: string | null;
}
