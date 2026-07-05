// 表示用ラベル・色・アイコン種別の一元定義（数値=確率は持たない＝バランスはバックエンド）。
// 色・傾向は design の EXP/MOD/sink 定義を踏襲。
import type { NodeKind, SinkType } from "../api/types";

// 体験タイプ（enemies.json の experience は日本語）。color/tend は design 由来。
export interface ExpMeta {
  jp: string;
  en: string;
  iconType: string; // Icon/Motif のキー
  color: string;
  tend: string;
}

export const EXPERIENCE: Record<string, ExpMeta> = {
  削り合い: { jp: "削り合い", en: "Attrition", iconType: "grind", color: "#6E93B8", tend: "じわじわ削る・堅実" },
  賭け: { jp: "賭け", en: "Wager", iconType: "gamble", color: "#C2493B", tend: "大当たりか空振り" },
  レース: { jp: "レース", en: "Ramp", iconType: "race", color: "#C9A24B", tend: "長引くほど重い" },
  ずれ: { jp: "ずれ", en: "Slip", iconType: "evade", color: "#5E9A78", tend: "攻撃を空振りさせる" },
  カオス: { jp: "カオス", en: "Chaos", iconType: "chaos", color: "#9C79BC", tend: "予測不能" },
};

export function experienceMeta(exp: string | null | undefined): ExpMeta {
  return (exp && EXPERIENCE[exp]) || { jp: exp ?? "?", en: "", iconType: "default", color: "var(--ink2)", tend: "" };
}

// フロア名（floors.json 正本。装飾的固有名は無い）。
export const FLOOR_NAMES: Record<number, string> = {
  1: "1F チュートリアル",
  2: "2F",
  3: "3F",
  4: "4F",
  5: "5F 頂上",
};
export function floorName(n: number): string {
  return FLOOR_NAMES[n] ?? `${n}F`;
}

// 敵以外のノード種別（敵は experience 側を使う）。
export const NODE_KIND: Record<NodeKind, { jp: string; iconType: string; color: string }> = {
  enemy: { jp: "卓", iconType: "sword", color: "var(--ink2)" },
  treasure: { jp: "宝箱", iconType: "treasure", color: "var(--brass)" },
  heal: { jp: "控え室", iconType: "heal", color: "var(--moss)" },
  gate: { jp: "胴元の関門", iconType: "gate", color: "var(--brass)" },
  gate_route: { jp: "通路", iconType: "arrow", color: "var(--ink3)" },
};

// sink の表示（GDD §13.2）。コストは available_actions が供給（メタ強化反映済み）。
export const SINK_META: Record<SinkType, { label: string; effect: string; iconType: string }> = {
  scout: { label: "偵察", effect: "次の手を1つ読む", iconType: "eye" },
  heal_small: { label: "小回復", effect: "HPを少し戻す", iconType: "heal" },
  heal_large: { label: "大回復", effect: "HPを大きく戻す", iconType: "heal" },
  attack_boost: { label: "攻撃強化", effect: "次の一撃を重く", iconType: "sword" },
  gate_guarantee: { label: "関門保証", effect: "大ダメの確率を減らす（特殊は残る）", iconType: "shield" },
  treasure_reroll: { label: "引き直す", effect: "宝箱を引き直す", iconType: "arrow" },
};

// 技（mod）id→アイコン種別（mods.json は id がそのまま日本語名）。
export const MOD_ICON: Record<string, string> = {
  反射: "reflect",
  見切り: "evade",
  重装甲: "shield",
  好機: "star",
  先読み: "eye",
  加速止め: "cap",
};

// 技の効果説明は mods.json 由来の catalog（/api/catalog/mods）が正本。
// フロントでの重複定義（旧 MOD_EFFECT）は撤去した。
export function modLabel(id: string): string {
  return id;
}

// 敵の行動種別（combat_resolver の behaviors）。意味は定性的に説明し、確率は出さない（暗黙知 GDD §5）。
export interface BehaviorMeta {
  key: string;
  jp: string;
  meaning: string;
  color: string;
  iconType: string; // Icon のキー。色とセットでバー/CIひげ/リプレイの行タグ/サイドベットUI等の配色にも流用
  guardAdvice: string; // 先読みで確定したとき、受け（ガード）と連動した一言
}
export const BEHAVIOR: BehaviorMeta[] = [
  { key: "counter", jp: "反撃", meaning: "ほぼ等倍で殴り返す（被ダメ＝相手の攻撃力ぶん）", color: "var(--danger)", iconType: "reflect", guardAdvice: "受けると被害を抑えられる" },
  { key: "heavy_blow", jp: "強打", meaning: "たまに大振り。当たると重い（約1.8倍）", color: "var(--danger)", iconType: "sword", guardAdvice: "重い一撃。受けると大きく軽減できる" },
  { key: "evade", jp: "回避", meaning: "こちらの攻撃を空振りさせる（ダメージが通らない）", color: "var(--moss)", iconType: "evade", guardAdvice: "攻撃が空を切る手。偵察/強化に回すのも手" },
  { key: "ramp_hit", jp: "蓄積の一撃", meaning: "長引くほど蓄積が増え、まとめて返してくる", color: "var(--brass)", iconType: "race", guardAdvice: "蓄積の一撃。受けで軽減できる" },
  { key: "none", jp: "様子見", meaning: "何もしてこない（被ダメ 0）", color: "var(--ink2)", iconType: "eye", guardAdvice: "様子見。攻めどき" },
];

const BEHAVIOR_BY_KEY: Record<string, BehaviorMeta> = Object.fromEntries(BEHAVIOR.map((b) => [b.key, b]));
export function behaviorMeta(key: string | null | undefined): BehaviorMeta | undefined {
  return key ? BEHAVIOR_BY_KEY[key] : undefined;
}

// ゲート出目（floors.json gate_result_table のキー）。
export const GATE_OUTCOME: Record<string, { jp: string; color: string }> = {
  unhurt: { jp: "無傷で通過", color: "var(--moss)" },
  minor: { jp: "小ダメージで通過", color: "var(--brass)" },
  major: { jp: "大ダメージで通過", color: "var(--danger)" },
  special: { jp: "特殊・胴元の恩恵", color: "var(--brass)" },
};
export function gateOutcome(key: string) {
  return GATE_OUTCOME[key] ?? { jp: key, color: "var(--ink2)" };
}

// death_cause（機械語）の日本語化（GDD §15.1: 死亡原因は必須表示＝学習を促すため生の機械語を出さない）。
// 形式は backend/_die 準拠: "gate:{outcome}" ＝関門死／"{enemy_id}:{action}" ＝戦闘死。
// 敵名は /catalog/enemies の id→name マップを呼び出し側が供給（未取得・未知idは素通しフォールバック）。
const GATE_DEATH_JP: Record<string, string> = {
  minor: "関門の小ダメージ",
  major: "関門の大ダメージ",
};
export function deathCauseLabel(cause: string, enemyNames: Record<string, string>): string {
  const i = cause.indexOf(":");
  if (i < 0) return cause;
  const head = cause.slice(0, i);
  const tail = cause.slice(i + 1);
  if (head === "gate") return GATE_DEATH_JP[tail] ?? `関門・${gateOutcome(tail).jp}`;
  const name = enemyNames[head] ?? head;
  const behavior = behaviorMeta(tail)?.jp ?? tail;
  return `${name}（${behavior}）`;
}
