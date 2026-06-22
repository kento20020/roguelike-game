import type { GameState } from "../api/types";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import ResultSummary from "../components/result/ResultSummary";
import { floorName } from "../lib/labels";

// 敗北（dead）。パーマデス。コア表示＝到達/総ターン/取得mod（GDD §15.1）。
// death_cause は機械語。日本語化辞書が無いので任意の補足表示に留める。
export default function DeadPage({ state }: { state: GameState }) {
  const newRun = useGameStore((s) => s.newRun);
  const reset = useGameStore((s) => s.reset);
  const busy = useGameStore((s) => s.busy);
  const rec = state.run_record;

  return (
    <CenterStage tone="lose" maxWidth={560}>
      <span className="label" style={{ color: "var(--danger)" }}>
        一勝負は遠かった
      </span>
      <h1 className="font-serif" style={{ fontSize: 48, color: "var(--danger)" }}>
        敗北
      </h1>
      {rec?.death_floor != null && (
        <p className="font-sans" style={{ fontSize: 14, color: "var(--ink)" }}>
          {floorName(rec.death_floor)} で倒れた
          {rec.death_cause ? `（${rec.death_cause}）` : ""}
        </p>
      )}
      {rec && <ResultSummary record={rec} />}
      <div className="flex items-center gap-3">
        <button className="btn" style={{ minWidth: 160 }} disabled={busy} onClick={() => newRun()}>
          もう一度
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={reset}>
          タイトルへ
        </button>
      </div>
    </CenterStage>
  );
}
