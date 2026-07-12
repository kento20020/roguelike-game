# CONTRIBUTING — 開発運用ルール（正本）

> 本書は「**変更の入れ方**」の正本。
> 設計の正本は `docs/`、数値の正本は `backend/app/data/*.json`、API実形の正本は `engine.snapshot()` / Pydantic。
> 正本の優先順位・文書統治・版管理の詳細は [docs/architecture.md](docs/architecture.md)（§0.1–§0.2）を参照。

---

## 1. ブランチとコミット

- **main へ直接コミットしない**（ブランチ保護で強制）。**1テーマ = 1ブランチ = 1PR**。
- ブランチ命名: `feat/` `fix/` `docs/` `balance/` `refactor/` `ci/` ＋ kebab-case
  （例: `feat/save-load`, `docs/gate-spec`, `balance/floor3-enemies`）。
- **PRタイトルに `feat:` / `fix:` / `docs:` / `test:` / `ci:` の prefix 必須**。
  squash merge で main のコミットメッセージが「`type: 題名 (#N)`」になるため、ブランチ内の途中コミットのメッセージは自由でよい。

## 2. PRフロー

- **squash merge のみ**（main は 1PR = 1コミット）。AI対話での試行錯誤・手戻りはブランチ内に閉じ、main には畳んだ結果だけを残す。
- solo 運用のため self-merge 可。ただし **CI green（`balance` / `lint` / `check-docs` / `frontend`）必須**。
- マージ後のブランチは自動削除（リポジトリ設定）。
- マージ前のローカル確認: `pytest`（backend変更時）/ `npm run typecheck`（frontend変更時）/ `python scripts/check_docs.py`（docs・data・API変更時）。

## 3. 変更クラス分類（spec-first の適用ルール）

すべてのPRは以下のいずれか1クラスに属する。PRテンプレートで自己申告する。

| クラス | 内容 | docs PR 先行 | docs 更新義務 |
|:---:|---|:---:|---|
| **S: 仕様変更** | ゲームルール・状態遷移・API形・画面仕様・データ構造の変更 | **必須**（docs PR をマージしてから実装PR） | changelog 必須。ADR・版bump は要判断（§5） |
| **B: バランス数値のみ** | `app/data/*.json`・baseline の数値変更（構造は不変） | 不要（数値の正本は JSON 側） | **同PRで `docs/schemas/` ミラー同期**（CI が強制）。GDD 本文の数表は要約のため追随任意 |
| **F: バグ修正** | コードを既存仕様に合わせる修正 | 不要 | 不要。準拠する仕様の §番号を PR 本文に引用 |
| **R: リファクタ/テスト/CI** | 外部挙動・仕様が変わらない変更 | 不要 | 不要 |
| **D: docs のみ** | 誤記修正・実装との整合・OPEN 表更新 | —（それ自体が docs PR） | — |

- **迷ったら S**。
- **実装中に仕様変更の必要が判明したら、実装を中断して S に昇格**（docs PR を先に切ってマージしてから実装を再開する）。
- **「ついで仕様変更」禁止**: 実装PRの中で仕様を変えない。仕様に触るなら必ず docs PR が先。

## 4. 課題管理（ハイブリッド）

1. 仕様上の未決事項は [docs/operations.md](docs/operations.md) §21.2 の **OPEN-xxx 表が正本**（起票・文言変更は D クラスの docs PR）。
2. **実装着手時**: GitHub Issue を「`OPEN-0xx: 題名`」で起票し、OPEN 表の状態列に `起票 #N` を記入。作業開始で `対応中 #N` に更新。
3. 実装PRに **`Closes #N`** を書く（squash merge で Issue が自動クローズ）。
4. **完了時**: 同PRまたは直後の D PR で OPEN 行の対応フェーズ列に解消版数（例 `解消（v1.5）`）・状態列に `解消` を記入し、[docs/changelog.md](docs/changelog.md) に解消経緯を記録（**行は表に残す**既存慣行を踏襲）。
5. OPEN 由来でない純粋な実装バグは Issue のみでよい（OPEN 表には足さない）。
6. **本文の「未定義/要確定/任意対応」は必ず OPEN を持つ**: docs 正本の本文に未決事項を書き残す場合は、対応する OPEN-xxx を起票して ID を併記する（受け皿の無い自己申告未定義を残さない）。参照先の OPEN が解消されたら、参照元の本文も同PRか直後の D PR で更新する。

## 5. changelog / ADR / 版 bump の基準

- **changelog**（[docs/changelog.md](docs/changelog.md)）: S クラスは必須。B・影響の大きい F は任意。
- **ADR**（[docs/adr/](docs/adr/)）: 技術選定・アーキテクチャ絶対原則の追加/変更時に `000N-題名.md` を追加（Status / Context / Decision / Consequences 形式）。
- **版 bump**: まとまった仕様改訂時のみ。[docs/architecture.md](docs/architecture.md) §0.1 の版管理ルール（版の正本は changelog.md 先頭エントリ・インデックス冒頭バナーと同一コミットで更新・doc-CI が一致を機械検査）に従う。ファイル名はバージョンレス固定のまま変えない。

## 6. AI対話（Claude Code / Codex）で設計・実装する際の作法

- 設計検討・実装は**必ずブランチ上**で行う（main の working tree を dirty にしない）。
- AI が提案した仕様変更も **S クラス**として扱う（docs PR 先行）。
- 保護ファイル（`backend/app/data/*.json`・`backend/app/engine/rng.py`・docs 正本）は CLAUDE.md / AGENTS.md の規約通り、人間の確認なしに変更しない。
- 大きな作業は plan mode で合意してから実装する。

## 7. CI 構成とブランチ保護

| ワークフロー | ジョブ名（=必須チェック名） | 内容 | PRでの発火 |
|---|---|---|---|
| `balance.yml` | `balance` | backend pytest 全件（カバレッジ計測）＋バランス回帰ゲート | `backend/**` 変更時 |
| `balance.yml` | `lint` | backend 静的解析 ruff＋mypy（`balance` と並列） | `backend/**` 変更時 |
| `docs-ci.yml` | `check-docs` | `scripts/check_docs.py`（schemas JSON 妥当性・相対リンク切れ・版/OPEN 整合・doc⇄コード drift 検知の11検査） | **常時（全PR）** |
| `frontend-ci.yml` | `frontend` | eslint（`npm run lint`）＋ build（`tsc --noEmit` 内包） | `frontend/**` 変更時 |

- main のブランチ保護は **`check-docs` を必須チェック**とし、force push・ブランチ削除を禁止する。`balance` / `lint` / `frontend` は path フィルタ発火のため**必須チェックにはしない**（path フィルタでスキップされたワークフローはステータスを報告せず、必須にすると無関係な PR がマージ不能になる）。発火した場合に green であることが self-merge の前提（§2）である点は従来どおり。
- `balance.yml`（`backend/**`）と `frontend-ci.yml`（`frontend/**`）は push / PR を **path フィルタで発火**させ、ジョブ内で変更有無を判定する skip は行わない。**`docs-ci.yml` のみ path フィルタなしの常時実行**（意図的な例外）: check_docs.py は docs⇄コードの二辺比較のため、paths で表現するとスクリプトが読むファイル一覧との二重管理になり追随漏れの穴が再発する。軽量（標準ライブラリのみ・約1秒）なので常時実行が安全側（docs-ci.yml 冒頭コメント）。
- 緊急時（CI 自体の障害等）のみ、ブランチ保護の「管理者にも適用」を一時無効化して対処し、復旧後すぐ戻す。
