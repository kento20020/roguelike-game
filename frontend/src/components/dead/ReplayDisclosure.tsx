import { useState } from "react";
import Icon from "../common/Icon";
import type { PostmortemResponse } from "../../api/types";
import TurnRow from "./TurnRow";

// リプレイ＝任意の深掘り。デフォルト折りたたみ、致命ターンだけは閉じた状態でもプレビューで見える。
// 「戦闘の再演」ではなく「記録の閲覧」なので開閉アニメーションは高さのfadeUp程度に留める。DeadPage から抽出。
export default function ReplayDisclosure({ pm }: { pm: PostmortemResponse }) {
  const [open, setOpen] = useState(false);
  if (pm.turn_history.length === 0) return null;
  const fatalEntry = pm.turn_history[pm.fatal_turn_index];

  return (
    <div
      className="flex w-full flex-col"
      style={{
        borderRadius: 12,
        border: "1px solid var(--rule2)",
        background: "var(--paper2)",
        overflow: "hidden",
        animation: "fadeUp .4s var(--ease) .2s both",
      }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-2 font-sans"
        style={{
          width: "100%",
          padding: "12px 16px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "var(--ink2)",
          fontSize: 12.5,
        }}
      >
        <Icon
          type="arrow"
          size={13}
          style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)", transition: "transform .2s var(--ease)", flex: "none" }}
        />
        <span>ターンごとの記録を見る（全{pm.turn_history.length}手）</span>
      </button>
      {!open && fatalEntry && (
        <div
          role="button"
          tabIndex={0}
          onClick={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") setOpen(true);
          }}
          title="クリックで全ターンを展開"
          style={{ padding: "0 12px 12px", textAlign: "left", cursor: "pointer" }}
        >
          <TurnRow entry={fatalEntry} index={pm.fatal_turn_index} isFatal />
        </div>
      )}
      {open && (
        <div style={{ maxHeight: 360, overflowY: "auto", textAlign: "left", padding: "0 12px 12px" }}>
          {pm.turn_history.map((entry, i) => (
            <TurnRow key={i} entry={entry} index={i} isFatal={i === pm.fatal_turn_index} />
          ))}
        </div>
      )}
    </div>
  );
}
