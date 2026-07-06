# 障害時手順（Runbook）

> v1.4 で最小限の運用基盤（Alembic・ログ＋リクエストID・`.env.example`・`/health`・CI）を整備した。
> 残課題（Docker・バックアップ自動化・ONBOARDING）は OPEN-027 を参照。

## 0. 環境変数

`backend/.env.example` を参照（`DATABASE_URL` / `ALLOWED_ORIGINS` / `LOG_LEVEL`）。

## 1. 死活・セッション確認

- 死活: `GET /health` → `{"status":"ok"}`。
- 進行中ランの状態は `GET /api/run/{session_id}`（§25.1）。
- 進行中の GameState は `session_store`（メモリ保持・単一プロセス）にあり、**サーバ再起動で消失**する（§25.1 / OPEN-007）。永続化は未実装のため再起動を跨ぐ復旧はできない。

## 2. 追跡・ログ

- 全レスポンスに `X-Request-ID` ヘッダが付く（クライアント指定があればそれを尊重）。4xx は WARNING、未処理例外（500）はスタックトレース付き ERROR でサーバログに残る（`main.py`）。
- ログレベルは `LOG_LEVEL`（既定 INFO）。

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
