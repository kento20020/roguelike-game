import { useEffect } from "react";
import type { GameState } from "../api/types";
import { useGameStore } from "../store/gameStore";
import CenterStage from "../components/common/CenterStage";
import ResultSummary from "../components/result/ResultSummary";
import EmptyState from "../components/dead/EmptyState";
import PostmortemCard from "../components/dead/PostmortemCard";
import ReplayDisclosure from "../components/dead/ReplayDisclosure";
import { floorName, deathCauseLabel } from "../lib/labels";

// 敗北（dead）。パーマデス。コア表示＝到達/総ターン/取得mod（GDD §15.1）。
// death_cause は機械語。日本語化辞書が無いので任意の補足表示に留める。
// 決算(常時)→検死レポート(常時・最重要)→リプレイ(折りたたみ・任意)の順に縦積み。
// 粒度の異なる3体験を並列タブで同格に扱わない（design/spec_postmortem_replay.md）。
// 検死・リプレイは戦闘死のみ利用可(関門死はpostmortemが404＝unavailable)。
// データ取得は gameStore に集約（コンポーネントから gameApi を直接呼ばない）。
export default function DeadPage({ state }: { state: GameState }) {
  const newRun = useGameStore((s) => s.newRun);
  const reset = useGameStore((s) => s.reset);
  const busy = useGameStore((s) => s.busy);
  const rec = state.run_record;

  const pm = useGameStore((s) => s.postmortem);
  const pmLoading = useGameStore((s) => s.postmortemLoading);
  const pmUnavailable = useGameStore((s) => s.postmortemUnavailable);
  const pmError = useGameStore((s) => s.postmortemError);
  const loadPostmortem = useGameStore((s) => s.loadPostmortem);
  // death_cause の敵id→敵名変換用（GDD §15.1: 死亡原因は日本語で必須表示）。取得失敗時はid素通し。
  const enemyCatalog = useGameStore((s) => s.enemyCatalog);
  const loadEnemyCatalog = useGameStore((s) => s.loadEnemyCatalog);
  const enemyNames = Object.fromEntries(
    Object.values(enemyCatalog).map((e) => [e.id, e.name]));

  useEffect(() => {
    loadEnemyCatalog();
  }, [loadEnemyCatalog]);

  useEffect(() => {
    loadPostmortem(state.session_id);
  }, [loadPostmortem, state.session_id]);

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
