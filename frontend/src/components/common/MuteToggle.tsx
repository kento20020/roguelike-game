import { useState } from "react";
import { isMuted, setMuted } from "../../lib/sfx";
import Icon from "./Icon";

// SE ミュート切替。状態は localStorage 永続（ゲーム状態ではない=store は汚さない）。
export default function MuteToggle() {
  const [muted, setLocalMuted] = useState(isMuted);

  function toggle() {
    const next = !muted;
    setMuted(next);
    setLocalMuted(next);
  }

  return (
    <button
      onClick={toggle}
      aria-label={muted ? "効果音をオンにする" : "効果音をオフにする"}
      title={muted ? "SE: OFF" : "SE: ON"}
      className="flex items-center justify-center"
      style={{
        width: 30,
        height: 30,
        borderRadius: 999,
        border: "1px solid var(--rule2)",
        background: "transparent",
        color: muted ? "var(--ink3)" : "var(--accent)",
        cursor: "pointer",
      }}
    >
      <Icon type={muted ? "volumeMute" : "volume"} size={15} />
    </button>
  );
}
