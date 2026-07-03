// Zustand: ゲーム状態（バックエンドの完全状態をそのまま保持）。
// React は計算しない（CLAUDE.md）。各操作は gameApi を呼び、返ってきた状態で置換するだけ。
import { create } from "zustand";
import { gameApi, ApiError } from "../api/gameApi";
import type { GameState, ModCatalogItem, SideBet, SinkType, UpgradeState } from "../api/types";

interface GameStore {
  state: GameState | null;
  busy: boolean;
  error: string | null;
  catalog: Record<string, ModCatalogItem>; // 技(mod) id → 表示情報（一度だけ取得）
  loadCatalog: () => Promise<void>;

  upgrade: UpgradeState | null;            // 恒久強化の現在状態（ClearedPage で割り振り）
  loadUpgradeState: () => Promise<void>;
  allocateUpgrade: (upgradeType: string) => Promise<void>;

  newRun: (seed?: number) => Promise<void>;
  selectNode: (nodeId: string) => Promise<void>;
  attack: (sideBet?: SideBet) => Promise<void>;
  guard: (sideBet?: SideBet) => Promise<void>;
  sink: (sinkType: SinkType) => Promise<void>;
  treasureOpen: () => Promise<void>;
  treasureReroll: () => Promise<void>;
  gateResolve: () => Promise<void>;
  continueRun: () => Promise<void>;
  clearError: () => void;
  reset: () => void;
}

export const useGameStore = create<GameStore>((set, get) => {
  // 任意の API 呼び出しを busy/error 管理つきで実行し、状態を置換する共通ラッパ。
  async function run(fn: (sid: string) => Promise<GameState>) {
    const cur = get().state;
    if (!cur) return;
    set({ busy: true, error: null });
    try {
      const next = await fn(cur.session_id);
      set({ state: next, busy: false });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : (e as Error).message;
      set({ busy: false, error: msg });
    }
  }

  return {
    state: null,
    busy: false,
    error: null,
    catalog: {},
    upgrade: null,

    loadCatalog: async () => {
      if (Object.keys(get().catalog).length > 0) return;
      try {
        const items = await gameApi.modsCatalog();
        const map: Record<string, ModCatalogItem> = {};
        for (const it of items) map[it.id] = it;
        set({ catalog: map });
      } catch {
        /* カタログ取得失敗は致命ではない（効果文が出ないだけ） */
      }
    },

    newRun: async (seed) => {
      set({ busy: true, error: null });
      try {
        const next = await gameApi.newRun(seed);
        set({ state: next, busy: false });
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : (e as Error).message;
        set({ busy: false, error: msg });
      }
    },

    loadUpgradeState: async () => {
      try {
        set({ upgrade: await gameApi.upgradeState() });
      } catch {
        /* 取得失敗は致命ではない（割り振りUIが出ないだけ） */
      }
    },

    allocateUpgrade: async (upgradeType) => {
      const cur = get().state;
      if (!cur) return;
      set({ busy: true, error: null });
      try {
        const up = await gameApi.upgrade(cur.session_id, upgradeType);
        set({ upgrade: up, busy: false });
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : (e as Error).message;
        set({ busy: false, error: msg });
      }
    },

    selectNode: (nodeId) => run((sid) => gameApi.selectNode(sid, nodeId)),
    attack: (sideBet) => run((sid) => gameApi.attack(sid, sideBet)),
    guard: (sideBet) => run((sid) => gameApi.guard(sid, sideBet)),
    sink: (sinkType) => run((sid) => gameApi.sink(sid, sinkType)),
    treasureOpen: () => run((sid) => gameApi.treasureOpen(sid)),
    treasureReroll: () => run((sid) => gameApi.treasureReroll(sid)),
    gateResolve: () => run((sid) => gameApi.gateResolve(sid)),
    continueRun: () => run((sid) => gameApi.continueRun(sid)),

    clearError: () => set({ error: null }),
    reset: () => set({ state: null, error: null, busy: false, upgrade: null }),
  };
});
