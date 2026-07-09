import type { Battle } from "../../api/types";

// 「受け」の効き（減衰段）インジケータ。受け（ジャストガード）は同一戦闘で使うほど
// 軽減量が半減していくため、次に受けたときの効きが直感的に分かるよう可視化する。
// 効き% は backend の guard_next_scale をそのまま表示（アーキ原則1: Reactは減衰を計算しない）。
// ピップは guard_uses（整数の使用段）を左から1つずつ消して減衰を示す（◆◆◆◆→◇◆◆◆…）。
const PIPS = 4;

export default function GuardEfficacy({ battle }: { battle: Battle }) {
  const uses = battle.guard_uses ?? 0;
  const scale = battle.guard_next_scale ?? 1;
  const pct = Math.round(scale * 100);
  const spent = uses >= PIPS; // 効きがほぼ尽きた（表示だけ沈める）

  return (
    <div
      className="flex items-center"
      style={{
        gap: 8,
        padding: "5px 12px",
        borderRadius: 999,
        border: "1px solid var(--rule2)",
        background: "var(--paper2)",
      }}
      title="受け（ジャストガード）は同じ戦闘で使うほど軽減量が半減していく。これは「次に受けたときの効き」の目安。"
    >
      <span className="label" style={{ whiteSpace: "nowrap" }}>
        受けの効き
      </span>
      <div className="flex items-center" style={{ gap: 3 }}>
        {Array.from({ length: PIPS }, (_, i) => {
          const lit = i >= uses; // 左から消えていく
          return (
            <span
              key={i}
              style={{
                width: 9,
                height: 9,
                transform: "rotate(45deg)",
                borderRadius: 1.5,
                background: lit ? "var(--moss)" : "transparent",
                border: `1px solid ${lit ? "var(--moss)" : "var(--rule2)"}`,
                opacity: lit ? 1 : 0.45,
                transition: "all .18s var(--ease)",
              }}
            />
          );
        })}
      </div>
      <span
        style={{
          fontFamily: "var(--mono)",
          fontSize: 12,
          fontWeight: 600,
          color: spent ? "var(--ink3)" : "var(--moss)",
        }}
      >
        {pct}%
      </span>
    </div>
  );
}
