import { useState } from "react";
import type { GameState, SinkType } from "../api/types";
import { useGameStore } from "../store/gameStore";
import EmberBackground from "../components/common/EmberBackground";
import Header from "../components/common/Header";
import SinkMenu from "../components/common/SinkMenu";
import BehaviorGlossary from "../components/common/BehaviorGlossary";
import TreeCanvas from "../components/exploring/TreeCanvas";
import Icon from "../components/common/Icon";
import { EXPERIENCE } from "../lib/labels";

// 探索（exploring）。下の卓から選び、上の関門へ（登る）。幅に自動フィット。
export default function ExploringPage({ state }: { state: GameState }) {
  const selectNode = useGameStore((s) => s.selectNode);
  const sink = useGameStore((s) => s.sink);
  const busy = useGameStore((s) => s.busy);
  const [help, setHelp] = useState(false);

  if (!state.player || !state.floor) return null;

  return (
    <div className="relative min-h-screen">
      <EmberBackground />
      <div className="relative z-10">
        <Header player={state.player} floorNumber={state.current_floor} />
        <section className="px-6 py-7">
          <div className="panel mx-auto px-6 py-6" style={{ maxWidth: 1100, width: "100%" }}>
            <div className="mb-3 flex items-center justify-between gap-4">
              <span className="label">下の卓から選び、上の関門へ</span>
              <div className="flex flex-wrap items-center gap-3">
                <span className="label" style={{ fontSize: 9 }}>相手の傾向</span>
                {Object.values(EXPERIENCE).map((g) => (
                  <span key={g.jp} className="flex items-center gap-1.5" style={{ color: g.color }}>
                    <Icon type={g.iconType} size={14} />
                    <span className="font-sans" style={{ fontSize: 11, color: "var(--ink2)" }}>
                      {g.jp}
                    </span>
                  </span>
                ))}
                <button
                  onClick={() => setHelp((h) => !h)}
                  className="btn btn-ghost"
                  style={{ padding: "3px 10px", fontSize: 11, borderRadius: 999 }}
                >
                  {help ? "× 閉じる" : "？ ヘルプ"}
                </button>
              </div>
            </div>

            {help && (
              <div className="mb-4 flex flex-col gap-3" style={{ borderTop: "1px solid var(--rule)", paddingTop: 12 }}>
                <div className="flex flex-wrap gap-x-8 gap-y-2">
                  {Object.values(EXPERIENCE).map((g) => (
                    <div key={g.jp} className="flex items-center gap-2" style={{ minWidth: 220 }}>
                      <span style={{ color: g.color, display: "flex" }}>
                        <Icon type={g.iconType} size={16} />
                      </span>
                      <span className="font-sans" style={{ fontSize: 12, color: "var(--ink)" }}>
                        {g.jp}
                      </span>
                      <span className="font-sans" style={{ fontSize: 11.5, color: "var(--ink2)" }}>
                        — {g.tend}
                      </span>
                    </div>
                  ))}
                </div>
                <BehaviorGlossary defaultOpen title="敵の手筋" />
              </div>
            )}

            <div className="py-2">
              <TreeCanvas floor={state.floor} busy={busy} onSelect={selectNode} />
            </div>
          </div>
          <div className="mt-5">
            <SinkMenu actions={state.available_actions} chips={state.player.chips} onSink={(s: SinkType) => sink(s)} busy={busy} />
          </div>
        </section>
      </div>
    </div>
  );
}
