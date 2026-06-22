# backend 実装ノート（設計判断・バランス所見）

このパスで固めた**設計判断**と、変更時に再質問せず済ませるための記録。
数値の正本は `app/data/*.json`、設計の正本は GDD。ここは「コードがデータをどう解釈するか」のメモ。

## このパスの範囲
- 実装: `app/data`（ローダ/検証）・`app/engine`（rng/combat/floor/chaos/gate/game_engine）・`app/schemas`・`app/simulation`・`tests`。
- 未実装（次段）: `app/api`（FastAPI）、SQLAlchemy/SQLite 永続化、`frontend/`、TS版RNG。
- テスト: `pytest`（99件）。bot検証: `python -m app.simulation.phase12_harness [N]`。
- Python は `py -3.12`（pip入り）を使用。エンジン本体は標準ライブラリのみ。

## 設計判断（データ/GDD で未指定 → 既定値を採用。balance に関わるものは human レビュー対象）
1. **post_damage順序** = 重装甲(軽減) → player被弾 → 反射(counter) → 好機(heavy追撃) → 死亡判定。
   「反射×重装甲」synergy（軽減後に被弾しつつ反射を返す）が分岐なしで自然成立。
2. **ramp** = config式 `ramp_value(n)=ramp_base_initial(5)+ramp_increment*(n-1)`、n=戦闘ターン番号。
   旧バニラ試作の per-enemy init は破棄（データが正本）。
3. **カオス敵の ramp** = ramp_increment 未定義のため増分0（=毎回 base_initial 5 の平打ち）。要 human 判断なら config に既定増分を追加。
4. **好機クールダウン** = 発動でcd=cooldown_1(1)/cooldown_stack(0)。**発動しなかったターン末**にのみ減衰 → 1枚は「1ターン空け」、2枚は毎ターン。
5. **宝箱** = dead-end は宝箱/回復の専用ノード。presence は生成時に確定（dead-end 60%、親が強敵なら+20pt。親=row1敵で生成時に強敵性が確定するため「アンロック時」と同義）。**中身mod は開封時に6種から抽選**（reroll は stream を進めて引き直し）。
   - **多親(enemy)ノードの撃破ドロップ（GDD §11.4）＝実装済み**：多親×enemy ノードに生成時 `has_treasure` を事前抽選（`config.treasure.base_chance_multi_parent`=0.3、強敵は `strong_enemy.treasure_chance_bonus_pt`=+0.2＝0.5）。抽選は **`STREAM_GENERAL`(7)** で行い既存ストリーム列の決定性を乱さない。**1F（fixed_layout）は固定宝箱のみ＝除外**。撃破時 `_victory` で `has_treasure` なら `treasure_preview`（pending.source="enemy"）へ遷移し、既存 `treasure_open` が mod を付与。
6. **gate_route** = row2_pool が空のフロア（1F）の多親ノードは敵を持たない通過ノード。選択で無料解決し、ゲートを解放。
7. **チュートリアル** = 1F dead-end A に 反射(hansha) 確定宝箱（presence=1.0）。
8. **chaos分布** = {counter,heavy_blow,evade,ramp_hit} に各最低5pt＋一様正規化で合計100（パラメータ無し）。balance調整余地あり。
9. **TS版RNG** = 本パス未実装。Python SFC32 ＋ golden vector（tests/test_rng.py）で凍結済み。将来TS移植はこの値に一致させる。
10. **永続化** = 本パスはメモリ（RunRecord dataclass）。SQLAlchemy/SQLite は API 段。

## バランス所見（harness 計測, N=400, CRN）
`data/*.json` の数値は config の `_comment` 通り**叩き台**。恒久強化（win-to-progress）込みで計測:

| 恒久強化 | strong クリア率 | 主な死亡フロア |
|---|---|---|
| base（新規アカウント・0強化） | **0.0%** | 3〜4F |
| mid（〜6クリア相当） | 0.0%（4〜5Fまで到達） | 4〜5F |
| maxed（26クリア相当） | **38.8%** CI[34,44] | 5F |

**結論:**
- エンジン/ボットは健全（maxed で 25–40% 帯に入り、クリア可能性を実証）。クリア率は強化量に単調。
- random は全プロファイルで 0%（スキル幅は確保。CI は strong-maxed と非重複）。
- **新規アカウントが極端に難しい**のは data が叩き台のため。fresh acct も帯域に寄せたい場合は、
  base_hp/base_attack/HP tier係数/敵attack/経済（gold_base・heal費）を **human が JSON で調整**する。
  CLAUDE.md 原則: `data/*.json` はバランスの正本・無断改変禁止（Goodhart回避は方策ではなく数値で）。

