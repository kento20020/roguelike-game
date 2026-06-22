// API エラーの簡易表示（409/400/404 等の detail）。
export default function ErrorToast({ error, onClose }: { error: string | null; onClose: () => void }) {
  if (!error) return null;
  return (
    <div
      className="fixed left-1/2 z-50 flex items-center gap-3 px-4 py-2.5"
      style={{
        bottom: 24,
        transform: "translateX(-50%)",
        background: "var(--paper2)",
        border: "1px solid var(--danger)",
        borderRadius: 10,
        boxShadow: "0 14px 40px rgba(0,0,0,0.5)",
      }}
    >
      <span className="font-sans" style={{ fontSize: 13, color: "var(--ink)" }}>
        {error}
      </span>
      <button onClick={onClose} className="font-sans" style={{ fontSize: 12, color: "var(--ink3)", cursor: "pointer", background: "none", border: "none" }}>
        ✕
      </button>
    </div>
  );
}
