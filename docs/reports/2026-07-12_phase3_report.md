# Phase3 実施レポート — mod寄与 ablation（2026-07-12）

> **位置づけ**: セッション作業レポート（非正本）。§18.2 Phase3（単一mod寄与・ペア交互作用＝OPEN-023）の実施記録。合否の正本は operations.md §18.1。
> **方法**: `mod_ablation.py`（PR #36 で新設）。宝箱抽選プールからの leave-one-out／leave-two-out 除去実験・CRN（seed 0-999・N=1000・mid パネル）・単体寄与は対差の anytime-valid CI＋McNemar e-process・交互作用は I=Δxy−Δx−Δy を bernoulli CS/e値・**e-BH 2ファミリ**（直接比較21件／交互作用15件）で FDR 制御。閾値は v1.11 事前登録（単体±8pt・ペア±W=10pt）。

---

## 1. 実施の時系列（1セッションで完結）

1. **ツール実装**（PR #36・クラスR）: opus が本体・sonnet がテスト15件＋INTEGRATION.md を実装、検収後マージ。装置検証＝full コホートが Phase2 実測 31.1%（311/1000）と完全一致
2. **初回測定**: kouki=broken／mikiri=trap／yomi=dead を検出（§2）
3. **バグ発見**（PR #37・クラスF）: mikiri の是正感度実験で「効果量を変えても 22,000 ラン無変化」→ **`_mikiri_factor_from_mods` が 0.5/0.0 をハードコードし mods.json（数値の正本）を読んでいない** doc-code drift を特定・修正（現行値では挙動不変＝回帰ベースライン不変で証明）
4. **是正実験**（修正済みエンジン）: mikiri 0.25 単独／yomi 2T/4T 単独／両方 の3条件で ablation 再測定
5. **是正採用**（PR #38・クラスB・デザイナー決定）: 両方採用。mid 31.1%→**34.4%（帯内維持）**

## 2. 初回測定（v1.11 データ・是正前）

full = **311/1000 = 31.1%**（Phase2 と完全一致・CRN 装置検証 OK）

| mod | Δ（full−除去） | CI | FDR | 判定 |
|---|---:|---|:-:|---|
| kouki（好機） | **+18.2pt** | [+14.4, +23.4] | * | **broken**（±8pt 超過） |
| juso（重装甲） | +12.6pt | [+7.4, +16.4] | * | healthy（帯超え疑い） |
| kasoku_dome | +5.8pt | [+1.0, +10.8] | * | healthy |
| hansha（反射） | −3.0pt | [−7.4, +2.6] | | inconclusive（1F確定分交絡＝追加取得分のみの測定） |
| yomi（先読み） | −4.1pt | [−9.4, +0.4] | | **dead**（寄与実質ゼロ以下） |
| mikiri（見切り） | **−5.5pt** | [−9.6, −0.2] | * | **trap**（除外した方が強い・負寄与が有意） |

**ペア交互作用**: e-BH で FDR 有意なし（15件）。CI が ±10pt に収まらないペア4件（N不足）。juso|yomi（+5.5 [+0.8,+13.2]）・juso|hansha（+7.6 [+1.2,+14.4]・1F交絡付き）に **substitute（冗長・逓減）傾向**——設計上狙った「被弾上等」シナジー（§10.4）と逆方向の観測。

## 3. 是正実験と採用（デザイナー決定）

| 条件 | full | mikiri Δ | yomi Δ |
|---|---:|---|---|
| 是正前 | 31.1% | −5.5 trap | −4.1 dead |
| mikiri 0.25 のみ | 32.0% | −4.6 dead | −2.9 dead |
| **両方（採用・PR #38）** | **34.4%** | **−6.2 trap（FDR有意）** | **−0.5 inconclusive＝中立化** |

- **yomi は数値バフで救えた**（1枚=2ターン/2枚=4ターン公開）。dead → 中立
- **mikiri は数値バフでは救えないことを実証**：効果を倍化（evade 50%→75%削減）しても trap 帯のまま。構造要因＝効果が「ずれ系4体＋カオスの一部」限定なのに、leave-one-out の機会費用は常時有効な kouki(+19)/juso(+12) と競合する。**§19.2 が予見した「ずれ系敵が出ないランで見切りが腐る」の因果的確証**。→ 効果リワーク（クラスS）を **OPEN-047** として起票
- **kouki（broken +19.5pt）は残す**（デザイナー決定・§10.4/§18.4 非対称運用「壊れmodは残す」。mid 34.4%＝帯内でクリア率を破壊していない。帯の kouki 依存度は観測継続）

## 4. 最終状態（採用値・公式記録 `baselines/mod_ablation_result.json`）

full = **344/1000 = 34.4%**（帯 25〜40% 内）

| mod | Δ | CI | 判定 |
|---|---:|---|---|
| kouki | +19.5pt | [+14.2, +23.4] | broken（**残す**・観測継続） |
| juso | +11.5pt | [+5.0, +13.6] | healthy（±8pt 超え疑い・観測継続） |
| kasoku_dome | +6.1pt | [+1.0, +11.0] | healthy |
| yomi | −0.5pt | [−6.4, +3.2] | inconclusive（**是正済み・中立化**） |
| hansha | −3.8pt | [−8.6, +1.2] | inconclusive（1F交絡） |
| mikiri | −6.2pt | [−11.6, −2.2] | **trap → OPEN-047（リワーク）** |

ペア交互作用: FDR 有意なし。juso|hansha +8.1 [+2.0,+16.0]・juso|yomi +4.7 [+1.2,+12.8] の substitute 傾向は継続観測（±10pt CI 外は3件＝N不足）。

## 5. 測定上の注意（honest limitations）

- **hansha**: 1F 確定配置（floors.json content 経由・プール外）が全コホートに残るため、測定は「確定1枚を超える追加取得の寄与」。hansha を含むペアの交互作用（特に juso|hansha の設計シナジー検証）はこの ablation では正しく測れない（confounded フラグで明示）
- **leave-one-out の意味論**: Δ_X は「X の絶対価値」ではなく「X が置き換える他modとの相対価値＋プール占有の機会費用」。mikiri の負値は「mikiri が引かれる枠で他modを引いた方が強い」の意味
- **bot 方策の内生性**: juso は脅威推定・yomi はガード方策のトリガーとして bot が利用する（方策込みの総合効果を測っている＝意図どおり）

## 6. 再現方法

```
py -3.12 -m app.simulation.mod_ablation --n 1000 --profile mid --out baselines/mod_ablation_result.json
```
