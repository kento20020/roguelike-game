import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Floor } from "../../api/types";
import NodeCard from "./NodeCard";

// フロアツリー（design 忠実）。下の卓→上の関門（登る）。親→子を連結線で結ぶ。
// コンテナ幅を測り、自然サイズを超える場合は縮小して常に幅に収める（横スクロールしない）。
const CARD_W = 158;
const CARD_H = 64;
const ROW_GAP = 150;
const COL_GAP = 196;
const PAD = 28;

export default function TreeCanvas({
  floor,
  busy,
  onSelect,
}: {
  floor: Floor;
  busy: boolean;
  onSelect: (id: string) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [containerW, setContainerW] = useState(0);

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const update = () => setContainerW(el.clientWidth);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { items, edges, width, height } = useMemo(() => {
    const nodes = Object.values(floor.nodes);
    const rows = [...new Set(nodes.map((n) => n.row))].sort((a, b) => b - a); // 高row(関門)=上
    const maxCount = Math.max(1, ...rows.map((r) => nodes.filter((n) => n.row === r).length));
    const width = Math.max(560, maxCount * COL_GAP);
    const pos: Record<string, { x: number; y: number }> = {};
    rows.forEach((r, ri) => {
      const inRow = nodes.filter((n) => n.row === r).sort((a, b) => (a.id < b.id ? -1 : 1));
      const n = inRow.length;
      const y = PAD + ri * ROW_GAP;
      inRow.forEach((node, j) => {
        pos[node.id] = { x: width / 2 + (j - (n - 1) / 2) * COL_GAP, y };
      });
    });
    const height = PAD + (rows.length - 1) * ROW_GAP + CARD_H + PAD;
    const edges: Array<{ x1: number; y1: number; x2: number; y2: number; active: boolean }> = [];
    for (const node of nodes) {
      for (const p of node.parents) {
        const a = pos[p];
        const b = pos[node.id];
        if (!a || !b) continue;
        edges.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y + CARD_H, active: floor.nodes[p]?.state === "resolved" });
      }
    }
    const items = nodes.map((node) => ({ node, ...pos[node.id] }));
    return { items, edges, width, height };
  }, [floor]);

  // 自然幅がコンテナを超えたら縮小（拡大はしない）。
  const scale = containerW > 0 ? Math.min(1, containerW / width) : 1;

  return (
    <div ref={wrapRef} style={{ width: "100%", height: height * scale, position: "relative" }}>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: "50%",
          width,
          height,
          transform: `translateX(-50%) scale(${scale})`,
          transformOrigin: "top center",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: -6,
            left: "50%",
            transform: "translateX(-50%)",
            width: 340,
            height: 150,
            borderRadius: "50%",
            background: "radial-gradient(ellipse, rgba(200,90,42,0.12), rgba(0,0,0,0) 70%)",
            filter: "blur(8px)",
            pointerEvents: "none",
          }}
        />
        <svg style={{ position: "absolute", inset: 0, width, height, pointerEvents: "none", overflow: "visible" }}>
          {edges.map((e, i) => (
            <line
              key={i}
              x1={e.x1}
              y1={e.y1}
              x2={e.x2}
              y2={e.y2}
              stroke={e.active ? "var(--accentRing)" : "var(--rule2)"}
              strokeWidth={e.active ? 2 : 1.4}
              strokeDasharray={e.active ? undefined : "3 6"}
              strokeLinecap="round"
            />
          ))}
        </svg>
        {items.map(({ node, x, y }) => (
          <div key={node.id} style={{ position: "absolute", left: x - CARD_W / 2, top: y, width: CARD_W }}>
            <NodeCard node={node} busy={busy} onClick={onSelect} />
          </div>
        ))}
      </div>
    </div>
  );
}
