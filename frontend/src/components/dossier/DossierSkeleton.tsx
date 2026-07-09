// 調書読み込み中のスケルトン表示。DossierPage から抽出。
export default function DossierSkeleton() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="dossier-skeleton"
          style={{ width: "100%", height: 96, borderRadius: 10, border: "1px solid var(--rule)" }}
        />
      ))}
    </>
  );
}
