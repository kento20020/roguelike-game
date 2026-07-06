import Icon from "../common/Icon";

// 穏やかな空状態（検死データ取得に失敗した場合のみ使用。読み込み中は無演出で待つ）。DeadPage から抽出。
export default function EmptyState({ icon, text }: { icon: string; text: string }) {
  return (
    <div
      className="flex flex-col items-center gap-3"
      style={{
        padding: "34px 30px",
        borderRadius: 14,
        border: "1px dashed var(--rule2)",
        background: "var(--paper2)",
        maxWidth: 380,
        animation: "fadeUp .35s var(--ease) both",
      }}
    >
      <Icon type={icon} size={26} style={{ color: "var(--ink3)" }} />
      <p className="font-sans" style={{ fontSize: 13, lineHeight: 1.6, color: "var(--ink3)" }}>
        {text}
      </p>
    </div>
  );
}
