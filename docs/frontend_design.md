# フロントエンド設計（画面・状態管理・UI責務）
> 元 `game_design_document.md`（v1.2）の §15・§24・§26 を再配置。フロントは計算せずバックの完全状態を表示する（原則は architecture.md 参照）。相互参照の §番号は元GDD準拠。

## 15. 死亡・クリア画面

### 15.1 死亡画面

| 表示項目 | 内容 |
|---------|------|
| 到達フロア | 何フロアまで登ったか |
| 総ターン数 | **戦闘ターンの総和**（`RunRecord.total_turns`・§19.1。ラン全体の経過ターンではない） |
| 取得mod一覧 | 集めたmod |
| 死亡原因 | 死亡敵・行動（`death_cause`）または `gate:結果`（ゲート死） |
| 獲得/消費チップ | `gold_earned` / `gold_spent` 合計 |
| 強敵撃破数 | `enemies_defeated` のうち強敵の数 |

> コピー軸：「全てを賭けた一勝負」に届かなかった敗北を演出。次への学習を促す。「知識が報われる」（§3③）ため、死亡原因は必須表示。
> **データソース**：結果画面は**確定済み RunRecord** を表示（進行中 GameState ではなく、統計と表示のズレを防ぐ・§15.3）。

### 15.2 クリア画面

| 表示項目 | 内容 |
|---------|------|
| 総ターン数 | 戦闘ターンの総和（§19.1 `total_turns`） |
| 取得mod一覧 | 集めたmod |
| → 恒久強化割り振り | そのままポイント配分画面へ遷移 |

### 15.3 拡張性

表示項目はリスト定義。後から「最大連勝記録」「獲得ゴールド合計」等を追加するだけで増やせる。

---

## 24. コンポーネントリスト

> **実装メモ（実装に追随）**：下記は設計上の理想分割。実装では機能等価のまま一部を統合している。
> `GoldDisplay`/`ModInventory` は `Header` に内包、`RampIndicator` は `CombatPanel` に内包、`TreasurePreview`/`ModReveal` は `TreasurePage` に統合、`UpgradeAllocator` は `components/result/` に実装し `ClearedPage` に組込。`ScreenTransition` は CSS アニメーションで代替（独立コンポーネント未実装）。`EnemyIndicator` 相当は `NodeCard` に内包。`TreeCanvas` は `nodes`(dict)+各ノードの `parents` から辺を描画（`edges` 配列は持たない）。

### 24.1 共通コンポーネント（components/common/）

| コンポーネント | props | 使用phase | 説明 |
|------------|-------|----------|------|
| `HpBar` | `current, max` | 常時 | HP残量バー。50/20%で色変化 |
| `GoldDisplay`（実装ではHeaderに内包） | `chips` | 常時 | チップ残高表示 |
| `ModInventory` | `mods` | 常時 | 所持mod一覧。**アクティブシナジー表示は非スコープ**（`active_interactions` は snapshot に無い＝React に計算させない。表示するなら Python 側で付与・§10.4） |
| `SinkMenu` | `chips, phase, available_actions` | 常時 | 表示可否は `available_actions` に従う（§22.3）。スカウト/攻撃ブースト=battle、ゲート保証=gate_preview、回復=常時。**リロールは `/sink` 非対応＝専用ルート**のため SinkMenu には出さず TreasurePreview の onReroll に一本化 |
| `ScreenTransition` | `phase, children` | 全phase | phase切り替えアニメーション |

### 24.2 探索（components/exploring/）

| コンポーネント | props | 説明 |
|------------|-------|------|
| `TreeCanvas` | `nodes, onSelect` | ツリー構造の描画。辺は各ノードの `parents` から描く（`edges` 配列は持たない） |
| `NodeCard` | `node, onClick` | 各ノード（`state`/`experience` は `node` 内包を参照＝二重供給しない）。体験タイプで枠色変化 |
| `EnemyIndicator` | `difficulty, experience` | 強敵マーク・体験タイプアイコン |

### 24.3 戦闘（components/battle/）

| コンポーネント | props | 説明 |
|------------|-------|------|
| `CombatPanel` | `enemy, player, onAttack` | 敵HP・プレイヤー情報・攻撃ボタン |
| `CombatLog` | `log` | 全ログ保持・スクロール（デフォルト8行表示） |
| `RampIndicator` | `value, max` | ramp蓄積値。高いほど警告色・点滅 |

### 24.4 宝箱（components/treasure/）

| コンポーネント | props | 説明 |
|------------|-------|------|
| `TreasurePreview` | `chips, onOpen, onReroll` | 開封/リロール（30G）選択（props は `gold`→`chips` に整合） |
| `ModReveal` | `mod` | 開封演出・mod効果表示 |

### 24.5 結果（components/result/）

| コンポーネント | props | 説明 |
|------------|-------|------|
| `ResultSummary` | `floorReached, totalTurns, mods` | 到達フロア・ターン数・mod一覧（死亡/クリア共通） |
| `UpgradeAllocator` | `points, upgrades, onAllocate` | 恒久強化ポイント割り振り |

