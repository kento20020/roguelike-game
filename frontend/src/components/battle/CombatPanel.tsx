import { useEffect, useState } from "react";
import type { Battle, Player, SideBet } from "../../api/types";
import { experienceMeta, behaviorMeta, BEHAVIOR } from "../../lib/labels";
import Icon from "../common/Icon";
import Motif from "../common/Motif";
import HpBar from "../common/HpBar";
import CombatLog from "./CombatLog";
import BehaviorGlossary from "../common/BehaviorGlossary";
import { useCombatFx } from "../../hooks/useCombatFx";

const SIDE_BET_AMOUNTS = [5, 10, 20];
// config.json side_bet ブロックと同期（表示計算専用の静的値。正本はバックエンド）。
const PAYOUT_MULTIPLIER = 3;
const PER_BATTLE_CAP = 40;

// 戦闘ステージ全体（design 忠実）：敵名・体験タイプ・敵HP・ramp・先読み・ログ・自分パネル・攻撃。
export default function CombatPanel({
  battle,
  player,
  busy,
  canAttack,
  canGuard,
  onAttack,
  onGuard,
}: {
  battle: Battle;
  player: Player;
  busy: boolean;
  canAttack: boolean;
  canGuard: boolean;
  onAttack: (sideBet?: SideBet) => void;
  onGuard: (sideBet?: SideBet) => void;
}) {
  const e = battle.enemy;
  const exp = experienceMeta(e.experience);
  // 演出は GameState の差分（実現結果）だけから駆動する（確率・非表示weightは見ない）。
  const fx = useCombatFx(battle, player);

  // サイドベット『読み宣言』: 次の敵行動への任意ベット。賭けない状態がデフォルト。
  const [betBehavior, setBetBehavior] = useState<string | null>(null);
  const [betAmount, setBetAmount] = useState<number>(SIDE_BET_AMOUNTS[0]);

  const capTotal = battle.side_bet_total ?? 0;
  const remainingCap = Math.max(0, PER_BATTLE_CAP - capTotal);
  const capRatio = PER_BATTLE_CAP > 0 ? capTotal / PER_BATTLE_CAP : 0;
  const capColor = capRatio >= 0.85 ? "var(--danger)" : capRatio >= 0.5 ? "var(--brass)" : "var(--ink3)";
  // 上限/残高から見て、いま選べる賭け額が1つも無い＝実質ベット不可（事前抑制）。
  const bettingDisabled = SIDE_BET_AMOUNTS.every((amt) => amt > remainingCap || amt > player.chips);
  const canBet = player.chips >= betAmount && betAmount <= remainingCap;
  const previewPayout = Math.round(betAmount * (PAYOUT_MULTIPLIER - 1));

  useEffect(() => {
    if (bettingDisabled && betBehavior !== null) setBetBehavior(null);
  }, [bettingDisabled, betBehavior]);

  const sideBet: SideBet | undefined =
    betBehavior != null && canBet ? { behavior: betBehavior, amount: betAmount } : undefined;

  const statusText = betBehavior
    ? `${behaviorMeta(betBehavior)?.jp ?? betBehavior} に ${betAmount} 賭ける${canBet ? "" : player.chips < betAmount ? "（チップ不足）" : "（賭け上限超過）"}`
    : "未選択＝賭けない（デフォルト）";

  function submitAttack() {
    onAttack(sideBet);
    setBetBehavior(null);
  }
  function submitGuard() {
    onGuard(sideBet);
    setBetBehavior(null);
  }

  return (
    <section
      className="flex flex-col items-center"
      style={{ maxWidth: 780, margin: "0 auto", animation: "fadeUp .32s var(--ease)" }}
    >
      <span className="label" style={{ letterSpacing: "0.22em" }}>
        {exp.en || "Encounter"}
      </span>
      <div className="flex items-center gap-3" style={{ marginTop: 9 }}>
        <span style={{ color: exp.color, display: "flex" }}>
          <Icon type={exp.iconType} size={24} />
        </span>
        <h2 style={{ margin: 0, fontFamily: "var(--serif)", fontSize: 35, lineHeight: 1 }}>{e.name}</h2>
        {e.is_strong && (
          <span className="pill" style={{ color: "var(--brass)", borderColor: "var(--brass)" }}>
            大物
          </span>
        )}
      </div>
      <div
        style={{
          marginTop: 13,
          display: "inline-flex",
          alignItems: "center",
          gap: 11,
          padding: "7px 15px",
          borderRadius: 999,
          border: `1px solid ${exp.color}`,
          background: "var(--paper2)",
        }}
      >
        <Motif type={exp.iconType} color={exp.color} />
        <span style={{ fontFamily: "var(--sans)", fontSize: 12.5 }}>
          <span style={{ color: exp.color, fontWeight: 600 }}>{exp.jp}</span> · {exp.tend}
        </span>
      </div>

      <div
        className={`flex items-center gap-3${fx.enemyShaking ? " fx-shake" : ""}`}
        style={{ marginTop: 22, position: "relative" }}
      >
        <span className="label">HP</span>
        <HpBar current={e.hp} max={e.max_hp} width={340} colorOverride="var(--accent)" />
        <span style={{ fontFamily: "var(--mono)", fontSize: 13 }}>
          {e.hp}
          <span style={{ color: "var(--ink3)" }}> / {e.max_hp}</span>
        </span>
        {fx.enemyDamage && (
          <span key={fx.enemyDamage.id} className="fx-dmg-pop">
            −{fx.enemyDamage.amount}
          </span>
        )}
      </div>

      {battle.ramp_value > 0 && (
        <div
          style={{ marginTop: 12, display: "inline-flex", alignItems: "center", gap: 8, padding: "5px 12px", borderRadius: 999, border: "1px solid var(--danger)", background: "var(--paper2)" }}
        >
          <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--danger)", animation: "pulseDot 1.1s ease-in-out infinite" }} />
          <span style={{ fontSize: 11, color: "var(--ink2)" }}>蓄積ダメージ</span>
          <span style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--danger)" }}>{battle.ramp_value}</span>
        </div>
      )}
      {(() => {
        // 先読み＝確定の次手（種別を明示）／スカウト＝傾向（控えめ）。
        const nb = behaviorMeta(battle.next_action);
        if (nb) {
          return (
            <div
              className="flex flex-col items-center"
              style={{ marginTop: 12, gap: 4, padding: "8px 16px", borderRadius: 8, border: `1px solid ${nb.color}`, background: "var(--paper2)" }}
            >
              <div className="flex items-center gap-2">
                <span className="label" style={{ color: "var(--brass)" }}>先読み · 確定</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: nb.color }}>次は {nb.jp}</span>
              </div>
              <span style={{ fontSize: 11.5, color: "var(--ink2)" }}>{nb.meaning}</span>
              <span style={{ fontSize: 11.5, color: "var(--brass)" }}>▸ {nb.guardAdvice}</span>
            </div>
          );
        }
        if (battle.scout_hint) {
          return (
            <div
              style={{ marginTop: 12, display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 13px", borderRadius: 6, border: "1px dashed var(--accentRing)", background: "var(--accentSoft)" }}
            >
              <span className="label" style={{ color: "var(--accent)" }}>スカウト · 傾向</span>
              <span style={{ fontSize: 12.5 }}>{battle.scout_hint}</span>
            </div>
          );
        }
        return null;
      })()}

      <div style={{ width: "100%", maxWidth: 560, marginTop: 22 }}>
        <CombatLog log={battle.log} />
      </div>
      <div style={{ width: "100%", maxWidth: 560, marginTop: 12 }}>
        <BehaviorGlossary />
      </div>

      <div
        className={fx.playerShaking ? "fx-shake" : undefined}
        style={{ marginTop: 22, width: "100%", maxWidth: 560, display: "flex", alignItems: "center", gap: 16, padding: "12px 18px", borderRadius: 8, border: "1px solid var(--rule2)", background: "var(--paper2)", position: "relative", overflow: "hidden" }}
      >
        {fx.playerCritFlash && <span className="fx-crit-flash" style={{ background: fx.playerCritColor }} />}
        {fx.playerGuardFlash && <span className="fx-guard-flash" />}
        <span className="label" style={{ whiteSpace: "nowrap" }}>You · あなた</span>
        <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 10, position: "relative" }}>
          <span style={{ fontSize: 10, color: "var(--ink2)" }}>HP</span>
          <HpBar current={player.hp} max={player.max_hp} width="100%" />
          <span style={{ fontFamily: "var(--mono)", fontSize: 13, whiteSpace: "nowrap" }}>
            {player.hp}
            <span style={{ color: "var(--ink3)" }}> / {player.max_hp}</span>
          </span>
          {fx.playerDamage && (
            <span key={fx.playerDamage.id} className="fx-dmg-pop">
              −{fx.playerDamage.amount}
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, paddingLeft: 16, borderLeft: "1px solid var(--rule)", color: "var(--accent)" }}>
          <Icon type="sword" size={16} />
          <span className="label">攻撃力</span>
          <span style={{ fontFamily: "var(--mono)", fontSize: 16, fontWeight: 600 }}>{player.attack}</span>
        </div>
      </div>

      <div className="flex items-center gap-3" style={{ marginTop: 18 }}>
        <button onClick={submitAttack} disabled={!canAttack || busy} className="btn" style={{ minWidth: 200, height: 50 }}>
          攻撃する — {player.attack}
          {player.attack_boost_pending ? "（強化）" : ""}
        </button>
        <button onClick={submitGuard} disabled={!canGuard || busy} className="btn btn-ghost" style={{ minWidth: 130, height: 50 }}>
          受ける
        </button>
      </div>
      <div style={{ marginTop: 9, fontSize: 11, color: "var(--ink3)" }}>
        攻撃＝確率で相手が反応／受け＝与ダメ半減・被ダメを大きく軽減（先読みで危険を受け流す）
      </div>

      {battle.side_bet_result && (
        <div
          className="flex items-center gap-2"
          style={{
            marginTop: 14,
            padding: battle.side_bet_result.hit ? "8px 18px" : "7px 16px",
            borderRadius: 999,
            border: `1px solid ${battle.side_bet_result.hit ? "var(--brass)" : "var(--danger)"}`,
            background: battle.side_bet_result.hit
              ? "color-mix(in srgb, var(--brass) 16%, var(--paper2))"
              : "var(--paper2)",
            boxShadow: battle.side_bet_result.hit
              ? "0 0 0 3px color-mix(in srgb, var(--brass) 24%, transparent), 0 8px 22px rgba(201, 162, 75, 0.25)"
              : "none",
            opacity: battle.side_bet_result.hit ? 1 : 0.85,
            animation: battle.side_bet_result.hit ? "sideBetHit .4s var(--ease)" : "sideBetMiss .28s var(--ease)",
          }}
        >
          <span
            style={{
              fontSize: 12.5,
              fontWeight: battle.side_bet_result.hit ? 700 : 500,
              color: battle.side_bet_result.hit ? "var(--brass)" : "var(--ink2)",
            }}
          >
            サイドベット · {battle.side_bet_result.hit ? "読み的中" : "外れ"}
          </span>
          <span
            style={{
              fontFamily: "var(--mono)",
              fontSize: battle.side_bet_result.hit ? 15 : 13,
              fontWeight: battle.side_bet_result.hit ? 700 : 400,
              color: battle.side_bet_result.hit ? "var(--brass)" : "var(--danger)",
            }}
          >
            {battle.side_bet_result.payout >= 0 ? "+" : ""}
            {battle.side_bet_result.payout}
          </span>
        </div>
      )}

      <div
        className="flex flex-col items-center"
        style={{
          marginTop: 16,
          width: "100%",
          maxWidth: 560,
          gap: 10,
          padding: "14px 16px",
          borderRadius: 8,
          border: "1px dashed var(--rule2)",
          background: "var(--paper2)",
        }}
      >
        <div className="flex items-center justify-between" style={{ width: "100%" }}>
          <span className="label" style={{ color: "var(--brass)" }}>
            サイドベット · 読み宣言（任意・次の敵行動を予想）
          </span>
          <div className="flex items-center gap-2">
            <span style={{ fontSize: 10, color: "var(--ink3)" }}>賭け累計</span>
            <HpBar current={capTotal} max={PER_BATTLE_CAP} width={64} colorOverride={capColor} />
            <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: capColor }}>
              {capTotal}/{PER_BATTLE_CAP}
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
            return (
              <button
                key={b.key}
                disabled={busy || bettingDisabled}
                onClick={() => setBetBehavior(active ? null : b.key)}
                title={b.jp}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 40,
                  height: 40,
                  borderRadius: 8,
                  border: `${active ? 2 : 1}px solid ${active ? b.color : "var(--rule2)"}`,
                  background: active ? `color-mix(in srgb, ${b.color} 18%, var(--paper2))` : "transparent",
                  boxShadow: active ? `0 0 0 3px color-mix(in srgb, ${b.color} 22%, transparent)` : "none",
                  color: active ? b.color : "var(--ink3)",
                  opacity: busy || bettingDisabled ? 0.4 : active ? 1 : 0.85,
                  transform: active ? "scale(1.08)" : "scale(1)",
                  transition: "all .14s var(--ease)",
                  cursor: busy || bettingDisabled ? "default" : "pointer",
                }}
              >
                <Icon type={b.iconType} size={18} />
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          {SIDE_BET_AMOUNTS.map((amt) => {
            const affordable = player.chips >= amt && amt <= remainingCap;
            const active = betAmount === amt;
            return (
              <button
                key={amt}
                disabled={busy || !affordable}
                onClick={() => setBetAmount(amt)}
                className={active ? "btn" : "btn btn-ghost"}
                style={{
                  minWidth: 56,
                  height: 32,
                  fontSize: 12,
                  padding: "0 10px",
                  transform: active ? "scale(1.06)" : "scale(1)",
                  boxShadow: active ? "0 0 0 2px color-mix(in srgb, var(--accent) 32%, transparent)" : "none",
                  transition: "all .14s var(--ease)",
                }}
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
    </section>
  );
}
