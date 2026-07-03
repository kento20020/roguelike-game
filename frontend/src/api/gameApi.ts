// API 通信の集約点（CLAUDE.md: コンポーネントから直接 fetch しない）。
// 将来 TanStack Query へ移行する際はこのファイルだけを差し替える。
import type {
  DossierEnemy,
  EnemyCatalogItem,
  GameState,
  ModCatalogItem,
  PostmortemResponse,
  SideBet,
  SinkType,
  UpgradeState,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, method: "GET" | "POST", body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(0, `ネットワークエラー: ${(e as Error).message}`);
  }
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail ?? detail;
    } catch {
      /* body 無し */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return (await res.json()) as T;
}

export const gameApi = {
  newRun: (seed?: number) =>
    request<GameState>("/run/new", "POST", seed !== undefined ? { seed } : {}),
  getRun: (sid: string) => request<GameState>(`/run/${sid}`, "GET"),
  selectNode: (sid: string, nodeId: string) =>
    request<GameState>(`/run/${sid}/select-node`, "POST", { node_id: nodeId }),
  attack: (sid: string, sideBet?: SideBet) =>
    request<GameState>(`/run/${sid}/attack`, "POST", sideBet ? { side_bet: sideBet } : {}),
  guard: (sid: string, sideBet?: SideBet) =>
    request<GameState>(`/run/${sid}/guard`, "POST", sideBet ? { side_bet: sideBet } : {}),
  sink: (sid: string, sinkType: SinkType) =>
    request<GameState>(`/run/${sid}/sink`, "POST", { sink_type: sinkType }),
  treasureOpen: (sid: string) => request<GameState>(`/run/${sid}/treasure/open`, "POST", {}),
  treasureReroll: (sid: string) => request<GameState>(`/run/${sid}/treasure/reroll`, "POST", {}),
  gateResolve: (sid: string) => request<GameState>(`/run/${sid}/gate/resolve`, "POST", {}),
  continueRun: (sid: string) => request<GameState>(`/run/${sid}/continue`, "POST", {}),
  upgradeState: () => request<UpgradeState>("/profile/upgrades", "GET"),
  upgrade: (sid: string, upgradeType: string) =>
    request<UpgradeState>(`/run/${sid}/upgrade`, "POST", { upgrade_type: upgradeType }),
  history: () => request<GameState["run_record"][]>("/stats/history", "GET"),
  modsCatalog: () => request<ModCatalogItem[]>("/catalog/mods", "GET"),
  postmortem: (sid: string) => request<PostmortemResponse>(`/run/${sid}/postmortem`, "GET"),
  enemiesCatalog: () => request<EnemyCatalogItem[]>("/catalog/enemies", "GET"),
  dossier: (dataVersion?: string) =>
    request<DossierEnemy[]>(
      `/profile/dossier${dataVersion ? `?data_version=${encodeURIComponent(dataVersion)}` : ""}`,
      "GET",
    ),
};
