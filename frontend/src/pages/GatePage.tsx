import type { GameState, SinkType } from "../api/types";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import { gateOutcome, SINK_META } from "../lib/labels";

// 関門（gate_preview）。出目の確率分布＋被ダメを見せ、関門保証で安全側に寄せるか判断させる（GDD §7.4）。
const ORDER = ["unhurt", "minor", "major", "special"];

export default function GatePage({ state }: { state: GameState }) {
  const gateResolve = useGameStore((s) => s.gateResolve);
  const sink = useGameStore((s) => s.sink);
  const busy = useGameStore((s) => s.busy);

  const pending = state.pending as { table?: Record<string, number>; damage?: Record<string, number> };
  const table = pending.table ?? {};
  const damage = pending.damage ?? {};
  const guarantee = state.available_actions.find((a) => a.type === "use_sink" && a.sink === "gate_guarantee");

  return (
    <CenterStage maxWidth={500}>
      <span className="label">ハウスルール</span>
      <div className="font-serif" style={{ fontSize: 38, color: "var(--brass)" }}>
        胴元の関門
      </div>
      <p className="font-sans" style={{ fontSize: 12.5, color: "var(--ink2)", lineHeight: 1.6 }}>
        通れば次の階へ。ただし胴元の取り分は出目しだい。
      </p>

      {/* 出目の確率バー（幅∝確率） */}
      <div style={{ width: "100%", display: "flex", height: 16, borderRadius: 999, overflow: "hidden", border: "1px solid var(--rule)" }}>
        {ORDER.map((o) => {
          const p = table[o] ?? 0;
          if (p <= 0) return null;
          return <div key={o} style={{ width: `${p * 100}%`, background: gateOutcome(o).color }} />;
        })}
      </div>

      {/* 出目ごと：名前・被ダメ・確率 */}
      <div style={{ width: "100%" }}>
        {ORDER.map((o) => {
          const p = table[o] ?? 0;
          const d = damage[o] ?? 0;
          const meta = gateOutcome(o);
          return (
            <div key={o} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 2px", borderBottom: "1px solid var(--rule)" }}>
              <span style={{ width: 9, height: 9, borderRadius: 2, background: meta.color, flex: "none" }} />
              <span style={{ flex: 1, textAlign: "left", fontFamily: "var(--sans)", fontSize: 12.5, color: "var(--ink)" }}>{meta.jp}</span>
              <span style={{ fontFamily: "var(--sans)", fontSize: 11, color: d > 0 ? "var(--danger)" : "var(--ink3)" }}>
                {d > 0 ? `−${d}` : "無し"}
              </span>
              <span style={{ fontFamily: "var(--mono)", fontSize: 13.5, minWidth: 48, textAlign: "right" }}>{Math.round(p * 100)}%</span>
            </div>
          );
        })}
      </div>

      {/* 所持チップ */}
      <div
        style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", borderRadius: 6, border: "1px solid var(--rule)", background: "var(--felt)" }}
      >
        <span className="font-sans" style={{ fontSize: 12, color: "var(--ink2)" }}>
          所持チップ
          {guarantee?.cost != null ? `（保証に ${guarantee.cost}）` : ""}
        </span>
        <span style={{ fontFamily: "var(--mono)", fontSize: 15, color: "var(--brass)" }}>{state.player?.chips ?? 0}</span>
      </div>

      <div className="flex items-center gap-3">
        {guarantee && (
          <button className="btn btn-ghost" disabled={busy} onClick={() => sink("gate_guarantee" as SinkType)}>
            {SINK_META.gate_guarantee.label}
            {guarantee.cost != null ? ` · ${guarantee.cost}` : ""}
          </button>
        )}
        <button className="btn" style={{ minWidth: 160 }} disabled={busy} onClick={gateResolve}>
          通過する
        </button>
      </div>
      <div style={{ fontSize: 11, color: "var(--ink3)" }}>関門保証は大ダメの確率を無傷・小ダメへ寄せる（特殊＝当たりは残る／確実な安全は買えない）</div>
    </CenterStage>
  );
}
