import type { GameState } from "../api/types";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import Icon from "../components/common/Icon";
import { modLabel, MOD_ICON } from "../lib/labels";

// 宝箱（treasure_preview / treasure_opened）。撃破ドロップ（source=enemy）も同フロー。
export default function TreasurePage({ state }: { state: GameState }) {
  const treasureOpen = useGameStore((s) => s.treasureOpen);
  const treasureReroll = useGameStore((s) => s.treasureReroll);
  const continueRun = useGameStore((s) => s.continueRun);
  const busy = useGameStore((s) => s.busy);
  const catalog = useGameStore((s) => s.catalog);

  const pending = state.pending as { mod?: string; count?: number; source?: string };
  const opened = state.phase === "treasure_opened";
  const fromEnemy = pending.source === "enemy";
  const canReroll = state.available_actions.some((a) => a.type === "treasure_reroll");

  if (opened) {
    const mod = pending.mod;
    const count = pending.count ?? 1;
    const item = mod ? catalog[mod] : undefined;
    const effect = item ? (count >= 2 ? item.effect_stack : item.effect_1) : "";
    return (
      <CenterStage tone="win" maxWidth={460}>
        <div key="opened" className="flex flex-col items-center gap-6" style={{ animation: "fadeUp .4s var(--ease) both" }}>
          <span className="label">必勝の秘技</span>
          <div className="flex items-center gap-2" style={{ color: "var(--brass)" }}>
            {mod && <Icon type={MOD_ICON[mod] ?? "star"} size={26} />}
            <div className="font-serif" style={{ fontSize: 38 }}>{mod ? modLabel(mod) : "技"}</div>
          </div>
          {effect && (
            <p className="font-sans" style={{ fontSize: 13, color: "var(--ink2)", lineHeight: 1.6, maxWidth: 360 }}>
              {effect}
            </p>
          )}
          {count >= 2 && (
            <span className="pill" style={{ color: "var(--brass)", borderColor: "var(--brass)" }}>
              強化（{count}枚目）
            </span>
          )}
          <button className="btn" style={{ minWidth: 180 }} disabled={busy} onClick={continueRun}>
            手にする
          </button>
        </div>
      </CenterStage>
    );
  }

  return (
    <CenterStage maxWidth={460}>
      <div key="preview" className="flex flex-col items-center gap-6" style={{ animation: "fadeUp .32s var(--ease) both" }}>
        <span className="label">イカサマ道具</span>
        <div className="font-serif" style={{ fontSize: 40 }}>
          ？？？
        </div>
        <p className="font-sans" style={{ fontSize: 13, color: "var(--ink2)" }}>
          {fromEnemy
            ? "倒した相手が何かを落とした。中身は開けるまで分からない。"
            : "宝箱を見つけた。中身は開けるまで分からない。"}
        </p>
        <div className="flex items-center gap-3">
          <button className="btn" style={{ minWidth: 140 }} disabled={busy} onClick={treasureOpen}>
            開封する
          </button>
          {canReroll && (
            <button className="btn btn-ghost" disabled={busy} onClick={treasureReroll}>
              引き直す
            </button>
          )}
        </div>
      </div>
    </CenterStage>
  );
}
