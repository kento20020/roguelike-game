# API契約（API Contract）
> 元 `game_design_document.md`（v1.2）の §25 を再配置。API実形の正本は `engine.snapshot()` / Pydantic（`backend/app/schemas`）。相互参照の §番号・OPEN-xxx は元GDD準拠。

## 25. APIエンドポイント仕様

### 25.1 設計方針

- ゲームの全ロジックはバックエンド。フロントは操作を送って新しい状態を受け取るだけ
- 各レスポンスは**完全なゲーム状態**を返す（フロントは差分計算不要）
- `session_id`（uuid）でランを識別。**進行中の GameState は `session_store` がプロセス内メモリで保持**し、DBへは**確定 RunRecord と Profile のみ**を永続化する（`session_store.py`）。**サーバ再起動で進行中ランは失われる**（単一プロセス前提・OPEN-007/026）。`GET /run/{id}`（再開）は同一プロセス生存中のみ成立。旧記述「DBに永続化」は実態と不一致だったため訂正。
- **完全状態返却の例外**：`/upgrade`・`/profile/upgrades` は `UpgradeState`、`/catalog/mods` は `ModCatalogItem[]`、`/stats/history` は `RunRecord[]` を返す（原則6の明示的例外）。

### 25.2 エンドポイント一覧

| メソッド | パス | 用途 | リクエスト | レスポンス |
|---------|------|------|----------|----------|
| POST | `/api/run/new` | 新規ラン開始 | `{ seed?: int, bot_type?: str }` | `GameState` |
| GET | `/api/run/{session_id}` | 状態取得（再開・同一プロセス生存中） | — | `GameState` |
| POST | `/api/run/{session_id}/select-node` | ノード選択 | `{ node_id }` | `GameState` |
| POST | `/api/run/{session_id}/attack` | 攻撃 | — | `GameState` |
| POST | `/api/run/{session_id}/guard` | 受け（防御・§8.4） | — | `GameState` |
| POST | `/api/run/{session_id}/sink` | sink使用 | `{ sink_type }` | `GameState` |
| POST | `/api/run/{session_id}/treasure/open` | 宝箱開封 | — | `GameState` |
| POST | `/api/run/{session_id}/treasure/reroll` | 宝箱リロール | — | `GameState` |
| POST | `/api/run/{session_id}/gate/resolve` | ゲート通過 | — | `GameState` |
| POST | `/api/run/{session_id}/continue` | モーダルphase前進（treasure_opened/heal/next_floor→exploring） | — | `GameState` |
| POST | `/api/run/{session_id}/upgrade` | 恒久強化割り振り | `{ upgrade_type }` | `UpgradeState` |
| GET | `/api/profile/upgrades` | 恒久強化状態（ClearedPage初期表示） | — | `UpgradeState` |
| GET | `/api/catalog/mods` | mod効果文カタログ（表示の正本） | — | `ModCatalogItem[]` |
| GET | `/api/stats/history` | RunRecord履歴 | `{ limit?: int=50 }` | `RunRecord[]` |

> **sink_typeの値**：`scout` / `heal_small` / `heal_large` / `gate_guarantee` / `attack_boost`（実装の `use_sink` が受け付ける値）。
> **宝箱リロールは専用ルート**：`/treasure/reroll` のみで実行する。`/sink` に `treasure_reroll` を渡すと **400**（実装は `use_sink` で未対応）。※ RunRecord の `gold_spent.treasure_reroll`（§19.1）はチップ消費の記録カテゴリとしては残る。
> **ゲート保証の重ねがけ**：`sink_type: "gate_guarantee"` を `gate_preview` phaseで複数回POSTできる。サーバーが現在の重ねがけ回数 `n` を保持し、コスト `50G×1.5^(n-1)` と削減量 `25%×0.5^(n-1)` を計算してGameStateに反映。ゴールド不足時は400を返す。
> **攻撃ブースト**：`sink_type: "attack_boost"` は `battle` phaseでのみ有効。次の `attack` 1回だけ `stance_multiplier` に ×2.0 を**乗算**（`guard` では消費しない）。
> **UpgradeState の形**：`{ points:int, levels:{max_hp,attack,init_gold,gold_drop,sink_cost}, maxes:{…} }`（`UpgradeStateResponse`）。`/upgrade`・`/profile/upgrades` が返す。理想は `/upgrade` も完全GameState（＋upgrade_state内包）だが現状は UpgradeState 単体（原則6の例外）。**スコープの矛盾（OPEN-002）**：恒久強化は Profile（ラン非依存）の資産だが操作口は `/run/{session_id}/upgrade`（ラン依存）。バンクした余剰ポイント（§12.3）を次ラン中に割り振れる phase は未定義——`/api/profile/upgrade`（セッション非依存）への移設 or 許可 phase の明記を OPEN-002 で扱う。
> **冪等性・認証は非スコープ（OPEN-026）**：全 mutating POST に Idempotency-Key・state_version は無い。再送で `gate_guarantee` 二重課金・`/attack` 二重進行（RNGドリフト）が起き得る。単一プレイヤー・ローカル前提では実害限定だが、公開時は冪等キー＋楽観ロック＋所有者照合を必須化。`/stats/history` は無条件全件（`limit`のみ）＝スコープ化（client_id）＋件数上限を追跡。

