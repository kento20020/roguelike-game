# 変更履歴（Changelog）

各版で確定した内容の経緯。現行仕様は本文を正本とし、ここは時系列の記録。

- **v1.9**（2026-07-11）：**設計書ギャップ監査の反映（ドキュメントのみ改訂・コード/JSON/バランス数値は不変）**。docs全読＋3レンズ調査（`reports/2026-07-11_gdd_gap_audit.md`・35所見）を反映。
  - **矛盾訂正（監査反映①）**：api_contract §25.1 を v1.5 セッション永続化の実態（active_sessions＋rebuild_engine による透過復元）へ訂正、architecture §22.3 に workers=1 制約を復元（v1.3 明文化分が分割時に脱落していた）、ONBOARDING §4 へ check_docs.py を追加。
  - **OPEN-030〜042 起票（監査反映②）**：Phase1前数値調整・サイドベット経済検証＋テレメトリ・ランライフサイクル（復帰UX/放棄記録）・リスペック/リセット・型共有自動化・公開準備（PRD §16.3 の旧 OPEN-027 誤参照を OPEN-035 へ付替え）・rebuild版跨ぎ互換・pending契約（§20.8 の旧 OPEN-013 紐づけを OPEN-037 へ付替え）・調書カオス表示・テル開示整合・検死heal死分類・L2解禁仕様・強敵撃破数記録。CONTRIBUTING §4 に「本文の未決は必ず OPEN ID を持つ」規約を追加。
  - **仕様確定（監査反映③・デザイナー決定 2026-07-11）**：①§9.1 の旧 row1 枠規則（枠A/B/C）を**廃止**し、§4.2 袋方式の2制約（同一row内同一体験タイプ≤2・最終row非カオス≥1）へ一本化（「row3(5F)」→「最終row」に統一・§9 表から row1枠 列を削除・§11.3 の row 見出しは歴史的グルーピングと注記）。②**全ノード「選択＝コミット」**を §7.5 として明文化（宝箱・ゲートも exploring へ戻れない。GATE 選択にUI確認ダイアログ必須・§26.4/§6.1）。③サイドベットの賭け対象は**常時5種固定表示・死にベット許容**（サポート集合の非開示維持・§15.4/§5・検証規則と bot_type 規約を §25.2 へ）。
  - **章追加（監査反映④）**：PRD へ §27（ターゲット・プラットフォーム・セッション設計・成功指標・非機能要件・完走後の想定）、frontend_design へ §28（通信規約・エラーUX・セッション復帰骨子・多重タブ・gameStore規約・テスト方針）、operations §18.1 へ観測指標4行（ゲート死率・チップ枯渇・サイドベット収支・ラン実時間）＋§18.6 人間プレイテスト計画（骨子）。数値はいずれも叩き台（要デザイナー確定）。
  - **統治（監査反映⑤）**：design/ の位置づけ（非正本・Claude Design 作業ファイル）を文書統治へ明記、improvement_ideas の fun_metrics 実装仕様 v0.1 参照へ「docs未収録」注記。
  - **デザイナー最終レビュー反映（監査反映⑥・2026-07-11）**：**balance_model.md（統合バランスモデル：フロア別目標カーブ・ゲート累計被ダメ≈56%の可視化・チップ収支・恒久強化差分・調整ノブ対応表＝OPEN-030 の判断基準）**・**playtest_plan.md（人間プレイテスト実施計画・§18.6 の実施正本）**・**ADR-0004（win-to-progress の設計根拠・リスク・緩和策）**を新設。game_design §14.3（FTUE設計目標・OPEN-022 低→中）、PRD §3.1（公平なランダム性の担保）・§27.1（ペルソナ具体化）・§27.3（プレイ時間目標の詳細表：クリアラン15〜25分等）・§27.7（リプレイ性目標＝ビルド4系統）、frontend_design §28.7（UI情報優先度）・§28.8（アクセシビリティ方針＝OPEN-009 の方針正本）、operations §18.1（公平性監視の観測指標）・§18.7（バランス変更手順）・§18.8（QAチェックリスト）、data_model §20.9（コンテンツ追加手順）、runbook §7（公開前チェックリスト＝OPEN-035 の実体）を追加。数値はすべて叩き台（要デザイナー確定）・コード/JSON不変。
