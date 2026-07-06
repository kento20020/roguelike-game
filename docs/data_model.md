# データモデル・永続化（Data Model）
> 元 `game_design_document.md`（v1.2）の §0.3・§19・§20（20.4を除く）を再配置。**実行時データの正本は `backend/app/data/*.json`**（config/enemies/mods/floors）。`docs/schemas/*.json` は参照用ミラー。相互参照の §番号・OPEN-xxx は元GDD準拠。

### 0.3 通貨・主要キーの正準（gold / chips）

通貨は実装上3つの呼び名が併存する。本書では**現状を正準として明文化**する（リネームはしない）。

| 層 | 正準名 | 例 |
|----|--------|----|
| 実行時ドメイン / フロント / API | **`chips`** | `player.chips`、`schemas/models.py` の `Player.chips`、`types.ts` |
| 永続・統計スキーマ（RunRecord/DB） | **`gold_*`**（歴史的経緯で保持） | `gold_earned` / `gold_spent`（`db/models.py`） |
| config 内部パラメータ名 | **`gold`** | `config.json` の `gold.floor_multiplier` |
| 恒久強化キー（初期チップ） | **`init_gold`**（歴史的経緯で保持） | `config.permanent_upgrades.items.init_gold` / `ProfileRow.init_gold`（表示は「初期チップ」） |
| UI表示名 | **「チップ」** | ヘッダのチップ残高 |

- **`chips` は実行時の唯一の通貨変数**。`gold_earned`/`gold_spent` は**書き出し専用ミラー**（統計）で、`chips` → `gold_*` の写しは RunRecord 生成・sink 支出記録の1経路のみ。`init_gold`（恒久強化）は**ラン開始時に `chips` へ初期付与**するキー。それ以外で名前を混ぜない。
- 本書本文で「ゴールド」「G」と書いている箇所は**表示・口語表現**であり、内部キーは上表に従う。
- その他の用語揺れも同様に実形へ寄せる：状態フェーズは `phase`（旧 `game_phase`）、ノードのロック状態は `state`（`available`/`locked`/`resolved`。旧 `locked` 単独フラグは廃止）。

---

## 19. テレメトリー（RunRecord）

### 19.1 スキーマ（全フィールド採用）

```
RunRecord:
  # ラン識別
  run_id: string               # = "run-{seed}"（session_id=uuid とは別物・同一seedで衝突し得る）
  seed: int
  timestamp: datetime          # 実装では created_at（DB server_default=now）として永続化

  # 結果
  cleared: bool
  floor_reached: int          # 1〜5
  total_turns: int

  # プレイヤー
  final_hp: int
  mods_acquired: string[]      # 取得modのリスト

  # 経済
  gold_earned: int
  gold_spent: { scout: int, heal_small: int, heal_large: int,
                gate_guarantee: int, treasure_reroll: int,
                attack_boost: int }    # 攻めのsink
  gate_guarantee_stacks: int           # ゲート保証の重ねがけ回数（合計）

  # 戦闘詳細
  enemies_defeated: [
    { enemy_id: string, experience: string, floor: int, turns: int }
  ]                            # 体験タイプも記録（mod×敵の化学反応分析用）
  death_cause: string | null   # "敵id:行動タイプ" または "gate:結果"（ゲート死。例 gate:major）
  death_floor: int | null

  # 統計用
  bot_type: string             # "strong" / "random"
  permanent_upgrades_state: { max_hp: int, attack: int,
                              init_gold: int, gold_drop: int, sink_cost: int }

  # 世代札・テレメトリ（v1.4 追加・OPEN-024/025 解消）
  data_version: string         # 4JSON(config/enemies/mods/floors)内容のsha256短縮(12hex)
  strategy_version: string|null  # bot方策の版（bots.STRATEGY_VERSION）。human は null
  sink_use_counts: { <sink_type>: int }          # sink別の使用回数（ROI=回数×効果の逆算用）
  gate_results: [ { floor: int, outcome: str } ] # per-floorゲート結果（特殊発生率・保証ROI検証用）
  action_counts: { attack: int, guard: int, heal_small: int, heal_large: int }  # player_move別ターン数
```