### 25.3 GameStateレスポンスの形

> **実装に追随した版**。下記が `engine.snapshot()` の実形。過去ドラフトからの変更点：
> - `player.gold` → **`player.chips`**（§16.2 テーマ読替＝チップ）。`attack_boost_pending` を追加。
> - `floor` は `tree_shape`/`edges` 配列ではなく **`nodes`（id→ノードの dict）**。辺は各ノードの **`parents`** で表現し、`tree_shape` は floors.json 側の定義に集約。`locked` 単独フラグは廃止し **`state`（available/locked/resolved）** に統一。
> - トップレベルの `combat_log`/`available_sinks` は廃止 → ログは **`battle.log`**、sink候補は **`available_actions`（cost付き・上位互換）** に統合。
> - `run_record` をトップレベルに含む（決算・履歴用）。

> 例: [`schemas/gamestate_example.json`](schemas/gamestate_example.json)（exploring phase の完全な snapshot）

> **battle phase の例（実装準拠・要点）**：
> 例: [`schemas/battle_example.json`](schemas/battle_example.json)（battle phase の要点）
> `battle` は `BattleOut`（enemy/turns/ramp_value/scout_hint/preview/next_action/log）。`pending` は phase別（§20.8。例：`gate_preview`=`{table,damage}`、`treasure_opened`=`{mod,count}`）。`available_actions[].type` は §20.7。未インタラクトノードにも name/max_hp が乗る（§5・OPEN-015）。`resolved` は `state` 由来の派生（§20.4）。

### 25.4 エラーハンドリング

| ステータス | 意味 |
|----------|------|
| 400 | 不正な操作（ロック中ノード選択・チップ不足・未対応sink_type等） |
| 404 | session_idが存在しない |
| 409 | phase不整合（戦闘中にノード選択等） |

**phase不整合の例（サーバ側で必ず拒否＝409）**：フロントで防いでいてもバックエンドの防御は必須。

| 現在phase | 不正操作 | 返す |
|----------|---------|:---:|
| `battle` | select-node | 409 |
| `exploring` | attack / treasure・gate系 | 409 |
| `treasure_opened` | treasure/reroll | 409 |
| `gate_resolve` | select-node / attack | 409 |
| `dead` / `cleared` | attack / sink / select-node | 409 |

> sink の許可phaseは §13.2 準拠（scout/attack_boost=battle、gate_guarantee=gate_preview、reroll=treasure_preview、回復=exploring/battle）。許可外phaseでの sink は **409**（`WrongPhase`）で拒否。

> **判定順（実装準拠）**：`get_engine_or_404`→**404**（session不在）／`WrongPhase`→**409**（phase不整合）／`InvalidMove`→**400**（ロックnode選択・不在node_id・チップ不足・満タン回復・未知sink/upgrade項目）。**チップ不足・ロックnode は 400**（`InvalidMove`）である点に注意（資源不足を422で別立てするかは将来）。例：battle 中の `heal_small` チップ不足=**400**（許可phase内の資源不足）／battle 中の `gate_guarantee`=**409**（phase違反）。
> **select-node の異常入力**：不在 node_id・前フロアの stale id（現フロア `nodes` に無い）は **400**、解決済み/ロック中の再選択も 400（`node_state != available`）。node_id はフロア間で L/M/R を再利用するが、フロア遷移で `resolved` リセット＆ `nodes` 再生成のため stale id は現フロアに無く 400 になる。
> **攻撃ブーストの二重課金（OPEN-021）**：`attack_boost_pending=true` 中の `/sink attack_boost` 再POSTは現状サーバ側 guard が無く再課金し得る（`available_actions` は非提示）。400（無効）で弾くのが望ましい。
> **エラーbody構造（OPEN-026）**：現状はHTTPステータスのみ。`{error_code, message, req_id}` で構造化し ErrorToast の分岐・ログ集計に載せるのが望ましい（運用・別タスク）。

### 25.5 型共有

`backend/app/schemas/api_schemas.py`（Pydantic）と `frontend/src/api/types.ts`（TypeScript）で同じ型を定義。
将来的にはOpenAPIスキーマからTypeScript型を自動生成することも可能（FastAPIがSwaggerを吐くため）。

---