- **v1.8**（2026-07-09）：**ジャストガード（guard再設計・OPEN-018大半解消）**。旧仕様（被ダメ一律×0.25・無コスト・回数無制限）は非ランプ敵（ロスター約7割）への「常時受け」が支配戦略になり得た。数値圧縮でなくルールで排除する再設計を採用（`docs/proposals/guard_redesign.md`）。
  - **ジャストガード**：被ダメ軽減率を敵の実際の行動に連動させる（heavy 90%／counter 50%／ramp_hit 50%／none・evade 0%＝空振りは与ダメ半減のコストのみ）。先読み（yomi/tell/scout）の情報を賭けに変える行動へ再定義。
  - **重ねがけ減衰**：同一戦闘内で受けるたび軽減量が半減（`stack_decay 0.5`・空振りもカウント・戦闘毎リセット）。ゲート保証の「重ねがけは効果半減」と同じ哲学。盲guard連打の期待値が急落し、支配戦略が構造的に消える。
  - **bot行動空間の一致（OPEN-018受入条件）**：strong bot に受け方策を実装（`strategy_version=strong-v2`。UIにも公開される`next_action`に対してのみ張る・盲guardしない・3回目以降は張らない）。random bot の guard が無言no-opだった潜在バグも修正。
  - **反実仮想（検死）の忠実化**：`pre_turn_snapshot`に`guard_uses`を追加し、postmortemのguard反転再解決が致命ターン直前の減衰段を引き継ぐようにした（旧データは`.get`で後方互換）。
  - **効果測定**：maxed 強botクリア率 5% → **10.2%**（N=1000・CRN）。ベースライン再生成済み（15/120）。base/mid は依然0%で、深度カーブ等の数値調整（デザイナー・v1.4注記）は引き続きPhase1前に必要。軽減率・減衰係数は叩き台であり、感度分析→デザイナー確定まで Phase1 は開始しない。
  - **感度分析による数値確定**：`guard_sensitivity.py`（N=400・maxedプロファイル・CRN・heavy∈{0.7,0.8,0.9}×decay∈{0.4,0.5,0.7}の9combo×方策{smart/never/always}）で最終数値を検証。always（常時受け）は全comboでクリア≈0%・dominance（always−never）は全comboで負（-3.5〜-3.75pt）＝支配戦略は再発せず、skill_expression（smart−never）は全comboで正（+4.8〜+6.8pt）。最大は heavy0.9×decay0.5（+6.8pt・smart 10.5% vs never 3.8%）で、同率の decay0.7 よりスパム抑止がわずかに強くゲート保証「重ねがけ半減」の哲学とも一致するため採用。**確定値は叩き台のまま（heavy0.9/counter0.5/ramp_hit0.5/stack_decay0.5）＝config.json変更なし**。詳細は `docs/proposals/guard_redesign.md` §8。
- **v1.7**（2026-07-07）：**運用・開発基盤整備**。DevOps監査で見つかった改善項目を順次実装している。
  - **frontend-ci.yml新設**：frontend側のCIが存在せず`npm run typecheck`/`lint`/`build`がPRマージ時に未検証だった問題を解消。`balance.yml`と同型でtypecheck/lint/buildを検証。
  - **Pythonバージョン統一**：`balance.yml`(3.11)と`docs-ci.yml`(3.12)の不一致を3.12に統一し、依存キャッシュも追加。
  - **pip-compileで依存ピン留め**：`backend/requirements.txt`が全て`>=`の範囲指定のみでロックファイルが存在しなかった再現性リスクを解消。`requirements.in`（ランタイム）/`requirements-dev.in`（テスト専用）からpip-compileで完全ピン留めしたロックを生成。
  - **Dependabot有効化**：`.github/dependabot.yml`を新設し、pip（backend）・npm（frontend）・github-actionsの3エコシステムを週次で自動更新PR化。
  - **pytest-cov導入（閾値なし）**：CIでcoverageを計測・可視化するのみに留め、強制ゲート（`--cov-fail-under`）は設けない（統計指標を最適化目標にしないというGoodhart回避の哲学に整合させるため）。
  - **ruff + mypyをCIに追加**：backendに静的解析が一切なく規約が未検証だった状態を解消。ベースライン計測（ruff違反216件・mypyエラー176件＝うち`union-attr`が149件）を踏まえ、段階導入の緩めの厳格度で導入。ruffは`E,F,W,I,B,UP`から開始し、大量に出る/機能価値の低いルール（`E501`93件＝主に日本語コメント・`UP045`56件＝`Optional`モダナイズ・`B008`＝FastAPI `Depends`イディオム・`B905`/`UP047`）はTODO付きで`ignore`、安全な自動修正（未使用import整理・`typing`→`collections.abc`・注釈のアンクォート等）のみ適用（`ruff format`は`git blame`破壊のため不使用）。mypyはエンジンのOptional状態機械設計に起因する`union-attr`等をモジュール単位の`overrides`で緩和（エンジンのロジックは不変・型注釈追加のみ）、簡単な`var-annotated`5件のみ実修正。設定は`backend/pyproject.toml`（`[project]`を持たないツール設定専用）に集約。CLAUDE.mdの「型ヒント必須」規約を`balance.yml`の`lint`ジョブ（`balance`と並列）で自動検証できるようにした。
  - **active_sessions TTL自動化**：`delete_stale_active_sessions`が定義済みだが本番コードから一度も呼ばれていなかった問題を解消。FastAPI lifespan + asyncioバックグラウンドタスクで周期実行（新規依存なし。APSchedulerは既存の最小フットプリント志向に合わせ不採用）。
  - **構造化ログ + request_id伝播**：`X-Request-ID`がレスポンスヘッダには付くがログレコードには自動連携していなかった問題を解消。`contextvars`でrequest_idを全ログレコードへ自動注入し、`LOG_FORMAT=json`でJSON構造化出力に切り替え可能にした（既定は`text`でローカル開発の可読性を維持）。
  - **ONBOARDING.md作成**：`docs/ONBOARDING.md`を新設し、環境構築からテスト・静的解析の回し方までを一本化。README/operations.md/runbook.mdの残課題記述（OPEN-027）からONBOARDINGを解消済みに更新。
