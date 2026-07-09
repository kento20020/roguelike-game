import type { Player } from "../../api/types";
import type { CombatFx } from "../../hooks/useCombatFx";
import Icon from "../common/Icon";
import HpBar from "../common/HpBar";

// 自分パネル: HPバー・攻撃力・被弾演出(シェイク/強打・受けのフラッシュ)。CombatPanel から抽出。
export default function PlayerStatusBar({ player, fx }: { player: Player; fx: CombatFx }) {
  return (
    <div
      className={fx.playerShaking ? "fx-shake" : undefined}
      style={{ marginTop: 22, width: "100%", maxWidth: 560, display: "flex", alignItems: "center", gap: 16, padding: "12px 18px", borderRadius: 8, border: "1px solid var(--rule2)", background: "var(--paper2)", position: "relative", overflow: "hidden" }}
    >
      {fx.playerCritFlash && <span className="fx-crit-flash" />}
      {fx.playerGuardFlash && <span className="fx-guard-flash" />}
      <span className="label" style={{ whiteSpace: "nowrap" }}>You · あなた</span>
      <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 10, position: "relative" }}>
        <span style={{ fontSize: 10, color: "var(--ink2)" }}>HP</span>
        <HpBar current={player.hp} max={player.max_hp} width="100%" />
        <span style={{ fontFamily: "var(--mono)", fontSize: 13, whiteSpace: "nowrap" }}>
          {player.hp}
          <span style={{ color: "var(--ink3)" }}> / {player.max_hp}</span>
        </span>
        {fx.playerDamage && (
          <span key={fx.playerDamage.id} className="fx-dmg-pop">
            −{fx.playerDamage.amount}
          </span>
        )}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, paddingLeft: 16, borderLeft: "1px solid var(--rule)", color: "var(--accent)" }}>
        <Icon type="sword" size={16} />
        <span className="label">攻撃力</span>
        <span style={{ fontFamily: "var(--mono)", fontSize: 16, fontWeight: 600 }}>{player.attack}</span>
      </div>
    </div>
  );
}
