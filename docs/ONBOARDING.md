# オンボーディング（Onboarding）

新しく参加する開発者・エージェントが、環境構築からテスト・静的解析の実行までを迷わず一本道で辿れるようにするための手順書。
既存文書（README.md / CLAUDE.md / runbook.md / CI設定）の再構成であり、ここに新しいルール・数値は無い。詳細は各章末尾の参照先を見る。

---

## 1. 前提条件

CI（`.github/workflows/`）が実際に使っているバージョンと揃える。

| ツール | バージョン | 根拠 |
|--------|-----------|------|
| Python | 3.12 | `.github/workflows/balance.yml` の `actions/setup-python` |
| Node.js | 22 | `.github/workflows/frontend-ci.yml` の `actions/setup-node` |
| git | 任意の最新版 | — |

---

## 2. backend セットアップ

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# サーバ起動のみで良い場合はこれだけで足りる
pip install -r requirements.txt

# pytest・ruff・mypy も回す場合はテスト専用依存も追加
pip install -r requirements.txt -r requirements-dev.txt

# DBスキーマを最新化（新規DBならこれだけで良い。既存DBの場合は docs/runbook.md §3 を参照）
alembic upgrade head

# 起動（http://localhost:8000）
uvicorn main:app --reload
```

起動確認: `GET http://localhost:8000/health` が `{"status": "ok"}` を返せば成功。

---

## 3. frontend セットアップ

```bash
cd frontend
npm ci
npm run dev
```

`http://localhost:5173` で画面が開けば成功（Vite dev server）。

---

## 4. テスト・静的解析の回し方

| コマンド | 対象 | 実行場所 |
|---------|------|---------|
| `pytest -q` | backend の全テスト | `backend/` |
| `ruff check .` | backend の lint（設定は `backend/pyproject.toml`） | `backend/` |
| `mypy app main.py` | backend の型検査（設定は `backend/pyproject.toml`） | `backend/` |
| `npm run lint` | frontend の ESLint | `frontend/` |
| `npm run typecheck` | frontend の型検査（`tsc --noEmit`） | `frontend/` |
| `python scripts/check_docs.py` | docs の検査（schemas JSON 妥当性・相対リンク切れ・`backend/app/data` ミラー一致・API 契約表一致）。docs・data・API 変更時は必須（CONTRIBUTING §2） | リポジトリルート |

`npm run build` は `tsc --noEmit && vite build` なので、ビルドが通れば型検査も内包して通っている（`frontend/package.json`）。

---

## 5. 依存の更新方法

`backend/requirements.txt` / `requirements-dev.txt` は手書きしない。`requirements.in`（ランタイム） / `requirements-dev.in`（テスト専用）を編集してから `pip-compile` で再生成するロックファイル運用。手順の詳細は **[`docs/runbook.md`](runbook.md) §6「依存関係の更新（pip-compile）」** を参照。

frontend は通常の `npm install <pkg>` → `package-lock.json` 更新でよい。

---

## 6. ドキュメントの読み順

1. **[`README.md`](../README.md)** — ゲーム概要・遊び方・アーキテクチャ図・起動方法
2. **[`CLAUDE.md`](../CLAUDE.md)** — 作業の進め方・コーディング規約・触ってはいけないファイル一覧・壊してはいけない不変条件
3. **[`docs/architecture.md`](architecture.md)** — 正本の優先順位（本書/JSON/コードの食い違いをどちらで直すか）・乱数アーキテクチャ・技術スタック
4. **[`docs/runbook.md`](runbook.md)** — 障害対応・DBマイグレーション・ログ調査・依存更新の実手順

---

## 7. トラブルシューティング

- **Windows で `alembic` コマンドが文字化け/エラーになる**: `backend/alembic.ini` は ASCII のみで書く。`configparser` が Windows のロケール（cp932）でこのファイルを読むため、非ASCII文字が混ざると壊れる。
- **列を追加したのに反映されない**: `main.py` の `create_all` は開発/テスト用フォールバックで、**既存テーブルへの列追加はしない**。スキーマ変更は必ず Alembic マイグレーションで行う（`docs/runbook.md` §3）。
- **DB周りの排他制御**: SQLite は WAL mode で運用している（`game.db`）。
- **既定ポートが埋まっている**: backend は `8000`、frontend は `5173` が既定。

---

## 8. 環境変数一覧

`backend/.env.example` を参照（コピーして `.env` を作るか、シェルで `export` して使う。`.env` は git 管理外）。

| 変数 | 既定値 | 用途 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///` backend/game.db 相当 | DB接続文字列。PostgreSQL移行時はここを差し替えるだけ |
| `ALLOWED_ORIGINS` | Vite dev server のみ | CORS 許可オリジン（カンマ区切り） |
| `LOG_LEVEL` | `INFO` | ログレベル（DEBUG/INFO/WARNING/ERROR） |
| `LOG_FORMAT` | `text` | ログ出力形式。`json` にすると1行構造化JSON（`ts`/`level`/`logger`/`msg`/`request_id`/`exc`）に切り替わる |
| `SESSION_TTL_HOURS` | `168`（7日） | `active_sessions` の TTL。超過分は自動掃除される |
| `SESSION_CLEANUP_INTERVAL_HOURS` | `24` | TTL 掃除タスクの実行間隔 |

---

## 9. CI概要

`.github/workflows/` の全ワークフローと `.github/dependabot.yml` の役割。

| ファイル | 役割 |
|---------|------|
| [`.github/workflows/balance.yml`](../.github/workflows/balance.yml) | backend の `balance` ジョブ（pytest 全体 + カバレッジ + バランス回帰ゲート `test_balance_regression`）と `lint` ジョブ（ruff + mypy）を並列実行 |
| [`.github/workflows/frontend-ci.yml`](../.github/workflows/frontend-ci.yml) | frontend の ESLint と `npm run build`（`tsc --noEmit` を内包）を実行 |
| [`.github/workflows/docs-ci.yml`](../.github/workflows/docs-ci.yml) | `docs/` 配下の JSON スキーマ妥当性・相対リンク切れを [`scripts/check_docs.py`](../scripts/check_docs.py) で検査 |
| [`.github/dependabot.yml`](../.github/dependabot.yml) | pip（backend）/ npm（frontend）/ github-actions の週次自動更新PR（minor/patchはグループ化・majorは個別PR） |
