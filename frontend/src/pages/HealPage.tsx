import type { GameState } from "../api/types";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import HpBar from "../components/common/HpBar";

// 回復（heal）。大小・回復量はバックエンドで決定済み。グローは使わない（mossの静かなトーン）。
// player.hp は回復適用後の値（engine._resolve_heal が min(max_hp, hp+amt) を先に反映してから
// pending={"heal":amt,"big":big} を積む）。amt は名目値で、上限到達時は実回復量と一致しない。
// 「回復前」はフロントで逆算しない（計算禁止＋切り詰めで不正確になる）ため、
// 名目の +N と回復後のHPという「表示できる事実」だけを見せる。
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
      <p className="font-sans" style={{ fontSize: 12.5, color: "var(--ink3)", lineHeight: 1.7 }}>
        グラスの氷が澄んだ音を立てる。勝負の喧騒が、少しだけ遠のく。
      </p>
      {typeof pending.heal === "number" && (
        <div className="flex flex-col items-center gap-1">
          <span className="label">回復量</span>
          <span className="font-mono" style={{ fontSize: 22, color: "var(--moss)" }}>
            +{pending.heal}
          </span>
        </div>
      )}
      {state.player && (
        <div
          className="flex w-full flex-col items-center gap-2"
          style={{ borderTop: "1px solid var(--rule)", paddingTop: 16 }}
        >
          <span className="label">回復後の体力</span>
          <HpBar current={state.player.hp} max={state.player.max_hp} width={220} />
          <span className="font-mono" style={{ fontSize: 13, color: "var(--ink2)" }}>
            HP {state.player.hp} / {state.player.max_hp}
          </span>
        </div>
      )}
      <button className="btn" style={{ minWidth: 180 }} disabled={busy} onClick={continueRun}>
        席を立つ
      </button>
    </CenterStage>
  );
}
