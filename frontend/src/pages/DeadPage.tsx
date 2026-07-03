import { useEffect, useState } from "react";
import type { GameState, PostmortemResponse, TurnHistoryEntry } from "../api/types";
import { useGameStore } from "../store/gameStore";
import { gameApi, ApiError } from "../api/gameApi";
import CenterStage from "../components/common/CenterStage";
import ResultSummary from "../components/result/ResultSummary";
import { floorName, behaviorMeta } from "../lib/labels";

type Tab = "result" | "postmortem" | "replay";

const CATEGORY_TONE: Record<string, string> = {
  unavoidable: "var(--danger)",
  avoidable_guard: "var(--moss)",
  avoidable_attack: "var(--moss)",
  mutual_kill_victory: "var(--brass)",
};

// 小さなHPバー（チャートライブラリ不使用・div幅のみ）。
function HpBar({ before, after, max, color }: { before: number; after: number; max: number; color: string }) {
  const m = Math.max(max, 1);
  const pctBefore = Math.max(0, Math.min(100, (before / m) * 100));
  const pctAfter = Math.max(0, Math.min(100, (after / m) * 100));
  return (
    <div style={{ position: "relative", width: 90, height: 8, borderRadius: 4, background: "var(--rule)" }}>
      <div style={{ position: "absolute", inset: 0, width: `${pctBefore}%`, borderRadius: 4, background: "var(--rule2)" }} />
      <div style={{ position: "absolute", inset: 0, width: `${pctAfter}%`, borderRadius: 4, background: color }} />
    </div>
  );
}

function TurnRow({ entry, index }: { entry: TurnHistoryEntry; index: number }) {
  const meta = behaviorMeta(entry.action);
  return (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 10, padding: "8px 4px",
        borderBottom: "1px solid var(--rule)", fontSize: 12,
      }}
    >
      <span className="font-mono" style={{ width: 28, color: "var(--ink3)" }}>#{index + 1}</span>
      <span className="font-sans" style={{ width: 56, color: entry.guard ? "var(--moss)" : "var(--ink)" }}>
        {entry.guard ? "受け" : "攻撃"}
      </span>
      <span className="font-sans" style={{ width: 72, color: meta?.color ?? "var(--ink2)" }}>
        {meta?.jp ?? entry.action}
      </span>
      <span className="font-mono" style={{ width: 130, textAlign: "left", color: "var(--ink2)" }}>
        与{entry.dealt} / 被{entry.incoming}
      </span>
      <span className="flex items-center gap-2">
        <span className="font-mono" style={{ fontSize: 10, color: "var(--ink3)", width: 64 }}>
          自 {entry.player_hp_before}→{entry.player_hp_after}
        </span>
        <HpBar
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
        <HpBar
          before={entry.enemy_hp_before}
          after={entry.enemy_hp_after}
          max={entry.pre_turn_snapshot?.enemy?.max_hp ?? entry.enemy_hp_before}
          color="var(--danger)"
        />
      </span>
    </div>
  );
}

