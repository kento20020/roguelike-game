## 概要

<!-- 何をなぜ変えるか。squash後のmainコミット本文になる前提で書く -->

## 変更クラス（1つ選択・定義は CONTRIBUTING.md §3）

- [ ] **S: 仕様変更** — 先行 docs PR: #__（マージ済みであること）
- [ ] **B: バランス数値のみ** — `docs/schemas/` ミラー同期済み
- [ ] **F: バグ修正** — 準拠仕様: docs/____.md §__
- [ ] **R: リファクタ / テスト / CI**
- [ ] **D: docs のみ**

## 関連

- OPEN-xxx: <!-- 該当なしなら削除 -->
- Closes #

## チェックリスト

- [ ] ローカル検証を通した（該当分: `pytest` / `npm run typecheck` / `python scripts/check_docs.py`）
- [ ] changelog 追記の要否を判断した（S は必須）
- [ ] ADR の要否を判断した（技術選定・絶対原則の変更時）
- [ ] OPEN 表の状態列を更新した（該当時）
- [ ] 保護ファイル（`app/data/*.json`・`rng.py` 等）に触れる場合、変更理由を本文に明記した
