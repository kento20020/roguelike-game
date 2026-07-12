# アーキテクチャ（Architecture）
> 元 `game_design_document.md`（分割時点 v1.2）の §0.1・§0.2・§17・§22・§23 を再配置。相互参照の §番号は元GDD準拠。

---

### 0.1 文書管理

| 項目 | 内容 |
|------|------|
| 文書名 | カジノタワー・ローグライト ゲーム仕様定義書 |
| ファイル | `docs/game_design_document.md`（**バージョンレス固定名**・インデックス。実体は分割 `docs/*.md`） |
| 現行版 | [changelog.md](changelog.md) **先頭エントリを正**とする（この表には版番号を書かない・構成監査 F-03 で一元化） |
| ステータス | 実装フェーズ移行可能 |
| 対象読者 | ゲーム/UI実装者、データ調整担当、レビュワー |
| 技術構成 | React + TypeScript + Vite / FastAPI / SQLite |
| 正本データ | `backend/app/data/*.json`（§20.5） |
| 関連文書 | 本書 / API実形=`engine.snapshot()` / `backend/app/simulation/INTEGRATION.md` |

> **版管理ルール（齟齬防止・分割後の構成に対応）**：設計書群の**ファイル名はバージョンを含めず固定**。版の正本は **[changelog.md](changelog.md) の先頭エントリ**の1箇所のみ。インデックス（`game_design_document.md`）冒頭の版バナーはそれに追随し、一致を doc-CI（`scripts/check_docs.py`）が機械検査する。**バージョンを上げてもファイル名・参照リンクは変更しない**ため、CLAUDE.md・README 等の参照が版ごとにズレることがない。
> **版 bump 手順（部分更新の禁止）**：版を上げるときは「①changelog.md へのエントリ追加・②インデックス冒頭バナーの更新」を**同一コミットで一括更新**する。片方だけ先行して書き換えない（doc-CI が不一致を fail させる。旧・単一ファイル時代に変更履歴だけ先行して版表記が割れた事例、および分割後に版表記が v1.2/v1.3/v1.5/v1.8 の4枝へ割れた事例＝構成監査 2026-07-11 の再発防止）。この2箇所以外のファイルには**現行版の版番号を直書きしない**（「v1.9 で追加」等の来歴注記は可。現行版は changelog への参照で示す。直書きは doc-CI が検出して fail）。作業途中の版は変更履歴に `(WIP)` と明記する。

### 0.2 正本（source of truth）の優先順位

本書・JSON・コードで記述が食い違った場合、**何を真実とみなし、どちらを直すか**を以下で固定する。

| 対象 | 正本 |
|------|------|
| 設計意図・体験設計・状態遷移・ルールの構造 | **本書（GDD）** |
| 数値（戦闘係数・確率・敵パラメータ・sink・恒久強化） | **`backend/app/data/*.json`** |
| APIレスポンスの実形・フィールド名 | **`engine.snapshot()` / `backend/app/schemas`（Pydantic）** |

- ドリフトを検知したら、上表の**正本でない側を修正**し、巻末「変更履歴」に記録する。
- 本書本文の数表（敵HP表・ゲート確率表など）は**要約・参考**であり、実装は必ずJSONを読む（§20.5）。
- 「矛盾ゼロ」を保証する運用はしない。代わりに**機械検証**でドリフトを検出する。検証器は `backend/app/data/loader.py` の `GameData.validate()`（データロード時に必ず走る fail-fast）＝**実在**。検査項目：敵ID一意／非カオス敵の behaviors weight 合計=100／カオス敵は behaviors 空＋`chaos:true`／`ramp_hit` を持つ敵は `ramp_increment` 必須／mod ID一意／floor の pool ID が実在／アンロック親整合（多親=2親・単親=1親・親の実在）。pytest（`backend/tests/`）でも同じ不変条件を回帰する。
- **未カバーの検査（OPEN-013）**：ゲート確率合計=1.0／dead-end に敵を置かない kind 整合／5F row3→ゲート経路≥2／恒久強化の上限Lv合計=21 は現 `validate()` に無い（§20.5 の検査項目へ追加予定）。
- **design/（Claude Design 作業ファイル）は正本ではない**（v1.9 明記）：`design/*.dc.html`・`design/spec_*.md` は UI 制作フロー（CLAUDE.md「画面は Claude Design で作る」）の**入力・検討記録**であり、React 化された時点で画面仕様の正本は frontend_design.md（構成・責務）＋実装（視覚の実体）へ移る。doc-CI の検査対象外。design/ と frontend_design.md が食い違ったら frontend_design.md＋実装を正として design/ 側は更新しない（作業履歴として残す）。

