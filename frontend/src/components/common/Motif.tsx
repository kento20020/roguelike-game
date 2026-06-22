// 行動の「傾向」を定性的な形で示す motif（design の motif() を忠実移植・42×14）。数値は出さない。
const PATHS: Record<string, { p?: string; dots?: [number, number][]; dash?: string }> = {
  grind: { p: "M1 9 L7 5 L13 9 L19 5 L25 9 L31 5 L37 9 L41 7" },
  gamble: { p: "M1 11 L15 11 L20 2 L25 11 L41 11" },
  race: { p: "M1 12 L9 12 L9 9 L17 9 L17 6 L25 6 L25 3 L41 3" },
  evade: { p: "M1 7 H41", dash: "3 4" },
  chaos: { dots: [[5, 5], [13, 10], [21, 4], [29, 11], [37, 6]] },
};

export default function Motif({ type, color = "currentColor" }: { type: string; color?: string }) {
  const m = PATHS[type] ?? { p: "M1 7 H41" };
  return (
    <svg width={42} height={14} viewBox="0 0 42 14" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      {m.dots
        ? m.dots.map(([cx, cy], i) => <circle key={i} cx={cx} cy={cy} r={1.3} fill={color} stroke="none" />)
        : <path d={m.p} strokeDasharray={m.dash} />}
    </svg>
  );
}
