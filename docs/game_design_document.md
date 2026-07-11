# ゲーム設計書（インデックス） — カジノタワー ローグライト

> **v1.9**（設計書ギャップ監査反映。現行版の正本は [changelog.md](changelog.md) 先頭エントリ）。本書は従来1ファイルに集約していた設計書を役割別に分割した**目次（インデックス）**です。各内容は下記の分割ファイルが正本。相互参照の §番号・OPEN-xxx は分割前の番号を維持しています。
> 数値の正本は `backend/app/data/*.json`（config/enemies/mods/floors）。API実形は `engine.snapshot()` / Pydantic（`backend/app/schemas`）。

確率ベースの戦闘を核に、**カジノタワーを登り詰める**5フロアのパーマデス制ローグライト。React(表示) + FastAPI(全ロジック) のモノレポ。ゲームロジックはすべて Python 側に集約し、同じエンジンを API と bot シミュレーションの両方が呼ぶ。

## ドキュメント構成（最初に読む順の目安）

| ファイル | 内容 | 元GDD節 |
|---|---|---|
| [product_requirements.md](product_requirements.md) | 何を作るか・ユーザー価値（コンセプト / ループ / 3本柱 / 世界観 / スコープ） | §0.4, §1–§3, §16 |
| [game_design.md](game_design.md) | ゲーム仕様（フロア / 情報開示 / ノード / 戦闘 / 体験タイプ / mod / 敵 / 恒久強化 / 経済 / チュートリアル / 用語集） | §0.5, §4–§5, §7–§14 |
| [architecture.md](architecture.md) | 全体アーキテクチャ・文書統治・正本優先度・乱数アーキ・技術スタック・ディレクトリ | §0.1–§0.2, §17, §22–§23 |
| [api_contract.md](api_contract.md) | API契約（エンドポイント / GameState / エラー / 型共有） | §25 |
| [frontend_design.md](frontend_design.md) | 画面・コンポーネント・UI責務・死亡/クリア画面 | §15, §24, §26 |
| [backend_design.md](backend_design.md) | 状態遷移(phase)・ランタイム状態・ドメインロジック方針 | §6, §20.4 |
| [data_model.md](data_model.md) | DB・永続化・RunRecord・データモデル・通貨正準 | §0.3, §19, §20（除 §20.4） |
| [operations.md](operations.md) | バランス検証・未決事項（OPEN-001〜044）・運用方針 | §18, §21 |
| [runbook.md](runbook.md) | 障害時手順（骨子・多くは OPEN-027 で未整備） | — |
| [changelog.md](changelog.md) | 変更履歴（v0.6〜現行。**現行版の正本＝先頭エントリ**） | 付録 |
| [adr/](adr/) | アーキテクチャ決定記録（FastAPI / サーバ権威 / SQLite先行） | §22 由来 |
| [schemas/](schemas/) | データ正本ミラー＋API例JSON（config/enemies/mods/floors ＋ gamestate/battle/mod_interactions） | §10.4, §25.3 |
| [proposals/](proposals/) | 改善アイディア集（**提案・正本ではない**。採用時はクラスSとして正本へ反映してから実装） | — |

## 正本の優先順位（要約）

| 対象 | 正本 |
|------|------|
| 設計意図・体験設計・状態遷移・ルール構造 | 上記の分割 `docs/*.md` |
| 数値（戦闘係数・敵・sink・恒久強化） | `backend/app/data/*.json` |
| APIレスポンスの実形・フィールド名 | `engine.snapshot()` / `backend/app/schemas`（Pydantic） |

詳細な文書統治・版管理ルール・正本優先度は [architecture.md](architecture.md)（§0.1–§0.2）を参照。
開発運用ルール（ブランチ / PR / 変更クラス / 課題管理）は [CONTRIBUTING.md](../CONTRIBUTING.md) を参照。

> 分割前の単一ファイル版（全内容を1ファイルに集約）は git 履歴で参照可能（このコミット以前）。ファイル名 `game_design_document.md` は固定のまま（CLAUDE.md / AGENTS.md / README の参照はこのインデックスに着地する）。
