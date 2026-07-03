// 演出・音の基礎体力（juice foundation）: Web Audio API による短い合成効果音。
// 外部音源ファイルは使わず、OscillatorNode + GainNode のエンベロープだけで鳴らす。
//
// 重要（演出原則）: このファイルは「鳴らす」だけの薄いユーティリティであり、
// いつ・何の音を鳴らすかの判断は一切含まない。判断は呼び出し側（useCombatFx）が
// バックエンドの実現結果（GameState の差分）だけを見て行う。
// ここに確率・重み・敵の内部状態などを持ち込まないこと。

type ToneOptions = {
  freqStart: number;
  freqEnd?: number;
  duration: number; // 秒
  type?: OscillatorType;
  gain?: number;
  delay?: number; // 秒（重ね音のタイミングずらし用）
};

let sharedCtx: AudioContext | null = null;

function getCtx(): AudioContext | null {
  if (typeof AudioContext === "undefined") return null; // SSR/非対応環境では無音でスキップ
  if (!sharedCtx) sharedCtx = new AudioContext();
  if (sharedCtx.state === "suspended") {
    // ブラウザの自動再生制限対策。攻撃/受けボタン押下（ユーザ操作）の延長で呼ばれるため resume 可能。
    void sharedCtx.resume();
  }
  return sharedCtx;
}

// 短音を1つ鳴らす（アタック→ディケイの簡易エンベロープでクリックノイズを避ける）。
function tone({ freqStart, freqEnd, duration, type = "sine", gain = 0.18, delay = 0 }: ToneOptions): void {
  const ctx = getCtx();
  if (!ctx) return;
  const start = ctx.currentTime + delay;

  const osc = ctx.createOscillator();
  const env = ctx.createGain();

  osc.type = type;
  osc.frequency.setValueAtTime(freqStart, start);
  if (freqEnd !== undefined) {
    osc.frequency.exponentialRampToValueAtTime(Math.max(freqEnd, 1), start + duration);
  }

  env.gain.setValueAtTime(0.0001, start);
  env.gain.exponentialRampToValueAtTime(gain, start + 0.012);
  env.gain.exponentialRampToValueAtTime(0.0001, start + duration);

  osc.connect(env);
  env.connect(ctx.destination);
  osc.start(start);
  osc.stop(start + duration + 0.02);
}

// 打撃音：自分の攻撃が敵に命中した（=enemy.hp が減った）結果を受けて鳴らす。短く硬いクリック。
export function playHit(): void {
  tone({ freqStart: 620, freqEnd: 240, duration: 0.09, type: "square", gain: 0.16 });
}

// 受け音：防御・軽減が発生した結果を受けて鳴らす。低めでこもった音。
export function playGuard(): void {
  tone({ freqStart: 180, freqEnd: 90, duration: 0.14, type: "sine", gain: 0.16 });
}

// 強打音：被弾（反撃・強打・蓄積ダメージ等）の結果を受けて鳴らす。重めの二重音で衝撃感を出す。
export function playHeavy(): void {
  tone({ freqStart: 140, freqEnd: 55, duration: 0.22, type: "sawtooth", gain: 0.2 });
  tone({ freqStart: 90, freqEnd: 45, duration: 0.18, type: "sine", gain: 0.22, delay: 0.03 });
}

// 成功音：関門通過など、明るい確定結果を受けて鳴らす（上昇するトライアングル波）。
export function playGateSuccess(): void {
  tone({ freqStart: 440, freqEnd: 880, duration: 0.16, type: "triangle", gain: 0.16 });
}
