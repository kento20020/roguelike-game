import type { GameState, SinkType } from "../api/types";
import { useGameStore } from "../store/gameStore";
import EmberBackground from "../components/common/EmberBackground";
import Header from "../components/common/Header";
import SinkMenu from "../components/common/SinkMenu";
import CombatPanel from "../components/battle/CombatPanel";

// 戦闘（battle）。攻撃するのみ（意思決定はマップ層）。
export default function BattlePage({ state }: { state: GameState }) {
  const attack = useGameStore((s) => s.attack);
  const guard = useGameStore((s) => s.guard);
  const sink = useGameStore((s) => s.sink);
  const busy = useGameStore((s) => s.busy);

  if (!state.player || !state.battle) return null;
  const canAttack = state.available_actions.some((a) => a.type === "attack");
  const canGuard = state.available_actions.some((a) => a.type === "guard");

  return (
    // 戦闘画面は 1 画面（100dvh）に固定し、はみ出しは内部スクロールに閉じ込める
    // （ページ全体＝body はスクロールさせない）。ヘッダーは上部固定、本文だけがスクロールする。
    <div className="relative flex h-[100dvh] flex-col overflow-hidden">
      <EmberBackground />
      <div className="relative z-10 flex min-h-0 flex-1 flex-col">
        <Header player={state.player} floorNumber={state.current_floor} />
        <section className="flex min-h-0 flex-1 flex-col items-center gap-4 overflow-y-auto px-6 pb-6 pt-5">
          {/* shrink-0: 画面が低いとき flex 子が潰れて中身が重なるのを防ぎ、代わりに section が内部スクロールする */}
          <div className="flex w-full shrink-0 flex-col items-center">
            <CombatPanel
              battle={state.battle}
              player={state.player}
              busy={busy}
              canAttack={canAttack}
              canGuard={canGuard}
              onAttack={attack}
              onGuard={guard}
            />
          </div>
          <div className="shrink-0">
            <SinkMenu actions={state.available_actions} chips={state.player.chips} onSink={(s: SinkType) => sink(s)} busy={busy} />
          </div>
        </section>
      </div>
    </div>
  );
}
