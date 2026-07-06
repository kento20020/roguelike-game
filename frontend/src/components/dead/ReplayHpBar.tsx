import { useEffect, useState } from "react";

// リプレイ用HPバー。マウント時に before→after へ縮む(=被弾)動きを付ける(控えめ・1回のみ)。DeadPage から抽出。
export default function ReplayHpBar({ before, after, max, color }: { before: number; after: number; max: number; color: string }) {
  const m = Math.max(max, 1);
  const targetBefore = Math.max(0, Math.min(100, (before / m) * 100));
  const targetAfter = Math.max(0, Math.min(100, (after / m) * 100));
  const [w, setW] = useState({ before: targetBefore, after: targetBefore });

  useEffect(() => {
    const id = requestAnimationFrame(() => setW({ before: targetBefore, after: targetAfter }));
    return () => cancelAnimationFrame(id);
  }, [targetBefore, targetAfter]);

  return (
    <div style={{ position: "relative", width: 90, height: 8, borderRadius: 4, background: "var(--rule)", overflow: "hidden" }}>
      <div
        style={{
          position: "absolute", inset: 0, width: `${w.before}%`, borderRadius: 4,
          background: "var(--rule2)", transition: "width .5s var(--ease)",
        }}
      />
      <div
        style={{
          position: "absolute", inset: 0, width: `${w.after}%`, borderRadius: 4,
          background: color, transition: "width .5s var(--ease) .1s",
        }}
      />
    </div>
  );
}
