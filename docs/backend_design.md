# バックエンド設計（状態遷移・ドメインロジック）
> 元 `game_design_document.md`（v1.2）の §6・§20.4 を再配置。戦闘ルール本体は game_design.md §8、API契約は api_contract.md §25 を参照。相互参照の §番号は元GDD準拠。

## 6. game_phase 状態遷移

### 6.1 全phase一覧（厳密型）

| phase | 意味 | 主な遷移先 |
|-------|------|----------|
| `exploring` | マップ上でノード選択中 | battle / treasure_preview / heal / gate_preview |
| `battle` | 戦闘中 | exploring（勝利・ドロップ無）/ **treasure_preview（勝利・撃破ドロップ有**・§4.2 `pending.source="enemy"`**）**/ dead（HP0） |
| `treasure_preview` | 宝箱選択後・開封前（リロール可能） | treasure_opened（開封）/ treasure_preview のまま（リロールは中身を引き直すだけでphase不変・実装準拠）|
| `treasure_opened` | 宝箱開封後・mod確認中 | exploring（`POST /continue`） |
| `heal` | 回復ノード解決中（大小決定済み） | exploring（`POST /continue`） |
| `gate_preview` | ゲート選択後・通過前（ゲート保証sink使用可能） | gate_resolve |
| `gate_resolve` | ゲート結果ロール・適用（**瞬間phase＝滞在しない**） | next_floor（1〜4F通過）/ **cleared（5F通過）** / dead（HP0） |
| `next_floor` | 次フロアへの遷移演出 | exploring（`POST /continue`） |
| `cleared` | 5Fゲート通過・クリア | （恒久強化画面へ） |
| `dead` | HP0・ゲームオーバー | （死亡画面へ） |
| `pause` | ポーズ中（**将来・未実装**） | 直前のphaseへ復帰 |

> **モーダルphaseの前進（実装準拠）**：`treasure_opened`・`heal`・`next_floor` は `POST /api/run/{sid}/continue`（内部 `engine.dismiss()`）で `exploring` へ戻す。UIの[確認]/[次の階層へ]はこの1本に集約（§25.2）。
> **battle 中の回復 sink は1ターン消費（v1.4・OPEN-020）**：`use_sink('heal_*')` を battle 中に使うと phase は battle のまま**敵の行動のみが解決される**（`_resolve_battle_turn(player_attacks=False)`）。敵の反応で dead / 勝利（反射・好機による撃破）へ遷移し得る。探索中の回復は従来どおりターン消費なし。
> **gate_resolve は瞬間phase**：`POST /gate/resolve` の処理内で next_floor / cleared / dead まで確定するため、`gate_resolve` phase には滞在しない（定数 `PHASE_GATE_RESOLVE` は存在）。**次フロアは gate_resolve 処理内で生成**（RNGストリーム消費）し、`next_floor` 演出 →`continue` で `exploring` に入る。
> **pause は将来（未実装）**：`models.py` の phase 定数は10種で `pause` は未定義（§6.2 図の対象外）。将来追加時は battle 中の ramp・attack_boost_pending の復元を OPEN 化する。
> **選択＝コミット（v1.9 明文化・§7.5）**：`treasure_preview`・`gate_preview`・`heal` から `exploring` への復帰遷移は**存在しない**（遷移図に復帰辺が無いのは仕様）。宝箱・ゲートも敵ノード（§7.1）と同様、選択した時点でコミットされる。GATE 選択時の誤タップ防止（確認ダイアログ）は UI 側の責務（§26.4）。

### 6.2 状態遷移図

