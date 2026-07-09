import type { CSSProperties } from "react";
import EnemyPortraitCard from "../common/EnemyPortraitCard";
import { experienceMeta } from "../../lib/labels";
import BehaviorRow from "./BehaviorRow";
import type { MergedEnemy } from "./sortEnemies";

const cardStyle: CSSProperties = {
  width: "100%",
  border: "1px solid var(--rule)",
  borderRadius: 10,
  background: "var(--paper2)",
  padding: "12px 16px",
  textAlign: "left",
};

// ランク(数札/絵札)はdifficultyから算出するが、difficultyは調書APIでは非開示（開示不変条件・
// backend/tests/test_dossier.py test_catalog_enemies_never_exposes_weights）。
// そのためここでは rank を渡さず、既に開示済みの experience(色・アイコン)のみでカード化する。
// DossierPage から抽出。
export default function EnemyCard({ enemy }: { enemy: MergedEnemy }) {
  const exp = experienceMeta(enemy.experience);
  return (
    <div className="dossier-card" style={cardStyle}>
      <div className="flex items-center gap-2" style={{ marginBottom: 8 }}>
        <EnemyPortraitCard name={enemy.name} exp={exp} size="sm" />
        <span className="font-mono" style={{ fontSize: 10.5, color: "var(--ink3)", marginLeft: "auto", flex: "none" }}>
          観測 n={enemy.nTotal}
        </span>
      </div>

      {enemy.behaviors
        .slice()
        .sort((a, b) => b.count - a.count)
        .map((b) => (
          <BehaviorRow key={b.behavior} {...b} />
        ))}
    </div>
  );
}

export function UnmetEnemyCard({ enemy }: { enemy: MergedEnemy }) {
  const exp = experienceMeta(enemy.experience);
  return (
    <div className="dossier-card dossier-card--unmet" style={{ ...cardStyle, padding: "9px 16px" }}>
      <div className="flex items-center gap-2">
        <EnemyPortraitCard name={enemy.name} exp={exp} size="sm" />
        <span className="font-mono" style={{ fontSize: 10, color: "var(--ink4)", marginLeft: "auto", flex: "none" }}>
          未遭遇
        </span>
      </div>
    </div>
  );
}