function PostmortemPanel({ pm, loading, error }: { pm: PostmortemResponse | null; loading: boolean; error: string | null }) {
  if (loading) {
    return <p className="font-sans" style={{ fontSize: 13, color: "var(--ink3)" }}>検死中…</p>;
  }
  if (error) {
    return <p className="font-sans" style={{ fontSize: 13, color: "var(--ink3)" }}>{error}</p>;
  }
  if (!pm) return null;
  const cf = pm.counterfactual;
  const tone = CATEGORY_TONE[cf.category] ?? "var(--ink2)";
  return (
    <div className="flex w-full flex-col items-center gap-4">
      <span className="label" style={{ color: tone }}>
        致命の一手（{cf.original_guard ? "受け" : "攻撃"}を選んだターン）
      </span>
      <p className="font-serif" style={{ fontSize: 22, color: tone }}>{cf.message}</p>
      <div className="flex flex-wrap items-start justify-center gap-x-8 gap-y-3" style={{ fontSize: 12 }}>
        <div className="flex flex-col items-center gap-1">
          <span className="label">実際の選択</span>
          <span className="font-mono">{cf.original_guard ? "受け" : "攻撃"}</span>
        </div>
        <div className="flex flex-col items-center gap-1">
          <span className="label">もし逆を選んでいたら</span>
          <span className="font-mono">{cf.counterfactual_guard ? "受け" : "攻撃"}</span>
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

function ReplayPanel({ pm, loading, error }: { pm: PostmortemResponse | null; loading: boolean; error: string | null }) {
  if (loading) {
    return <p className="font-sans" style={{ fontSize: 13, color: "var(--ink3)" }}>読み込み中…</p>;
  }
  if (error) {
    return <p className="font-sans" style={{ fontSize: 13, color: "var(--ink3)" }}>{error}</p>;
  }
  if (!pm || pm.turn_history.length === 0) {
    return <p className="font-sans" style={{ fontSize: 13, color: "var(--ink3)" }}>リプレイできるターンがない。</p>;
  }
  return (
    <div className="flex w-full flex-col" style={{ maxHeight: 340, overflowY: "auto", textAlign: "left" }}>
      {pm.turn_history.map((entry, i) => (
        <TurnRow key={i} entry={entry} index={i} />
      ))}
    </div>
  );
}

// 敗北（dead）。パーマデス。コア表示＝到達/総ターン/取得mod（GDD §15.1）。
// death_cause は機械語。日本語化辞書が無いので任意の補足表示に留める。
// [結果]/[検死レポート]/[リプレイ] の3タブ。検死・リプレイは戦闘死のみ利用可（関門死は対象外・404）。
export default function DeadPage({ state }: { state: GameState }) {
  const newRun = useGameStore((s) => s.newRun);
  const reset = useGameStore((s) => s.reset);
  const busy = useGameStore((s) => s.busy);
  const rec = state.run_record;

  const [tab, setTab] = useState<Tab>("result");
  const [pm, setPm] = useState<PostmortemResponse | null>(null);
  const [pmLoading, setPmLoading] = useState(true);
  const [pmError, setPmError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setPmLoading(true);
    setPmError(null);
    gameApi
      .postmortem(state.session_id)
      .then((res) => {
        if (!cancelled) setPm(res);
      })
      .catch((e) => {
        if (cancelled) return;
        const msg = e instanceof ApiError && e.status === 404
          ? "この死には検死データがない（関門などでの死亡）。"
          : "検死データの取得に失敗した。";
        setPmError(msg);
      })
      .finally(() => {
        if (!cancelled) setPmLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [state.session_id]);

  const TABS: { key: Tab; label: string }[] = [
    { key: "result", label: "結果" },
    { key: "postmortem", label: "検死レポート" },
    { key: "replay", label: "リプレイ" },
  ];

  return (
    <CenterStage tone="lose" maxWidth={620}>
      <span className="label" style={{ color: "var(--danger)" }}>
        一勝負は遠かった
      </span>
      <h1 className="font-serif" style={{ fontSize: 48, color: "var(--danger)" }}>
        敗北
      </h1>
      {rec?.death_floor != null && (
        <p className="font-sans" style={{ fontSize: 14, color: "var(--ink)" }}>
          {floorName(rec.death_floor)} で倒れた
          {rec.death_cause ? `（${rec.death_cause}）` : ""}
        </p>
      )}

      <div className="flex items-center gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={tab === t.key ? "btn" : "btn btn-ghost"}
            style={{ minWidth: 100, fontSize: 12 }}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "result" && rec && <ResultSummary record={rec} />}
      {tab === "postmortem" && <PostmortemPanel pm={pm} loading={pmLoading} error={pmError} />}
      {tab === "replay" && <ReplayPanel pm={pm} loading={pmLoading} error={pmError} />}

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
