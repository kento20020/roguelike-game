import { useEffect, useRef, useState } from "react";

// チップ（ゴールド）表示の微アニメーション：数値が変わった瞬間にカウントアップ＋差分ポップを出す。
// GameState の数値そのものだけを見て駆動する表示専用フック（ロジックには関与しない）。

const COUNT_MS = 480; // 数値が旧→新へ移行する時間
const POP_MS = 620; // index.css の dmgPop アニメーション長と合わせる

export interface ChipPopup {
  id: number;
  delta: number;
}

export interface ChipFx {
  displayValue: number;
  popup: ChipPopup | null;
}

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

export function useChipFx(value: number): ChipFx {
  const [displayValue, setDisplayValue] = useState(value);
  const [popup, setPopup] = useState<ChipPopup | null>(null);

  const prevRef = useRef(value);
  const idRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const popupTimerRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    return () => {
      if (rafRef.current !== null) window.cancelAnimationFrame(rafRef.current);
      window.clearTimeout(popupTimerRef.current);
    };
  }, []);

  useEffect(() => {
    const from = prevRef.current;
    const delta = value - from;
    prevRef.current = value;

    if (delta === 0) {
      setDisplayValue(value);
      return;
    }

    idRef.current += 1;
    setPopup({ id: idRef.current, delta });
    window.clearTimeout(popupTimerRef.current);
    popupTimerRef.current = window.setTimeout(() => setPopup(null), POP_MS);

    const start = performance.now();
    if (rafRef.current !== null) window.cancelAnimationFrame(rafRef.current);

    function step(now: number) {
      const t = Math.min(1, (now - start) / COUNT_MS);
      setDisplayValue(Math.round(from + delta * easeOutCubic(t)));
      if (t < 1) {
        rafRef.current = window.requestAnimationFrame(step);
      } else {
        rafRef.current = null;
      }
    }
    rafRef.current = window.requestAnimationFrame(step);
  }, [value]);

  return { displayValue, popup };
}
