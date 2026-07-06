import { useEffect, useState } from "react";
import type { Battle, Player, SideBet } from "../api/types";
import { behaviorMeta } from "../lib/labels";

// ボタンとして提示する賭け額の候補（UI表現の選択）。有効範囲・払戻・上限の規則は
// battle.side_bet（正本 config.json をバックエンドが供給）に従い、ここでは数値規則を複製しない。
const SIDE_BET_AMOUNT_PRESETS = [5, 10, 20];

export interface SideBetState {
  amounts: number[];
  betBehavior: string | null;
  setBetBehavior: (b: string | null) => void;
  betAmount: number;
  setBetAmount: (n: number) => void;
  capTotal: number;
  perBattleCap: number;
  remainingCap: number;
  capColor: string;
  bettingDisabled: boolean;
  canBet: boolean;
  previewPayout: number;
  statusText: string;
  sideBet: SideBet | undefined;
  resetBet: () => void;
}

// サイドベット『読み宣言』: 次の敵行動への任意ベット（stream2の既存ロールで判定・新規RNG消費なし）。
// 賭けない状態がデフォルト。CombatPanel から状態・派生値を切り出したフック（UIはSideBetPanelが持つ）。
export function useSideBet(battle: Battle, player: Player): SideBetState {
  const [betBehavior, setBetBehavior] = useState<string | null>(null);
  const [betAmount, setBetAmount] = useState<number>(SIDE_BET_AMOUNT_PRESETS[0]);

  // 数値規則はバックエンド供給（battle.side_bet・正本 config.json）。未供給時のみ従来定数へ後退。
  const rules = battle.side_bet;
  const payoutMultiplier = rules?.payout_multiplier ?? 3;
  const perBattleCap = rules?.per_battle_cap ?? 40;
  const amounts = SIDE_BET_AMOUNT_PRESETS.filter(
    (amt) => amt >= (rules?.min_amount ?? 5) && amt <= (rules?.max_amount ?? 20),
  );

  const capTotal = battle.side_bet_total ?? 0;
  const remainingCap = Math.max(0, perBattleCap - capTotal);
  const capRatio = perBattleCap > 0 ? capTotal / perBattleCap : 0;
  const capColor = capRatio >= 0.85 ? "var(--danger)" : capRatio >= 0.5 ? "var(--brass)" : "var(--ink3)";
  // 上限/残高から見て、いま選べる賭け額が1つも無い＝実質ベット不可（事前抑制）。
  const bettingDisabled = amounts.every((amt) => amt > remainingCap || amt > player.chips);
  const canBet = amounts.includes(betAmount) && player.chips >= betAmount && betAmount <= remainingCap;
  const previewPayout = Math.round(betAmount * (payoutMultiplier - 1));

  useEffect(() => {
    if (bettingDisabled && betBehavior !== null) setBetBehavior(null);
  }, [bettingDisabled, betBehavior]);

  const sideBet: SideBet | undefined =
    betBehavior != null && canBet ? { behavior: betBehavior, amount: betAmount } : undefined;

  const statusText = betBehavior
    ? `${behaviorMeta(betBehavior)?.jp ?? betBehavior} に ${betAmount} 賭ける${canBet ? "" : player.chips < betAmount ? "（チップ不足）" : "（賭け上限超過）"}`
    : "未選択＝賭けない（デフォルト）";

  return {
    amounts,
    betBehavior,
    setBetBehavior,
    betAmount,
    setBetAmount,
    capTotal,
    perBattleCap,
    remainingCap,
    capColor,
    bettingDisabled,
    canBet,
    previewPayout,
    statusText,
    sideBet,
    resetBet: () => setBetBehavior(null),
  };
}