## bot 方策（app/simulation/bots.py）
- **strong**: 低HPで回復 → 無料dead-end(宝箱/回復/gate_route)を先取り → ゲートへ最短climb（高row優先・宝箱解放敵を優先・脅威最小）→ とどめは attack_boost → ゲート前は低HPなら保証1回。
- **random**: 合法手から一様（独立 bot RNG、CRN）。

## API 段（app/api・app/db・main.py）— 設計判断
- **セッション保持＝メモリ**（`app/session_store.py`: `session_id → GameEngine`）。DBは結果のみ。
  単一プロセス前提・退避/TTLなし。**再起動で進行中ランは消える**（仕様）。再起動/マルチワーカー対応が
  必要なら engine の全状態（rng含む）シリアライズが前提。
- **DB（SQLite/SQLAlchemy）= RunRecord履歴 ＋ Profile のみ**。combat_log は永続化しない。
- **Profile = 単一行（id=1）** の恒久強化（points＋5項目Lv）。cleared 検知で 1pt 付与、`/upgrade` で消費。
  `/run/new` が Profile.levels を engine に渡す（win-to-progress が次ランへ反映）。
- **`POST /run/{sid}/continue`** は §25 に無いがモーダルphase（treasure_opened/heal）を閉じるため追加（dismiss）。
- **`GET /catalog/mods`**（§25外・追加）：`mods.json` の6種を `{id,name,effect_1,effect_stack}` で返す。技の効果文の**正本**で、フロントは起動時に一度取得して開封リベール／ヘッダー技パネルに表示（フロントの重複定義 `MOD_EFFECT` は撤去）。`gate_preview` の pending には `table`＋`damage`（被ダメ実値）、`treasure_open` の pending には `count`（スタック段階）を載せる。
- **先読み(yomi)の確定表示**：snapshot の battle に `next_action`（＝`pending_action`＝公開済みの**確定の次手の種別**、未公開は None）を追加（`BattleOut.next_action`）。エンジンの先読みロジックは無改変。UI は `next_action` を行動グロッサリの名前＋色で「先読み·確定：次は◯◯」と出し、スカウト(`scout_hint`=傾向)と明確に区別する。
- **`POST /run/{sid}/guard`**（§25外・追加）＝戦闘の攻防選択。`combat_resolver.resolve_turn(..., guard=True)`：与ダメ ×`config.combat.guard.deal_factor`(0.5)・**boost非消費**、被ダメ ×`incoming_factor`(0.25, 重装甲の軽減後に乗算)。`available_actions` の battle に `{"type":"guard"}` を追加。**回数無制限**（攻撃を捨てる機会コストが抑制）。先読み/スカウトの情報を活かす手。**任意手＝非使用なら既存の強プレイ帯は不変**（bot harness で確認: 敵ドロップ実装後の maxed は ~44.5%、ガード非使用で前回と整合）。数値は叩き台・human調整対象。
- **エラー対応**: `WrongPhase→409` / `InvalidMove→400` / `UpgradeError→400` / session不在→404 /
  Pydantic→422（FastAPI既定）。エンジン例外を2サブクラス化して精度を出した。
- **seed 省略時**は API 境界で `secrets.randbits(32)` を生成（エンジンは決定論のまま）。
- **CORS** 全許可（将来の Vite dev server 用）。
- **`game.db`** は backend/ に生成・.gitignore 済み。テストは in-memory SQLite（StaticPool）で隔離。
- 起動: `py -3.12 -m uvicorn main:app --reload` → `/docs`。テスト計110件（engine/sim 99 ＋ API 11）。

### snapshot のバグ修正
`Node.snapshot` の `resolved` は engine 側の解決状態（`state=="resolved"`）から導出するよう修正。
Node.resolved 属性はエンジンが更新しないため state を正とする。

### CI 動作確認
2026-06-22: GitHub Actions `balance` ワークフロー（§18 ゲート）のトリガー検証。
`backend/**` 変更で push 時に Phase0 全テスト＋Phase5 回帰ゲートが自動実行されることを確認するための記録行。
