# ガード再設計: ジャストガード＋重ねがけ減衰（OPEN-018 対応案）

> 状態: **実装済み・数値確定（v1.8・感度分析済み）**。§7 の3決定はデザイナー承認済み（叩き台数値承認・空振りカウントする・ramp_hit 50%軽減）。
> §6-6 感度分析が完了し、数値は heavy 0.9 / counter 0.5 / ramp_hit 0.5 / stack_decay 0.5（＝§4 の叩き台のまま。config.json 変更なし）で確定した。詳細は §8。OPEN-018 は解消。
> 対象: `config.json combat.guard` / `combat_resolver.py` / `schemas/models.py Battle` / `bots.py` / snapshot・replay
> 起点: OPEN-018「現行 guard（deal 0.5 / incoming 0.25・無コスト・回数無制限）は非ランプ敵（ロスター約7割）に対する支配戦略になり得る」

---

## 1. 目的

guard を「毎ターン無条件に得な保険」から **「先読み情報を使った賭け（ベット）」** に再定義する。

- 軽減率を敵の実際の行動に連動させる（**ジャストガード**）→ 盲打ちは損、読み勝ちは大きく得
- 同一戦闘内の使用ごとに軽減量を半減（**重ねがけ減衰**）→ 連打が数学的に死ぬ
- 情報源（yomi mod のターン先読み・tell・scout の傾向示唆）→ guard 判断、という
  「情報を買って賭ける」ループはカジノテーマの中核体験と一致する

既存哲学との一貫性: 減衰はゲート保証の不変条件「重ねがけは効果半減」と同じ規則を適用する。

## 2. 新ルール

### 2.1 ジャストガード（行動連動の軽減率）

guard したターンの被ダメ軽減率は、敵が実際に取った行動で決まる:

| 敵の行動 | 基礎軽減率（叩き台） | 意図 |
|---|---|---|
| heavy_blow | **90%**（被ダメ ×0.10） | 読み勝ちの大報酬。「大振りを見てから受ける」 |
| counter | **50%**（×0.50） | 中間報酬 |
| ramp_hit | **50%**（×0.50） | ランプ敵は戦闘長期化自体が guard 不利なので heavy より弱く |
| none / evade | **0%（空振り）** | 軽減対象なし。deal 半減のコストだけ払う |

### 2.2 重ねがけ減衰

同一戦闘内で k 回目（当回含む）の guard は軽減量が半減していく:

```
実効軽減率(action, k) = 基礎軽減率(action) × stack_decay^(k-1)    # stack_decay = 0.5
```

- 例（heavy）: 1回目 90% → 2回目 45% → 3回目 22.5% → …
- カウンタは **戦闘終了でリセット**（`Battle.guard_uses`、戦闘単位）
- **空振り（none/evade に guard）もカウントに含める**（推奨・要確認 §7-2）

### 2.3 変えないもの

- 与ダメ側: `attack × stance_multiplier × deal_factor(0.5)`・attack_boost 非消費（現行どおり）
- 適用順序: 重装甲の軽減 **後** に guard 軽減を乗算（現行どおり・combat_resolver の不変条件）
- **反射**（counter 被弾時の固定ダメ）・**好機**（heavy 被弾時の追撃）は guard 中も発動する。
  「heavy をジャストで受けつつ好機の追撃を入れる」は読み勝ちの意図的シナジーとして残す
- 新規 RNG を導入しない（軽減は決定的）→ 9ストリーム不変・同一 seed 再現性に影響なし

## 3. ダメージ式（§8.5 追補案）

```
与ダメ(guard)    = player.attack × player.stance_multiplier × guard.deal_factor(0.5)
基礎軽減率       = mitigation_by_action[action]   # heavy 0.9 / counter 0.5 / ramp_hit 0.5 / 他 0
実効軽減率       = 基礎軽減率 × stack_decay^(guard_uses - 1)
最終被ダメ(guard) = round( max(0, 計算被ダメ − 重装甲軽減) × (1 − 実効軽減率) )
```