---

## 17. 乱数アーキテクチャ

### 17.1 アルゴリズム
- **SFC32**（32bit）をPython・TypeScript双方で同一実装
- 同一シードで同一結果を黄金テストで確認
- **SFC32 はゲーム再現用**（決定論）であり、**秘密・トークン生成には使わない**（暗号用途ではない）。session_id 等の秘密は `secrets` 等で別途生成する

### 17.2 ドメイン別独立ストリーム

| ID | 用途 |
|:--:|------|
| 0 | フロア生成（ツリー・ノード配置） |
| 1 | 敵プール抽選 |
| 2 | 行動テーブルロール |
| 3 | 宝箱mod抽選 |
| 4 | 回復ノード（大/小） |
| 5 | ゲートイベント結果 |
| 6 | **floor_topology（フロア接続トポロジー生成・v1.4）** |
| 7 | 汎用 |
| 8 | **chaos（カオス敵の行動比率決定）** |

> **消費契約（実装準拠）**：`floor_generator` は stream0（FLOOR）で終端単親dead-endの宝箱presence、stream1（ENEMY_POOL）で敵配置shuffle（袋方式）、stream4（HEAL）で回復ノード選択、**stream6（TOPOLOGY）でrow幅・接続ステアケース・dead-end配置**、**stream7（GENERAL）で多親敵の撃破ドロップpresence**を引く。戦闘は stream2（BEHAVIOR）、宝箱の中身mod抽選は stream3（TREASURE）、ゲート結果は stream5（GATE）、カオス比率は stream8（CHAOS・敵あたり4回・id昇順）。
> **stream6 の転用（v1.4）**：旧「stance予約」枠を接続トポロジー生成に転用した（9本不変条件を維持・新規10本目を増設しない）。フェーズB（スタンス）を将来実装する場合は新たな乱数設計を OPEN-006 で行う。
> **サイドベット『読み宣言』の判定（§15.4）**：そのターンの stream2 の既存ロール結果（`res["action"]`）をそのまま使い、**新規RNG消費はゼロ**（消費契約を変えない）。
> **先読みの消費（yomi/scout）**：yomi は `prepare_preview` が **stream2 から次行動を先引きしてキャッシュ**（`pending_action`）し、実ターンの `resolve_turn` がそのキャッシュを消費する（＝先読みが嘘にならない・二重消費しない）。scout は `top_behavior`（最大weightの示唆）を返すだけで**RNGを消費しない**。
> **stream7（汎用）の用途限定**：現状は多親敵の撃破ドロップpresenceに使用。再現性に影響する新用途は専用ストリームを割り当て、汎用へ混ぜない（§17.1「ストリームを混ぜない」）。