- **v1.6**（2026-07-07）：**run_idのseed非依存化**。`run_id = "run-{seed}"` はクライアントが任意指定できる`seed`に由来するため、同一seedの複数ラン（明示指定・共有プレイ等）で衝突し得た（`data_model.md`に既知の限界として記載済みだったが未修正）。放置すると検死レポート取り違えに加え、`crud.run_record_exists`によるクラッシュ復元時finalizeの誤スキップ（RunRecordがサイレントに欠落）にもつながるため修正。`game_engine.new_run()` の run_id 生成を `uuid.uuid4()` ベースに変更し、`run_records`/`postmortems`/`run_actions` の `run_id` にDB UNIQUE制約を追加（`0004_run_id_unique`）。
  - **副作用の是正**：`new_run()`は呼ぶたびに新しいrun_idを発行するため、そのままでは`app.engine.replay.rebuild_engine()`によるキャッシュミス後の再構築のたびにrun_idが変わってしまい、セッション永続化（v1.5）のRunRecord/postmortem参照キーとズレる回帰を生んでいた。`active_sessions`にrun_id列を追加してライブ生成時の値を保存し、`rebuild_engine()`が同じ値へ上書きすることで解消（`0005_active_session_run_id`）。
- **v1.5**（2026-07-07）：**セッション永続化（OPEN-007解消）**。本番で複数人に遊んでもらう際の最大の障害だった「進行中ランがプロセス内メモリのみ・単一プロセス前提」を解消した。
  - **アクションログ再生方式を採用**（GameStateの全フィールドをスナップショットする方式は不採用）：GameEngineは(seed, upgrades, 操作列)の純粋関数（同一seed→同一結果の不変条件）であることを利用し、`active_sessions`テーブルへ「seed＋初期upgrades＋適用アクション列」だけを記録。インメモリキャッシュミス時（再起動・LRU追い出し直後）に`app.engine.replay.rebuild_engine`が`new_run`+アクション再適用で状態を再構築する。フィールド追加のたびに保存/復元コードを同期する必要がなく、将来の変更に自動追従する。
  - **session_storeをLRU上限（既定500）つきキャッシュに変更**：追い出されても実害なし（DBから透過的に復元）。「遊ばれるほどメモリが増え続ける」問題も同時に解消。
  - **DBはSQLiteのままWAL modeを追加**（Redis等の新規インフラは導入せず。将来Postgres移行時も`DATABASE_URL`差し替えのみで済む設計を維持）。
  - `active_sessions`テーブル新設（`0003_active_sessions`）。終局後も即削除せずTTL掃除に委ねる（クリア直後の再起動でGETが404になる退行を避けるため）。
  - スコープ外として明記：認証・複数プロファイル対応（OPEN-026）、複数ワーカー間の同一session_idへの真の同時書き込み競合のハードニング。