## 4. config.json 変更案（人間承認必須ファイル）

```jsonc
"guard": {
  "deal_factor": 0.5,
  "mitigation_by_action": { "heavy_blow": 0.9, "counter": 0.5, "ramp_hit": 0.5 },
  "stack_decay": 0.5,
  "count_whiff": true,
  "_comment": "受け（ジャストガード）: 軽減率は敵の実際の行動に連動し、同一戦闘内の使用ごとに軽減量が stack_decay 倍に減衰（ゲート保証の重ねがけ半減と同哲学）。空振り(none/evade)は軽減なし。数値は叩き台・bot再検証で調整。"
}
```

旧 `incoming_factor`（一律 0.25）は廃止。

## 5. なぜ支配戦略が消えるか（数理）

非ランプ敵の典型分布（heavy 25% / counter 35% / none·evade 40%、敵攻撃力 A）で試算:

- **盲 guard（1回目）**: 期待軽減 ≈ 0.25×1.8A×0.9 + 0.35×1.0A×0.5 ≈ **0.58A**。
  対価は与ダメ半減＝戦闘延長≒追加被ダメ期待 0.8A/延長ターン。**期待値でほぼ損**
- **盲 guard 連打**: 減衰で2回目以降の期待軽減が 0.29A → 0.15A と急落。**スパムは常に損**
- **読み guard（heavy 確定時）**: 軽減 1.8A×0.9 = **1.62A** を確実に得る。**明確に得**

→ 「情報がある時だけ guard が正解」という構造が数値でなくルールで保証される。
現行仕様（一律 0.25・減衰なし）は盲 guard 期待軽減 ≈ 0.6A が毎ターン無限に成立していた。

## 6. 実装計画（TDD・着手順）

1. **テスト先行**（`tests/test_guard.py` 新設）
   - heavy×guard 1回目: 被ダメが ×0.1 相当（丸め込み）
   - counter / ramp_hit: ×0.5
   - none/evade へ guard: 軽減ログなし・（count_whiff=true なら）guard_uses 加算
   - 減衰: 同戦闘2回目 heavy = 45% 軽減、3回目 22.5%
   - 戦闘を跨ぐと guard_uses リセット
   - 重装甲→guard の適用順不変・反射/好機の発動不変
   - 同一 seed 黄金テスト（guard 込み操作列の再現）
2. `schemas/models.py`: `Battle.guard_uses: int = 0` 追加
3. `combat_resolver.resolve_turn`: §3 の式へ差し替え（guard分岐のみ・他経路は不変）
4. snapshot / replay: `guard_uses` のシリアライズ追加（アクションログ再生では決定論的に復元される）
5. `bots.py`: strong-v2 方策（§6.1）・`STRATEGY_VERSION = "strong-v2"` にバンプ
6. 感度分析: mitigation（heavy 0.8/0.9）× decay（0.5/0.7）× 空振り規則 を振って
   クリア率・guard 使用率・敵タイプ別 guard ROI を一覧化 → デザイナーが最終数値決定
7. 数値確定後 `python -m app.simulation.gen_baseline` で回帰基準を再生成（承認手順）
8. docs 更新（要レビュー）: game_design.md §8.4 改訂・operations.md OPEN-018 消し込み・changelog 追記

### 6.1 bot 方策（strong-v2 叩き台）

bot 行動空間 = UI 一致の原則（OPEN-018 受入条件）に従い、**UIに公開される情報と同粒度のみ使用**:

- 先読み公開中（yomi mod / tell で `battle.preview` 提示中）に次行動 = heavy → **guard**（ジャスト確定）
- 次行動 = counter かつ HP が危険域（敵 attack×2 以下）→ **guard**
- 次行動不明 → **attack**（盲 guard しない）
- 同一戦闘 3 回目以降は guard しない（減衰で期待値が立たないため）

