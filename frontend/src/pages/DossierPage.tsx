import { useEffect, useMemo, useState, type CSSProperties } from "react";
import clsx from "clsx";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import Icon from "../components/common/Icon";
import { behaviorMeta, experienceMeta } from "../lib/labels";
import type { DossierBehavior, DossierEnemy, EnemyCatalogItem } from "../api/types";

// ディーラー調書: プレイヤーが観測した「敵の行動頻度」だけをWilson信頼区間つきで見せる。
// 真のweight/確率は一切表示しない(開示不変条件はバックエンドAPI側で担保・ここは受け取った値をそのまま出すだけ)。
// StartPage(state===null のとき)からのみ到達するため、ラン中は自然に閲覧不可。

type SortMode = "encounters" | "name";

interface MergedEnemy {
  enemyId: string;
  name: string;
  experience?: string;
  nTotal: number;
  behaviors: DossierBehavior[];
}

// CI幅(パーセンテージ点)がこれを超えたら「まだ様子見」の質感にする。狭ければ「確信度が高い」表示。
const CONFIDENT_CI_WIDTH = 30;

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

function splitAndSort(
  dossier: DossierEnemy[] | null,
  enemyCatalog: Record<string, EnemyCatalogItem>,
  sortMode: SortMode,
): { encountered: MergedEnemy[]; unencountered: MergedEnemy[] } {
  const byId = new Map((dossier ?? []).map((d) => [d.enemy_id, d]));
  const ids = new Set<string>([...byId.keys(), ...Object.keys(enemyCatalog)]);

  const merged: MergedEnemy[] = Array.from(ids).map((enemyId) => {
    const d = byId.get(enemyId);
    const cat = enemyCatalog[enemyId];
    return {
      enemyId,
      name: cat?.name ?? enemyId,
      experience: cat?.experience,
      nTotal: d?.n_total ?? 0,
      behaviors: d?.behaviors ?? [],
    };
  });

  const byName = (a: MergedEnemy, b: MergedEnemy) => a.name.localeCompare(b.name, "ja");

  const encountered = merged.filter((e) => e.nTotal > 0);
  const unencountered = merged.filter((e) => e.nTotal === 0);

  encountered.sort(sortMode === "encounters" ? (a, b) => b.nTotal - a.nTotal || byName(a, b) : byName);
  unencountered.sort(byName);

  return { encountered, unencountered };
}

function DossierSkeleton() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="dossier-skeleton"
          style={{ width: "100%", height: 96, borderRadius: 10, border: "1px solid var(--rule)" }}
        />
      ))}
    </>
  );
}

function EmptyDossier() {
  return (
    <div
      style={{
        width: "100%",
        border: "1px dashed var(--rule2)",
        borderRadius: 10,
        padding: "28px 16px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        color: "var(--ink3)",
      }}
    >
      <Icon type="eye" size={26} style={{ color: "var(--ink3)" }} />
      <span className="font-sans" style={{ fontSize: 13, color: "var(--ink2)" }}>
        まだ観測記録が無い。
      </span>
      <span className="font-sans" style={{ fontSize: 12, color: "var(--ink3)" }}>
        卓に着いて戦えば、ここに手筋が記録されていく。
      </span>
    </div>
  );
}

