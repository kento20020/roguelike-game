# デザイン仕様 — 検死レポート＆リプレイシアター（敗北後）

Claude Design で `.dc.html` を起こすための**画面仕様の正本**。対象は**DeadPage（敗北）画面の拡張**：既存の「敗北」全画面に、検死レポート＋リプレイ（ターン別振り返り）を追加する。実装ロジックは backend に確定済み（このdocは「何を表示し何を叩くか」だけを定義）。

> 進め方（CLAUDE.md準拠）: この仕様 → Claude Design で `.dc.html` 作成 → `design/` に取り込み → React化。
> 見た目の正本はデザイン側に残す。レイアウトを白紙から手書きで起こさない。

> **背景**: GDD §15.2（`docs/game_design.md`）で定義された機能。既存実装（`frontend/src/pages/DeadPage.tsx`）は先にコードで実装済みだが、「結果／検死レポート／リプレイ」を横並びタブにしたため、粒度の異なる3つの体験（常時見たい決算・最重要な単一ターンの反実仮想・任意で深掘りする全ターン俯瞰）が同格に扱われてしまっている。本specはその**情報設計をやり直す**ためのもの。API・データ契約・視覚トークンは変更しない。

---

## 0. 視覚言語（既存 `地下カジノ・探索と戦闘.dc.html` / `spec_end_and_transition.md` から継承・必ず流用）

| トークン | 値 | 用途 |
|---|---|---|
| `--paper / --paper2 / --paper3` | `#15120E / #1F1B15 / #2A241B` | 暗色地・紙テクスチャ |
| `--felt` | `#171814` | 卓/パネル面 |
| `--ink / --ink2 / --ink3` | `#F1ECE0` / 60% / 33% | 文字・副次・微弱 |
| `--accent / --accent2` | `#C85A2A / #9A3A14` | 朱（行動・危険寄り） |
| `--brass` | `#C9A24B` | 真鍮（ゲート・チップ・勝利） |
| `--danger` | `#C7402A` | 敗北・大ダメージ |
| `--moss` | `#5E8A66` | 回復・安全 |
| serif | Instrument Serif + Noto Serif JP | 大見出し・章 |
| sans | Geist + Noto Sans JP | UI |
| mono | JetBrains Mono（tabular-nums） | 全数値 |

DeadPage 既存演出（据え置き・変更しない）：
- 残り火は朱、ヘイズは暗く沈める。見出し「敗北」は遅れてフェードイン（`spec_end_and_transition.md` §3）。
- 本specが追加する要素は、この敗北画面の**見出し＋決算カードの下に続くセクション**として設計する。全画面・ヘッダー無し・単一カラム中央寄せ（`spec_end_and_transition.md` §4を継承）は変えない。

---

## 1. 情報設計の変更点（現状の課題→方針）

| 現状（実装済みタブ） | 課題 | 方針 |
|---|---|---|
| 結果／検死レポート／リプレイ を横並びタブで等価に切替 | 決算（常時知りたい）・単一ターンの核心（最重要）・全ターン俯瞰（任意の深掘り）という粒度差が、タブという同格UIに埋もれる | タブを廃止。**縦に積む**：①決算（常時表示）→②検死レポート（常時表示・最重要）→③リプレイ（折りたたみ・任意） |
| ゲート死は「検死レポートがない」という空のタブ内容が独立のタブ枠を占める | 存在しない機能のために画面上の場所が確保され続ける | ゲート死のときは②③セクションごと描画せず、死因一文の下に一言添えるだけに留める |

---

## 2. データ契約

### 2.1 GameState（既存・DeadPageに既に渡っている）
```
phase: "dead"
run_record: {
  cleared: false,
  floor_reached: int,
  death_cause: str,        # "gate:major_damage" 等 or 敵名/挙動由来
  death_floor: int,
  total_turns, final_hp(=0), gold_earned, gold_spent,
  mods_acquired, enemies_defeated, permanent_upgrades_state
}
```

### 2.2 検死レポート（`GET /run/{sid}/postmortem`。戦闘死のみ・ゲート死は404）
```
PostmortemResponse {
  run_id: str
  fatal_turn_index: int
  counterfactual: {
    fatal_turn_index: int
    original_guard: bool          # 実際に選んだ行動（true=受け）
    counterfactual_guard: bool    # もし逆を選んでいたら
    category: "unavoidable" | "avoidable_guard" | "avoidable_attack" | "mutual_kill_victory"
    avoidable: bool | null
    message: str                  # 表示用の一文（正本はbackend生成・フロントは編集しない）
    counterfactual_result: {
      action: str, dealt: int, incoming: int,
      player_hp: int, enemy_hp: int,
      enemy_dead: bool, player_dead: bool
    }
  }
  turn_history: [
    {
      node_id, enemy_id, guard: bool, action: str,
      dealt: int, incoming: int,
      player_hp_before, player_hp_after,
      enemy_hp_before, enemy_hp_after,
      ramp_value, kouki_cooldown,
      pre_turn_snapshot: { player:{hp,max_hp}, enemy:{hp,max_hp}, battle:{turns,ramp_value,...} }
    }, ...
  ]
}
```
- 404（ゲート死）の場合、②③セクションは描画しない。
- `category` の表示トーン（既存実装 `CATEGORY_META` を踏襲・本specで正本化）：

