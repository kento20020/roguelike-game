"""面白さの操作的代理指標（GDD §18 補完／元の関心『統計で面白さを測る』の中核）。

クリア率(合否)だけでは捉えられない「面白さ」を RunRecord から定量化する。
すべて RunRecord snapshot の list（phase12_harness.run_cohort の records）だけで算出でき、
追加トレース不要（per-battle の緊張感等は将来 trace.py 導入時に精度が上がる）。

指標は「測るだけ」。合否判定や JSON 改変はしない（Goodhart回避・CLAUDE.md）。
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from statistics import mean, pstdev
from typing import Optional

from app.data.loader import get_data


def _max_hp(rec: dict) -> int:
    """RunRecord から当該ランの最大HPを復元（base_hp + per_level×Lv）。"""
    cfg = get_data().config
    base = cfg["player"]["base_hp"]
    per = cfg["permanent_upgrades"]["items"]["max_hp"]["per_level"]
    lv = (rec.get("permanent_upgrades_state") or {}).get("max_hp", 0)
    return base + per * lv


def close_win_rate(records: Sequence[dict], thresh: float = 0.15) -> Optional[float]:
    """僅差勝率: クリアしたランのうち final_hp ≤ max_hp×thresh の割合。
    低=作業ゲー（楽勝）/ 高=運ゲー（薄氷）。中庸が緊張感のある設計の代理。"""
    cleared = [r for r in records if r.get("cleared")]
    if not cleared:
        return None
    close = sum(1 for r in cleared if r["final_hp"] <= _max_hp(r) * thresh)
    return close / len(cleared)


def clear_turn_stats(records: Sequence[dict]) -> dict:
    """クリアランの所要ターン平均・分散。短すぎ=単調、分散小=選択が結果に効かない。"""
    turns = [r["total_turns"] for r in records if r.get("cleared")]
    if not turns:
        return {"mean": None, "stdev": None, "n": 0}
    return {"mean": mean(turns), "stdev": pstdev(turns) if len(turns) > 1 else 0.0, "n": len(turns)}


def mod_diversity_entropy(records: Sequence[dict]) -> dict:
    """取得modの多様性（シャノンエントロピー）。クリアランのビルドが一本道だと低い。"""
    counts: Counter = Counter()
    for r in records:
        if r.get("cleared"):
            counts.update(r.get("mods_acquired") or [])
    total = sum(counts.values())
    if total == 0:
        return {"entropy_bits": None, "normalized": None, "distribution": {}}
    probs = [c / total for c in counts.values()]
    ent = -sum(p * math.log2(p) for p in probs if p > 0)
    k = len(counts)
    return {
        "entropy_bits": ent,
        "normalized": ent / math.log2(k) if k > 1 else 0.0,   # 0..1（1=完全に均等）
        "distribution": dict(counts),
    }


def mod_marginal_clear_rates(records: Sequence[dict]) -> dict:
    """mod を取得したランのクリア率（mod別）と、その分散（synergy/効き目のばらつき代理）。"""
    seen: Counter = Counter()
    won: Counter = Counter()
    for r in records:
        for m in set(r.get("mods_acquired") or []):
            seen[m] += 1
            if r.get("cleared"):
                won[m] += 1
    rates = {m: won[m] / seen[m] for m in seen if seen[m] > 0}
    var = pstdev(list(rates.values())) ** 2 if len(rates) > 1 else 0.0
    return {"per_mod": rates, "variance": var, "spread": (max(rates.values()) - min(rates.values())) if rates else 0.0}


def gate_guarantee_dependence(records: Sequence[dict]) -> dict:
    """ゲート保証への依存度。自力突破の緊張が sink 頼みに薄まっていないかの代理。"""
    if not records:
        return {"mean_stacks": None, "used_rate": None}
    stacks = [r.get("gate_guarantee_stacks", 0) for r in records]
    used = sum(1 for s in stacks if s > 0)
    return {"mean_stacks": mean(stacks), "used_rate": used / len(records)}


def race_avg_turns(records: Sequence[dict], experience: str = "race") -> dict:
    """レース系（蓄積）敵を倒すのにかかった平均ターン。短い=圧勝（緊張なし）、適度=ヒリつき。"""
    turns = []
    for r in records:
        for e in r.get("enemies_defeated") or []:
            if e.get("experience") == experience:
                turns.append(e.get("turns", 0))
    return {"avg_turns": mean(turns) if turns else None, "n": len(turns)}


def compute(records: Sequence[dict]) -> dict:
    """全 fun-metrics をまとめて算出（balance_report から呼ぶ）。"""
    return {
        "close_win_rate": close_win_rate(records),
        "clear_turns": clear_turn_stats(records),
        "mod_diversity": mod_diversity_entropy(records),
        "mod_marginal_clear_rates": mod_marginal_clear_rates(records),
        "gate_guarantee_dependence": gate_guarantee_dependence(records),
        "race_avg_turns": race_avg_turns(records),
    }
