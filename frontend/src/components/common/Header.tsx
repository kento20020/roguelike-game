import { useState } from "react";
import type { Player } from "../../api/types";
import { floorName, modLabel, MOD_ICON } from "../../lib/labels";
import { useGameStore } from "../../store/gameStore";
import HpBar from "./HpBar";
import Icon from "./Icon";

// 探索/戦闘の固定ヘッダー（design 忠実）。フロア章・HP・攻・チップ・技mod（ドロップダウン）。
export default function Header({ player, floorNumber }: { player: Player; floorNumber: number }) {
  const [open, setOpen] = useState(false);
  const catalog = useGameStore((s) => s.catalog);
  const uniqueMods = [...new Set(player.mods)];

  return (
    <header
      className="relative z-20 flex items-center gap-4 px-6"
      style={{ height: 66, borderBottom: "1px solid var(--rule)", background: "rgba(21,18,14,0.66)", backdropFilter: "blur(12px)" }}
    >
      <div className="flex items-center gap-3">
        <div
          className="flex items-center justify-center font-mono"
          style={{ width: 42, height: 42, borderRadius: 999, border: "1px solid var(--rule2)", color: "var(--accent)", fontSize: 14 }}
        >
          {floorNumber}F
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="label" style={{ fontSize: 9.5 }}>
            Floor {String(floorNumber).padStart(2, "0")}
          </span>
          <span className="font-serif" style={{ fontSize: 20, lineHeight: 1 }}>
            {floorName(floorNumber)}
          </span>
        </div>
      </div>

      <div className="flex-1" />

      <div className="flex items-center gap-2.5">
        <span className="label">HP</span>
        <HpBar current={player.hp} max={player.max_hp} />
        <span className="font-mono" style={{ fontSize: 13 }}>
          {player.hp}
          <span style={{ color: "var(--ink3)" }}> / {player.max_hp}</span>
        </span>
      </div>

      <div style={{ width: 1, height: 26, background: "var(--rule)" }} />

      <div className="flex items-center gap-1.5" style={{ color: "var(--accent)" }}>
        <Icon type="sword" size={15} />
        <span className="label">攻</span>
        <span className="font-mono" style={{ fontSize: 14, color: "var(--ink)" }}>
          {player.attack}
          {player.attack_boost_pending && <span style={{ color: "var(--accent)" }}> ⤴</span>}
        </span>
      </div>

      <div style={{ width: 1, height: 26, background: "var(--rule)" }} />

      <div className="flex items-center gap-2">
        <span style={{ width: 13, height: 13, borderRadius: 999, border: "1.5px solid var(--brass)", display: "inline-block" }} />
        <span className="label">Chips</span>
        <span className="font-mono" style={{ fontSize: 14, color: "var(--brass)" }}>
          {player.chips}
        </span>
      </div>

      {uniqueMods.length > 0 && (
        <>
          <div style={{ width: 1, height: 26, background: "var(--rule)" }} />
          <div className="relative">
            <button
              onClick={() => setOpen((o) => !o)}
              className="flex items-center gap-1.5"
              style={{ background: "transparent", border: "1px solid var(--rule)", borderRadius: 999, padding: "4px 9px 4px 11px", cursor: "pointer" }}
            >
              <span className="label">技</span>
              {uniqueMods.map((m) => (
                <span key={m} className="pill">
                  {modLabel(m)}
                </span>
              ))}
              <span style={{ fontSize: 9, color: "var(--ink3)" }}>▾</span>
            </button>
            {open && (
              <div
                className="absolute"
                style={{ top: 44, right: 0, width: 288, background: "var(--paper2)", border: "1px solid var(--rule2)", borderRadius: 8, boxShadow: "0 18px 50px rgba(0,0,0,0.5)", padding: "6px 16px 10px", zIndex: 30 }}
              >
                <div className="flex items-center justify-between" style={{ padding: "9px 0 5px" }}>
                  <span className="label">技 · Mods</span>
                  <span className="label">効果</span>
                </div>
                {uniqueMods.map((m) => {
                  const count = player.mods.filter((x) => x === m).length;
                  const item = catalog[m];
                  const effect = item ? (count >= 2 ? item.effect_stack : item.effect_1) : "";
                  return (
                    <div key={m} className="flex items-start gap-3" style={{ padding: "10px 0", borderTop: "1px solid var(--rule)" }}>
                      <span style={{ color: "var(--accent)", marginTop: 1 }}>
                        <Icon type={MOD_ICON[m] ?? "star"} size={18} />
                      </span>
                      <div className="flex flex-col gap-1">
                        <span className="font-sans" style={{ fontSize: 13, fontWeight: 500 }}>
                          {modLabel(m)}
                          {count > 1 && <span style={{ color: "var(--brass)" }}> ×{count}</span>}
                        </span>
                        <span className="font-sans" style={{ fontSize: 11.5, lineHeight: 1.45, color: "var(--ink2)" }}>
                          {effect}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}
    </header>
  );
}
