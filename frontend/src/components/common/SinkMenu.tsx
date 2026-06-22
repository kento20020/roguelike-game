import type { ActionItem, SinkType } from "../../api/types";
import { SINK_META } from "../../lib/labels";
import Icon from "./Icon";

// チップ sink ツールバー（design 忠実・フロート pill）。コストは action から（メタ強化反映済み）。
export default function SinkMenu({
  actions,
  chips,
  onSink,
  busy,
}: {
  actions: ActionItem[];
  chips: number;
  onSink: (s: SinkType) => void;
  busy: boolean;
}) {
  const sinks = actions.filter((a) => a.type === "use_sink" && a.sink);
  if (sinks.length === 0) return null;
  return (
    <div
      style={{
        width: "max-content",
        maxWidth: "94vw",
        margin: "0 auto",
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 10px",
        borderRadius: 999,
        border: "1px solid var(--rule2)",
        background: "rgba(31,27,21,0.86)",
        boxShadow: "0 10px 30px rgba(0,0,0,0.4)",
      }}
    >
      <span className="label" style={{ paddingLeft: 6, whiteSpace: "nowrap" }}>
        Chips Sink · 残り <span style={{ fontFamily: "var(--mono)", fontSize: 12, color: "var(--brass)" }}>{chips}</span>
      </span>
      {sinks.map((a) => {
        const sink = a.sink as SinkType;
        const meta = SINK_META[sink];
        return (
          <button
            key={sink}
            disabled={busy}
            onClick={() => onSink(sink)}
            className="btn btn-ghost"
            style={{ display: "flex", alignItems: "center", gap: 9, padding: "7px 12px", borderRadius: 999 }}
          >
            <span style={{ color: "var(--ink2)", display: "flex" }}>
              <Icon type={meta.iconType} size={18} />
            </span>
            <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.18, whiteSpace: "nowrap", textAlign: "left" }}>
              <span style={{ fontSize: 12.5, color: "var(--ink)" }}>{meta.label}</span>
              <span style={{ fontSize: 9.5, color: "var(--ink3)" }}>{meta.effect}</span>
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 3, fontFamily: "var(--mono)", fontSize: 11, color: "var(--brass)" }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, border: "1.5px solid var(--brass)", display: "inline-block" }} />
              {a.cost ?? ""}
            </span>
          </button>
        );
      })}
    </div>
  );
}