- **v1.4**（2026-07-06）：**設計書準拠のベストプラクティス書き換え（コード＋docs同時改訂）**。健康診断（設計-実装一致度監査）で確認した乖離を、docs に方針が明記済みの項目からコード側で解消し、実装が先行していた機能を正本へ昇格させた。
  - **不変条件回復**：seed非露出（§17.3・進行中 run_record=null＋スナップショットテスト）、OPEN-010（勝利時 hp=max(1,hp)）。
  - **異常系ガード**：OPEN-016（保証の削減0で400）・OPEN-017の1F分（確定mod宝箱のリロール400）・OPEN-019（sinkコスト下限1）・OPEN-021（boost持越し＋二重課金400）。
  - **挙動変更**：OPEN-020（battle中healの1ターン消費）・OPEN-015（L2/L3のstate別マスク）・OPEN-012（experienceのromaji enum化）。
  - **テレメトリ/DB**：Alembic導入（0001_baseline/0002_telemetry）、RunRecordへ data_version・strategy_version・sink_use_counts・gate_results・action_counts、run_actions（全ラン操作履歴）新設（OPEN-024/025解消）。OPEN-013 のデータ検査を loader.validate／validate_floor／テストへ実装。
  - **フロア可変深度化＋あみだくじ型接続生成（proposals/floor_depth_randomization.md 採用・クラスS昇格）**：§4を「固定形状の列挙」から「生成規則」へ全面改訂。深度カーブ 2/3/4/5/6・統合enemy_pool・格子ランタイム生成（stream6転用）・depth_scaling。**maxed強botクリア 18/120→6/120（数値調整はデザイナーレビュー待ち・§18.2注記）**。
  - **運用/セキュリティ**：CORSのALLOWED_ORIGINS化・ログ＋X-Request-ID・.env.example・seed/limit入力検証・BattleOut.tell_reliability契約修復・eslint導入・DeadPageのstore集約。
  - **正本昇格**：実装済みの検死リプレイ（§15.2）・ディーラー調書（§15.3）・サイドベット（§15.4）・テル試作（§15.5）を api_contract/data_model/architecture/frontend_design に反映。runbook を実手順化。改善提案アイディア4/6/7/8 は詳細仕様待ちで見送り。
- **v1.3**：**分割後の横断整合レビュー（シニアSE・3巡目）反映・ドキュメントのみ改訂**（コード/JSON/バランス数値は不変）。
  - **矛盾訂正**：§4.1 1Fゲート経路 1本→**2本**（B/C・経路数の定義を新設）、§6.1 battle→**treasure_preview**（撃破ドロップ有）遷移を追加、phase数表記を **10（+pause予約）** に統一（§20.4/§22.2）、§24.6 GatePage の担当を gate_preview のみに訂正（gate_resolve=瞬間phase・§26.4に演出の実体を注記）、§25.3 例の heal_small cost を 2F実値25に訂正、§20.1 `heal_node_config`→実データの `heal_node`/`heal_node_position` に訂正、§5 L4 スカウトを「最頻行動の示唆」（yomi=確定先引きと別商品）に訂正、snapshot非出力テストの「担保する」を**未実装（OPEN-013）**と明示、§4.3 回復ノードを「dead-end 置換」の正確な表現へ。
  - **明文化**：§8.2 **同時解決制**（致死打でも敵行動ロールは実行）、§10.1 反射/好機の発動条件=行動タイプ（実被ダメ0でも発動）・効果量の正本は mods.json、§7.2 空宝箱（kind=treasure のまま・`empty_treasure` 演出）、§11.2 強敵閾値4の終盤退化（4F 7/8・5F 10/10）、§12.3 +max_hp×ゲート被ダメの相互作用・バンク消化導線の未定義、§13.1 期待値の前提未定義、§22.3 **workers=1 制約**、§23 models.py 命名衝突、§18.1 効果量閾値（X/Y/Z/W）の**事前登録**・確定帯は guard 無し測定、§18.2 CI実態（docs-ciのみ稼働）、§20.8 empty_treasure/victory の dismiss 対応未確定、§25.4 400/409 の具体例。
  - **OPEN 改訂**：OPEN-018 中→**高**（guard 支配戦略リスク・**Phase1 前必須・決着まで Phase1 開始不可**）、OPEN-020 中→**高**（018と束ねて決着）、OPEN-004 を「値」→**定義方式**の再設計へ、OPEN-017 から 1F確定宝箱リロール非提示を分離し先行（高・実装前半）、OPEN-024 に strategy_version 同乗＋Phase1 初回データ前へ前倒し、OPEN-025 に guard 記録追加、OPEN-002 に割り振り導線、OPEN-007 に session 上限/DELETE。**OPEN-028（カオスramp空砲）/OPEN-029（初クリア体験曲線）を新規起票**。
