import { useEffect, useRef, useState } from "react";
import type { Battle, LogLine, Player } from "../api/types";
import { playGuard, playHeavy, playHit } from "../lib/sfx";

// ─────────────────────────────────────────────────────────────────
// 演出原則（カンニング防止）:
// このフックは「直前レンダーの GameState」と「今回の GameState」の差分
// ―― battle.enemy.hp / player.hp / battle.log 末尾要素の kind ――
// だけを見て演出（シェイク・ダメージポップ・SE）を決める。
// これらはすべてバックエンドが確定させ、既に画面に表示している「実現結果」。
// 確率・重み・敵の内部AI状態など非表示のデータには一切アクセスしない。
// ログの文言も CombatLog に既に表示済みの公開テキストのみを見る（新規の非公開情報は見ない）。
// ─────────────────────────────────────────────────────────────────

const SHAKE_MS = 320; // index.css の hitShake アニメーション長と合わせる
const CRIT_MS = 280; // index.css の critFlash アニメーション長と合わせる
const GUARD_FLASH_MS = 300; // index.css の guardFlash アニメーション長と合わせる

// 「受け」ターンかどうかは combat_resolver が付与する "受け · " 接頭辞（既に log に表示済み）で判定する。
function isGuardTurn(entries: LogLine[]): boolean {
  return entries.some((e) => e.k === "hit" && e.t.startsWith("受け"));
}

// GDD §15.1: 「被弾」(全ヒット共通=揺れ+ダメージポップ)と「強打を受けた」(それに加え
// 通常より強い赤の光)は別の段の演出。backend は反撃/強打/蓄積の一撃を全て kind="hurt" で
// 一括ログするため、ログ文言の "強打" 接頭辞だけを見て強打の一撃かどうかを判別する
// (反撃・蓄積の一撃は揺れ+ポップに留め、強打フラッシュを出さない＝強打の重さを際立たせる)。
function isHeavyBlowHit(entries: LogLine[]): boolean {
  return entries.some((entry) => entry.k === "hurt" && entry.t.startsWith("強打"));
}

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
      const guardTurn = isGuardTurn(newEntries);

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
        } else if (isHeavyBlowHit(newEntries)) {
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
