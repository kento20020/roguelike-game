# バランス検証フレームワーク — 統合マップ（GDD §18.3 INTEGRATION.md）

§18.2 の各 Phase と、使用する統計手法（§18.3）、§18.1 の合格条件、実装ファイルの対応表。
**方針**：統計指標は「合格条件」であって最適化目標ではない（§18.4 Goodhart回避）。
帯域内の判断はデザイナー、`data/*.json` の数値は人間が触る。ツールは「測るだけ」。

## Phase × 手法 × 合格条件 × ファイル

| Phase | 目的 | 手法（balance_stats） | §18.1 合格条件 | 判定 | 実装 |
|---|---|---|---|:--:|---|
| 0 | 実装・バグゼロ | — | — | gate | `pytest`（全テスト） |
| 1 | クリア率帯域 | `band_test`（BernoulliCS）/ `wilson` | 強25-40%・random1-5% | warn | `phase12_harness.py` / `balance_report.py` |
| 2 | スキル幅 | `mcnemar_eprocess`（CRN対標本）＋ Wilson非重なり | CIが0をまたがない | **fail** | `balance_report.py` |
| 2 | 初手別差・選択感度 | `first_move_sensitivity`（forced_first_node）＋`mcnemar_eprocess`＋`ebh_fdr` | 初手別±5pt・有意差 | warn | `balance_analysis.py` |
| 3 | 単一mod寄与（FDR） | 観察: `mod_marginal_contribution`＋`diff_bootstrap_ci`＋`equivalence_check`。**正**: ablation・因果推定は `mod_ablation.py`（CRN対標本＋McNemar e-process＋e-BH） | ±8pt以内（平均寄与のみ） | warn | `balance_analysis.py`（観察）／`mod_ablation.py`（正） |
| 3 | ペア交互作用（OPEN-023） | `mod_ablation.py`（2mod同時除外・CRN・純交互作用I＋e-BH 第2ファミリ） | ±10pt(W)以内 | warn | `mod_ablation.py` |
| 3 | 死亡フロア集中 | `concentration_evalue`（BernoulliCS） | 集中しない | warn | `balance_analysis.py` |
| 4 | 経済・sink ROI・hoarder | `sink_roi_observational`・`hoarder_detection` | （記述・監視） | info | `balance_analysis.py` |
| 5 | 回帰（CI） | `regression_snapshot`（決定論・整数厳密比較） | 基準からの逸脱なし | **fail** | `tests/test_balance_regression.py` |

**厳格 fail は2点のみ**：スキル幅（Phase2）と回帰（Phase5）。他は warn（デザイナー判断に返す）。

## 面白さ代理指標（`fun_metrics.py`・測るだけ）
RunRecord のみで算出：僅差勝率 / クリアターン分散 / 取得modエントロピー / mod別クリア率分散 /
ゲート保証依存度 / レース系被ターン。per-battle の緊張感・逆転・退屈さは将来 `trace.py` で精度向上（C案）。

## e-value / anytime-valid の根拠
hedged capital `K_t = ½∏(1+λ_i(x_i-m)) + ½∏(1-λ_i(x_i-m))`（λ_i 予測可能）は H0:μ=m の下で
平均1の非負マルチンゲール。Ville の不等式 `P(sup_t K_t ≥ 1/α) ≤ α` より、`{m: sup_t K_t < 1/α}` は
被覆 ≥ 1-α の信頼系列（任意停止に頑健）。被覆率は `test_balance_stats.py` で実測検証。

## 運用コマンド
- レポート: `python -m app.simulation.balance_report --n 1000 --out report.json`
- 回帰基準の再生成（バランス変更を承認する時）: `python -m app.simulation.gen_baseline`
- Phase1 簡易: `python -m app.simulation.phase12_harness 1000`
- mod ablation（単体寄与＋ペア交互作用・OPEN-023）: `python -m app.simulation.mod_ablation --n 1000 --profile mid --out baselines/mod_ablation_result.json`

## 依存
`numpy`（e-value/CS のベクトル化）。エンジン本体は依存しない（simulation/分析専用）。

## 未実装（将来・別軸）
- 真の sink ROIアブレーション（sink無効化bot方策の別コホート）。現状は観察的ROI。
  mod の ablation（宝箱抽選プール除外・`mod_ablation.py`）は実装済み（Phase3表の行を参照）
  — sink ROI は対象が異なる別軸のため、これとは別に引き続き未実装。
- `llm_content_pipeline.py`（Generator→Validator→Simulator→Critic）。
- per-battle `trace.py`（緊張感/逆転/退屈さの直接計測）。
- `forced_first_mod`（build固定）。現状は `forced_first_node`（初手位置固定）で初手別を測る。