function EnemyCard({ enemy }: { enemy: MergedEnemy }) {
  const exp = experienceMeta(enemy.experience);
  return (
    <div className="dossier-card" style={cardStyle}>
      <div className="flex items-center gap-2" style={{ marginBottom: 8 }}>
        <span className="font-sans" style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)" }}>
          {enemy.name}
        </span>
        {enemy.experience && (
          <span className="font-mono" style={{ fontSize: 10, color: exp.color }}>
            {exp.jp}
          </span>
        )}
        <span className="font-mono" style={{ fontSize: 10.5, color: "var(--ink3)", marginLeft: "auto" }}>
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

function UnmetEnemyCard({ enemy }: { enemy: MergedEnemy }) {
  const exp = experienceMeta(enemy.experience);
  return (
    <div className="dossier-card dossier-card--unmet" style={{ ...cardStyle, padding: "9px 16px" }}>
      <div className="flex items-center gap-2">
        <span className="font-sans" style={{ fontSize: 13, fontWeight: 600, color: "var(--ink3)" }}>
          {enemy.name}
        </span>
        {enemy.experience && (
          <span className="font-mono" style={{ fontSize: 10, color: "var(--ink4)" }}>
            {exp.jp}
          </span>
        )}
        <span className="font-mono" style={{ fontSize: 10, color: "var(--ink4)", marginLeft: "auto" }}>
          未遭遇
        </span>
      </div>
    </div>
  );
}

const cardStyle: CSSProperties = {
  width: "100%",
  border: "1px solid var(--rule)",
  borderRadius: 10,
  background: "var(--paper2)",
  padding: "12px 16px",
  textAlign: "left",
};

function BehaviorRow({ behavior, count, n_total, ci_low, ci_high }: DossierBehavior) {
  const meta = behaviorMeta(behavior);
  const color = meta?.color ?? "var(--ink2)";
  const label = meta?.jp ?? behavior;
  const observedPct = n_total > 0 ? (count / n_total) * 100 : 0;
  const loPct = ci_low * 100;
  const hiPct = ci_high * 100;
  const ciWidthPct = hiPct - loPct;
  const confident = ciWidthPct <= CONFIDENT_CI_WIDTH;

  return (
    <div style={{ marginBottom: 10 }}>
      <div className="flex items-center gap-1.5" style={{ marginBottom: 3 }}>
        {meta && (
          <span style={{ display: "flex", flex: "none", color, opacity: confident ? 0.95 : 0.55 }}>
            <Icon type={meta.iconType} size={13} />
          </span>
        )}
        <span className="font-sans" style={{ fontSize: 12, fontWeight: 600, color, flex: "none" }}>
          {label}
        </span>
        <span className="font-mono" style={{ fontSize: 11, color: "var(--ink3)", marginLeft: "auto" }}>
          観測 {observedPct.toFixed(0)}%(n={n_total}, 95%CI {loPct.toFixed(0)}–{hiPct.toFixed(0)}%)
          {!confident && <span style={{ color: "var(--ink4)" }}> ・母数少なめ</span>}
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
        {/* 観測比率バー: 確信度が高いほど濃く塗る */}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: `${observedPct}%`,
            background: color,
            opacity: confident ? 0.6 : 0.28,
            transition: "width .3s var(--ease)",
          }}
        />
        {/* Wilson 95%CI ひげ: 確信度が高ければ実線・濃い色、低ければ点線・薄い色 */}
        {confident ? (
          <div
            style={{
              position: "absolute",
              left: `${loPct}%`,
              width: `${Math.max(0, ciWidthPct)}%`,
              top: "50%",
              height: 2.5,
              borderRadius: 2,
              background: color,
              opacity: 0.95,
              transform: "translateY(-50%)",
            }}
          />
        ) : (
          <div
            style={{
              position: "absolute",
              left: `${loPct}%`,
              width: `${Math.max(0, ciWidthPct)}%`,
              top: "50%",
              height: 0,
              borderTop: `1.5px dashed ${color}`,
              opacity: 0.5,
              transform: "translateY(-50%)",
            }}
          />
        )}
        <div
          style={{
            position: "absolute",
            left: `${loPct}%`,
            top: 1,
            bottom: 1,
            width: 2,
            background: color,
            opacity: confident ? 0.95 : 0.5,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: `${hiPct}%`,
            top: 1,
            bottom: 1,
            width: 2,
            background: color,
            opacity: confident ? 0.95 : 0.5,
          }}
        />
      </div>
    </div>
  );
}
