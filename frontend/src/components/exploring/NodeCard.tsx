import type { FloorNode } from "../../api/types";
import { experienceMeta, NODE_KIND } from "../../lib/labels";
import Icon from "../common/Icon";
import Motif from "../common/Motif";

// 1ノードのカード（design 忠実）。左色バー＋アイコン＋名前／下段に motif＋状態インジケータ。
export default function NodeCard({
  node,
  busy,
  onClick,
}: {
  node: FloorNode;
  busy: boolean;
  onClick: (id: string) => void;
}) {
  const available = node.state === "available";
  const resolved = node.state === "resolved";
  const locked = node.state === "locked";
  const isGate = node.kind === "gate";
  const isEnemy = node.kind === "enemy";
  const exp = isEnemy ? experienceMeta(node.experience) : null;
  const kindMeta = NODE_KIND[node.kind];
  const barColor = exp ? exp.color : kindMeta.color;
  const iconType = exp ? exp.iconType : kindMeta.iconType;
  const title = isEnemy ? node.name ?? "賭博者" : kindMeta.jp;

  const rightIcon = locked ? "lock" : resolved ? "check" : "arrow";
  const rightColor = locked ? "var(--ink3)" : resolved ? "var(--moss)" : "var(--accent)";

  return (
    <button
      disabled={!available || busy}
      onClick={() => onClick(node.id)}
      style={{
        position: "relative",
        width: 158,
        textAlign: "left",
        padding: "11px 13px",
        borderRadius: 10,
        background: "var(--felt)",
        border: "1px solid var(--rule2)",
        color: resolved ? "var(--ink3)" : "var(--ink)",
        opacity: locked ? 0.45 : 1,
        cursor: available && !busy ? "pointer" : "default",
        animation: available ? (isGate ? "gateGlow 2.6s infinite" : "availGlow 2.4s infinite") : undefined,
        overflow: "hidden",
        transition: "transform .08s var(--ease), opacity .2s var(--ease)",
      }}
    >
      <span style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: barColor }} />
      <div className="flex items-center gap-2" style={{ paddingLeft: 5 }}>
        <span style={{ display: "flex", flex: "none", color: barColor }}>
          <Icon type={iconType} size={20} />
        </span>
        <span
          style={{
            flex: 1,
            minWidth: 0,
            fontFamily: "var(--serif)",
            fontSize: 15,
            lineHeight: 1.1,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            color: "inherit",
          }}
        >
          {title}
        </span>
        {isEnemy && node.is_strong && (
          <span title="大物" style={{ width: 6, height: 6, borderRadius: 999, background: "var(--brass)", flex: "none" }} />
        )}
      </div>
      <div className="flex items-center justify-between" style={{ marginTop: 9, paddingLeft: 5, minHeight: 14 }}>
        <span style={{ display: "flex", color: barColor }}>{exp ? <Motif type={exp.iconType} color={barColor} /> : <span />}</span>
        <span style={{ display: "flex", flex: "none", color: rightColor }}>
          <Icon type={rightIcon} size={15} />
        </span>
      </div>
    </button>
  );
}