### 17.3 シード管理・ストリーム導出（実装準拠）
- 各ストリームは master seed から **`derived = master_seed ^ (stream_id × 0x9E3779B9)`（32bitマスク）** で種を分け、`Sfc32(derived)` を構成する（splitmix32 で a,b,c,d を充填 → 15回 warmup）。互いに独立。
- SFC32 本体・種導出・warmup 回数を含め **Python/TS で同一実装**にし、golden vector（`tests/test_rng.py`）へ一致させる（TS版の用途は §18.5）。
- botシミュレーションは固定シードパネル（seed 0〜999）で再現性を担保。
- **seed の範囲・生成**：`0 ≤ seed ≤ 2^32−1`（Pydantic `conint(ge=0, le=2**32-1)` で検証推奨）。未指定時はサーバが `secrets.randbits(32)` で生成。
- **seed・rng_streams は API 出力に含めない**（不変条件）。`RunRecord.seed` はラン**終了後**にのみ現れる（進行中は snapshot.run_record=null のため seed は露出せず、seed-scum を防ぐ）。`snapshot()` にも含まれず、同一SFC32実装で全ロールを事前計算されて暗黙知/スカウト経済が崩れるのを防ぐ。**スナップショットテストで非存在を assert 済み（v1.4 実装・`tests/test_invariants.py`。一時期この不変条件が実装で破れていたのを修復）**。`run_id` はseedとは独立に `uuid.uuid4()` から生成する一意ID（`"run-{uuid4}"`）で、同一seedの複数ランでも衝突しない（`RunRecordRow`/`PostmortemRow`/`RunActionsRow` ともにunique制約）。

---

## 22. 技術スタック仕様

### 22.1 全体構成

```
┌─────────────────────────────────────────┐
│  React + TypeScript + Vite (Frontend)    │
│  ┌────────────────────────────────────┐  │
│  │ Zustand (状態管理)                  │  │
│  │ Tailwind + clsx (スタイリング)      │  │
│  │ gameApi.ts (API通信を1ファイル集約) │  │
│  └──────────────┬─────────────────────┘  │
└─────────────────┼────────────────────────┘
                  │ REST API (HTTP/JSON)
                  ▼
┌─────────────────────────────────────────┐
│  Python + FastAPI (Backend)              │
│  ┌────────────────────────────────────┐  │
│  │ GameEngine (ゲームロジック)         │  │
│  │ FloorGenerator / CombatResolver     │  │
│  │ SQLAlchemy (ORM)                    │  │
│  └──────────────┬─────────────────────┘  │
└─────────────────┼────────────────────────┘
                  ▼
          ┌──────────────┐
          │ SQLite       │ ← 将来PostgreSQL移行
          │ (game.db)    │
          └──────────────┘
```

### 22.2 技術選定一覧

| レイヤー | 技術 | 選定理由 | 将来の移行先 |
|---------|------|---------|------------|
| フロントエンド | React + TypeScript + Vite | デファクト・起動が速い | — |
| 状態管理 | Zustand | 11phaseの管理に強い・2KB軽量 | + TanStack Query |
| スタイリング | Tailwind + clsx + CSS Variables | テーマ一元管理・ランタイムコストゼロ | — |
| バックエンド | Python + FastAPI | Swagger自動生成・型安全・非同期 | — |
| ORM | SQLAlchemy | DB切り替えがコード変更最小 | — |
| DB | SQLite | 設定ゼロ・ローカル開発に最適 | PostgreSQL |
| 通信 | REST API | ターン制と相性◎・botと同じエンジンを使える | — |
| リポジトリ | モノレポ | 管理が楽・ポートフォリオで見せやすい | — |

### 22.3 設計原則（移行容易性の確保）

実装開始時点から以下を守ることで、将来の技術移行コストを最小化する。

