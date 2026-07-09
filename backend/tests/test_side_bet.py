"""サイドベット『読み宣言』プロトタイプ: stream2(behavior_roll)の既存ロールをそのまま使い、
新規RNG消費は一切しないことの回帰テスト＋判定/検証ロジック。
"""
import pytest

from app.engine.game_engine import GameEngine, InvalidMove


def _enter_battle(data, seed=1, chips=200):
    eng = GameEngine(data)
    eng.new_run(seed)
    eng.select_node("L")
    assert eng.phase == "battle"
    eng.player.chips = chips  # 初期チップは0（base_gold=0）のためベット検証用に補充
    return eng


def test_side_bet_does_not_consume_new_rng(data):
    """最重要: 同一 seed から side_bet あり/なしで attack した場合、res["action"]（streamの消費結果）
    が完全に同一であること = サイドベットが新規RNG消費をしていないことの回帰テスト。"""
    eng_a = _enter_battle(data, seed=1)
    eng_b = _enter_battle(data, seed=1)

    # 同一シード・同一初期状態から、片方だけ side_bet を付けて attack。
    snap_a = eng_a.attack(side_bet=None)
    snap_b = eng_b.attack(side_bet={"behavior": "counter", "amount": 5})

    # 行動ロール結果(=streamの消費結果)が完全一致 → 敵の被ダメ・敵HP・プレイヤーHPが一致。
    assert snap_a["battle"]["enemy"]["hp"] == snap_b["battle"]["enemy"]["hp"]
    assert snap_a["player"]["hp"] == snap_b["player"]["hp"]
    assert snap_a["battle"]["ramp_value"] == snap_b["battle"]["ramp_value"]

    # 以降複数ターン回しても、逐ターン side_bet の有無で挙動が変わらないことを確認。
    for _ in range(5):
        if eng_a.phase != "battle" or eng_b.phase != "battle":
            break
        ra = eng_a.attack(side_bet=None)
        rb = eng_b.attack(side_bet={"behavior": "heavy_blow", "amount": 5})
        assert ra["battle"] is None or rb["battle"] is None or (
            ra["battle"]["enemy"]["hp"] == rb["battle"]["enemy"]["hp"]
            and ra["player"]["hp"] == rb["player"]["hp"]
        )


def test_side_bet_hit_pays_out_multiplier_minus_one(data):
    """的中時: player.chips += amount * (payout_multiplier - 1)。"""
    eng = _enter_battle(data, seed=1)
    mult = data.config["side_bet"]["payout_multiplier"]
    chips_before = eng.player.chips

    snap = eng.attack(side_bet=None)
    next_action = None
    # 直前の attack で next_action が分からないので、素の attack 結果から実際の action を
    # 別エンジンで確認してから正解を当てにいく（stream 消費は決定論的なので同一 seed で再現可能）。
    eng2 = _enter_battle(data, seed=1)
    ref_snap = eng2.attack(side_bet=None)
    # 敵の log から行動が特定できないため、ダメージ量から action を逆算する代わりに、
    # 全 behavior を試して一致するものを的中させる形で判定を検証する。
    behaviors = ["none", "counter", "heavy_blow", "ramp_hit", "evade"]
    hit_found = False
    for beh in behaviors:
        e = _enter_battle(data, seed=1)
        before = e.player.chips
        s = e.attack(side_bet={"behavior": beh, "amount": 5})
        result = s["battle"]["side_bet_result"] if s["battle"] else None
        if result is None:
            continue
        if result["hit"]:
            hit_found = True
            assert result["payout"] == round(5 * (mult - 1))
            assert e.player.chips == before + result["payout"]
        else:
            assert result["payout"] == -5
            assert e.player.chips == before - 5
    assert hit_found, "5種の behavior のいずれかは的中するはず"


