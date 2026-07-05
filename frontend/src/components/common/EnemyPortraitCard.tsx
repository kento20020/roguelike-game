import Icon from "./Icon";
import Motif from "./Motif";
import type { ExpMeta } from "../../lib/labels";

// 敵カードモチーフ(手配書/コートカード): トランプ札の様式に規格化した敵の肖像。
// 肖像は単色シルエット＋輪郭のリムライトのみ(色は経験タイプで統一)とし、個別の敵絵は持たない
// （design/claude_design_prompt_chip_fx_and_enemy_card_motif.md B案）。
// rank は difficulty(1-5・正本 enemies.json)から呼び出し側が算出して渡す（省略時はコーナー表示なし）。
// difficulty/is_strong は事前遭遇していない敵に対しては開示不変条件（backend/tests/test_dossier.py
// test_catalog_enemies_never_exposes_weights）により取得できないため、rank/boss を省略できるようにしてある。
export default function EnemyPortraitCard({
  name,
  exp,
  rank,
  boss = false,
  size = "md",
}: {
  name: string;
  exp: ExpMeta;
  rank?: string;
  boss?: boolean;
  size?: "md" | "sm";
}) {
  const frameColor = boss ? "var(--accent)" : exp.color;
  const portraitSize = size === "md" ? 72 : 44;
  const iconSize = size === "md" ? 38 : 22;
  const nameSize = size === "md" ? 30 : 15;

  return (
    <div
      className="flex items-center"
      style={{
        gap: size === "md" ? 16 : 10,
        padding: size === "md" ? "12px 20px 12px 12px" : "6px 10px 6px 6px",
        borderRadius: size === "md" ? 14 : 10,
        background: "var(--paper2)",
        border: `1px solid ${frameColor}`,
        boxShadow: boss
          ? `0 0 0 1px ${frameColor}, 0 0 26px var(--glowAccent), 0 10px 26px rgba(0, 0, 0, 0.45)`
          : "none",
      }}
    >
      <div
        style={{
          position: "relative",
          width: portraitSize,
          height: portraitSize,
          flex: "none",
          borderRadius: size === "md" ? 10 : 8,
          background: "var(--felt)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: `inset 0 0 0 1px var(--rule2), 0 0 ${size === "md" ? 22 : 12}px ${exp.color}55`,
        }}
      >
        <span style={{ color: exp.color, display: "flex" }}>
          <Icon type={exp.iconType} size={iconSize} />
        </span>
        {rank && (
          <span
            className="font-mono"
            style={{
              position: "absolute",
              top: 4,
              left: 6,
              fontSize: size === "md" ? 11 : 9,
              fontWeight: 700,
              color: exp.color,
            }}
          >
            {rank}
          </span>
        )}
      </div>
      <div className="flex flex-col" style={{ gap: 3, minWidth: 0 }}>
        {size === "md" && (
          <span className="label" style={{ letterSpacing: "0.16em" }}>
            {rank ? `RANK ${rank} · ` : ""}
            {exp.en}
            {boss ? " · BOSS" : ""}
          </span>
        )}
        <h2
          style={{
            margin: 0,
            fontFamily: "var(--serif)",
            fontSize: nameSize,
            lineHeight: 1.1,
            color: boss ? "var(--accent)" : "var(--ink)",
            whiteSpace: size === "sm" ? "nowrap" : undefined,
            overflow: size === "sm" ? "hidden" : undefined,
            textOverflow: size === "sm" ? "ellipsis" : undefined,
          }}
        >
          {name}
        </h2>
        {size === "md" && (
          <div className="flex items-center gap-2">
            <Motif type={exp.iconType} color={exp.color} />
            <span style={{ fontFamily: "var(--sans)", fontSize: 12 }}>
              <span style={{ color: exp.color, fontWeight: 600 }}>{exp.jp}</span> · {exp.tend}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
