import { useEffect, useState } from "react";
import type { GameState, PostmortemResponse, TurnHistoryEntry } from "../api/types";
import { useGameStore } from "../store/gameStore";
import { gameApi, ApiError } from "../api/gameApi";
import CenterStage from "../components/common/CenterStage";
import ResultSummary from "../components/result/ResultSummary";
import Icon from "../components/common/Icon";
import { floorName, behaviorMeta, deathCauseLabel } from "../lib/labels";

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

// 穏やかな空状態（検死データ取得に失敗した場合のみ使用。読み込み中は無演出で待つ）。
function EmptyState({ icon, text }: { icon: string; text: string }) {
  return (
    <div
      className="flex flex-col items-center gap-3"
      style={{
        padding: "34px 30px",
        borderRadius: 14,
        border: "1px dashed var(--rule2)",
        background: "var(--paper2)",
        maxWidth: 380,
        animation: "fadeUp .35s var(--ease) both",
      }}
    >
      <Icon type={icon} size={26} style={{ color: "var(--ink3)" }} />
      <p className="font-sans" style={{ fontSize: 13, lineHeight: 1.6, color: "var(--ink3)" }}>
        {text}
      </p>
    </div>
  );
}

// リプレイ用HPバー。マウント時に before→after へ縮む(=被弾)動きを付ける(控えめ・1回のみ)。
function ReplayHpBar({ before, after, max, color }: { before: number; after: number; max: number; color: string }) {
  const m = Math.max(max, 1);
  const targetBefore = Math.max(0, Math.min(100, (before / m) * 100));
  const targetAfter = Math.max(0, Math.min(100, (after / m) * 100));
  const [w, setW] = useState({ before: targetBefore, after: targetBefore });

  useEffect(() => {
    const id = requestAnimationFrame(() => setW({ before: targetBefore, after: targetAfter }));
    return () => cancelAnimationFrame(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetBefore, targetAfter]);

  return (
    <div style={{ position: "relative", width: 90, height: 8, borderRadius: 4, background: "var(--rule)", overflow: "hidden" }}>
      <div
        style={{
          position: "absolute", inset: 0, width: `${w.before}%`, borderRadius: 4,
          background: "var(--rule2)", transition: "width .5s var(--ease)",
        }}
      />
      <div
        style={{
          position: "absolute", inset: 0, width: `${w.after}%`, borderRadius: 4,
          background: color, transition: "width .5s var(--ease) .1s",
        }}
      />
    </div>
  );
}

function TurnRow({ entry, index, isFatal }: { entry: TurnHistoryEntry; index: number; isFatal: boolean }) {
  const meta = behaviorMeta(entry.action);
  const fatalTone = "var(--danger)";
  return (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 10, padding: isFatal ? "9px 10px" : "8px 10px",
        marginBottom: isFatal ? 4 : 0,
        borderBottom: isFatal ? "none" : "1px solid var(--rule)",
        borderRadius: isFatal ? 8 : 0,
        border: isFatal ? `1px solid ${fatalTone}` : undefined,
        background: isFatal ? "var(--dangerSoft)" : "transparent",
        animation: isFatal ? "fatalPulse 2.6s ease-in-out infinite" : undefined,
        fontSize: 12,
      }}
    >
      <span className="font-mono" style={{ width: 28, color: isFatal ? fatalTone : "var(--ink3)" }}>
        #{index + 1}
      </span>
      {isFatal && (
        <span
          className="label"
          style={{ color: fatalTone, border: `1px solid ${fatalTone}`, borderRadius: 999, padding: "1px 7px", whiteSpace: "nowrap" }}
        >
          致命の一手
        </span>
      )}
      <span
        className="flex items-center gap-1 font-sans"
        style={{ width: 56, color: entry.guard ? "var(--moss)" : "var(--ink)" }}
      >
        <Icon type={entry.guard ? "shield" : "sword"} size={13} />
        {entry.guard ? "受け" : "攻撃"}
      </span>
      <span className="flex items-center gap-1 font-sans" style={{ width: 84, color: meta?.color ?? "var(--ink2)" }}>
        <Icon type={meta?.iconType ?? "check"} size={13} />
        {meta?.jp ?? entry.action}
      </span>
      <span className="font-mono" style={{ width: 130, textAlign: "left", color: "var(--ink2)" }}>
        与{entry.dealt} / 被{entry.incoming}
      </span>
      <span className="flex items-center gap-2">
        <span className="font-mono" style={{ fontSize: 10, color: "var(--ink3)", width: 64 }}>
          自 {entry.player_hp_before}→{entry.player_hp_after}
        </span>
        <ReplayHpBar
          before={entry.player_hp_before}
          after={entry.player_hp_after}
          max={entry.pre_turn_snapshot?.player?.max_hp ?? entry.player_hp_before}
          color="var(--moss)"
        />
      </span>
      <span className="flex items-center gap-2">
        <span className="font-mono" style={{ fontSize: 10, color: "var(--ink3)", width: 64 }}>
          敵 {entry.enemy_hp_before}→{entry.enemy_hp_after}
        </span>
        <ReplayHpBar
          before={entry.enemy_hp_before}
          after={entry.enemy_hp_after}
          max={entry.pre_turn_snapshot?.enemy?.max_hp ?? entry.enemy_hp_before}
          color="var(--danger)"
        />
      </span>
    </div>
  );
}

