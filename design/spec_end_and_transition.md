# デザイン仕様 — エンド＆遷移（ラン完結）

Claude Design で `.dc.html` を起こすための**画面仕様の正本**。対象は3画面：
**フロア遷移 / クリア / 敗北**。実装ロジックは backend に確定済み（このdocは「何を表示し何を叩くか」だけを定義）。

> 進め方（CLAUDE.md準拠）: この仕様 → Claude Design で `.dc.html` 作成 → `design/` に取り込み → React化。
> 見た目の正本はデザイン側に残す。レイアウトを白紙から手書きで起こさない。

---

## 0. 視覚言語（既存 `地下カジノ・探索と戦闘.dc.html` から継承・必ず流用）

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

背景演出（既存と統一）: 紙ノイズ＋ヘイズ2枚（hazeDrift）＋残り火（emberRise）。
エンド画面では残り火の密度・色で「クリア＝真鍮の灰／敗北＝朱の残響」を出し分ける。

共通ヘッダー（探索/戦闘と同じバー）は**エンド3画面では出さない**。ランの幕引きとして全画面を使う。

---

## 1. フロア遷移（phase: `next_floor`）

ゲートを抜けた瞬間の「登った」一拍。すぐ上の階の探索へ繋ぐ短い幕間。

### データ契約（snapshot）
```
phase: "next_floor"
current_floor: int            # 到達した新フロア番号（advanced_to と一致）
player: { hp, max_hp, attack, chips, mods[] }   # ゲート通過後のHP（被弾後）
pending: { gate_outcome: str, advanced_to: int }
```
- `gate_outcome` … ゲートの出目（例: `safe` / `minor_damage` / `major_damage` / `special`）。被弾していれば player.hp が直前より減っている。
- フロア名は `backend/app/data/floors.json` の各フロア名（章タイトル）を参照。

### 画面構成
1. **中央に大きな章番号と章名**（serif）。「F{n} ▸ F{n+1}」のように下の階から上の階へ登る演出（このゲームはカジノタワー＝登るほど頂上=5Fに近づく）。章番号は昇順・矢印上向きで確定。
2. ゲート出目バッジ（`gate_outcome` を日本語化）。被弾時は HP の増減を差分で見せる（例 `-12`、`--danger`）。安全通過なら `--moss` の「無傷」。
3. 進行ドット（1F…5F を下から上へ積み上げ、到達点を真鍮で点灯。5F点灯＝頂上到達）。
4. CTA「次の階へ」 → これで `exploring` に入る。

### アクション
- 続行 → `POST /api/run/{sid}/continue`（モーダルphaseを閉じる dismiss）で `exploring` へ。
  - ※ next_floor が `continue` 必須か自動遷移かは要確認（§5-1）。仕様上は continue で閉じる前提で設計。

### 演出
- ゲート真鍮グローが上方向に抜けて（登攀＝上向き）、章タイトルがフェードイン（fadeUp）。1.5〜2秒で読めて、CTAは即押せる（待たせない）。

---

## 2. クリア（phase: `cleared`）

5F関門を突破＝全クリア。**ラン全体の決算**を見せ、メタ強化（+1pt）へ送り出す祝祭画面。

### データ契約（snapshot）
```
phase: "cleared"
pending: { gate_outcome: str }
run_record: {
  run_id, seed, bot_type,
  cleared: true,
  floor_reached: 5,
  total_turns: int,
  final_hp: int,
  mods_acquired: [str, ...],          # 取得した技mod
  gold_earned: int,
  gold_spent: { scout, heal_small, heal_large, attack_boost, gate_guarantee, treasure_reroll },
  enemies_defeated: [ {...}, ... ],    # 撃破した敵（名前・フロア等）
  permanent_upgrades_state: { max_hp, attack, init_gold, gold_drop, sink_cost }
}
```

### 画面構成
1. **大見出し「制覇」**（serif・真鍮グロー）。seed をモノで小さく添える（再現性の符牒）。
2. **決算カード（卓 `--felt`）** — 数値はすべて mono / tabular-nums：
   - 到達フロア 5/5、総ターン `total_turns`、最終HP `final_hp / max_hp`。
   - 稼いだチップ `gold_earned`、使ったチップ内訳（`gold_spent` を sink 別の小バー/行で）。
   - 撃破数 `enemies_defeated.length`（一覧は折りたたみ可）。
   - 取得した技 `mods_acquired`（探索/戦闘ヘッダーと同じ pill デザインを流用）。
