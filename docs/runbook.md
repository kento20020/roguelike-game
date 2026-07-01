# 障害時手順（Runbook）

> 本書は**骨子（スケルトン）**であり、運用手順の多くは**未整備**。運用基盤（Alembic・Docker・game.db バックアップ・構造化ログ+req_id・`.env.example`・CI・`/health`・RUNBOOK/ONBOARDING）の整備は **OPEN-027** として GDD 外の別タスクに集約されている（詳細は `operations.md` の §21.2 を参照）。現時点で確立している手順のみを記す。

## 1. セッション確認

進行中ランの状態は `GET /api/run/{session_id}` で取得する（§25.1）。

- 進行中の GameState は `session_store`（メモリ保持・単一プロセス）にあり、**サーバ再起動で消失**する（§25.1 / OPEN-007）。
- 永続化（DB/Redis へのシリアライズ）は未実装のため、再起動を跨ぐ復旧はできない（OPEN-007 / OPEN-026）。

## 2. 追跡・ログ

- req_id・構造化ログによるリクエスト追跡は**未整備**（OPEN-027）。
- `/health` エンドポイントも OPEN-027 の範囲で未整備。

## 3. game.db バックアップ / リストア

- バックアップ・リストアは**方針のみで手順は未整備**（OPEN-027）。
- `game.db`（SQLite）に永続するのは RunRecord（統計）と PlayerProfile / ProfileRow（メタ進行・§20.6）のみで、進行中ランは含まれない。

## 4. データ版の切り戻し

- RunRecord の `data_version`（config/enemies/mods/floors のハッシュ）は**未実装**のため、版混在時の切り分け・切り戻しはできない（OPEN-024）。
- 対応後は 4JSON ハッシュを RunRecord に付与し、版フィルタで版別集計・切り戻す想定（OPEN-024）。
