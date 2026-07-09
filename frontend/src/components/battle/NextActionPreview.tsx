import type { Battle } from "../../api/types";
import { behaviorMeta, TELL_META } from "../../lib/labels";
import Icon from "../common/Icon";

// 先読み＝確定の次手（種別を明示）／スカウト＝傾向（控えめ）。CombatPanel から抽出。
export default function NextActionPreview({ battle }: { battle: Battle }) {
  // テル試作: バックエンドが返した気配信頼度ラベルのみで駆動（フロントで確率・weightは計算しない）。
  const nb = behaviorMeta(battle.next_action);
  if (nb) {
    const tell = TELL_META[battle.tell_reliability ?? ""];
    return (
      <div
        className="flex flex-col items-center"
        style={{ marginTop: 12, gap: 4, padding: "8px 16px", borderRadius: 8, border: `1px solid ${nb.color}`, background: "var(--paper2)" }}
      >
        <div className="flex items-center gap-2">
          <span className="label" style={{ color: "var(--brass)" }}>先読み · 確定</span>
          {/* サイドベットの賭けボタンと同じ図形・同色（labels.ts の BEHAVIOR 正本）で対応づける */}
          <span style={{ color: nb.color, display: "inline-flex", flex: "none" }}>
            <Icon type={nb.iconType} size={16} />
          </span>
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
}