```
                    ┌──────────────┐
                    │  exploring   │◄─────────────┐
                    └──────┬───────┘              │
        ┌──────────┬───────┼────────┬─────────┐   │
        ▼          ▼       ▼        ▼         │   │
   ┌────────┐ ┌─────────┐ ┌────┐ ┌──────────┐ │   │
   │ battle │ │treasure │ │heal│ │   gate   │ │   │
   │        │ │_preview │ │    │ │ _preview │ │   │
   └───┬─┬──┘ └────┬────┘ └─┬──┘ └────┬─────┘ │   │
       │ │         │        │         │       │   │
     勝利 HP0    開封      解決      通過      │   │
       │ │         ▼        │         ▼       │   │
       │ │   ┌─────────┐    │   ┌──────────┐  │   │
       │ │   │treasure │    │   │   gate   │  │   │
       │ │   │_opened  │    │   │ _resolve │  │   │
       │ │   └────┬────┘    │   └──┬────┬──┘  │   │
       │ │        │         │   通過│  HP0│    │   │
       │ │        └─────────┴──────┘    │    │   │
       │ │              │               │    │   │
       │ │              └───────────────┼────┘   │
       │ │                              │        │
       │ │         ┌────────────┐  ┌─────────┐   │
       │ │         │ next_floor │  │ cleared │   │
       │ │         └─────┬──────┘  └─────────┘   │
       │ │               └──────────────────────┘
       │ │
       │ └──────────► ┌──────┐
       │              │ dead │
       │              └──────┘
       └─► (戦闘継続はbattle内ループ)
```

> **図注**：battle 勝利時に撃破ドロップ（多親敵・§4.2）がある場合は **battle → treasure_preview** へ遷移する（図では省略）。

### 6.3 拡張ポイント

将来イベント（商人・呪い・隠し部屋）は**新phaseを追加するだけ**で組み込める。
phaseごとに「許可される操作」を制限するため、不正遷移を防ぎやすい。

| 将来phase | 内容 |
|----------|------|
| `merchant` | ゴールドでmod/回復を購入 |
| `curse` | 選択を強制するイベント |
| `hidden_room` | 特定条件で出現する隠し部屋 |

---

### 20.4 ゲーム状態

> 本表は**内部ドメイン状態**。クライアントに返る**API出力の実形は §25.3**（`engine.snapshot()`）であり、フィールド名が一部異なる：内部 `game_phase`→出力 `phase`、内部 `combat_log`→出力 `battle.log`、内部 `floor_state`→出力 `floor`、ノードのロック状態は単独 `locked` ではなく `state`（`available`/`locked`/`resolved`）。
> **`state` が唯一の真実源**で、API の `resolved` は `state=='resolved'` の**読取専用派生**（`Node.snapshot`。同時生成のため乖離しない。dataclass の `Node.resolved` 属性は未使用）。
> **snapshot に出さない内部状態**：`chaos_weights`（カオス比率）・`seed`/`rng_streams`（§17.3 不変条件）・`combat_log`（表示は `battle.log`）は API 出力に含めない。**進行中は `run_record` も null**（RunRecord は seed を含むため終端 phase でのみ開示。v1.4 実装・スナップショットテストで担保）。
> **ゲート保証の二重スコープ**：`gate_guarantee_uses`（エンジン内部・**フロア毎リセット**・snapshot非出力）と `run.gate_guarantee_stacks`（**ラン累計**・RunRecord §19.1）は別フィールド。同名で混同しないよう分離済み。

| フィールド | 型 | 内容 |
|---------|---|------|
| `current_floor` | int | 現在フロア |
| `player` | object | プレイヤーデータ（通貨は `chips`、§0.3） |
| `floor_state` | object | フロア進行状況（ノードは `state` でロック状態を表現） |
| `seed` | int | マスターシード |
| `rng_streams` | object | 9本のストリーム状態 |
| `game_phase` / （API出力では `phase`） | string | §6.1の10phase（＋pause予約・未実装） |
| `battle` | object\|null | 戦闘中一時データ（ログは `battle.log`） |
| `combat_log` | string[] | 表示専用・使い捨て（戦闘終了で破棄可・統計には使わない） |
| `chaos_weights` | object | このランのカオス敵行動比率（ストリーム8から生成） |
| `gate_guarantee_stacks` | int | 現在のゲートでの保証重ねがけ回数 |
| `pending` | object | phase固有の保留データ（API出力、§25.3） |
| `available_actions` | object[] | その時点で許可される操作（cost付き。API出力の正準。§25.3／§26運用原則） |