// 検死レポート＝この画面で最も重い視覚的ウェイトを持つ常時表示カード（タブの奥に隠さない）。
// 決算カードにわずかに遅れてフェードインし、「決算の次に主役」であることを示す。
function PostmortemCard({ pm }: { pm: PostmortemResponse }) {
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

// リプレイ＝任意の深掘り。デフォルト折りたたみ、致命ターンだけは閉じた状態でもプレビューで見える。
// 「戦闘の再演」ではなく「記録の閲覧」なので開閉アニメーションは高さのfadeUp程度に留める。
function ReplayDisclosure({ pm }: { pm: PostmortemResponse }) {
  const [open, setOpen] = useState(false);
  if (pm.turn_history.length === 0) return null;
  const fatalEntry = pm.turn_history[pm.fatal_turn_index];

  return (
    <div
      className="flex w-full flex-col"
      style={{
        borderRadius: 12,
        border: "1px solid var(--rule2)",
        background: "var(--paper2)",
        overflow: "hidden",
        animation: "fadeUp .4s var(--ease) .2s both",
      }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-2 font-sans"
        style={{
          width: "100%",
          padding: "12px 16px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "var(--ink2)",
          fontSize: 12.5,
        }}
      >
        <Icon
          type="arrow"
          size={13}
          style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)", transition: "transform .2s var(--ease)", flex: "none" }}
        />
        <span>ターンごとの記録を見る（全{pm.turn_history.length}手）</span>
      </button>
      {!open && fatalEntry && (
        <div
          role="button"
          tabIndex={0}
          onClick={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") setOpen(true);
          }}
          title="クリックで全ターンを展開"
          style={{ padding: "0 12px 12px", textAlign: "left", cursor: "pointer" }}
        >
          <TurnRow entry={fatalEntry} index={pm.fatal_turn_index} isFatal />
        </div>
      )}
      {open && (
        <div style={{ maxHeight: 360, overflowY: "auto", textAlign: "left", padding: "0 12px 12px" }}>
          {pm.turn_history.map((entry, i) => (
            <TurnRow key={i} entry={entry} index={i} isFatal={i === pm.fatal_turn_index} />
          ))}
        </div>
      )}
    </div>
  );
}

const GENERIC_FAIL_MESSAGE = "検死データの取得に失敗した。";

// 敗北（dead）。パーマデス。コア表示＝到達/総ターン/取得mod（GDD §15.1）。
// death_cause は機械語。日本語化辞書が無いので任意の補足表示に留める。
// 決算(常時)→検死レポート(常時・最重要)→リプレイ(折りたたみ・任意)の順に縦積み。
// 粒度の異なる3体験を並列タブで同格に扱わない（design/spec_postmortem_replay.md）。
// 検死・リプレイは戦闘死のみ利用可(関門死はpostmortemが404＝pmUnavailable)。
export default function DeadPage({ state }: { state: GameState }) {
  const newRun = useGameStore((s) => s.newRun);
  const reset = useGameStore((s) => s.reset);
  const busy = useGameStore((s) => s.busy);
  const rec = state.run_record;

  const [pm, setPm] = useState<PostmortemResponse | null>(null);
  const [pmLoading, setPmLoading] = useState(true);
  const [pmUnavailable, setPmUnavailable] = useState(false);
  const [pmError, setPmError] = useState<string | null>(null);
  // death_cause の敵id→敵名変換用（GDD §15.1: 死亡原因は日本語で必須表示）。取得失敗時はid素通し。
  const [enemyNames, setEnemyNames] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    gameApi
      .enemiesCatalog()
      .then((list) => {
        if (!cancelled) setEnemyNames(Object.fromEntries(list.map((e) => [e.id, e.name])));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setPmLoading(true);
    setPmUnavailable(false);
    setPmError(null);
    gameApi
      .postmortem(state.session_id)
      .then((res) => {
        if (!cancelled) setPm(res);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) setPmUnavailable(true);
        else setPmError(GENERIC_FAIL_MESSAGE);
      })
      .finally(() => {
        if (!cancelled) setPmLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [state.session_id]);

  return (
    <CenterStage tone="lose" maxWidth={660}>
      <span className="label" style={{ color: "var(--danger)" }}>
        一勝負は遠かった
      </span>
      <h1 className="font-serif" style={{ fontSize: 48, color: "var(--danger)" }}>
        敗北
      </h1>
      {rec?.death_floor != null && (
        <p className="font-sans" style={{ fontSize: 14, color: "var(--ink)" }}>
          {rec.death_cause
            ? `${floorName(rec.death_floor)} で ${deathCauseLabel(rec.death_cause, enemyNames)} に倒れた`
            : `${floorName(rec.death_floor)} で倒れた`}
        </p>
      )}
      {!pmLoading && pmUnavailable && (
        <p className="font-sans" style={{ fontSize: 11.5, color: "var(--ink3)" }}>
          この死因には検死レポートがない（関門での敗北のため）。
        </p>
      )}

      {rec && <ResultSummary record={rec} />}

      {!pmLoading && pmError && <EmptyState icon="gate" text={pmError} />}
      {!pmLoading && pm && (
        <>
          <PostmortemCard pm={pm} />
          <ReplayDisclosure pm={pm} />
        </>
      )}

      <div className="flex items-center gap-3">
        <button className="btn" style={{ minWidth: 160 }} disabled={busy} onClick={() => newRun()}>
          もう一度
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={reset}>
          タイトルへ
        </button>
      </div>
    </CenterStage>
  );
}
