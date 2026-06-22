import type { GameState } from "../api/types";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import ResultSummary from "../components/result/ResultSummary";
import UpgradeAllocator from "../components/result/UpgradeAllocator";

// クリア（cleared）。GDD §26.6 では決算＋恒久強化割り振りを同一画面に。
export default function ClearedPage({ state }: { state: GameState }) {
  const newRun = useGameStore((s) => s.newRun);
  const reset = useGameStore((s) => s.reset);
  const busy = useGameStore((s) => s.busy);
  const rec = state.run_record;

  return (
    <CenterStage tone="win" maxWidth={640}>
      <span className="label" style={{ color: "var(--brass)" }}>
        全てを賭けた一勝負
      </span>
      <h1 className="font-serif" style={{ fontSize: 52, color: "var(--brass)" }}>
        制覇
      </h1>
      {rec && (
        <>
          <span className="font-mono" style={{ fontSize: 11, color: "var(--ink3)" }}>
            seed {rec.seed}
          </span>
          <ResultSummary record={rec} />
        </>
      )}
      <UpgradeAllocator />
      <div className="flex items-center gap-3">
        <button className="btn" style={{ minWidth: 160 }} disabled={busy} onClick={() => newRun()}>
          次のランへ
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={reset}>
          タイトルへ
        </button>
      </div>
    </CenterStage>
  );
}