| category | バッジ文言 | トーン |
|---|---|---|
| `unavoidable` | 回避不能だった | 中立（`--ink2`）。責めない・淡々と |
| `avoidable_guard` / `avoidable_attack` | 回避可能だった | 警告（`--danger`）。「あのとき知っていれば」の学習訴求 |
| `mutual_kill_victory` | 刺し違い勝利だった | 真鍮（`--brass`）。惜しかった・ほぼ勝ちの手応え |

### 2.3 行動ラベル（`turn_history[].action` の日本語化。既存 `behaviorMeta` を踏襲・正本は変えない）

| key | 表示 | 色 |
|---|---|---|
| `counter` | 反撃 | `--danger` |
| `heavy_blow` | 強打 | `--danger` |
| `evade` | 回避 | `--moss` |
| `ramp_hit` | 蓄積の一撃 | `--brass` |
| `none` | 様子見 | `--ink2` |

---

## 3. 画面構成（DeadPageへの追加。上から順）

1. **見出し＋死因一文**（既存据え置き）：「敗北」＋「{death_floor}階『{章名}』で {死因} に倒れた」
   - ゲート死（`death_cause` が `gate:` prefix）の場合、この一文の下に控えめな注記を1行添えるのみで②③は描画しない：「この死因には検死レポートがない（関門での敗北のため）」（`--ink3`・小さく・演出なし）

2. **決算カード**（既存 `ResultSummary` 据え置き）：到達フロア・総ターン・mod一覧・獲得/消費チップ・強敵撃破数

3. **検死レポートカード（新規重み付け・常時展開・戦闘死のみ）**
   - 決算カードのすぐ下に常時表示する（タブの奥に隠さない）。
   - 構成（既存`PostmortemPanel`のロジックを流用しつつ配置を変更）：
     - カテゴリバッジ（§2.2の表参照）
     - 「致命の一手（{実際の選択}を選んだターン）」ラベル
     - メッセージ本文（`message`。serif・カテゴリ色、22px程度で目立たせる）
     - 対比列（実際の選択／もしも逆を選んでいたら／その結果＝反実仮想後の自HP・敵HP）
   - この画面で**最も重い視覚的ウェイト**を持たせる（GDDの「知識が報われる」を体現する核。§15.1）。

4. **リプレイ（折りたたみ・デフォルト閉・戦闘死のみ）**
   - 見出し行：「ターンごとの記録を見る（全{turn_history.length}手）」＋開閉シェブロン。
   - **閉じた状態でも致命ターンのプレビューだけは見える**（「#{fatal_turn_index+1} 致命の一手」の1行を見出しのすぐ下に薄く表示。クリックで展開へのショートカットにもなる）。
   - 展開時：既存 `TurnRow` 相当（ターン番号／攻撃or受けアイコン／行動ラベル／与えた・被ったダメージ／自HP・敵HPのbefore→afterバー）を全ターン分スクロール表示。致命ターンは強調（既存 `fatalPulse` 演出を踏襲）。
   - 開閉アニメーションは高さの `fadeUp` 程度に留め、演出過多にしない（振り返り画面なので、戦闘中の派手な演出とはトーンを変える＝控えめに）。

5. **CTA**（既存据え置き）：主ボタン「もう一度」／副ボタン「タイトルへ」

---

## 4. 演出方針

- 検死レポートカードの登場は決算カードに0.1〜0.2秒ほど遅れてフェードイン（優先度が高い＝すぐ見えるが、決算より一拍遅れて主役感を出す）。
- リプレイは「戦闘の再演」ではなく「記録の閲覧」なので、画面揺れ・光の点滅などは使わない。HPバーのbefore→after遷移のみ（既存`ReplayHpBar`）に留める。
- ゲート死の注記は演出無し（フェードのみ）。空虚さを機能で表現しない（テキスト一言で済ませる）。

---

## 5. 着手前に潰す確認ポイント

1. 検死レポートカードを「常時展開」にすることで、決算カードと合わせて画面が縦に長くなる。スクロールを許容するか、決算カードの表示密度を上げるか要検討（既存`ResultSummary`のレイアウト次第）。
2. リプレイの「閉じた状態の致命ターン1行プレビュー」は新規UIパターン。折りたたみ（disclosure）自体がこのアプリ初出（現状 `Tabs` も `Accordion` も共通コンポーネント化されていない）なので、React化時に共通コンポーネントとして切り出すか検討。
3. `mutual_kill_victory` のトーン（真鍮＝惜しかった演出）が「敗北」画面全体の沈んだトーンと衝突しないか（喜びすぎない範囲で調整）。

---

## 次段（このdocの後）

承認後、上記を Claude Design に渡して `.dc.html` を作成 → `design/` 取り込み → React化（`DeadPage.tsx` のタブ実装をこの構成に置き換え。`PostmortemPanel`/`TurnRow`/`ReplayHpBar` の内部ロジックは流用しつつ、配置と開閉制御を作り直す）。
