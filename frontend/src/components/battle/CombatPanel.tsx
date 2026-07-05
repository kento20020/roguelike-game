import { useEffect, useState } from "react";
import clsx from "clsx";
import type { Battle, Player, SideBet } from "../../api/types";
import { experienceMeta, behaviorMeta, BEHAVIOR, TELL_META } from "../../lib/labels";
import Icon from "../common/Icon";
import Motif from "../common/Motif";
import HpBar from "../common/HpBar";
import CombatLog from "./CombatLog";
import BehaviorGlossary from "../common/BehaviorGlossary";
import { useCombatFx } from "../../hooks/useCombatFx";

// ボタンとして提示する賭け額の候補（UI表現の選択）。有効範囲・払戻・上限の規則は
// battle.side_bet（正本 config.json をバックエンドが供給）に従い、ここでは数値規則を複製しない。
const SIDE_BET_AMOUNT_PRESETS = [5, 10, 20];

// チップの山（賭け累計の可視化）: 最小賭け単位=1チップ相当。per_battle_cap(既定40)/最小賭け(既定5)=8枚で満杯になる想定。
const CHIP_PILE_UNIT = 5;
const CHIP_PILE_MAX = 8;

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
          // テル試作: バックエンドが返した気配信頼度ラベルのみで駆動（フロントで確率・weightは計算しない）。
          const tell = TELL_META[battle.tell_reliability ?? ""];
          return (
            <div
              className="flex flex-col items-center"
              style={{ marginTop: 12, gap: 4, padding: "8px 16px", borderRadius: 8, border: `1px solid ${nb.color}`, background: "var(--paper2)" }}
            >
              <div className="flex items-center gap-2">
                <span className="label" style={{ color: "var(--brass)" }}>先読み · 確定</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: nb.color }}>次は {nb.jp}</span>
                {tell && (
                  <>
                    <span style={{ width: 1, height: 14, background: "var(--rule2)", flex: "none" }} />
                    <span
                      key={`tell-${battle.turns}`}
                      className="pill"
                      style={{
                        color: tell.color,
                        borderColor: tell.color,
                        borderStyle: "dashed",
                        background: tell.bg,
                        fontSize: 10.5,
                        gap: 5,
                        animation: "fadeUp .3s var(--ease)",
                      }}
                      title={`気配の信頼度: この敵の行動パターンはどれくらい読みやすいか（${tell.hint}）。先読みの確定情報とは違い、あくまで傾向のヒント`}
                    >
                      <span style={{ width: 5, height: 5, borderRadius: 999, background: tell.color, flex: "none" }} />
                      気配 · {tell.jp}
                    </span>
                  </>
                )}
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
        {fx.playerCritFlash && <span className="fx-crit-flash" />}
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

      <SideBetResultCard key={battle.turns} result={battle.side_bet_result} />

      {/* サイドベットは「攻撃する/受ける」に一切影響しない独立した賭け（GDD §15.4）だが、
          宣言はボタンを押す前に決める必要があるため、コミット操作(攻撃/受け)より上に置く。
          真鍮の縁取りで戦闘の主フローとは別の「賭けの窓口」であることを視覚的に区別する。 */}
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
    </section>
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