3. **報酬バナー**「+1 強化ポイント」（cleared 検知で付与済み。win-to-progress の核）。
4. CTA 2つ：**強化へ進む**（メタ強化画面・次段）／**もう一度**（タイトル→新ラン）。

### アクション
- このランは終端。`run_record` は API 側で永続化済み。画面遷移はフロント内（→メタ強化 or タイトル）。
- 戦績は `GET /api/stats/history` で参照可能（戦績画面・次段）。

### 演出
- 真鍮の残り火を多めに。決算カードは数値が上から順にカウントアップ（最後に「+1pt」）。

---

## 3. 敗北（phase: `dead`）

パーマデス。**何が起きて終わったか**を簡潔に突きつけ、再走への動線だけ残す。湿っぽくしない。

### データ契約（snapshot）
```
phase: "dead"
run_record: {
  cleared: false,
  floor_reached: int,
  death_cause: str,        # 例 "gate:major_damage"、戦闘要因（敵名/挙動）
  death_floor: int,
  total_turns, final_hp(=0想定), gold_earned, gold_spent,
  mods_acquired, enemies_defeated, permanent_upgrades_state
}
```
- `death_cause` は機械語。日本語化マップが要る（例 `gate:major_damage` → 「関門の大ダメージ」／戦闘なら敵名＋挙動）。→ §5-2。

### 画面構成
1. **大見出し「敗北」**（serif・`--danger`）。残り火は朱で、ヘイズを暗く沈める。
2. **死因の一文**（最重要・大きく）: 「{death_floor}階『{章名}』で {死因} に倒れた」。
3. **簡易戦績**（クリアより小さく）：到達フロア `floor_reached`、総ターン、撃破数、稼いだチップ。
   - クリアと違い「決算」より「記録」のトーン。数値は控えめ。
4. CTA：**もう一度**（タイトル→新ラン）。※敗北では pt 付与なし。

### アクション
- 終端。`run_record` 永続化済み。フロント遷移のみ（→タイトル）。

### 演出
- 朱の残り火が一度爆ぜて沈む（emberRise を逆向き/減衰）。見出しは遅れてフェードイン。

---

## 4. 3画面の共通仕様

- **全画面・ヘッダー無し**（ランの外枠）。最大幅 ~560px の単一カラム中央寄せ（決算カードのみ ~640px）。
- 数値は必ず mono + tabular-nums。ラベルは sans 10px / letter-spacing 広め / uppercase（既存踏襲）。
- CTA ボタンは既存の朱ボタン（`--accent`）を主、ゴースト枠を副。
- レスポンシブはデスクトップ密度優先（既存と同方針）。モバイルは縦積みでフォールバック。
- アニメは既存 keyframes（fadeUp / overlayIn / emberRise / hazeDrift）を再利用。新規追加は最小限。

---

## 5. 着手前に潰す確認ポイント

1. **next_floor の閉じ方** … `continue` 必須の幕間オーバーレイか、自動で `exploring` に流すか。後者なら「遷移画面」ではなく探索画面に被せる短いトースト演出にする。→ backend の実遷移を1本通して確認（要なら私が確認）。
2. **death_cause の日本語化辞書** … `gate:*` と戦闘要因の表記ゆれを洗い出し、表示マップを1つ用意（コピーライティング）。
3. **方向の演出** … v1.0で『登る』確定済み（カジノタワー＝頂上=5Fを目指す）。章番号は昇順・矢印は上向きで確定。
4. **クリア後の主動線** … 「強化へ」を主にするか「もう一度」を主にするか（win-to-progressを推すなら強化を主CTA）。
5. **enemies_defeated の見せ方** … 一覧を出すか、撃破数だけにするか（dictの実キーは確認して列を決める）。

---

## 次段（このdocの後）

承認後、上記を Claude Design に渡して3画面の `.dc.html` を作成 → `design/` 取り込み → React化（`frontend/` 構築時に `gameApi.ts` 経由で本APIへ接続）。
