import type { GameState } from "../api/types";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";

// 回復（heal）。大小はバックエンドで決定済み。
export default function HealPage({ state }: { state: GameState }) {
  const continueRun = useGameStore((s) => s.continueRun);
  const busy = useGameStore((s) => s.busy);
  const pending = state.pending as { heal?: number; big?: boolean };

  return (
    <CenterStage maxWidth={440}>
      <span className="label">控え室・バーカウンター</span>
      <div className="font-serif" style={{ fontSize: 34, color: "var(--moss)" }}>
        ♥ {pending.big ? "大回復" : "小回復"}
      </div>
      {typeof pending.heal === "number" && (
        <div className="font-mono" style={{ fontSize: 22, color: "var(--moss)" }}>
          +{pending.heal}
        </div>
      )}
      {state.player && (
        <span className="font-mono" style={{ fontSize: 13, color: "var(--ink2)" }}>
          HP {state.player.hp} / {state.player.max_hp}
        </span>
      )}
      <button className="btn" style={{ minWidth: 180 }} disabled={busy} onClick={continueRun}>
        席を立つ
      </button>
    </CenterStage>
  );
}