### 6.2 測定計画（OPEN-018 の決着判定）

- **ablation**: guard 禁止 bot vs strong-v2 のクリア率差 = guard の寄与
- 寄与が**非ランプ敵に一様に大きい** → まだ支配的（数値を絞る）
- 寄与が**情報あり（yomi/tell）状況とランプ/非ランプで分化** → 意図どおり
- 併せて guard 使用率・ジャスト成功率・敵タイプ別 ROI を balance_report に追加

## 7. デザイナー確認事項（実装着手のブロッカー）

1. **叩き台数値の承認**: heavy 0.9 / counter 0.5 / ramp_hit 0.5・stack_decay 0.5・deal_factor 0.5 据え置き
2. **空振りのカウント**: する（推奨。スパム抑止が強く規則も単純）/ しない（空振りは deal 半減の損のみで二重罰を避ける）
3. **ramp_hit への軽減**: 0.5（推奨。長期化不利と併せた二重の緩い耐性）/ 0（guard 完全無効＝ランプ敵を明示的な guard メタにする）
4. **config.json の構造変更**（`incoming_factor` → `mitigation_by_action` マップ）の承認

## 8. 感度分析の結果と数値確定（2026-07-09）

`guard_sensitivity.py`（N=400・maxedプロファイル・CRN）で `heavy_mitigation ∈ {0.7, 0.8, 0.9} × stack_decay ∈ {0.4, 0.5, 0.7}` の9comboを、方策 smart（現行の受け方策）／never（受けない＝旧 strong-v1 相当）／always（毎ターン受ける＝旧仕様で支配戦略だった「常時受け」の再現）の3方策で比較した。counter/ramp_hit=0.5・deal_factor=0.5・count_whiff=true は全comboで固定。生データ: `backend/app/simulation/baselines/guard_sensitivity_result.json`。

### 8.1 結果の要点

- **支配戦略の消滅**: always は全9comboでクリア率≈0%（8combo が0.0%・heavy0.9×decay0.7のみ0.25%）。dominance（always−never、never=3.75%）は全comboで負（-3.5〜-3.75pt）。旧仕様（一律25%軽減・無コスト・回数無制限）で成立していた「常時受けが得」という期待値優位は、どのcomboでも再現されない
- **スキル表現**: skill_expression（smart−never）は全comboで正（+4.8〜+6.8pt）。「情報がある時だけ受けが得」という設計意図どおり、賢い方策のみが受けから恩恵を得る構造になっている
- **最大スキル表現**: heavy 0.9 × decay 0.5 で +6.8pt（smart 10.5% vs never 3.8%）。heavy 0.9 × decay 0.7 も同率の +6.8pt だが、always のスパム抑止がわずかに弱い（always 0.2% > 0%＝完全にはゼロへ抑えられない）

### 8.2 選定基準と確定値

1. dominance ≤ 0（支配戦略の再発なし）を必須条件とする
2. 満たすcombo群の中で skill_expression を最大化する
3. 同率の場合は既存哲学（ゲート保証「重ねがけは効果半減」）との一貫性で決める

→ heavy 0.9 × decay 0.5 を採用。decay 0.7 は同率のスキル表現だがスパム抑止がわずかに弱く、「重ねがけは効果半減」の哲学とも一致する 0.5 を選ぶ。

**確定値**（config.json は変更なし＝§4 の叩き台がそのまま最終値）:

| 係数 | 確定値 |
|---|---|
| `mitigation_by_action.heavy_blow` | 0.9 |
| `mitigation_by_action.counter` | 0.5 |
| `mitigation_by_action.ramp_hit` | 0.5 |
| `stack_decay` | 0.5 |
| `count_whiff` | true |
| `deal_factor` | 0.5 |

### 8.3 再現方法

```
python -m app.simulation.guard_sensitivity [N]   # 既定 N=400
```
