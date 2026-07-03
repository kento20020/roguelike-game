import { useState } from "react";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";

// スタート画面（既存デザイン範囲外の最小エントリ）。ランを開始する。
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
      <h1 className="font-serif" style={{ fontSize: 52, lineHeight: 1.05, color: "var(--ink)" }}>
        カジノタワー
      </h1>
      <p className="font-sans" style={{ fontSize: 13.5, color: "var(--ink2)", lineHeight: 1.7 }}>
        頂上に待つ、全てを賭けた一勝負を目指す。
        <br />
        5つの関門を抜けて頂上へ。倒れれば、そこで終わり。
      </p>

      <div className="flex items-center gap-2">
        <span className="label">seed（任意）</span>
        <input
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          placeholder="ランダム"
          className="font-mono"
          style={{
            width: 120,
            padding: "6px 10px",
            background: "var(--paper)",
            border: "1px solid var(--rule2)",
            borderRadius: 8,
            color: "var(--ink)",
            fontSize: 13,
            textAlign: "center",
          }}
        />
      </div>

      <button className="btn" style={{ minWidth: 200 }} disabled={busy} onClick={start}>
        {busy ? "…" : "卓に着く"}
      </button>
      <button className="btn btn-ghost" style={{ minWidth: 200 }} onClick={openDossier}>
        調書を見る
      </button>
    </CenterStage>
  );
}
