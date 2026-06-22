import { useEffect, useRef } from "react";
import type { LogLine } from "../../api/types";

// 戦闘ログ（全保持・スクロール）。design 継承。k で色を出し分け。
const KIND_COLOR: Record<string, string> = {
  player: "var(--ink)",
  damage: "var(--danger)",
  enemy: "var(--accent)",
  heal: "var(--moss)",
  mod: "var(--brass)",
  info: "var(--ink2)",
};

export default function CombatLog({ log }: { log: LogLine[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [log]);

  return (
    <div
      ref={ref}
      className="font-mono"
      style={{
        maxHeight: 168,
        overflowY: "auto",
        background: "var(--paper)",
        border: "1px solid var(--rule)",
        borderRadius: 10,
        padding: "10px 14px",
        fontSize: 12.5,
        lineHeight: 1.7,
      }}
    >
      {log.length === 0 && <div style={{ color: "var(--ink3)" }}>—</div>}
      {log.map((l, i) => (
        <div key={i} style={{ color: KIND_COLOR[l.k] ?? "var(--ink2)" }}>
          <span style={{ color: "var(--ink3)" }}>›</span> {l.t}
        </div>
      ))}
    </div>
  );
}
