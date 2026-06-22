import type { ReactNode } from "react";
import EmberBackground from "./EmberBackground";

// モーダル/結果系phaseの中央寄せ全画面ステージ。
export default function CenterStage({
  children,
  tone = "normal",
  maxWidth = 560,
}: {
  children: ReactNode;
  tone?: "normal" | "win" | "lose";
  maxWidth?: number;
}) {
  return (
    <div className="relative min-h-screen">
      <EmberBackground tone={tone} />
      <div className="relative z-10 flex min-h-screen items-center justify-center px-6">
        <div
          className="panel flex w-full flex-col items-center gap-6 px-10 py-12 text-center"
          style={{ maxWidth, animation: "fadeUp .5s var(--ease) both" }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
