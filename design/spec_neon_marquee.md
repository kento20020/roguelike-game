# デザイン仕様 — A案「ネオン・マーキー」（注目箇所だけ光らせる強調演出）

Claude Designプロジェクト「カジノタワー・ローグライト デザインシステム」の
`preview/components-glow-marquee.html`（A案）を React 実装へ落とした際の**適用範囲と抑制ルールの正本**。
「常時は暗い felt 地のまま、注目対象にだけグローを乗せて視線誘導する」がコンセプト。

> B案（敵カードモチーフ）・C案（チップ&カード演出）は `spec_chip_fx_and_enemy_card_motif.md` を参照。

---

## 1. 提供する部品（`frontend/src/index.css` + `components/common/`）

| 部品 | 実体 | 用途 |
|---|---|---|
| `.glow-title` / `GlowTitle` | marqueeGlow 3.2s の真鍮 text-shadow 明滅 | 画面の「看板」となる serif 見出し |
| `.btn-glow` | btnPulse 2.2s の朱 box-shadow 明滅（`.btn` に併用） | その画面で「押すべき一手」の主ボタン |
| `.gate-dot` / `.gate-dot--lit` / `FloorProgressDots` | 真鍮の静的発光ドット（アニメ無し） | フロア到達進行（1〜5F） |
| `.victory-badge` | 真鍮枠 pill + 静的グロー | クリア画面の勝利バッジ |
| `.glow-ring` | `.panel` の box-shadow を真鍮リングに上書き | クリア画面のパネル縁取り |
| トークン | `--glowBrass` / `--glowBrassStrong`（--glowAccent は既存） | 上記の発光色 |

フォントトークン `--serif/--sans/--mono` も :root に正本定義済み（tailwind.config.js と同一スタック）。

## 2. 画面ごとの適用（正本）

| 画面 | 光らせるもの（最大2種） | 光らせないもの |
|---|---|---|
| StartPage | タイトル(GlowTitle 52) + 「卓に着く」(btn-glow) | 「調書を見る」 |
| GatePage | 「胴元の関門」(GlowTitle 38) + 「通過する」(btn-glow・**関門保証ボタンが併存する時のみ**) | 関門保証、出目テーブル |
| NextFloorPage | 到達フロア名(GlowTitle 44) + FloorProgressDots(縦・withLabel) | gate_outcome ラベル（意味色を維持） |
| ClearedPage | victory-badge + GlowTitle「制覇」(52) + panel の glow-ring | ResultSummary / UpgradeAllocator |
| Header | FloorProgressDots(横・静的) のみ | その他すべて |
| HealPage | **一切光らせない**（moss の静かなトーンが正） | — |
| 探索/戦闘/敗北/調書 | 既存演出（availGlow/gateGlow/fatalPulse等）のまま。A案は追加しない | — |

## 3. 抑制ルール（このデザインの本体）

1. **1画面で光る要素は最大2種**。3つ以上光ると視線誘導が壊れる
2. **btn-glow は「ボタンが2つ以上ある画面の主ボタン」のみ**。単一ボタンの画面では使わない（迷いがない場面に強調は不要）
3. **常時表示要素（Header）は静的発光のみ**。無限アニメーションを足さない
4. 色の意味分離を守る: **真鍮=到達・勝利・チップ／朱=押すべき一手・危険／moss=回復・安全**。
   回復画面に真鍮/朱のグローを持ち込まない
5. ClearedPage の glow-ring は「ラン終了の一度きりの見せ場」だから許される例外的な面発光。通常画面のパネルには使わない

## 4. 経緯

- 2026-07: Workflow分担方式で実装（基盤1エージェント→画面4班+監査1班の並列→統合）。
  監査で発見された未定義フォント変数（var(--serif)等が全て sans に落ちていた）も同時に修正。