- **v1.2**：**実装コードとの実差分監査（doc-code drift audit）に基づく整合改訂**（コード/JSON/バランス数値は不変）。fugu / fugu-ultra 2回のレビュー（剛腕SE上司）の指摘を、GDD単独ではなく **engine/schemas/routes/JSON の実体と照合**して反映。レビューが指摘した重大欠落の多くは**既にコード実装済み**（`/guard`・`/continue`・`/catalog/mods`・`/profile/upgrades`・`PlayerProfile`永続・宝箱撃破ドロップ・カオスramp・特殊+40G）であることを確認し、**実態へGDDを寄せた**。
  - **§0**：版をv1.2へ一括確定（部分更新禁止を§0.1に明記）、通貨正準に `init_gold`、用語集に sink/tier/behaviors 等を追加、§0.2 の検証器を実在 `loader.validate()` に特定。
  - **§4/§11**：宝箱モデルを実装（多親=撃破時30%+20ptドロップ／終端単親dead-end=60%+20pt presence）に一本化、1F形Bは row2_pool 空で B/C=`gate_route`＝敵3体（36体整合）、§4.4 体験タイプ段階導入を実ロスター（ずれ2F/カオス3F）へ訂正、§11.3 レースcounterを 60/30/10 に統一、§11.2 死蔵 `ramp_initial` 削除、強敵閾値を config 参照化。
  - **§5〜§10**：§5 L2/L3未分離を明記（OPEN-015）、§6.1 `/continue`(dismiss)・gate_resolve瞬間phase・pause未実装、§7.4 特殊=+40G・削減0課金(OPEN-016)、§7.2 リロール限界(OPEN-017)、§8.2 フック位置を実装順へ、§8.4 受け(guard)を A案改訂として反映(OPEN-018)、§8.5/§9.2 カオスramp=base_initial(5)・Dirichlet決定論、§8.6 base_damage定義、§10 好機の追撃仕様・見切り×先読みの正確な挙動。
  - **§12/§13**：**「26点」→21点**（config.json コメントの同誤記は human 対応）、恒久強化の `ProfileRow` 永続、-sinkコスト式と scout無料化(OPEN-019)・heal非消費(OPEN-020)・攻撃ブースト異常系(OPEN-021)。
  - **§17〜§20**：RNG導出式（`master_seed ^ stream_id×0x9E3779B9`）・ストリーム消費契約・先読み消費・seed非直列化、§18 死亡分布の終盤集中許容・効果量ゲート・ツール帰属、§19 death_cause の gate 表現・run_id≠session_id・data_version/use_count 欠落(OPEN-024/025)、§20 snapshot非出力・state唯一真実源・PlayerProfile(§20.6)・値集合(§20.7)・pendingスキーマ(§20.8)。
  - **§22〜§26**：PostgreSQL「1行移行」撤回、tests/と運用未整備(OPEN-027)、§24 props整合・NextFloorPage/StartPage、§25 in-memory永続・4エンドポイント追加・冪等/認証非スコープ(OPEN-026)・battle/pending実例・400/409判定順、§26 受けボタン・特殊+40G・表示ラベル・heal/next_floor画面。
  - **OPEN-011〜027 を新規起票**（doc-code drift 由来）。運用系（Alembic/Docker/バックアップ/構造化ログ/RUNBOOK）は GDD 外の別タスクとして OPEN-027 に集約。
