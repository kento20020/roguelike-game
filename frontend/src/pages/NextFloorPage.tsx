import type { GameState } from "../api/types";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import FloorProgressDots from "../components/common/FloorProgressDots";
import GlowTitle from "../components/common/GlowTitle";
import { floorName, gateOutcome } from "../lib/labels";

// フロア遷移（next_floor）。ゲート結果＋登った一拍。GDD では gate 結果表示＋遷移演出。
export default function NextFloorPage({ state }: { state: GameState }) {
  const continueRun = useGameStore((s) => s.continueRun);
  const busy = useGameStore((s) => s.busy);
  const pending = state.pending as { gate_outcome?: string; advanced_to?: number };
  const out = pending.gate_outcome ? gateOutcome(pending.gate_outcome) : null;
  const to = pending.advanced_to ?? state.current_floor;

  return (
    <CenterStage tone="win" maxWidth={460}>
      {out && (
        <span className="label" style={{ color: out.color }}>
          {out.jp}
        </span>
      )}
      {/* 縦ドットで「タワーを登った」実感を出す（到達済みだけ真鍮に灯る） */}
      <FloorProgressDots current={to} orientation="vertical" withLabel />
      <GlowTitle size={44}>{floorName(to)}</GlowTitle>
      <p className="font-sans" style={{ fontSize: 12.5, color: "var(--ink2)" }}>
        関門を抜けた。さらに上へ。
      </p>
      {state.player && (
        <span className="font-mono" style={{ fontSize: 13, color: "var(--ink2)" }}>
          HP {state.player.hp} / {state.player.max_hp}
        </span>
      )}
      <button className="btn" style={{ minWidth: 180 }} disabled={busy} onClick={continueRun}>
        次の階へ
      </button>
    </CenterStage>
  );
}
