"""Phase5 回帰CIの基準値を再生成する（バランス変更を人間が承認する時に実行）。

実行: python -m app.simulation.gen_baseline [N]
bot は決定論的（同一 seed→同一結果）なので、data/*.json やエンジンの数値を意図的に変えた
場合のみ基準が動く。再生成＝その変更を「正」として承認すること。
"""
from __future__ import annotations

import json
import os
import sys

from app.simulation.balance_report import regression_snapshot

PATH = os.path.join(os.path.dirname(__file__), "baselines", "balance_baseline.json")
_NOTE = ("Phase5回帰CIの基準値。data/*.jsonやエンジンの数値変更で test_balance_regression が"
         "失敗したら、変更が意図的なら python -m app.simulation.gen_baseline で再生成して承認する。")


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    snap = regression_snapshot(n)
    snap["_comment"] = _NOTE
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    print("wrote", PATH)
    print(json.dumps(snap, ensure_ascii=False))


if __name__ == "__main__":
    main()
