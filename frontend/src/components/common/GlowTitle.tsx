import type { CSSProperties, ReactNode } from "react";
import clsx from "clsx";

// A案「ネオン・マーキー」（design/preview/components-glow-marquee.html 由来）の serif 見出し。
// 常時は暗い felt 地のまま、見出しにだけ真鍮グロー（marqueeGlow）を乗せて視線誘導する。
export default function GlowTitle({
  children,
  size = 40,
  as: Tag = "h1",
  className,
  style,
}: {
  children: ReactNode;
  size?: number;
  as?: "h1" | "h2";
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <Tag
      className={clsx("font-serif glow-title", className)}
      style={{ fontSize: size, margin: 0, lineHeight: 1.1, ...style }}
    >
      {children}
    </Tag>
  );
}
