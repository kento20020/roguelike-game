import { useEffect } from "react";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import { behaviorMeta, experienceMeta } from "../lib/labels";

// ディーラー調書: プレイヤーが観測した「敵の行動頻度」だけをWilson信頼区間つきで見せる。
// 真のweight/確率は一切表示しない（開示不変条件はバックエンドAPI側で担保・ここは受け取った値をそのまま出すだけ）。
// StartPage（state===null のとき）からのみ到達するため、ラン中は自然に閲覧不可。
export default function DossierPage({ onBack }: { onBack: () => void }) {
  const dossier = useGameStore((s) => s.dossier);
  const dossierLoading = useGameStore((s) => s.dossierLoading);
  const loadDossier = useGameStore((s) => s.loadDossier);
  const enemyCatalog = useGameStore((s) => s.enemyCatalog);
  const loadEnemyCatalog = useGameStore((s) => s.loadEnemyCatalog);

  useEffect(() => {
    loadDossier();
    loadEnemyCatalog();
  }, [loadDossier, loadEnemyCatalog]);

  return (
    <CenterStage maxWidth={720}>
      <span className="label">個人の観測記録</span>
      <h1 className="font-serif" style={{ fontSize: 40, color: "var(--ink)" }}>
        ディーラー調書
      </h1>
      <p className="font-sans" style={{ fontSize: 12.5, color: "var(--ink2)", lineHeight: 1.7 }}>
        あなたがこれまでの卓で見た「相手の手」の頻度だけを記録したもの。
        <br />
        母数（n）が少ないうちは信頼区間（CI）が広く、まだ当てにならない。
      </p>

      <div style={{ width: "100%", maxHeight: "56vh", overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
        {dossierLoading && (
          <span className="font-mono" style={{ fontSize: 12, color: "var(--ink3)" }}>読み込み中…</span>
        )}
        {!dossierLoading && dossier && dossier.length === 0 && (
          <span className="font-sans" style={{ fontSize: 13, color: "var(--ink3)" }}>
            まだ観測記録が無い。卓に着いて戦えば、ここに手筋が記録されていく。
          </span>
        )}
        {dossier?.map((enemy) => (
          <EnemyCard key={enemy.enemy_id} enemyId={enemy.enemy_id} nTotal={enemy.n_total} behaviors={enemy.behaviors}
            name={enemyCatalog[enemy.enemy_id]?.name}
            experience={enemyCatalog[enemy.enemy_id]?.experience} />
        ))}
      </div>

      <button className="btn btn-ghost" style={{ minWidth: 160 }} onClick={onBack}>
        戻る
      </button>
    </CenterStage>
  );
}

function EnemyCard({
  enemyId,
  name,
  experience,
  nTotal,
  behaviors,
}: {
  enemyId: string;
  name?: string;
  experience?: string;
  nTotal: number;
  behaviors: { behavior: string; count: number; n_total: number; ci_low: number; ci_high: number }[];
}) {
  const exp = experienceMeta(experience);
  return (
    <div
      style={{
        width: "100%",
        border: "1px solid var(--rule)",
        borderRadius: 10,
        background: "var(--paper2)",
        padding: "12px 16px",
        textAlign: "left",
      }}
    >
      <div className="flex items-center gap-2" style={{ marginBottom: 8 }}>
        <span className="font-sans" style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)" }}>
          {name ?? enemyId}
        </span>
        {experience && (
          <span className="font-mono" style={{ fontSize: 10, color: exp.color }}>
            {exp.jp}
          </span>
        )}
        <span className="font-mono" style={{ fontSize: 10.5, color: "var(--ink3)", marginLeft: "auto" }}>
          観測 n={nTotal}
        </span>
      </div>

      {behaviors
        .slice()
        .sort((a, b) => b.count - a.count)
        .map((b) => (
          <BehaviorRow key={b.behavior} {...b} />
        ))}
    </div>
  );
}

function BehaviorRow({
  behavior,
  count,
  n_total,
  ci_low,
  ci_high,
}: {
  behavior: string;
  count: number;
  n_total: number;
  ci_low: number;
  ci_high: number;
}) {
  const meta = behaviorMeta(behavior);
  const color = meta?.color ?? "var(--ink2)";
  const label = meta?.jp ?? behavior;
  const observedPct = n_total > 0 ? (count / n_total) * 100 : 0;
  const loPct = ci_low * 100;
  const hiPct = ci_high * 100;

  return (
    <div style={{ marginBottom: 10 }}>
      <div className="flex items-center" style={{ justifyContent: "space-between", marginBottom: 3 }}>
        <span className="font-sans" style={{ fontSize: 12, fontWeight: 600, color }}>
          {label}
        </span>
        <span className="font-mono" style={{ fontSize: 11, color: "var(--ink3)" }}>
          観測 {observedPct.toFixed(0)}%（n={n_total}, 95%CI {loPct.toFixed(0)}–{hiPct.toFixed(0)}%）
        </span>
      </div>
      <div
        style={{
          position: "relative",
          height: 10,
          borderRadius: 5,
          background: "var(--paper)",
          border: "1px solid var(--rule)",
          overflow: "hidden",
        }}
      >
        {/* 観測比率バー */}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: `${observedPct}%`,
            background: color,
            opacity: 0.45,
          }}
        />
        {/* Wilson 95%CI ひげ */}
        <div
          style={{
            position: "absolute",
            left: `${loPct}%`,
            width: `${Math.max(0, hiPct - loPct)}%`,
            top: "50%",
            height: 2,
            background: color,
            transform: "translateY(-50%)",
          }}
        />
        <div style={{ position: "absolute", left: `${loPct}%`, top: 1, bottom: 1, width: 2, background: color }} />
        <div style={{ position: "absolute", left: `${hiPct}%`, top: 1, bottom: 1, width: 2, background: color }} />
      </div>
    </div>
  );
}