### 24.6 Pages（pages/）

| Page | 対応phase | 主な子コンポーネント |
|------|----------|------------------|
| `StartPage` | （phase外・session未生成） | 新規ラン開始（`POST /run/new`）。GameState/phase 不在の初期画面＋[調書を見る]（DossierPage へ） |
| `DossierPage` | （phase外・ラン中は不可） | ディーラー調書（§15.3）。`/profile/dossier`＋`/catalog/enemies` を store 経由で取得し、観測頻度＋Wilson CI をカード表示。「テーブルへのメモ持ち込み禁止」の世界観でラン中は閲覧不可 |
| `ExploringPage` | exploring | TreeCanvas, NodeCard, SinkMenu, ModInventory |
| `BattlePage` | battle | CombatPanel（攻撃/受け/サイドベット『読み宣言』ベットスポット・§15.4／テル気配表示・§15.5）, CombatLog, RampIndicator, SinkMenu |
| `TreasurePage` | treasure_preview / treasure_opened | TreasurePreview, ModReveal |
| `HealPage` | heal | HpBar（回復演出）＋[確認]（`/continue`） |
| `NextFloorPage` | next_floor | 次フロア演出＋[次の階層へ]（`/continue`） |
| `GatePage` | gate_preview | ゲート保証sink（**gate_resolve は瞬間phaseで滞在しない**・§6.1。結果は `pending.gate_outcome` を NextFloorPage / ClearedPage / DeadPage 側で表示・§20.8） |
| `DeadPage` | dead | ResultSummary＋**検死レポート（PostmortemCard）＋リプレイ（ReplayDisclosure/TurnRow）**（§15.2・`GET /run/{sid}/postmortem`。関門死は404=非表示。データ取得は gameStore に集約） |
| `ClearedPage` | cleared | ResultSummary, UpgradeAllocator（`/profile/upgrades`・`/upgrade`） |

> **App.tsx の描画分岐**：通常は `phase` で Page を切り替えるが、**session 未生成時は phase 不在**のため `StartPage` を phase 外の前段ルートとして扱う（session 生成後は phase 駆動。`dossierOpen` 時は DossierPage）。`next_floor` の演出 Page（NextFloorPage）は §6.1 の現役 phase で、[次の階層へ]=`/continue`。
> **§24 表の粒度（v1.4 注記）**：上記は設計時のコア構成。実装では共通部品（Header/ErrorToast/Icon/Motif/GlowTitle/FloorProgressDots/CenterStage/EnemyPortraitCard/BehaviorGlossary/EmberBackground/MuteToggle）・hooks（useChipFx/useCombatFx）・lib（labels/sfx）が追加されている（`design/spec_*.md` 由来の視覚拡張。網羅列挙は実装を正とする）。
> **L3マスク（v1.4・OPEN-015）**：未インタラクトの敵ノードには `name`/`max_hp` が来ない。NodeCard は名前を「賭博者」でフォールバック表示する。
> **lint（v1.4）**：eslint（flat config・typescript-eslint＋react-hooks）を導入済み。`npm run lint` を PR 前チェックに含める。

---

## 26. 画面設計

> フルスクリーン切り替え方式。各phaseが画面全体を占める。
> 共通コンポーネント（HpBar・GoldDisplay・ModInventory・SinkMenu）は各phaseの上部または側部に配置。

### 26.1 ExploringPage（探索）

```
┌──────────────────────────────────────────────┐
│ [HP ████░░ 80/100]  [💰45]  [Mod: 反射 見切り] │ ← 共通ヘッダー
│                                    [回復 ▼]    │ ← SinkMenu（探索中はスカウト非表示）
├──────────────────────────────────────────────┤
│                  2F                            │
│                 ┌─────┐                        │
│                 │GATE │  ← ゲート（画面上＝頂上）│
│                 └──▲──┘                        │
│                    │                           │
│      ┌────┐ ┌────┐ ┌────┐ ┌────┐             │
│      │ ?? │ │ ?? │ │ ?? │ │ ?? │ ← row2（ロック）│
│      └──▲─┘ └▲─▲─┘ └─▲──┘ └────┘             │
│        │    ╲   │  ╱    ╲  │                   │
│      ┌─┴──┐    ┌┴─┴─┐    ┌─┴──┐               │
│      │⚔️ │    │🎲 │    │⏫ │  ← row1（選択可・画面下）│
│      └────┘    └────┘    └────┘               │
└──────────────────────────────────────────────┘
（描画方向は§4：row1が画面下、ゲートが画面上。プレイヤーは下から上へ登る）
```

### 26.2 BattlePage（戦闘）