| 原則 | 目的 |
|------|------|
| ゲームロジックは全てPython。Reactは計算・勝敗判定しない | botシミュレーターとUIで同じエンジンを共有 |
| UIは `available_actions` を**操作可否の正本**にする | フロントの条件分岐を排し、含まれない操作は非表示/disabled（§25.3） |
| phase不整合の拒否はサーバ側で必ず行う（§25.4） | クライアント改ざん・不正遷移への防御 |
| API通信は `gameApi.ts` に集約（直接fetchしない） | TanStack Query移行時にこのファイルだけ変更 |
| DB操作はSQLAlchemy経由（生SQLを書かない） | PostgreSQL移行コストを最小化（型・並行性差＝JSON列/`server_default`/autoincrement 等の検証は別途必要。「1行で移行」は楽観表現のため撤回） |
| ダメージ計算は `attack × multiplier` で記述 | フェーズB（stance）追加に備える |
| uvicorn は **workers=1（単一ワーカー）**で運用する | 同一 `session_id` への複数ワーカー同時書き込み競合は未ハードニング（[runbook.md](runbook.md) §1）。※v1.3 で明文化済みの制約が分割時に脱落していたため復元 |

---

## 23. ディレクトリ構成

```
game-roguelike3/
├── README.md
├── docs/
│   └── game_design_document.md          # 本書（バージョンレス固定名・版はタイトル/変更履歴で管理）
│
├── frontend/                            # React + TypeScript + Vite
│   ├── package.json
│   ├── tailwind.config.ts               # カジノテーマカラー一元定義
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                      # phaseによるPage切り替え
│       │
│       ├── api/
│       │   ├── gameApi.ts               # API通信を集約（将来TanStack Query化）
│       │   └── types.ts                 # APIの型定義（バックエンドと共有）
│       │
│       ├── store/
│       │   └── gameStore.ts             # Zustand：ゲーム状態（RunRecord含む）
│       │
│       ├── lib/
│       │   ├── labels.ts                # 表示ラベル定義
│       │   └── sfx.ts                   # 効果音（ミュート設定の保存を内包）
│       │
│       ├── hooks/
│       │   ├── useCombatFx.ts           # 被弾・強打などの戦闘演出
│       │   ├── useChipFx.ts             # チップ増減演出
│       │   └── useSideBet.ts            # サイドベットの状態・派生値
│       │
│       ├── pages/                       # phaseごとのフルスクリーン
│       │   ├── StartPage.tsx
│       │   ├── ExploringPage.tsx
│       │   ├── BattlePage.tsx
│       │   ├── TreasurePage.tsx         # treasure_preview / treasure_opened（ModReveal統合）
│       │   ├── HealPage.tsx
│       │   ├── GatePage.tsx             # gate_preview / gate_resolve
│       │   ├── NextFloorPage.tsx
│       │   ├── ClearedPage.tsx
│       │   ├── DeadPage.tsx             # 検死レポート/リプレイの2タブを内包
│       │   └── DossierPage.tsx          # ディーラー調書（観測記録）
│       │
│       └── components/
│           ├── common/                  # 複数phaseで再利用
│           │   ├── Header.tsx           # チップ残高・所持mod一覧を内包
│           │   ├── HpBar.tsx
│           │   ├── SinkMenu.tsx         # スカウト・回復（常時表示）
│           │   ├── BehaviorGlossary.tsx # 敵behaviorの用語解説
│           │   ├── CenterStage.tsx      # 中央演出ステージ
│           │   ├── EmberBackground.tsx  # 背景演出
│           │   ├── ErrorToast.tsx       # APIエラー表示
│           │   ├── Icon.tsx
│           │   └── Motif.tsx            # 装飾モチーフ
│           ├── exploring/
│           │   ├── TreeCanvas.tsx       # ツリー構造の描画（nodes+parentsから辺を描画）
│           │   └── NodeCard.tsx         # 敵/宝箱/回復/ゲートノード（強敵・体験タイプ表示を内包）
│           ├── battle/
│           │   ├── CombatPanel.tsx      # 戦闘画面のオーケストレーション
│           │   ├── EnemyStage.tsx       # 敵肖像・HP・ramp蓄積バッジ
│           │   ├── NextActionPreview.tsx# 先読み/テル/スカウト表示
│           │   ├── PlayerStatusBar.tsx  # 自分パネル（HP・攻撃力・被弾演出）
│           │   ├── SideBetPanel.tsx     # サイドベットUI
│           │   └── CombatLog.tsx        # 全ログ保持・スクロール
│           ├── dead/                    # 検死レポート/リプレイの部品
│           ├── dossier/                 # 調書の部品（敵カード・ソート等）
│           └── result/
│               ├── ResultSummary.tsx    # 到達フロア・ターン数・mod一覧（死亡/クリア共通）
│               └── UpgradeAllocator.tsx # 恒久強化割り振り
│
└── backend/                             # Python + FastAPI
    ├── requirements.txt
    ├── main.py                          # FastAPIエントリポイント
    └── app/
        ├── api/
        │   ├── routes.py                # エンドポイント定義（§25）
        │   └── deps.py                  # 依存性注入（セッション取得。キャッシュミス時はDB再生にフォールバック）
        ├── session_store.py             # セッション管理（LRU上限つきホットキャッシュ。真の永続はactive_sessions）
        ├── engine/
        │   ├── game_engine.py           # ゲーム状態の中核（phase遷移・アクション受付）
        │   ├── snapshot.py              # APIスナップショット/ノードビュー構築（表示層）
        │   ├── floor_generator.py       # あみだくじ格子生成（可変深度・§4.2）
        │   ├── combat_resolver.py       # 戦闘1ターンの解決
        │   ├── gate_resolver.py         # ゲートイベント
        │   ├── postmortem.py            # 検死レポート（致命ターンの反実仮想解析）
        │   ├── tells.py                 # テル（気配）の判定
        │   ├── replay.py                # アクションログ再生（OPEN-007・進行中ラン復元）
        │   ├── chaos_weights.py         # カオス敵のラン別比率決定
        │   └── rng.py                   # SFC32（9ストリーム）
        ├── data/
        │   ├── loader.py                # JSONデータ読み込み
        │   ├── enemies.json             # 敵プール（§11.3）
        │   ├── mods.json                # mod定義（§10.1）
        │   ├── floors.json              # フロア構成・アンロックルール
        │   └── config.json              # 数値パラメータ（データ駆動調整対象）
        ├── db/
        │   ├── models.py                # SQLAlchemyモデル（RunRecord/ActiveSession等）
        │   ├── session.py               # DB接続（SQLite・WAL mode／PostgreSQL切り替え点）
        │   └── crud.py                  # DB操作
        ├── schemas/
        │   ├── api_schemas.py           # Pydanticモデル（リクエスト/レスポンス）
        │   └── models.py                # ドメインモデル
        └── simulation/                  # 既存のbot/統計ツール（再利用）
            ├── phase12_harness.py
            ├── bots.py                  # botプレイヤー
            ├── balance_stats.py
            ├── balance_analysis.py
            ├── balance_report.py
            ├── fun_metrics.py
            └── gen_baseline.py
```

> **重要**：`backend/app/simulation/` に既存の統計ツール群を配置。`game_engine.py` をbotシミュレーターとAPIの両方から呼べる構造にすることで、UIとbotで同じロジックを共有する。
> **テスト構成**：`backend/tests/`（`test_combat.py`・`test_rng.py`・`test_*` ＋ golden fixture）。Python/TS が共有する golden（seed→期待スナップショット列）は `tests/` 配下に置き、両実装で同一 seed の RNG 出力を突き合わせる（§17.3・§18.5）。
> **運用の未整備（OPEN-027）**：DBマイグレーション（Alembic）・デプロイ/ロールバック手順・game.db バックアップ・構造化ログ＋req_id・`.env.example`（設定外出し）・CIワークフロー実体・`GET /health` は本書のディレクトリに未反映。ポートフォリオ〜小規模本番向けの最小構成（単一コンテナ＋SQLiteボリューム＋静的配信）を別途 `docs/RUNBOOK.md` 等へ整備する。本改訂はコードを変更しないため OPEN-027 として記録（実装は別タスク）。
