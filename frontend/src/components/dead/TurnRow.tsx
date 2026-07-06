import Icon from "../common/Icon";
import { behaviorMeta } from "../../lib/labels";
import type { TurnHistoryEntry } from "../../api/types";
import ReplayHpBar from "./ReplayHpBar";

// リプレイの1ターン行（致命ターンは強調表示）。DeadPage から抽出。
export default function TurnRow({ entry, index, isFatal }: { entry: TurnHistoryEntry; index: number; isFatal: boolean }) {
  const meta = behaviorMeta(entry.action);
  const fatalTone = "var(--danger)";
  return (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 10, padding: isFatal ? "9px 10px" : "8px 10px",
        marginBottom: isFatal ? 4 : 0,
        borderBottom: isFatal ? "none" : "1px solid var(--rule)",
        borderRadius: isFatal ? 8 : 0,
        border: isFatal ? `1px solid ${fatalTone}` : undefined,
        background: isFatal ? "var(--dangerSoft)" : "transparent",
        animation: isFatal ? "fatalPulse 2.6s ease-in-out infinite" : undefined,
        fontSize: 12,
      }}
    >
      <span className="font-mono" style={{ width: 28, color: isFatal ? fatalTone : "var(--ink3)" }}>
        #{index + 1}
      </span>
      {isFatal && (
        <span
          className="label"
          style={{ color: fatalTone, border: `1px solid ${fatalTone}`, borderRadius: 999, padding: "1px 7px", whiteSpace: "nowrap" }}
        >
          致命の一手
        </span>
      )}
      <span
        className="flex items-center gap-1 font-sans"
        style={{ width: 56, color: entry.guard ? "var(--moss)" : "var(--ink)" }}
      >
        <Icon type={entry.guard ? "shield" : "sword"} size={13} />
        {entry.guard ? "受け" : "攻撃"}
      </span>
      <span className="flex items-center gap-1 font-sans" style={{ width: 84, color: meta?.color ?? "var(--ink2)" }}>
        <Icon type={meta?.iconType ?? "check"} size={13} />
        {meta?.jp ?? entry.action}
      </span>
      <span className="font-mono" style={{ width: 130, textAlign: "left", color: "var(--ink2)" }}>
        与{entry.dealt} / 被{entry.incoming}
      </span>
      <span className="flex items-center gap-2">
        <span className="font-mono" style={{ fontSize: 10, color: "var(--ink3)", width: 64 }}>
          自 {entry.player_hp_before}→{entry.player_hp_after}
        </span>
        <ReplayHpBar
          before={entry.player_hp_before}
          after={entry.player_hp_after}
          max={entry.pre_turn_snapshot?.player?.max_hp ?? entry.player_hp_before}
          color="var(--moss)"
        />
      </span>
      <span className="flex items-center gap-2">
        <span className="font-mono" style={{ fontSize: 10, color: "var(--ink3)", width: 64 }}>
          敵 {entry.enemy_hp_before}→{entry.enemy_hp_after}
        </span>
        <ReplayHpBar
          before={entry.enemy_hp_before}
          after={entry.enemy_hp_after}
          max={entry.pre_turn_snapshot?.enemy?.max_hp ?? entry.enemy_hp_before}
          color="var(--danger)"
        />
      </span>
    </div>
  );
}
