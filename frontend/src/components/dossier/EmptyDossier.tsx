import Icon from "../common/Icon";

// 観測記録が1件も無いときの空状態。DossierPage から抽出。
export default function EmptyDossier() {
  return (
    <div
      style={{
        width: "100%",
        border: "1px dashed var(--rule2)",
        borderRadius: 10,
        padding: "28px 16px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        color: "var(--ink3)",
      }}
    >
      <Icon type="eye" size={26} style={{ color: "var(--ink3)" }} />
      <span className="font-sans" style={{ fontSize: 13, color: "var(--ink2)" }}>
        まだ観測記録が無い。
      </span>
      <span className="font-sans" style={{ fontSize: 12, color: "var(--ink3)" }}>
        卓に着いて戦えば、ここに手筋が記録されていく。
      </span>
    </div>
  );
}
