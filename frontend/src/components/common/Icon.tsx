import type { CSSProperties } from "react";

// SVG アイコンファクトリ（design の icon() を忠実移植。1.6px stroke / 24グリッド）。
type Shape =
  | { p: string }
  | { rect: [number, number, number, number, number] }
  | { circle: [number, number, number] };

const ICONS: Record<string, Shape[]> = {
  grind: [{ p: "M3 7 H8 V12 H13 V17 H21" }],
  gamble: [
    { rect: [4, 4, 16, 16, 3] },
    { circle: [9.2, 9.2, 0.7] },
    { circle: [14.8, 14.8, 0.7] },
    { circle: [14.8, 9.2, 0.7] },
  ],
  race: [{ p: "M6 13 L12 7 L18 13" }, { p: "M6 18 L12 12 L18 18" }],
  evade: [
    { p: "M3 8 H14 a2.6 2.6 0 1 0 -2.6 2.6" },
    { p: "M3 13 H10 a2.2 2.2 0 1 1 -2.2 2.2" },
    { p: "M3 18 H8" },
  ],
  chaos: [
    { p: "M12 4 V20" },
    { p: "M4 12 H20" },
    { p: "M6.5 6.5 L17.5 17.5" },
    { p: "M17.5 6.5 L6.5 17.5" },
  ],
  treasure: [
    { rect: [4, 9, 16, 11, 1.5] },
    { p: "M4 13 H20" },
    { p: "M9.2 9 V7.2 a2.8 2.8 0 0 1 5.6 0 V9" },
    { circle: [12, 14.6, 0.8] },
  ],
  heal: [{ p: "M7 5 H17" }, { p: "M8 5 L9 16.5 a3 3 0 0 0 6 0 L16 5" }, { p: "M9.6 10.5 H14.4" }],
  gate: [{ p: "M5 20 V9 a7 7 0 0 1 14 0 V20" }, { p: "M4 20 H20" }, { p: "M12 12.5 V20" }],
  lock: [{ rect: [5.5, 11, 13, 8.5, 1.5] }, { p: "M8 11 V8.2 a4 4 0 0 1 8 0 V11" }],
  check: [{ p: "M4 12.5 L9.5 18 L20 6.5" }],
  arrow: [{ p: "M5 12 H18" }, { p: "M13 7 L18 12 L13 17" }],
  sword: [
    { p: "M4.5 19.5 L15 9" },
    { p: "M15 9 L19 5" },
    { p: "M12.5 6.5 L17.5 11.5" },
    { p: "M4.5 19.5 L3 21" },
    { p: "M7 17 L9 19" },
  ],
  eye: [{ p: "M2 12 C5 6.5 19 6.5 22 12 C19 17.5 5 17.5 2 12 Z" }, { circle: [12, 12, 2.4] }],
  plus: [{ p: "M12 5.5 V18.5" }, { p: "M5.5 12 H18.5" }],
  shield: [{ p: "M12 3 L19 6 V11 C19 16.2 12 21 12 21 C12 21 5 16.2 5 11 V6 Z" }],
  reflect: [{ p: "M4 8 H15 L11.5 4.5" }, { p: "M20 16 H9 L12.5 19.5" }],
  star: [{ p: "M12 3.5 L14.1 9.5 L20.5 9.7 L15.4 13.6 L17.2 19.8 L12 16 L6.8 19.8 L8.6 13.6 L3.5 9.7 L9.9 9.5 Z" }],
  cap: [{ p: "M6 15.5 L12 9.5 L18 15.5" }, { p: "M5 19.5 H19" }],
  volume: [
    { p: "M4 9.5 H7.2 L11.2 5.8 V18.2 L7.2 14.5 H4 Z" },
    { p: "M14.2 8.6 a5.4 5.4 0 0 1 0 6.8" },
    { p: "M16.6 6.2 a9 9.4 0 0 1 0 11.6" },
  ],
  volumeMute: [
    { p: "M4 9.5 H7.2 L11.2 5.8 V18.2 L7.2 14.5 H4 Z" },
    { p: "M15 9.5 L20 14.5" },
    { p: "M20 9.5 L15 14.5" },
  ],
};

export default function Icon({ type, size = 22, style }: { type: string; size?: number; style?: CSSProperties }) {
  const shapes = ICONS[type] ?? [{ circle: [12, 12, 7] as [number, number, number] }];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
    >
      {shapes.map((s, i) => {
        if ("p" in s) return <path key={i} d={s.p} />;
        if ("rect" in s) {
          const [x, y, w, h, r] = s.rect;
          return <rect key={i} x={x} y={y} width={w} height={h} rx={r} />;
        }
        const [cx, cy, r] = s.circle;
        return <circle key={i} cx={cx} cy={cy} r={r} />;
      })}
    </svg>
  );
}
