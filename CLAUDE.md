# CLAUDE.md — カジノタワー ローグライト

確率ベースの戦闘を核にした、カジノタワーを登り詰める5フロアのパーマデス制ローグライト。
React(表示) + FastAPI(全ロジック) のモノレポ。**詳細設計は `docs/game_design_document_v1.0.md` が正本。**

---

## 🛠 コマンド（最優先で参照）

### Backend (`backend/`)
- セットアップ: `pip install -r requirements.txt --break-system-packages`
- 起動: `uvicorn main:app --reload`
- テスト: `pytest`
- 単一テスト: `pytest tests/test_combat.py -v`
- botシミュレーション: `python -m app.simulation.phase12_harness`

### Frontend (`frontend/`)
- セットアップ: `npm install`
- 起動: `npm run dev`
- ビルド: `npm run build`
- lint: `npm run lint`
- 型チェック: `npm run typecheck`

---

## 🤝 作業の進め方（重要）

- **画面（UI）は Claude Design で作る。** デザインは Claude Design プロジェクトで `.dc.html` として作成し、`design/` に取り込んでから React コンポーネント化する。レイアウト/見た目を白紙から手書きで起こさない。
- **実装前に必ず確認の質問をする。** 設計に曖昧さがあれば、コードを書く前に質問する。勝手に解釈して進めない。
- **エンジンのロジックは必ずテストを書く（TDD寄り）。** 実装より先にテストを書く。
- **着手順序は backend/engine から。** ロジックを先に固め、botシミュレーションで検証してからUIに進む。
- 数値バランスはデザイナー（人間）が決める。統計指標は「合格条件」であって「最適化目標」ではない（Goodhart回避）。

---

## 🏗 アーキテクチャの絶対原則

これらは違反すると設計全体が崩れる。必ず守る。

1. **ゲームロジックは全てPython。Reactは一切計算しない。** Reactはバックエンドの結果を表示するだけ。
2. **同じ `game_engine` をAPIとbotシミュレーターの両方が呼ぶ。** UI用とbot用でロジックを分岐させない。
3. **API通信はフロントの `src/api/gameApi.ts` に集約。** コンポーネントから直接 `fetch` しない（将来TanStack Query移行のため）。
4. **DB操作はSQLAlchemy経由。** 生SQLを書かない（将来PostgreSQL移行のため）。
5. **ダメージ計算は必ず `attack × multiplier` の形で書く。** attackを直接使わない（フェーズB=スタンス追加のため）。multiplierは複数ソースの乗算。
6. **各レスポンスは完全なゲーム状態を返す。** フロントに差分計算をさせない。

---

## 📦 データファイルが正本（`backend/app/data/`）

全ての数値は以下のJSONに集約されている。**GDD本文の数表は要約。実装は必ずJSONを読む。**

- `config.json` — 全体パラメータ（戦闘係数・ramp初期値・sink・恒久強化・RNG定義）
- `enemies.json` — 全36体（behaviors weight・ramp_increment・gold_base・chaosフラグ）
- `mods.json` — 6種mod＋インタラクション。**mod の効果文（`effect_1`/`effect_stack`）は UI 表示の正本**。API `GET /api/catalog/mods` がこれを返し、フロントは重複定義せずカタログを使う
- `floors.json` — 5フロア構成・アンロック連鎖・ゲートテーブル

係数のフォールバック: `enemy.get("heavy_factor", config["heavy_factor"])`。敵が個別値を持てば優先、無ければconfig既定。

---

## 🚫 勝手に変更してはいけないファイル

以下は人間のレビューなしに数値や構造を変えない。変更が必要なら必ず質問する。

- `backend/app/data/*.json` — バランスの正本。勝手に数値を書き換えない
- `docs/game_design_document_v1.0.md` — 設計の正本
- `backend/app/engine/rng.py` — SFC32実装。seed再現性を壊さない

---

## ⚖️ 壊してはいけない不変条件

実装・テストで必ず保つ制約。

- **behaviors の weight 合計は常に100**（カオス系を除く。カオスは `chaos:true` でbehaviors空）
- **乱数は9本の独立ストリーム**（用途はconfig.jsonの `rng_streams`）。ストリームを混ぜない
- **同一seed → 同一結果**（Python/TS両実装で黄金テストを通す）
- **アンロック連鎖**: 多親=隣接2体から解放、単親=1体から解放（dead-endは必ず単親）
- **combat_logとRunRecordは別物**。combat_log=表示専用・使い捨て、RunRecord=統計専用・永続。**同期しない**
- **ramp計算**: `ramp_value(n) = base_initial(5) + ramp_increment × (n-1)`
- **ゲート保証**: 大ダメのみ削る・特殊は維持・重ねがけは効果半減＋コスト微増

---

## 📐 コーディング規約（リンターで強制できない方針のみ）

- **Backend**: 型ヒント必須。Pydanticでリクエスト/レスポンスを定義。エンジンは純粋関数寄りに（副作用を集約）
- **Frontend**: 関数コンポーネント＋TypeScript。状態はZustand（`src/store/`）。スタイルはTailwind + clsx
- **命名**: ファイルはComponentがPascalCase、それ以外はsnake_case(py)/camelCase(ts)
- **エラー**: 非同期は必ず try/catch。APIエラーは400(不正操作)/404(session無し)/409(phase不整合)

（フォーマットはリンター任せ。ここには書かない）

---

## 🔄 ワークフロー

- コミットは `feat:` / `fix:` / `test:` / `docs:` を接頭辞に
- PRは `pytest` と `npm run typecheck` を通してから
- 新機能は「テスト→エンジン実装→API→UI」の順
- phaseを増やすときは §6 の状態遷移図を更新してから実装

---

## 📚 詳細の参照先

迷ったらインラインで推測せず、以下を読む。

- 戦闘フロー・ダメージ式 → GDD §8
- アンロック連鎖の全形状マッピング → GDD §4.2
- game_phase 状態遷移 → GDD §6
- APIエンドポイント仕様 → GDD §25（§25外の追加: `GET /api/catalog/mods`＝技の効果文カタログ、`POST /api/run/{sid}/guard`＝戦闘の受け）
- コンポーネント構成 → GDD §24
- バランス検証フェーズ → GDD §18
