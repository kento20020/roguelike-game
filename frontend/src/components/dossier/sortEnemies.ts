import type { DossierBehavior, DossierEnemy, EnemyCatalogItem } from "../../api/types";

export type SortMode = "encounters" | "name";

export interface MergedEnemy {
  enemyId: string;
  name: string;
  experience?: string;
  nTotal: number;
  behaviors: DossierBehavior[];
}

// DossierPage の並び替え/未遭遇分離ロジック（表示順を決めるだけで、値そのものはバックエンド供給のまま）。
export function splitAndSort(
  dossier: DossierEnemy[] | null,
  enemyCatalog: Record<string, EnemyCatalogItem>,
  sortMode: SortMode,
): { encountered: MergedEnemy[]; unencountered: MergedEnemy[] } {
  const byId = new Map((dossier ?? []).map((d) => [d.enemy_id, d]));
  const ids = new Set<string>([...byId.keys(), ...Object.keys(enemyCatalog)]);

  const merged: MergedEnemy[] = Array.from(ids).map((enemyId) => {
    const d = byId.get(enemyId);
    const cat = enemyCatalog[enemyId];
    return {
      enemyId,
      name: cat?.name ?? enemyId,
      experience: cat?.experience,
      nTotal: d?.n_total ?? 0,
      behaviors: d?.behaviors ?? [],
    };
  });

  const byName = (a: MergedEnemy, b: MergedEnemy) => a.name.localeCompare(b.name, "ja");

  const encountered = merged.filter((e) => e.nTotal > 0);
  const unencountered = merged.filter((e) => e.nTotal === 0);

  encountered.sort(sortMode === "encounters" ? (a, b) => b.nTotal - a.nTotal || byName(a, b) : byName);
  unencountered.sort(byName);

  return { encountered, unencountered };
}
