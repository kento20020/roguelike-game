"""balance_report のスモーク（小Nで構造と判定の健全性のみ。帯域検証は手動 --n 大で）。"""
from app.simulation import balance_report as br


def test_build_report_structure():
    rep = br.build_report(n=12, n_first_move=12)
    assert rep["verdict"] in ("pass", "warn", "fail")
    assert set(rep["clear_rates"]) == set(br.PROFILES)
    assert "fun_metrics" in rep and "economy" in rep
    names = [c["name"] for c in rep["checks"]]
    # §18.1 の主要条件が出口を持つ
    assert any("スキル幅" in n for n in names)
    assert any("初手別" in n for n in names)
    assert any("単一mod寄与" in n for n in names)
    for c in rep["checks"]:
        assert c["status"] in ("pass", "warn", "fail")
        assert c["spec"].startswith("§18")
