import { useEffect } from "react";
import { useGameStore } from "../../store/gameStore";

// 恒久強化の割り振り（GDD §24.5 / §26.6）。ClearedPage 上で残ポイントを5項目に [Lv][+] で配分。
// 数値・上限はバックエンド（config.permanent_upgrades）が正本。表示はラベルのみ。
const ITEMS: { key: string; label: string }[] = [
  { key: "max_hp", label: "最大HP" },
  { key: "attack", label: "攻撃力" },
  { key: "init_gold", label: "初期チップ" },
  { key: "gold_drop", label: "獲得チップ率" },
  { key: "sink_cost", label: "sink割引" },
];

export default function UpgradeAllocator() {
  const upgrade = useGameStore((s) => s.upgrade);
  const loadUpgradeState = useGameStore((s) => s.loadUpgradeState);
  const allocateUpgrade = useGameStore((s) => s.allocateUpgrade);
  const busy = useGameStore((s) => s.busy);

  useEffect(() => {
    loadUpgradeState();
  }, [loadUpgradeState]);

  if (!upgrade) return null;
  const { points, levels, maxes } = upgrade;

  return (
    <div style={{ width: "100%", border: "1px solid var(--rule2)", borderRadius: 10, padding: "12px 16px" }}>
      <div className="font-sans" style={{ fontSize: 12.5, color: "var(--brass)", marginBottom: 8 }}>
        恒久強化（残りポイント {points}）
      </div>
      {ITEMS.map((it) => {
        const lv = levels[it.key] ?? 0;
        const mx = maxes[it.key] ?? 0;
        const maxed = lv >= mx;
        const canAdd = points > 0 && !maxed && !busy;
        return (
          <div
            key={it.key}
            style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0", borderBottom: "1px solid var(--rule)" }}
          >
            <span style={{ flex: 1, textAlign: "left", fontFamily: "var(--sans)", fontSize: 12.5, color: "var(--ink)" }}>
              {it.label}
            </span>
            <span style={{ fontFamily: "var(--mono)", fontSize: 12, color: maxed ? "var(--ink3)" : "var(--ink2)" }}>
              Lv{lv}/{mx}
            </span>
            <button
              className="btn btn-ghost"
              style={{ minWidth: 36 }}
              disabled={!canAdd}
              onClick={() => allocateUpgrade(it.key)}
            >
              {maxed ? "MAX" : "＋"}
            </button>
          </div>
        );
      })}
    </div>
  );
}
