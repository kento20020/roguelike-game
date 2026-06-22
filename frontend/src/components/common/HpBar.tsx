// HP残量バー。ratio で色変化（GDD §24: 50/20% で色変化）。
export default function HpBar({
  current,
  max,
  width = 130,
  colorOverride,
}: {
  current: number;
  max: number;
  width?: number | string;
  colorOverride?: string;
}) {
  const ratio = max > 0 ? Math.max(0, Math.min(1, current / max)) : 0;
  const color =
    colorOverride ?? (ratio > 0.5 ? "var(--moss)" : ratio > 0.2 ? "var(--brass)" : "var(--danger)");
  return (
    <div
      style={{
        position: "relative",
        width,
        height: 8,
        borderRadius: 999,
        background: "var(--paper3)",
        border: "1px solid var(--rule)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: 0,
          width: `${ratio * 100}%`,
          borderRadius: 999,
          background: color,
          transition: "width .28s var(--ease), background .28s var(--ease)",
        }}
      />
    </div>
  );
}
