"""バランス分析（GDD §18.2 Phase3-4 / §18.3 balance_analysis）。

RunRecord の list を入力に、単一mod寄与・初手別感度・死亡フロア集中・hoarder・sink ROI を算出。
統計判定は balance_stats（e-value/CS・ブートストラップ）に委譲。
すべて「測るだけ」。死にmodは潰す/壊れmodは残す（非対称運用）の判断材料を出すのみで JSON は変えない。
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from statistics import mean

from app.data.loader import get_data
from app.simulation import balance_stats as bs

GOLD_SINKS = ["scout", "heal_small", "heal_large", "attack_boost", "gate_guarantee", "treasure_reroll"]


def mod_marginal_contribution(records: Sequence[dict], delta: float = 0.08,
                              alpha: float = 0.05, seed: int = 0) -> dict:
    """単一mod寄与（§18.1 ±8pt以内・平均寄与のみ）。取得有/無の2群でクリア率差を測る。
    観察的平均寄与（因果でない）。差のブートストラップCI＋同等性(±delta)判定。
    CIが0を含まない＝有意効果、±delta外＝壊れ/死にmod候補（自動FAILにしない＝非対称運用）。"""
    with_clear: dict[str, list[int]] = {}
    without_clear: dict[str, list[int]] = {}
    all_mods: set[str] = set()
    for r in records:
        all_mods.update(r.get("mods_acquired") or [])
    for m in all_mods:
        with_clear[m], without_clear[m] = [], []
    for r in records:
        c = 1 if r.get("cleared") else 0
        owned = set(r.get("mods_acquired") or [])
        for m in all_mods:
            (with_clear[m] if m in owned else without_clear[m]).append(c)
    out = {}
    for m in sorted(all_mods):
        w, wo = with_clear[m], without_clear[m]
        rate_w = mean(w) if w else 0.0
        rate_wo = mean(wo) if wo else 0.0
        ci = bs.diff_bootstrap_ci(w, wo, alpha=alpha, seed=seed) if w and wo else (0.0, 0.0)
        out[m] = {
            "n_with": len(w), "n_without": len(wo),
            "rate_with": rate_w, "rate_without": rate_wo,
            "contribution": rate_w - rate_wo, "ci": ci,
            "significant": (ci[0] > 0 or ci[1] < 0),          # 0を含まない
            "within_pm_delta": bs.equivalence_check(ci, delta),  # ±delta以内（合格条件）
            "broken_or_dead": (ci[0] > delta or ci[1] < -delta),  # ±delta外で確定（要レビュー）
        }
    return out


def first_move_sensitivity(cohort_by_node: dict, delta: float = 0.05, alpha: float = 0.05) -> dict:
    """初手別クリア率差（§18.1 ±5pt以内）＋選択感度（有意な差）。
    cohort_by_node: {node_id: [RunRecord,...]}（同一 seed 順で整列していること＝CRN対標本）。
    ペアごとに McNemar e-process、多重比較は e-BH で FDR 制御。"""
    nodes = list(cohort_by_node)
    rates = {nid: (mean(1 if r.get("cleared") else 0 for r in recs) if recs else 0.0)
             for nid, recs in cohort_by_node.items()}
    spread = (max(rates.values()) - min(rates.values())) if rates else 0.0
    pairs_eval = []
    pair_keys = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            ra, rb = cohort_by_node[a], cohort_by_node[b]
            paired = [(1 if x.get("cleared") else 0, 1 if y.get("cleared") else 0)
                      for x, y in zip(ra, rb)]
            mc = bs.mcnemar_eprocess(paired, alpha=alpha)
            pairs_eval.append(mc["evalue"])
            pair_keys.append({"pair": f"{a}|{b}", **mc})
    sig_idx = set(bs.ebh_fdr(pairs_eval, alpha=alpha)) if pairs_eval else set()
    for k, pk in enumerate(pair_keys):
        pk["fdr_significant"] = k in sig_idx
    return {
        "clear_rates": rates,
        "spread": spread,
        "within_5pt": spread <= delta,                    # §18.1 ±5pt以内（合格条件）
        "sensitive": any(pk["fdr_significant"] for pk in pair_keys),  # §18.1 有意な差
        "pairs": pair_keys,
    }


def death_floor_concentration(records: Sequence[dict], threshold: float = 0.5, alpha: float = 0.05) -> dict:
    """死亡フロア分布が一フロアに集中していないか（§18.1 集中しない）。"""
    counts: Counter[int] = Counter()
    for r in records:
        df = r.get("death_floor")
        if df is not None:
            counts[df] += 1
    res = bs.concentration_evalue(dict(counts), threshold=threshold, alpha=alpha)
    res["counts"] = dict(sorted(counts.items()))
    return res


def _init_chips(rec: dict) -> int:
    cfg = get_data().config
    base = cfg["player"]["base_gold"]
    per = cfg["permanent_upgrades"]["items"]["init_gold"]["per_level"]
    lv = (rec.get("permanent_upgrades_state") or {}).get("init_gold", 0)
    return base + per * lv


def hoarder_detection(records: Sequence[dict], hoard_frac: float = 0.5) -> dict:
    """貯め込み（§18.2 Phase4）。余剰チップ比率が高いまま終わったランの割合。
    sink を使わず死ぬ＝難度設計が機能していない兆候（§13.3 監視項目）。"""
    if not records:
        return {"hoarder_rate": None, "mean_leftover": None, "hoarder_rate_died": None}
    leftovers, ratios, died_hoard = [], [], 0
    n_died = 0
    for r in records:
        earned = r.get("gold_earned", 0) + _init_chips(r)
        spent = sum((r.get("gold_spent") or {}).values())
        leftover = max(0, earned - spent)
        leftovers.append(leftover)
        ratio = leftover / earned if earned > 0 else 0.0
        ratios.append(ratio)
        if not r.get("cleared"):
            n_died += 1
            if ratio > hoard_frac:
                died_hoard += 1
    return {
        "hoarder_rate": sum(1 for x in ratios if x > hoard_frac) / len(records),
        "mean_leftover": mean(leftovers),
        "mean_leftover_ratio": mean(ratios),
        "hoarder_rate_died": (died_hoard / n_died) if n_died else None,  # 死亡ランの貯め込み率（重要）
    }


def sink_roi_observational(records: Sequence[dict], alpha: float = 0.05, seed: int = 0) -> dict:
    """sink ごとの観察的ROI: その sink を使ったラン vs 使わなかったランのクリア率差。
    観察的（使う/使わないはbot方策が内生的に決める）＝因果でない。真のアブレーションは
    sink無効化bot方策の別コホートが必要（balance_report側で拡張可能・現状は観察値）。"""
    out = {}
    for s in GOLD_SINKS:
        used: list[int] = []
        not_used: list[int] = []
        for r in records:
            spent = (r.get("gold_spent") or {}).get(s, 0)
            (used if spent > 0 else not_used).append(1 if r.get("cleared") else 0)
        ci = bs.diff_bootstrap_ci(used, not_used, alpha=alpha, seed=seed) if used and not_used else (0.0, 0.0)
        out[s] = {
            "n_used": len(used), "n_not_used": len(not_used),
            "rate_used": mean(used) if used else 0.0,
            "rate_not_used": mean(not_used) if not_used else 0.0,
            "roi_diff": (mean(used) if used else 0.0) - (mean(not_used) if not_used else 0.0),
            "ci": ci,
        }
    return out