def test_side_bet_miss_forfeits_amount(data):
    """外れ時: player.chips -= amount（没収）。"""
    eng = _enter_battle(data, seed=1)
    # "none" 以外との組み合わせで意図的に外させるため、behaviors を総当りして外れケースを1つ拾う。
    for beh in ["none", "counter", "heavy_blow", "ramp_hit", "evade"]:
        e = _enter_battle(data, seed=1)
        before = e.player.chips
        s = e.attack(side_bet={"behavior": beh, "amount": 5})
        result = s["battle"]["side_bet_result"] if s["battle"] else None
        if result and not result["hit"]:
            assert result["payout"] == -5
            assert e.player.chips == before - 5
            return
    pytest.fail("外れケースが1つも再現できなかった")


def test_side_bet_result_cleared_next_turn(data):
    """side_bet_result は表示専用・次ターンでクリアされる。"""
    eng = _enter_battle(data, seed=1)
    snap = eng.attack(side_bet={"behavior": "counter", "amount": 5})
    assert snap["battle"] is not None
    assert snap["battle"]["side_bet_result"] is not None
    if eng.phase == "battle":
        snap2 = eng.attack(side_bet=None)
        if snap2["battle"] is not None:
            assert snap2["battle"]["side_bet_result"] is None


def test_side_bet_amount_below_min_raises(data):
    eng = _enter_battle(data, seed=1)
    min_amount = data.config["side_bet"]["min_amount"]
    with pytest.raises(InvalidMove):
        eng.attack(side_bet={"behavior": "counter", "amount": min_amount - 1})


def test_side_bet_amount_above_max_raises(data):
    eng = _enter_battle(data, seed=1)
    max_amount = data.config["side_bet"]["max_amount"]
    with pytest.raises(InvalidMove):
        eng.attack(side_bet={"behavior": "counter", "amount": max_amount + 1})


def test_side_bet_per_battle_cap_exceeded_raises(data):
    eng = _enter_battle(data, seed=1)
    cap = data.config["side_bet"]["max_amount"]
    per_battle_cap = data.config["side_bet"]["per_battle_cap"]
    max_amount = data.config["side_bet"]["max_amount"]
    eng.player.chips = 9999
    total = 0
    # cap を超えるまで賭け続ける。
    while total + max_amount <= per_battle_cap and eng.phase == "battle":
        eng.attack(side_bet={"behavior": "none", "amount": max_amount})
        total += max_amount
    assert eng.phase == "battle", "テスト前提: まだ戦闘中であること（弱い敵で長引かせる想定）"
    with pytest.raises(InvalidMove):
        eng.attack(side_bet={"behavior": "none", "amount": max_amount})


def test_side_bet_insufficient_chips_raises(data):
    eng = _enter_battle(data, seed=1)
    eng.player.chips = 3  # min_amount(5) 未満
    with pytest.raises(InvalidMove):
        eng.attack(side_bet={"behavior": "counter", "amount": 5})


def test_snapshot_exposes_side_bet_rules_and_last_turn(data):
    """表示契約: フロントが config.json の数値(payout/cap等)を複製せずに済むよう
    snapshot の battle に side_bet 規則を載せる。last_turn は直近ターンの実現結果
    （ログ表示済みの公開情報のみ）で、UIがログ文言を文字列解析せず演出分岐するための構造化契約。"""
    eng = _enter_battle(data, seed=1)
    s = eng.snapshot()
    cfg = data.config["side_bet"]
    assert s["battle"]["side_bet"] == {
        k: cfg[k] for k in ("min_amount", "max_amount", "payout_multiplier", "per_battle_cap")
    }
    assert s["battle"]["last_turn"] is None  # ターン解決前は無し

    s2 = eng.attack()
    if s2["phase"] == "battle":
        lt = s2["battle"]["last_turn"]
        assert lt["guard"] is False
        assert lt["action"] in {"counter", "heavy_blow", "evade", "ramp_hit", "none"}
        s3 = eng.guard()
        if s3["phase"] == "battle":
            assert s3["battle"]["last_turn"]["guard"] is True
