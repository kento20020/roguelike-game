# 障害時手順（Runbook）

> v1.4 で最小限の運用基盤（Alembic・ログ＋リクエストID・`.env.example`・`/health`・CI）を整備した。
> 残課題（Docker・バックアップ自動化）は OPEN-027 を参照。

## 0. 環境変数

`backend/.env.example` を参照（`DATABASE_URL` / `ALLOWED_ORIGINS` / `LOG_LEVEL` / `SESSION_TTL_HOURS` / `SESSION_CLEANUP_INTERVAL_HOURS`）。

## 1. 死活・セッション確認

- 死活: `GET /health` → `{"status":"ok"}`。
- 進行中ランの状態は `GET /api/run/{session_id}`（§25.1）。
- `session_store` はLRU上限（既定500）つきのインメモリキャッシュ。**サーバ再起動・LRU追い出しでキャッシュミスしても、`active_sessions`（SQLite）に記録した「seed＋初期upgrades＋適用アクション列」から `app.engine.replay.rebuild_engine` が透過的に再構築する**ため、進行中ランは失われない（OPEN-007解消・v1.5）。
  - Redis 等の新規インフラは導入していない（既存 SQLite で十分と判断。将来スケールが必要になった場合の検討事項として残す）。
  - `active_sessions` は終局（cleared/dead）後も即削除しない（`RunRecordRow`/`RunActionsRow` が正の記録として既に確定しているため実害なし）。TTL超過分の掃除（`crud.delete_stale_active_sessions`）は FastAPI lifespan 起動の周期タスク（`app.maintenance.periodic_session_cleanup`）で自動化済み（起動直後に1回＋以降は間隔ごとに実行）。間隔・TTLは環境変数 `SESSION_CLEANUP_INTERVAL_HOURS`（既定24h）/ `SESSION_TTL_HOURS`（既定168h=7日）で調整可能。新規スケジューラ依存は増やしていない（既存の最小フットプリント志向に合わせ APScheduler 等は不採用）。
  - 既知の限界: 同一 `session_id` への複数ワーカー間の真の同時書き込み競合はハードニングしていない（小規模実利用では稀という前提）。

## 2. 追跡・ログ

- 全レスポンスに `X-Request-ID` ヘッダが付く（クライアント指定があればそれを尊重）。4xx は WARNING、未処理例外（500）はスタックトレース付き ERROR でサーバログに残る（`main.py`）。
- **`request_id` は全ログレコードへ自動付与される**（`contextvars` + `RequestIdFilter`。`app/logging_setup.py`）。障害調査ではレスポンスの `X-Request-ID` ヘッダを控え、同じ値でサーバログを串刺しにする。手動でメッセージへ ID を埋め込む必要はない。
- ログレベルは `LOG_LEVEL`（既定 INFO）。
- **ログ形式は `LOG_FORMAT`（既定 `text`）**。`text` は従来のプレーンテキスト（`%(asctime)s %(levelname)s %(name)s %(message)s`）でローカル開発の可読性を優先する。`LOG_FORMAT=json` を指定すると 1 行構造化 JSON（キー: `ts`/`level`/`logger`/`msg`/`request_id`、例外時は `exc`）へ切り替わり、ログ集約基盤や `jq` での機械的フィルタに向く。外部ライブラリは使わず標準ライブラリのみで実装（`JsonFormatter`）。
  - request_id で串刺しにする例（`LOG_FORMAT=json` の出力に対して）:
    ```
    grep '^{' server.log | jq -c 'select(.request_id=="1ec4b667e499")'
    ```
  - 既知の限界: 想定外の例外（`main.py` の汎用 `Exception` ハンドラ `_unhandled` が拾う 500）だけは `request_id` が `null` になる。このハンドラは Starlette の `ServerErrorMiddleware`（`request_id_middleware` の外側）で実行され、その時点で ContextVar が既に reset 済みのため。同じ経路ではレスポンスの `X-Request-ID` ヘッダも付かない（例外が `call_next` を貫通しヘッダ付与行に到達しないため。v1.4 以来の既存挙動）。**この経路は例外のスタックトレース自体（`exc`）が調査の主情報になる**。想定内の 500（例: セッション再構築失敗＝`deps.py` の `HTTPException(500)`）は `call_next` の内側で処理されるため `request_id` もヘッダも正しく付く。

## 3. DB スキーマ移行（Alembic）

- 新規DB: `cd backend && alembic upgrade head`（`DATABASE_URL` を尊重）。
- **既存DB（テーブルは有るが新列が無い）**: `alembic stamp 0001_baseline && alembic upgrade head`。
  `0002_telemetry` は存在チェック付き（`main.py` の `create_all` が先にテーブルだけ作っていても安全）。
- 注意: `create_all` は開発/テスト用フォールバックで、**既存テーブルへの列追加はしない**。列追加は必ず Alembic で行う。
- Windows 注意: `alembic.ini` は **ASCII のみ**（configparser が locale=cp932 で読むため非ASCIIで壊れる）。

## 4. game.db バックアップ / リストア

- SQLite 単一ファイルのため、**サーバ停止中に `backend/game.db` をコピーする**のが基本手順（稼働中は `sqlite3 game.db ".backup backup.db"` を使う）。
- 永続対象: RunRecord（統計）・ProfileRow（恒久強化）・PostmortemRow（検死）・ObservationRow（調書）・RunActionsRow（操作履歴）。進行中ランは含まれない。
- 自動化（cron 等）は未整備（OPEN-027 残）。

## 5. データ版の切り分け・切り戻し

- RunRecord には `data_version`（4JSON 内容の sha256 短縮・v1.4 実装）が刻印される。バランス改定を跨いだ統計は `data_version` でフィルタして分離する（OPEN-024 解消）。
- bot 統計は `strategy_version`（bots.STRATEGY_VERSION）でも分離できる。
- バランス回帰の基準値は `python -m app.simulation.gen_baseline` で再生成して承認する（意図的変更時のみ）。

## 6. 依存関係の更新（pip-compile）

`backend/requirements.txt` / `backend/requirements-dev.txt` は手書きしない。`requirements.in`（ランタイム）/ `requirements-dev.in`（テスト専用。`-c requirements.txt` でランタイムとのバージョン整合を取る）から [pip-tools](https://github.com/jazzband/pip-tools) の `pip-compile` で生成する完全ピン留めロックファイル。

- 依存を追加/変更する場合は `backend/requirements.in` または `backend/requirements-dev.in` を編集する（`requirements.txt`/`requirements-dev.txt` を直接編集しない）。
- 初回のみ: `pip install pip-tools`
- 再生成:
  ```
  cd backend
  pip-compile requirements.in -o requirements.txt
  pip-compile requirements-dev.in -o requirements-dev.txt
  ```
- 生成後は `pip install -r requirements.txt -r requirements-dev.txt` で実際にインストールできることを確認する。
- **CI環境（ubuntu-latest）との差異に注意**: `uvicorn[standard]` が引く `uvloop` は `sys_platform != "win32"` マーカー付きの依存で、Windows上で `pip-compile` を実行すると `requirements.txt` の解決結果からuvloopの行自体が（マーカー付きでも）出力されない。ただし `uvicorn[standard]==x.y.z` の行はextras付きのまま出力されるため、Linux CIで `pip install` する際はuvicorn自身のwheelメタデータに従いuvloopが正しく解決・インストールされる（CI上の欠落は無い）。唯一の妥協点は「uvloopのバージョンだけはこのロックファイルで固定されない」こと。完全に固定したい場合はLinux環境（CI相当）で `pip-compile` を再実行すること。詳細は `backend/requirements.in` のコメントを参照。
