import { useState } from "react";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import GlowTitle from "../components/common/GlowTitle";

// スタート画面。タイトルをネオン・マーキー（GlowTitle）にし、主ボタン1点へ視線誘導する。
export default function StartPage() {
  const newRun = useGameStore((s) => s.newRun);
  const busy = useGameStore((s) => s.busy);
  const openDossier = useGameStore((s) => s.openDossier);
  const [seed, setSeed] = useState("");

  const start = () => {
    const n = seed.trim() === "" ? undefined : Number(seed.trim());
    newRun(Number.isFinite(n as number) ? (n as number) : undefined);
  };

  return (
    <CenterStage maxWidth={480}>
      <span className="label">賭博都市の摩天楼</span>
      <GlowTitle size={52}>カジノタワー</GlowTitle>
      <p className="font-sans" style={{ fontSize: 13.5, color: "var(--ink2)", lineHeight: 1.7 }}>
        頂上に待つ、全てを賭けた一勝負を目指す。
        <br />
        5つの関門を抜けて頂上へ。倒れれば、そこで終わり。
      </p>

      <div className="flex items-center gap-2">
        <span className="label">seed（任意）</span>
        {/* .pill と同じトークン感（paper2 地・rule2 罫・丸め）に揃えた入力欄 */}
        <input
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          placeholder="ランダム"
          className="font-mono"
          style={{
            width: 120,
            padding: "6px 12px",
            background: "var(--paper2)",
            border: "1px solid var(--rule2)",
            borderRadius: 999,
            color: "var(--ink)",
            fontSize: 13,
            textAlign: "center",
          }}
        />
      </div>

      {/* 主ボタンのみ btn-glow。「調書を見る」は光らせず視線誘導を1点に保つ */}
      <button className="btn btn-glow" style={{ minWidth: 200 }} disabled={busy} onClick={start}>
        {busy ? "…" : "卓に着く"}
      </button>
      <button className="btn btn-ghost" style={{ minWidth: 200 }} onClick={openDossier}>
        調書を見る
      </button>
    </CenterStage>
  );
}
