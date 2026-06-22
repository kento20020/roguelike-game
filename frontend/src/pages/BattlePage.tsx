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
    <div className="relative min-h-screen">
      <EmberBackground />
      <div className="relative z-10">
        <Header player={state.player} floorNumber={state.current_floor} />
        <section className="flex flex-col items-center gap-6 px-6 pb-10 pt-7">
          <CombatPanel
            battle={state.battle}
            player={state.player}
            busy={busy}
            canAttack={canAttack}
            canGuard={canGuard}
            onAttack={attack}
            onGuard={guard}
          />
          <SinkMenu actions={state.available_actions} chips={state.player.chips} onSink={(s: SinkType) => sink(s)} busy={busy} />
        </section>
      </div>
    </div>
  );
}
