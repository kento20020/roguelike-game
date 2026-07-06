import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import DossierSkeleton from "../components/dossier/DossierSkeleton";
import EmptyDossier from "../components/dossier/EmptyDossier";
import EnemyCard, { UnmetEnemyCard } from "../components/dossier/EnemyCard";
import { splitAndSort, type SortMode } from "../components/dossier/sortEnemies";

// ディーラー調書: プレイヤーが観測した「敵の行動頻度」だけをWilson信頼区間つきで見せる。
// 真のweight/確率は一切表示しない(開示不変条件はバックエンドAPI側で担保・ここは受け取った値をそのまま出すだけ)。
// StartPage(state===null のとき)からのみ到達するため、ラン中は自然に閲覧不可。

export default function DossierPage({ onBack }: { onBack: () => void }) {
  const dossier = useGameStore((s) => s.dossier);
  const dossierLoading = useGameStore((s) => s.dossierLoading);
  const loadDossier = useGameStore((s) => s.loadDossier);
  const enemyCatalog = useGameStore((s) => s.enemyCatalog);
  const loadEnemyCatalog = useGameStore((s) => s.loadEnemyCatalog);
  const [sortMode, setSortMode] = useState<SortMode>("encounters");

  useEffect(() => {
    loadDossier();
    loadEnemyCatalog();
  }, [loadDossier, loadEnemyCatalog]);

  const { encountered, unencountered } = useMemo(
    () => splitAndSort(dossier, enemyCatalog, sortMode),
    [dossier, enemyCatalog, sortMode],
  );

  const ready = !dossierLoading && dossier !== null;
  const isEmpty = ready && encountered.length === 0;

  return (
    <CenterStage maxWidth={720}>
      <span className="label">個人の観測記録</span>
      <h1 className="font-serif" style={{ fontSize: 40, color: "var(--ink)" }}>
        ディーラー調書
      </h1>
      <p className="font-sans" style={{ fontSize: 12.5, color: "var(--ink2)", lineHeight: 1.7 }}>
        あなたがこれまでの卓で見た「相手の手」の頻度だけを記録したもの。
        <br />
        母数(n)が少ないうちは信頼区間(CI)が広く、まだ当てにならない。
      </p>

      {ready && !isEmpty && (
        <div className="flex items-center gap-2" style={{ alignSelf: "flex-end" }}>
          <span className="font-mono" style={{ fontSize: 10, color: "var(--ink3)" }}>
            並び替え
          </span>
          <button
            className={clsx("dossier-sort-btn", sortMode === "encounters" && "dossier-sort-btn--active")}
            onClick={() => setSortMode("encounters")}
          >
            遭遇数順
          </button>
          <button
            className={clsx("dossier-sort-btn", sortMode === "name" && "dossier-sort-btn--active")}
            onClick={() => setSortMode("name")}
          >
            名前順
          </button>
        </div>
      )}

      <div style={{ width: "100%", maxHeight: "56vh", overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
        {!ready && <DossierSkeleton />}

        {isEmpty && <EmptyDossier />}

        {ready &&
          encountered.map((enemy) => (
            <EnemyCard key={enemy.enemyId} enemy={enemy} />
          ))}

        {ready && unencountered.length > 0 && (
          <>
            <div className="flex items-center gap-2" style={{ margin: "4px 0", opacity: 0.6 }}>
              <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
              <span className="label" style={{ fontSize: 9.5 }}>
                未遭遇 ({unencountered.length})
              </span>
              <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
            </div>
            {unencountered.map((enemy) => (
              <UnmetEnemyCard key={enemy.enemyId} enemy={enemy} />
            ))}
          </>
        )}
      </div>

      <button className="btn btn-ghost" style={{ minWidth: 160 }} onClick={onBack}>
        戻る
      </button>
    </CenterStage>
  );
}
