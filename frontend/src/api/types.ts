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
  guard_uses?: number; // 受けの使用回数（当戦闘・重ねがけ減衰の現在段・戦闘毎リセット）
  guard_next_scale?: number; // 次の受けの効き（軽減量スケール = stack_decay^guard_uses・1.0→0.5→0.25…・バックエンド算出）
  scout_hint: string | null;
  preview: string | null;
  next_action?: string | null; // 先読みが公開した確定の次手の種別
  tell_reliability?: string | null; // テル試作: 次手公開時の敵ごとの気配信頼度（high/mid/low）
  log: LogLine[];
  side_bet_total?: number; // サイドベット『読み宣言』の戦闘あたり累計額（per_battle_cap 可視化用）
  side_bet_result?: { hit: boolean; payout: number } | null; // サイドベット直近ターン結果（次ターンでクリア）
  last_turn?: { action: string; guard: boolean } | null; // 直近ターンの実現結果（ログ表示済みの公開情報のみ）
  side_bet?: {
    min_amount: number;
    max_amount: number;
    payout_multiplier: number;
    per_battle_cap: number;
  } | null; // サイドベット表示規則（正本 config.json side_bet。フロントで定数を複製しない）
}

// サイドベット『読み宣言』: 次の敵行動(behavior)への任意ベット（stream2の既存ロールで判定・新規RNG消費なし）。
export interface SideBet {
  behavior: string;
  amount: number;
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
  gate_guarantee_stacks?: number; // ゲート保証の重ねがけ回数（ラン累計・GDD §19.1）
  // OPEN-024/025 テレメトリ（旧レコードは既定値）
  data_version?: string;
  strategy_version?: string | null;
  sink_use_counts?: Record<string, number>;
  gate_results?: Array<{ floor: number; outcome: string }>;
  action_counts?: Record<string, number>;
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

// 敵の表示用カタログ（/api/catalog/enemies）。id/name/experienceのみ・weight非開示。
export interface EnemyCatalogItem {
  id: string;
  name: string;
  experience: string;
}

// ディーラー調書（/api/profile/dossier）。自分が観測した行動頻度のみ・真のweight非開示。
export interface DossierBehavior {
  behavior: string;
  count: number;
  n_total: number;
  ci_low: number;
  ci_high: number;
}

export interface DossierEnemy {
  enemy_id: string;
  behaviors: DossierBehavior[];
  n_total: number;
}
