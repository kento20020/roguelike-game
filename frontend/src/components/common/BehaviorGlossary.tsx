import { useState } from "react";
import { BEHAVIOR } from "../../lib/labels";
import Icon from "./Icon";

// 敵の行動種別（反撃/強打/回避/蓄積の一撃/様子見）が何をするかを教える折りたたみパネル。
// 確率は出さない（暗黙知 GDD §5）。意味だけを伝える。
export default function BehaviorGlossary({
  defaultOpen = false,
  title = "相手の手筋",
}: {
  defaultOpen?: boolean;
  title?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ width: "100%", maxWidth: 560, border: "1px solid var(--rule)", borderRadius: 8, background: "var(--paper2)" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 14px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "var(--ink)",
        }}
      >
        <span className="label">{title} · 行動の意味</span>
        <span style={{ fontSize: 10, color: "var(--ink3)" }}>{open ? "▴ 閉じる" : "▾ 見る"}</span>
      </button>
      {open && (
        <div style={{ padding: "0 14px 10px" }}>
          {BEHAVIOR.map((b) => (
            <div key={b.key} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0", borderTop: "1px solid var(--rule)" }}>
              {/* サイドベット/先読み/調書と同じ図形・同色（BEHAVIOR 正本）で行動を対応づける */}
              <span style={{ flex: "none", color: b.color, display: "inline-flex" }}>
                <Icon type={b.iconType} size={14} />
              </span>
              <span style={{ flex: "none", minWidth: 64, fontFamily: "var(--sans)", fontSize: 12.5, fontWeight: 600, color: b.color }}>{b.jp}</span>
              <span style={{ fontFamily: "var(--sans)", fontSize: 11.5, lineHeight: 1.5, color: "var(--ink2)" }}>{b.meaning}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
