import { useEffect, useState } from "react";
import clsx from "clsx";
import type { Battle, Player } from "../../api/types";
import { BEHAVIOR } from "../../lib/labels";
import Icon from "../common/Icon";
import type { SideBetState } from "../../hooks/useSideBet";

// チップの山（賭け累計の可視化）: 最小賭け単位=1チップ相当。per_battle_cap(既定40)/最小賭け(既定5)=8枚で満杯になる想定。
const CHIP_PILE_UNIT = 5;
const CHIP_PILE_MAX = 8;

// サイドベットは「攻撃する/受ける」に一切影響しない独立した賭け（GDD §15.4）だが、
// 宣言はボタンを押す前に決める必要があるため、コミット操作(攻撃/受け)より上に置く。
// 真鍮の縁取りで戦闘の主フローとは別の「賭けの窓口」であることを視覚的に区別する。
// CombatPanel から抽出（状態・派生値は useSideBet フックに集約）。
export default function SideBetPanel({
  battle,
  player,
  busy,
  sb,
}: {
  battle: Battle;
  player: Player;
  busy: boolean;
  sb: SideBetState;
}) {
  const {
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
  } = sb;

  return (
    <>
      <SideBetResultCard key={battle.turns} result={battle.side_bet_result} />

      <div
        className="flex flex-col items-center"
        style={{
          marginTop: 16,
          width: "100%",
          maxWidth: 560,
          gap: 10,
          padding: "14px 16px",
          borderRadius: 8,
          border: "1px solid var(--brassSoft)",
          background: "var(--paper2)",
        }}
      >
        <div className="flex items-center justify-between" style={{ width: "100%" }}>
          <span className="label" style={{ color: "var(--brass)" }}>
            サイドベット · 読み宣言（任意・次の敵行動を予想）
          </span>
          <div className="flex items-center gap-2">
            <span style={{ fontSize: 10, color: "var(--ink3)" }}>賭け累計</span>
            <ChipPile total={capTotal} />
            <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: capColor }}>
              {capTotal}/{perBattleCap}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap" style={{ width: "100%" }}>
          <button
            disabled={busy}
            onClick={() => setBetBehavior(null)}
            title="賭けない"
            style={{
              display: "flex",
              alignItems: "center",
              height: 40,
              padding: "0 12px",
              borderRadius: 8,
              fontSize: 12,
              border: `1px solid ${betBehavior === null ? "var(--ink2)" : "var(--rule2)"}`,
              background: betBehavior === null ? "var(--paper3)" : "transparent",
              color: betBehavior === null ? "var(--ink)" : "var(--ink3)",
              transform: betBehavior === null ? "scale(1.04)" : "scale(1)",
              transition: "all .14s var(--ease)",
              cursor: busy ? "default" : "pointer",
            }}
          >
            見送る
          </button>
          {BEHAVIOR.map((b) => {
            const active = betBehavior === b.key;
            // 先読みで確定した次手＝この行動なら、NextActionPreview と同じ図形・同色で対応づけて強調する。
            const predicted = battle.next_action === b.key;
            const emphasized = active || predicted;
            return (
              <div key={b.key} style={{ position: "relative", display: "flex" }}>
                {predicted && !active && (
                  <span
                    style={{
                      position: "absolute",
                      top: -7,
                      left: "50%",
                      transform: "translateX(-50%)",
                      padding: "1px 5px",
                      borderRadius: 999,
                      fontSize: 8.5,
                      lineHeight: 1.2,
                      letterSpacing: "0.04em",
                      whiteSpace: "nowrap",
                      background: b.color,
                      color: "var(--paper)",
                      zIndex: 1,
                      pointerEvents: "none",
                    }}
                  >
                    読み
                  </span>
                )}
                <button
                  disabled={busy || bettingDisabled}
                  onClick={() => setBetBehavior(active ? null : b.key)}
                  title={predicted ? `${b.jp}（先読みで確定した次手）` : b.jp}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 40,
                    height: 40,
                    borderRadius: 8,
                    border: `${emphasized ? 2 : 1}px solid ${emphasized ? b.color : "var(--rule2)"}`,
                    background: active
                      ? `color-mix(in srgb, ${b.color} 18%, var(--paper2))`
                      : predicted
                        ? `color-mix(in srgb, ${b.color} 9%, var(--paper2))`
                        : "transparent",
                    boxShadow: active
                      ? `0 0 0 3px color-mix(in srgb, ${b.color} 22%, transparent)`
                      : predicted
                        ? `0 0 0 2px color-mix(in srgb, ${b.color} 26%, transparent)`
                        : "none",
                    color: emphasized ? b.color : "var(--ink3)",
                    opacity: busy || bettingDisabled ? 0.4 : emphasized ? 1 : 0.85,
                    transform: active ? "scale(1.08)" : predicted ? "scale(1.04)" : "scale(1)",
                    transition: "all .14s var(--ease)",
                    cursor: busy || bettingDisabled ? "default" : "pointer",
                  }}
                >
                  <Icon type={b.iconType} size={18} />
                </button>
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-3">
          {amounts.map((amt) => {
            const affordable = player.chips >= amt && amt <= remainingCap;
            const active = betAmount === amt;
            return (
              <button
                key={amt}
                disabled={busy || !affordable}
                onClick={() => setBetAmount(amt)}
                title={`${amt}チップ賭ける`}
                className={clsx("chip-btn", active && "chip-btn--active")}
              >
                {amt}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-3" style={{ minHeight: 16 }}>
          <span style={{ fontSize: 11, color: betBehavior ? "var(--brass)" : "var(--ink3)" }}>{statusText}</span>
          {betBehavior && (
            <span
              style={{
                fontSize: 11,
                fontFamily: "var(--mono)",
                color: canBet ? "var(--moss)" : "var(--ink3)",
              }}
            >
              的中時 +{previewPayout}
            </span>
          )}
        </div>
      </div>
    </>
  );
}

// 賭け累計チップの山: 新しく積まれた分だけ(既存の枚数はkeyが変わらないため再アニメしない)チップが浮き上がって現れる。
function ChipPile({ total }: { total: number }) {
  const units = Math.min(CHIP_PILE_MAX, Math.round(total / CHIP_PILE_UNIT));
  if (units <= 0) return <span style={{ fontSize: 10, color: "var(--ink4)" }}>—</span>;
  return (
    <div className="flex items-center" style={{ gap: 2 }}>
      {Array.from({ length: units }, (_, i) => (
        <span key={i} className="chip-disc fx-chip-enter" />
      ))}
    </div>
  );
}

// サイドベット結果の開示: 「?」の裏面から的中/外れの表面へ1回だけめくる(CombatPanel側でturnごとにkeyを変えて再マウントさせる)。
function SideBetResultCard({ result }: { result: { hit: boolean; payout: number } | null | undefined }) {
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    if (!result) return;
    const t = window.setTimeout(() => setFlipped(true), 30);
    return () => window.clearTimeout(t);
  }, [result]);

  if (!result) return null;

  return (
    <div className="flex items-center gap-3" style={{ marginTop: 14 }}>
      <div className="flip-scene">
        <div className={clsx("flip-card", flipped && "flipped")}>
          <div className="flip-face flip-back">?</div>
          <div
            className="flip-face flip-front"
            style={{
              borderColor: result.hit ? "var(--brass)" : "var(--danger)",
              color: result.hit ? "var(--brass)" : "var(--danger)",
              background: result.hit
                ? "color-mix(in srgb, var(--brass) 16%, var(--felt))"
                : "var(--felt)",
              boxShadow: result.hit ? "0 0 18px rgba(201, 162, 75, 0.35)" : "none",
            }}
          >
            {result.hit ? "WIN" : "LOSS"}
          </div>
        </div>
      </div>
      <div className="flex flex-col" style={{ gap: 2 }}>
        <span style={{ fontSize: 12, color: result.hit ? "var(--brass)" : "var(--ink2)" }}>
          前ターンの読み宣言 · {result.hit ? "読み的中" : "外れ"}
        </span>
        <span
          className="font-mono fx-counter-tick"
          style={{
            fontSize: 16,
            fontWeight: 700,
            color: result.hit ? "var(--brass)" : "var(--danger)",
          }}
        >
          {result.payout >= 0 ? "+" : ""}
          {result.payout}
        </span>
      </div>
    </div>
  );
}
