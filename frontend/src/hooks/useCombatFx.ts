import { useEffect, useRef, useState } from "react";
import type { Battle, Player } from "../api/types";
import { playGuard, playHeavy, playHit } from "../lib/sfx";

// ─────────────────────────────────────────────────────────────────
// 演出原則（カンニング防止）:
// このフックは「直前レンダーの GameState」と「今回の GameState」の差分
// ―― battle.enemy.hp / player.hp / battle.log の伸び / battle.last_turn ――
// だけを見て演出（シェイク・ダメージポップ・SE）を決める。
// これらはすべてバックエンドが確定させ、既に画面に表示している「実現結果」。
// 確率・重み・敵の内部AI状態など非表示のデータには一切アクセスしない。
// 受け/強打の判別は last_turn（構造化された公開結果）を使い、ログの日本語文言には依存しない。
// ─────────────────────────────────────────────────────────────────

const SHAKE_MS = 320; // index.css の hitShake アニメーション長と合わせる
const CRIT_MS = 280; // index.css の critFlash アニメーション長と合わせる
const GUARD_FLASH_MS = 300; // index.css の guardFlash アニメーション長と合わせる

export interface DamagePopup {
  id: number; // 表示のたびに変わる値。React key に使い、毎回フェード演出をやり直させる。
  amount: number;
}

export interface CombatFx {
  enemyShaking: boolean;
  playerShaking: boolean;
  enemyDamage: DamagePopup | null;
  playerDamage: DamagePopup | null;
  playerCritFlash: boolean; // 強打（heavy_blow）だけの一瞬のフラッシュ（GDD §15.1）
  playerGuardFlash: boolean; // 受け（ガード）で軽減できた被弾の落ち着いたフラッシュ
}

interface Snapshot {
  enemyHp: number;
  playerHp: number;
  logLen: number;
}

export function useCombatFx(battle: Battle | null, player: Player | null): CombatFx {
  const prevRef = useRef<Snapshot | null>(null);
  const idRef = useRef(0);
  const timersRef = useRef<{ enemy?: number; player?: number; crit?: number; guard?: number }>({});

  const [enemyShaking, setEnemyShaking] = useState(false);
  const [playerShaking, setPlayerShaking] = useState(false);
  const [enemyDamage, setEnemyDamage] = useState<DamagePopup | null>(null);
  const [playerDamage, setPlayerDamage] = useState<DamagePopup | null>(null);
  const [playerCritFlash, setPlayerCritFlash] = useState(false);
  const [playerGuardFlash, setPlayerGuardFlash] = useState(false);

  // アンマウント時にタイマーの後始末をする。
  useEffect(() => {
    return () => {
      const t = timersRef.current;
      if (t.enemy) window.clearTimeout(t.enemy);
      if (t.player) window.clearTimeout(t.player);
      if (t.crit) window.clearTimeout(t.crit);
      if (t.guard) window.clearTimeout(t.guard);
    };
  }, []);

  useEffect(() => {
    if (!battle || !player) {
      prevRef.current = null;
      return;
    }

    const prev = prevRef.current;
    const snapshot: Snapshot = { enemyHp: battle.enemy.hp, playerHp: player.hp, logLen: battle.log.length };

    if (prev) {
      const enemyDelta = prev.enemyHp - snapshot.enemyHp; // 実際に減った量（公開情報）
      const playerDelta = prev.playerHp - snapshot.playerHp;
      const newEntries = battle.log.slice(prev.logLen);
      const lastKind = newEntries.length > 0 ? newEntries[newEntries.length - 1].k : null;
      // last_turn は戦闘中保持されるため、実際にターンが進んだ（=ログが伸びた）ときだけ参照する。
      const lastTurn = newEntries.length > 0 ? (battle.last_turn ?? null) : null;
      const guardTurn = lastTurn?.guard === true;

      // SE: 受けたターンは常に playGuard（低音）。それ以外はログ末尾の kind で分岐する。
      if (guardTurn) playGuard();
      else if (lastKind === "hit") playHit();
      else if (lastKind === "hurt") playHeavy();
      else if (lastKind === "mod") playGuard();
      // "calm"（何も起きなかった）は無音のまま。

      if (enemyDelta > 0) {
        idRef.current += 1;
        setEnemyDamage({ id: idRef.current, amount: enemyDelta });
        setEnemyShaking(true);
        window.clearTimeout(timersRef.current.enemy);
        timersRef.current.enemy = window.setTimeout(() => setEnemyShaking(false), SHAKE_MS);
      }

      if (playerDelta > 0) {
        idRef.current += 1;
        setPlayerDamage({ id: idRef.current, amount: playerDelta });
        setPlayerShaking(true);
        window.clearTimeout(timersRef.current.player);
        timersRef.current.player = window.setTimeout(() => setPlayerShaking(false), SHAKE_MS);

        if (guardTurn) {
          // 受けで軽減できた被弾＝落ち着いた色の短いフラッシュ（強打の赤フラッシュとは紛れさせない）。
          setPlayerGuardFlash(true);
          window.clearTimeout(timersRef.current.guard);
          timersRef.current.guard = window.setTimeout(() => setPlayerGuardFlash(false), GUARD_FLASH_MS);
        } else if (lastTurn?.action === "heavy_blow") {
          // GDD §15.1: 強打だけは基本演出（揺れ+ポップ）に加えて強い赤の光を重ねる。
          setPlayerCritFlash(true);
          window.clearTimeout(timersRef.current.crit);
          timersRef.current.crit = window.setTimeout(() => setPlayerCritFlash(false), CRIT_MS);
        }
      }
    }

    prevRef.current = snapshot;
  }, [battle, player]);

  return {
    enemyShaking,
    playerShaking,
    enemyDamage,
    playerDamage,
    playerCritFlash,
    playerGuardFlash,
  };
}
