"""Phase5 回帰ゲート（GDD §18.2）。data/*.json やエンジンの数値変更で
バランスが基準からズレたら失敗する。bot は決定論的なので整数で厳密比較。

意図的な変更なら基準を再生成して承認:  python -m app.simulation.gen_baseline
"""
import json
import os

from app.simulation.balance_report import regression_snapshot

_BASELINE = os.path.join(os.path.dirname(__file__), "..", "app", "simulation",
                         "baselines", "balance_baseline.json")
_FIX = "意図的な変更なら基準を再生成して承認: python -m app.simulation.gen_baseline"


def test_balance_regression_matches_baseline():
    with open(_BASELINE, encoding="utf-8") as f:
        base = json.load(f)
    snap = regression_snapshot(base["n"])

    assert snap["clear_counts"] == base["clear_counts"], \
        f"strongクリア数が基準から変化: {snap['clear_counts']} != {base['clear_counts']}. {_FIX}"
    assert snap["random_clear_count"] == base["random_clear_count"], \
        f"randomクリア数が変化: {snap['random_clear_count']} != {base['random_clear_count']}. {_FIX}"
    # JSON 保存で int キーは str 化されるためキーを文字列に正規化して比較
    snap_df = {str(k): v for k, v in snap["maxed_death_floor"].items()}
    base_df = {str(k): v for k, v in base["maxed_death_floor"].items()}
    assert snap_df == base_df, \
        f"死亡フロア分布が変化: {snap_df} != {base_df}. {_FIX}"
    # スキル幅の不変条件（強bot は到達深度で random を上回る）
    assert snap["strong_depth_gt_random"] is True, "強botが到達深度でrandomを上回らない（スキル幅崩壊）"
