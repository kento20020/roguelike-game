import clsx from "clsx";
import { TOTAL_FLOORS } from "../../lib/labels";

// A案「ネオン・マーキー」由来のフロア進行インジケーター。
// 到達済みフロアだけ真鍮の静的発光（gate-dot--lit）。vertical 時は下から上へ積み上がる＝タワーを登る比喩。
export default function FloorProgressDots({
  current,
  total = TOTAL_FLOORS,
  orientation = "horizontal",
  withLabel = false,
}: {
  current: number;
  total?: number;
  orientation?: "horizontal" | "vertical";
  withLabel?: boolean;
}) {
  return (
    <div className={clsx("flex items-center gap-2", orientation === "vertical" && "flex-col-reverse")}>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={clsx("gate-dot", i + 1 <= current && "gate-dot--lit")} />
      ))}
      {withLabel && (
        <span className="label">
          {current} / {total}F
        </span>
      )}
    </div>
  );
}
