import type { RunRecord } from "../../api/types";
import { modLabel } from "../../lib/labels";

// 死亡/クリア共通の決算（GDD §24 ResultSummary）。
function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="label">{label}</span>
      <span className="font-mono" style={{ fontSize: 20 }}>
        {value}
      </span>
    </div>
  );
}

export default function ResultSummary({ record }: { record: RunRecord }) {
  return (
    <div className="flex w-full flex-col items-center gap-6">
      <div className="flex flex-wrap items-start justify-center gap-x-10 gap-y-5">
        <Stat label="到達" value={`${record.floor_reached} / 5`} />
        <Stat label="総ターン" value={record.total_turns} />
        <Stat label="最終HP" value={record.final_hp} />
        <Stat label="稼いだチップ" value={record.gold_earned} />
        <Stat label="撃破数" value={record.enemies_defeated.length} />
      </div>
      {record.mods_acquired.length > 0 && (
        <div className="flex flex-col items-center gap-2">
          <span className="label">手にした技</span>
          <div className="flex flex-wrap justify-center gap-1.5">
            {record.mods_acquired.map((m, i) => (
              <span key={`${m}-${i}`} className="pill">
                {modLabel(m)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