> **フィールド定義の明確化（実装準拠）**：
> - `run_id = "run-{seed}"`。`session_id`（uuid・`session_store`）とは**別物**で、同一seedを使う bot パネルでは run_id が衝突し得る（`RunRecordRow.run_id` は index で unique 制約なし）。ラン⇄セッションの紐付けは §25。
> - `mods_acquired` は同mod複数取得を**重複保持（取得順）**。`total_turns` は戦闘ターン総和。`permanent_upgrades_state` の各intは**レベル値**（0〜上限Lv）。`bot_type` は `human`/`strong`/`random`。`enemies_defeated[].experience` は **romaji enum**（§20.7・v1.4 で OPEN-012 解消。旧レコードには日本語が残るが data_version で世代が分かれる）。
>
> **v1.4 で追加済み（OPEN-024/025 解消・Alembic `0002_telemetry`）**：`data_version`・`strategy_version`・`sink_use_counts`・`gate_results`・`action_counts`。マイグレーション前の旧行は NULL のまま保持され、API 層（`to_dict`）が既定値（""/{}/[]）へ丸める。

### 19.2 用途
- Phase2以降の全統計検証の入力
- `enemies_defeated`に体験タイプを含むため「ずれ系敵が出ないランで見切りが腐ったか」を検出可能
- **操作履歴の永続化（v1.4 実装）**：戦闘ターンの操作履歴（`turn_history`：player_move/action/与被ダメ/前後HP/ターン開始前スナップショット）は、**全ラン**（クリア/死亡とも）終局時に `run_actions` テーブルへ一括保存される（improvement_ideas アイディア1 の共通基盤）。検死専用の `postmortems` とは別物。combat_log は従来どおり表示専用・非永続（§10.5）。ノード選択・ゲート等の非戦闘操作はまだ含まれないため、完全リプレイ（seed＋全操作列）への拡張は将来課題。

---

## 20. データモデル

### 20.1 フロアデータ（v1.4・可変深度スキーマ）

| フィールド | 型 | 内容 |
|---------|---|------|
| `floor_number` | int | 1〜5 |
| `fixed_layout` | bool | 1Fのみ true（`nodes_layout` による固定チュートリアル） |
| `depth` | int | 生成フロアの row 数（2F=3/3F=4/4F=5/5F=6・叩き台） |
| `enemy_pool` | string[] | フロア統合敵プール（袋方式で抽選・枯渇時のみ重複解禁） |
| `generation` | object | `main_width_min/max`（2〜3）・`dead_ends_max_per_row` |
| `gate_result_table` | object | ゲート確率テーブル（フロア別・合計1.0を機械検証） |
| `floor_multiplier` | float | ゴールド倍率 |
| `heal_node` | bool | 回復ノードの有無（配置先は生成された dead-end から stream4 で選択・§4.3） |

> 旧スキーマ（`tree_shape`・`row1_pool`/`row2_pool`/`row3_pool`・`unlock_map`・`heal_node_position`）は
> v1.4 の接続ランタイム生成化で**廃止**（1Fの `nodes_layout` を除く）。接続の不変条件は
> `floor_generator.validate_floor()` が生成毎に検証する（§4.2）。

### 20.2 敵データ
§11.2参照

### 20.3 プレイヤーデータ
§12.1参照

### 20.5 データファイル一覧（実装の正本）

ゲームの全数値は以下4ファイルに集約。GDD本文の数表は要約であり、**実装は必ずこれらのJSONを正本とする**。

| ファイル | 内容 | 機械検証 |
|---------|------|:------:|
| `config.json` | 全体パラメータ（戦闘係数・ramp初期値・sink・恒久強化・RNG定義） | ✅ |
| `enemies.json` | 全36体（behaviors weight合計100・レース系inc・gold_base・chaosフラグ） | ✅ weight合計100 |
| `mods.json` | 6種mod＋インタラクション（cancel/synergy）＋1F反射確定（`tutorial_guaranteed`） | ✅ mod ID一意 |
| `floors.json` | 5フロア構成・アンロック連鎖・ゲートテーブル・描画方向・1F反射配置（`content`） | ✅ アンロック整合（ゲート合計1.0はOPEN-013） |

**配置場所**：`backend/app/data/`（§23参照）。FastAPIエンジンとbotシミュレーターの両方がこれを読む。

**機械検証（`loader.validate()`・データロード時に常時実行）**：
- 敵ID一意
- 全非カオス敵の behaviors weight 合計＝100／カオスは behaviors 空＋`chaos:true`
- `ramp_hit` を持つ敵は `ramp_increment` 必須（レース系7体は inc 2〜8）
- mod ID一意／floor の pool ID が実在／1F固定レイアウトの親整合／生成フロアの depth・enemy_pool・generation 妥当性
- 全フロアのゲートテーブル＝キー4種・合計1.0（v1.4・OPEN-013）
- `experience` が romaji enum のみ（v1.4・OPEN-012 受入条件）

**生成毎の機械検証（`floor_generator.validate_floor()`・v1.4）**：
- 多親=2親／単親=1親／dead-end（treasure/heal）は単親／GATE親≥2／全ノード到達可能／最終rowに非カオス≥1

