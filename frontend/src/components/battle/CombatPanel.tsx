import type { Battle, Player, SideBet } from "../../api/types";
import { experienceMeta } from "../../lib/labels";
import CombatLog from "./CombatLog";
import BehaviorGlossary from "../common/BehaviorGlossary";
import EnemyStage from "./EnemyStage";
import NextActionPreview from "./NextActionPreview";
import PlayerStatusBar from "./PlayerStatusBar";
import SideBetPanel from "./SideBetPanel";
import { useCombatFx } from "../../hooks/useCombatFx";
import { useSideBet } from "../../hooks/useSideBet";

// 戦闘ステージ全体（design 忠実）：敵名・体験タイプ・敵HP・ramp・先読み・ログ・自分パネル・攻撃。
export default function CombatPanel({
  battle,
  player,
  busy,
  canAttack,
  canGuard,
  onAttack,
  onGuard,
}: {
  battle: Battle;
  player: Player;
  busy: boolean;
  canAttack: boolean;
  canGuard: boolean;
  onAttack: (sideBet?: SideBet) => void;
  onGuard: (sideBet?: SideBet) => void;
}) {
  const exp = experienceMeta(battle.enemy.experience);
  // 演出は GameState の差分（実現結果）だけから駆動する（確率・非表示weightは見ない）。
  const fx = useCombatFx(battle, player);

  // サイドベット『読み宣言』の状態・派生値は useSideBet に集約（UIは SideBetPanel が持つ）。
  const sb = useSideBet(battle, player);

  function submitAttack() {
    onAttack(sb.sideBet);
    sb.resetBet();
  }
  function submitGuard() {
    onGuard(sb.sideBet);
    sb.resetBet();
  }

  return (
    <section
      className="flex flex-col items-center"
      style={{ maxWidth: 780, margin: "0 auto", animation: "fadeUp .32s var(--ease)" }}
    >
      <EnemyStage battle={battle} exp={exp} fx={fx} />
      <NextActionPreview battle={battle} />

      <div style={{ width: "100%", maxWidth: 560, marginTop: 22 }}>
        <CombatLog log={battle.log} />
      </div>
      <div style={{ width: "100%", maxWidth: 560, marginTop: 12 }}>
        <BehaviorGlossary />
      </div>

      <PlayerStatusBar player={player} fx={fx} />

      <SideBetPanel battle={battle} player={player} busy={busy} sb={sb} />

      <div className="flex items-center gap-3" style={{ marginTop: 18 }}>
        <button onClick={submitAttack} disabled={!canAttack || busy} className="btn" style={{ minWidth: 200, height: 50 }}>
          攻撃する — {player.attack}
          {player.attack_boost_pending ? "（強化）" : ""}
        </button>
        <button onClick={submitGuard} disabled={!canGuard || busy} className="btn btn-ghost" style={{ minWidth: 130, height: 50 }}>
          受ける
        </button>
      </div>
      <div style={{ marginTop: 9, fontSize: 11, color: "var(--ink3)" }}>
        攻撃＝確率で相手が反応／受け＝与ダメ半減・被ダメを大きく軽減（先読みで危険を受け流す）
      </div>
    </section>
  );
}
