import type { GameState } from "../api/types";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import GlowTitle from "../components/common/GlowTitle";
import ResultSummary from "../components/result/ResultSummary";
import UpgradeAllocator from "../components/result/UpgradeAllocator";

// クリア（cleared）。GDD §26.6 では決算＋恒久強化割り振りを同一画面に。
// A案「ネオン・マーキー」: 真鍮グローは到達と勝利にのみ許される（badge＋glow-ring は静的、
// アニメーションするのは GlowTitle だけ）。badge の文言は英字 VICTORY —
// UI本文は日本語だが、design/*.dc.html の勝利演出は英字アクセント（"Cleared · 撃破"）を
// 使う運用のため、それに合わせて見出し「制覇」との重複を避ける。
export default function ClearedPage({ state }: { state: GameState }) {
  const newRun = useGameStore((s) => s.newRun);
  const reset = useGameStore((s) => s.reset);
  const busy = useGameStore((s) => s.busy);
  const rec = state.run_record;

  return (
    <CenterStage tone="win" maxWidth={640} panelClassName="glow-ring">
      <span className="victory-badge font-mono">✦ VICTORY ✦</span>
      <span className="label" style={{ color: "var(--brass)" }}>
        全てを賭けた一勝負
      </span>
      <GlowTitle size={52}>制覇</GlowTitle>
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