- **v0.6**：基礎を確定。パーマデス／5フロア／evade二重定義解消／戦闘内意思決定A案／ダメージ式／スケーリング式／強敵リワード／確率開示=暗黙知型／乱数アーキテクチャ（SFC32）／検証フレームワーク／強プレイのクリア率25〜40%。
- **v0.7**：14項目の設計決定を反映。アンロック連鎖をハイブリッド型（多親=隣接2体／単親=1体）で確定・全形状マッピング、sink使用タイミング、game_phaseの厳密型再設計、問E恒久強化（ポイント割り振り・上限レベル制）、発見型チュートリアル、死亡/クリア画面、カオスのランごとシード決定、コンバットログ全保持、modインタラクション拡張スキーマ、RunRecord全フィールド、フロア別ゲートテーブル、問F貯め込み逓減の自然解決、問D世界観（カジノ・賭博都市）、プレイヤー動機を確定。
- **v0.8**：実装のための技術仕様を追加。§22 技術スタック（React+TypeScript+Vite / Zustand / Tailwind / FastAPI / SQLite）、§23 ディレクトリ構成、§24 コンポーネントリスト、§25 APIエンドポイント仕様、§26 画面設計。
- **v0.9**：ゴールド経済を再設計。ゲート保証を確実突破から確率シフト型（大ダメのみ削る・特殊維持）へ、重ねがけを効果半減＋コスト微増の二重ブレーキで可能化、回復sinkをフロアコスト上昇＋固定値化、スカウトを強敵戦の道具として明確化、攻めのsink「攻撃ブースト（次の1撃のみ）」を追加。
- **v1.0**：矛盾解消・データ確定・テーマ転換。レース系weight（ramp_hit60/counter30/none10）、ramp初期値（base_initial=5＋敵ごとinc）、ダメージ係数（counter_factor=1.0/heavy_factor=1.8、config共通＋敵上書きのフォールバック）、1F反射mod配置、攻撃ブースト×フェーズBの乗算、強敵リワード+20pt（絶対値加算）、ゲート保証の半々split、ログ二重管理の役割分離、回復ノードと回復sinkの別系統化を確定。データファイル（config/enemies/mods/floors.json：全36体・6mod・5フロア）を機械検証パス済みで確定。**テーマ転換「地下に潜る → カジノタワーを登り詰める」**：UI描画が下から上（row1=画面下、ゲート=画面上）のSlay the Spire型になったことに合わせ、物語・固有名詞も「登る」で一貫させた。

- **v1.1**：**実装整合・ドキュメントのみ改訂**（コード/JSON/バランス数値は不変）。実装との突き合わせで判明したドリフト・記述不足を訂正し、実務の定義書として整備した。
  - **新設**：§0 文書管理（メタ／正本の優先順位／gold・chips の正準／v1.1スコープ／用語集）、§8.6 丸め規約、§18.5 受け入れ基準（完了の定義）、§21.1 確定状態マトリクス。
  - **用語**：通貨は実行時/UI=`chips`・永続/統計=`gold_*`・config=`gold` と正準化（現状追認、変換点1箇所）。`game_phase`→出力`phase`、ノードは`state`（available/locked/resolved）。§10.1に mod `id`列追加。
  - **実装準拠の訂正**：§8.2 ramp再計算を§8.5整合へ＋同時死亡=勝利優先を明記、evade処理順を注記。§7.4 ゲート保証に下限クランプ `min(現在の大ダメ率, 削減量)` を明記し「必ず残る」を訂正。§11.3 表のhpは`base_hp`（実HP=tierスケーリング後）と明記。§5/§13.2 スカウトを「battle時のみ」に訂正。§9.2 カオス生成を真のDirichlet実装に沿って記述。
  - **整合**：§6.1 gate_resolve→cleared追記、§18.3 ツール群を実在ファイルに同期（llm_content_pipeline=将来）、§19.2/§10.5 リプレイ要件（seed＋操作履歴＋データ版）を明記、§20.4 に pending/available_actions、§25.2 sink_typeから`treasure_reroll`削除（専用ルート）、§25.4 phase不整合409マトリクス、§26.1 画面図をrow1下・ゲート上へ修正、§22.3 にUI=available_actions信頼の原則追記。
  - **整理**：§11.1 命名を OPEN-001 化（実置換せず）、§21 未決事項を `OPEN-xxx` ID＋対応フェーズ列へ。冒頭ステータスから「矛盾ゼロ」を撤回。口語表現（チートすぎる等）を仕様文へ言い換え。
  - **2巡目レビュー反映**：§12.1 通貨を `chips` 化、§7.4 ゲート保証例表を実計算（3回目=削減-2.5%・大ダメ0%・コスト112G・累計237G）へ修正、§8.6 `round()` を ties-to-even（銀行丸め）と正しく記述、§8.2 勝利優先時のHP0クランプ挙動を明記しHP1補正を OPEN-010 化、§24 props を chips/state/nodes へ整合、§6.1 リロール後は phase 不変に訂正、§7.4 特殊=被ダメ0のみ・追加効果未実装を明記、§9.2 Dirichlet の各カテゴリ範囲5〜85%を補足、§10.4 mod_interactions を id 表記へ、§13 章名を「チップ経済システム」へ。なおファイル名はバージョンレス固定のため変更なし。

---

> 現行版は**本ファイル先頭のエントリ**を正とする（版入りフッタは自ファイル内ドリフトの温床のため v1.9 で廃止・構成監査 F-05）。
