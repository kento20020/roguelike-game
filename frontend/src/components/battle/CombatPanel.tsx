import type { Battle, Player } from "../../api/types";
import { experienceMeta, behaviorMeta } from "../../lib/labels";
import Icon from "../common/Icon";
import Motif from "../common/Motif";
import HpBar from "../common/HpBar";
import CombatLog from "./CombatLog";
import BehaviorGlossary from "../common/BehaviorGlossary";

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
  onAttack: () => void;
  onGuard: () => void;
}) {
  const e = battle.enemy;
  const exp = experienceMeta(e.experience);

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

      <div className="flex items-center gap-3" style={{ marginTop: 22 }}>
        <span className="label">HP</span>
        <HpBar current={e.hp} max={e.max_hp} width={340} colorOverride="var(--accent)" />
        <span style={{ fontFamily: "var(--mono)", fontSize: 13 }}>
          {e.hp}
          <span style={{ color: "var(--ink3)" }}> / {e.max_hp}</span>
        </span>
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
        style={{ marginTop: 22, width: "100%", maxWidth: 560, display: "flex", alignItems: "center", gap: 16, padding: "12px 18px", borderRadius: 8, border: "1px solid var(--rule2)", background: "var(--paper2)" }}
      >
        <span className="label" style={{ whiteSpace: "nowrap" }}>You · あなた</span>
        <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 10, color: "var(--ink2)" }}>HP</span>
          <HpBar current={player.hp} max={player.max_hp} width="100%" />
          <span style={{ fontFamily: "var(--mono)", fontSize: 13, whiteSpace: "nowrap" }}>
            {player.hp}
            <span style={{ color: "var(--ink3)" }}> / {player.max_hp}</span>
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, paddingLeft: 16, borderLeft: "1px solid var(--rule)", color: "var(--accent)" }}>
          <Icon type="sword" size={16} />
          <span className="label">攻撃力</span>
          <span style={{ fontFamily: "var(--mono)", fontSize: 16, fontWeight: 600 }}>{player.attack}</span>
        </div>
      </div>

      <div className="flex items-center gap-3" style={{ marginTop: 18 }}>
        <button onClick={onAttack} disabled={!canAttack || busy} className="btn" style={{ minWidth: 200, height: 50 }}>
          攻撃する — {player.attack}
          {player.attack_boost_pending ? "（強化）" : ""}
        </button>
        <button onClick={onGuard} disabled={!canGuard || busy} className="btn btn-ghost" style={{ minWidth: 130, height: 50 }}>
          受ける
        </button>
      </div>
      <div style={{ marginTop: 9, fontSize: 11, color: "var(--ink3)" }}>
        攻撃＝確率で相手が反応／受け＝与ダメ半減・被ダメを大きく軽減（先読みで危険を受け流す）
      </div>
    </section>
  );
}