**テストで担保（v1.4）**：
- `snapshot()` に seed・rng_streams・chaos_weights を含めない＋進行中 run_record=null（`test_invariants.py`）
- 恒久強化の上限Lv合計＝21（`test_data_validation.py`）
- RunRecord の `data_version` 刻印（`test_telemetry.py`）

### 20.6 メタ進行の永続エンティティ（PlayerProfile・実装準拠）

恒久強化（win-to-progress）の可変正本は RunRecord ではなく **`ProfileRow`（DB `profiles` テーブル）**：

| フィールド | 型 | 内容 |
|---------|---|------|
| `id` | int | **`1` 固定**（単一プロファイル・認証は非スコープ §0.4） |
| `points` | int | 未割当の恒久強化ポイント（クリアで +1・`award_points`） |
| `max_hp` / `attack` / `init_gold` / `gold_drop` / `sink_cost` | int | 各強化のレベル（0〜上限Lv） |

- `POST /run/new` が `profile_levels()` を読み初期 GameState へ反映（`new_run(upgrades=…)`）。`POST /upgrade` が `allocate_upgrade` で Profile を更新。`RunRecord.permanent_upgrades_state` は**ラン開始時スナップショット（統計用）**で可変正本ではない。
- マルチユーザ化する場合は `owner`/`client_id` 列を足す（現状は単一プロファイル前提・OPEN-026）。

### 20.6b その他の永続テーブル（v1.4 時点の全体像）

| テーブル | 内容 | 由来 |
|---------|------|------|
| `run_records` | ラン統計（§19.1・data_version 等のテレメトリ込み） | 従来＋v1.4拡張 |
| `profiles` | 恒久強化（id=1 固定・§20.6） | 従来 |
| `postmortems` | 検死レポート（turn_history＋致命ターンの反実仮想。戦闘死のみ・§15.2） | 検死機能 |
| `observations` | ディーラー調書の観測カウント（enemy_id×behavior×data_version・真のweightは持たない・§15.3） | 調書機能 |
| `run_actions` | 全ラン共通の操作履歴（terminal時に turn_history を一括保存） | v1.4（improvement_ideas アイディア1 基盤） |

- スキーマ進化は **Alembic**（`backend/migrations/`・SQLite は batch mode）。手順は runbook.md。`main.py` の `create_all` は開発/テスト用フォールバック（既存テーブルへの列追加はしない）。

### 20.7 値集合（enum の正準源）

`api_schemas.py`（Pydantic）と `types.ts`（Literal/union）の正準：

| 対象 | 値 |
|------|----|
| `node.kind` | `enemy` / `gate_route` / `treasure` / `heal` / `gate` |
| `parent_type` | `root` / `single` / `multi`（`multi`=OR/any解放） |
| `state` | `available` / `locked` / `resolved` |
| `available_actions[].type` | `select_node` / `attack` / `guard` / `use_sink` / `treasure_open` / `treasure_reroll` / `gate_resolve` / `dismiss` |
| `sink_type` | `scout` / `heal_small` / `heal_large` / `gate_guarantee` / `attack_boost`（`treasure_reroll` は専用ルート） |
| `phase` | §6.1（実装10種＋pause将来） |

- `experience` の正準キーは **romaji enum**（`grind`/`gamble`/`race`/`dodge`/`chaos`）。表示名（削り合い/賭け/レース/ずれ/カオス）は `labels.ts` の EXPERIENCE で変換する（v1.4 で OPEN-012 解消。受入条件「日本語が API/統計キーに出ない」を loader.validate でも強制）。

### 20.8 pending の phase別スキーマ（実装準拠）

`pending` は phase 固有の保留データ（React に計算させないための表示専用値を含む）：

| phase | pending の内容 |
|-------|------|
| `treasure_preview` | `{ node, [source="enemy", victory] }` |
| `treasure_opened` | `{ mod, count }`（count=スタック段階） |
| `heal` | `{ heal, big }` |
| `gate_preview` | `{ table, damage }`（現確率テーブル＋結果別の被ダメ実値） |
| `next_floor` | `{ gate_outcome, advanced_to, special_bonus }` |
| `cleared` | `{ gate_outcome, special_bonus }` |
| 空宝箱 / 勝利 | `{ empty_treasure }` / `{ victory }` |

> **dismiss との対応（要確定）**：`empty_treasure`・`victory` がどの phase に属し、どの操作（`/continue` か次操作での自動消去か）で解消されるかは本書未定義。実装準拠の追記が必要（OPEN-013 の契約検査とあわせて確定）。

---
