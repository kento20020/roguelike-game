import type { Battle } from "../../api/types";
import type { ExpMeta } from "../../lib/labels";
import type { CombatFx } from "../../hooks/useCombatFx";
import EnemyPortraitCard from "../common/EnemyPortraitCard";
import HpBar from "../common/HpBar";

// 敵カードモチーフ: difficulty(1-5・正本 enemies.json)をトランプのランクに変換。数札(10)→絵札(J/Q/K)でフロア深度を表す。
function enemyRank(difficulty: number): string {
  if (difficulty >= 5) return "K";
  if (difficulty === 4) return "Q";
  if (difficulty === 3) return "J";
  return "10";
}

// 敵の状態表示: 体験タイプラベル・肖像・HPバー・蓄積ダメージ(ramp)バッジ。CombatPanel から抽出。
export default function EnemyStage({ battle, exp, fx }: { battle: Battle; exp: ExpMeta; fx: CombatFx }) {
  const e = battle.enemy;
  return (
    <>
      <span className="label" style={{ letterSpacing: "0.22em" }}>
        {exp.en || "Encounter"}
      </span>
      <div style={{ marginTop: 13 }}>
        <EnemyPortraitCard name={e.name} exp={exp} rank={enemyRank(e.difficulty)} boss={e.is_strong} />
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
    </>
  );
}
