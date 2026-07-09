import Icon from "../common/Icon";
import { behaviorMeta } from "../../lib/labels";
import type { DossierBehavior } from "../../api/types";

// CI幅(パーセンテージ点)がこれを超えたら「まだ様子見」の質感にする。狭ければ「確信度が高い」表示。
const CONFIDENT_CI_WIDTH = 30;

// 1敵1行動の観測頻度行（Wilson信頼区間つき）。DossierPage から抽出。
export default function BehaviorRow({ behavior, count, n_total, ci_low, ci_high }: DossierBehavior) {
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
