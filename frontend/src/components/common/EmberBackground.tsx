import { useMemo } from "react";

// 紙地＋ヘイズ2枚＋立ちのぼる残り火。全phaseの背景（design 継承）。
// tone: 通常=朱+真鍮、win=真鍮多め、lose=朱で沈める。
export default function EmberBackground({ tone = "normal" }: { tone?: "normal" | "win" | "lose" }) {
  const count = tone === "lose" ? 12 : 18;
  const embers = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => {
        const left = (i * 37 + 11) % 100;
        const dur = 9 + ((i * 7) % 11);
        const delay = (i * 1.7) % 9;
        const size = 1.5 + ((i * 13) % 5) * 0.6;
        const color = tone === "win" ? "var(--brass)" : i % 4 === 0 ? "var(--brass)" : "var(--accent)";
        return { i, left, dur, delay, size, color };
      }),
    [count, tone]
  );

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <div
        style={{
          position: "absolute",
          width: 540,
          height: 540,
          left: "3%",
          top: "32%",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(200,90,42,0.06), rgba(0,0,0,0) 70%)",
          filter: "blur(26px)",
          animation: "hazeDrift 52s ease-in-out infinite",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 480,
          height: 480,
          right: "1%",
          top: "6%",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(201,162,75,0.05), rgba(0,0,0,0) 70%)",
          filter: "blur(28px)",
          animation: "hazeDrift 64s ease-in-out infinite reverse",
        }}
      />
      {embers.map((e) => (
        <span
          key={e.i}
          style={{
            position: "absolute",
            bottom: -10,
            left: `${e.left}%`,
            width: e.size,
            height: e.size,
            borderRadius: "999px",
            background: e.color,
            opacity: 0,
            animation: `emberRise ${e.dur}s linear ${e.delay}s infinite`,
          }}
        />
      ))}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at 50% 40%, rgba(0,0,0,0) 44%, rgba(0,0,0,0.5) 100%)",
        }}
      />
    </div>
  );
}
