import Icon from "../common/Icon";
import type { PostmortemResponse } from "../../api/types";

// 3分類の視覚トーン（CLAUDE.md: 既存CSS変数のみ使用）。
// unavoidable=落ち着いた色調／avoidable系=警告色／mutual_kill=惜しかった(真鍮)だが
// カード面自体は felt のまま中立に保ち、敗北全体の沈んだトーンと衝突させない（枠線のみ色を乗せる）。
const CATEGORY_META: Record<
  string,
  { tone: string; bg: string; border: string; icon: string; badge: string }
> = {
  unavoidable: { tone: "var(--ink2)", bg: "var(--paper2)", border: "var(--rule2)", icon: "lock", badge: "回避不能だった" },
  avoidable_guard: { tone: "var(--danger)", bg: "var(--dangerSoft)", border: "var(--danger)", icon: "warn", badge: "回避可能だった" },
  avoidable_attack: { tone: "var(--danger)", bg: "var(--dangerSoft)", border: "var(--danger)", icon: "warn", badge: "回避可能だった" },
  mutual_kill_victory: { tone: "var(--brass)", bg: "var(--brassSoft)", border: "var(--brass)", icon: "star", badge: "相打ち勝利だった" },
};
const DEFAULT_CATEGORY_META = { tone: "var(--ink2)", bg: "var(--paper2)", border: "var(--rule2)", icon: "check", badge: "" };

// 検死レポート＝この画面で最も重い視覚的ウェイトを持つ常時表示カード（タブの奥に隠さない）。
// 決算カードにわずかに遅れてフェードインし、「決算の次に主役」であることを示す。DeadPage から抽出。
export default function PostmortemCard({ pm }: { pm: PostmortemResponse }) {
  const cf = pm.counterfactual;
  const meta = CATEGORY_META[cf.category] ?? DEFAULT_CATEGORY_META;
  return (
    <div
      className="flex w-full flex-col items-center gap-4"
      style={{
        padding: "24px 28px",
        borderRadius: 14,
        border: `1px solid ${meta.border}`,
        background: "var(--felt)",
        boxShadow: "inset 0 1px 0 rgba(241, 236, 224, 0.04)",
        animation: "fadeUp .4s var(--ease) .12s both",
      }}
    >
      <div
        className="inline-flex items-center gap-2"
        style={{ padding: "6px 16px", borderRadius: 999, border: `1px solid ${meta.border}`, background: meta.bg }}
      >
        <span style={{ color: meta.tone, display: "flex" }}>
          <Icon type={meta.icon} size={15} />
        </span>
        <span className="label" style={{ color: meta.tone }}>
          {meta.badge}
        </span>
      </div>
      <span className="label">致命の一手（{cf.original_guard ? "受け" : "攻撃"}を選んだターン）</span>
      <p className="font-serif" style={{ fontSize: 22, color: meta.tone }}>
        {cf.message}
      </p>
      <div
        className="flex flex-wrap items-start justify-center gap-x-8 gap-y-3"
        style={{ fontSize: 12, borderTop: "1px solid var(--rule)", paddingTop: 16, width: "100%" }}
      >
        <div className="flex flex-col items-center gap-1">
          <span className="label">実際の選択</span>
          <span className="font-mono flex items-center gap-1.5">
            <Icon type={cf.original_guard ? "shield" : "sword"} size={13} />
            {cf.original_guard ? "受け" : "攻撃"}
          </span>
        </div>
        <div className="flex flex-col items-center gap-1">
          <span className="label">もし逆を選んでいたら</span>
          <span className="font-mono flex items-center gap-1.5" style={{ color: meta.tone }}>
            <Icon type={cf.counterfactual_guard ? "shield" : "sword"} size={13} />
            {cf.counterfactual_guard ? "受け" : "攻撃"}
          </span>
        </div>
        <div className="flex flex-col items-center gap-1">
          <span className="label">反実仮想の結果</span>
          <span className="font-mono">
            自HP {cf.counterfactual_result.player_hp} / 敵HP {cf.counterfactual_result.enemy_hp}
          </span>
        </div>
      </div>
    </div>
  );
}