```
┌──────────────────────────────────────────────┐
│ [HP ████░░ 80/100]  [💰45]  [Mod: 反射 見切り] │
│                                    [スカウト▼] │
├──────────────────────────────────────────────┤
│              博打狂                            │
│         [HP ██████░ 40/50]                     │
│         ⚠️ 蓄積: -- （ramp無し）               │ ← RampIndicator
│                                                │
│              🎲 賭け                           │
│                                                │
├──────────────────────────────────────────────┤
│  ┌──────────────────────────────────────┐    │
│  │ > 博打狂に15ダメージ                  │    │ ← CombatLog
│  │ > 強打！22ダメージを受けた            │    │   （全保持・スクロール）
│  │ > 博打狂に15ダメージ                  │    │
│  │ > （何もしてこない）                  │    │
│  └──────────────────────────────────────┘    │
│                                                │
│    [ 攻撃する ] [ 受ける ] [ 攻撃ブースト30G ]   │
└──────────────────────────────────────────────┘
```

### 26.3 TreasurePage（宝箱）

```
treasure_preview:
┌──────────────────────────────────────────────┐
│              ？？？                            │
│           宝箱を見つけた                       │
│                                                │
│      [ 開封する ]   [ 引き直す（30G） ]         │
└──────────────────────────────────────────────┘

treasure_opened:
┌──────────────────────────────────────────────┐
│              ✨ 反射 ✨                         │
│     counter被弾時、敵に追加ダメージ            │
│                                                │
│              [ 確認 ]                          │
└──────────────────────────────────────────────┘
```

### 26.4 GatePage（ゲート）

```
gate_preview:
┌──────────────────────────────────────────────┐
│            胴元の関門                          │
│       上の階層へ続く扉が立ちはだかる           │
│                                                │
│   現在の見込み: 無傷10% 小30% 大40% 特殊20%    │
│   保証（次1回=50G）→ 大15% 無傷22.5% 小42.5%   │
│                                                │
│  [ 通過する ]   [ ゲート保証（重ねがけ可） ]    │
└──────────────────────────────────────────────┘

gate_resolve:
┌──────────────────────────────────────────────┐
│         「小ダメージで通過」                   │
│         10ダメージを受けた                     │
│              [ 次の階層へ ]                    │
└──────────────────────────────────────────────┘
```

> **gate_resolve 画面の実体**：gate_resolve は瞬間phase（§6.1）のため、上図「gate_resolve:」の結果表示は実際には next_floor / cleared / dead 確定後に `pending.gate_outcome`（§20.8）を表示する演出。
> **特殊の表示**：特殊＝無傷通過＋ボーナスチップ **+40G**（§7.4）。UIの「特殊20%」は当たり（+40G）として訴求してよい（旧「実体なし」懸念は解消）。BattlePage は攻撃/受け/攻撃ブーストの3ボタン（§8.4）。

### 26.5 DeadPage（死亡）

```
┌──────────────────────────────────────────────┐
│              GAME OVER                         │
│       「全てを賭けた一勝負」は遠かった         │
│                                                │
│   到達: 3F   総ターン: 47   死因: 死闘の博徒(強打)│ ← ResultSummary(RunRecord由来)
│   取得mod: 反射, 見切り, 重装甲                │
│   獲得 100G / 消費 70G    強敵撃破: 2          │
│                                                │
│              [ もう一度 ]                      │
└──────────────────────────────────────────────┘
```

### 26.6 ClearedPage（クリア）

```
┌──────────────────────────────────────────────┐
│              CLEAR!                            │
│      頂上の一勝負を制した                      │
│                                                │
│   総ターン: 82                                 │
│   取得mod: 反射, 見切り, 重装甲, 好機          │
│                                                │
│   ── 恒久強化（残り1ポイント） ──              │ ← UpgradeAllocator
│   +最大HP    [Lv2] [+]                         │
│   +攻撃力    [Lv1] [+]                          │
│   +初期チップ [Lv0] [+]                         │
│   +チップ獲得率 [Lv1] [+]                       │
│   -関門コスト [Lv0] [+]                         │
│                                                │
│              [ 次のランへ ]                    │
└──────────────────────────────────────────────┘
```

### 26.7 HealPage / NextFloorPage（モーダル演出）

```
heal:
┌──────────────────────────────────────────────┐
│              バーカウンター                    │
│         大回復！ +30 回復した                  │
│              [ 確認 ]                          │ ← /continue
└──────────────────────────────────────────────┘

next_floor:
┌──────────────────────────────────────────────┐
│                3F へ                           │
│         胴元の関門を突破した                   │
│             [ 次の階層へ ]                     │ ← /continue
└──────────────────────────────────────────────┘
```
（回復量は大=+30／小=+15固定・§7.3。次フロアは gate_resolve 処理内で生成済み・§6.1）

### 26.8 レスポンシブ方針

- デスクトップファースト（情報密度の高いツリー表示が主役）。**サポート最低幅 `min-width: 1024px`**（それ未満は将来対応・モバイルは非スコープ§0.4）
- 将来のモバイル対応は共通コンポーネントのTailwindレスポンシブクラスで吸収
- TreeCanvasのみモバイルで縦スクロール対応が必要（将来課題）

---
