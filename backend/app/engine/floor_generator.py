"""フロア生成 — ツリー構築・敵割当・宝箱/回復配置・tier補正。

不変条件:
- アンロック: 多親=隣接2親 / 単親=1親 / dead-end は必ず単親。
- 1F は fixed_layout（敵固定・反射確定宝箱・回復なし）。
- row2 同一体験タイプ≤2。5F row3 はカオス以外最低1体（pool が保証）。
- tier補正: hp = base_hp × (1 + 0.15×(tier-1))、tier=floor_number。
- 宝箱presence: dead-end 60%（親が強敵なら +20pt）。中身modは開封時抽選。
"""
from __future__ import annotations

from app.data.loader import GameData
from app.engine.rng import (
    STREAM_ENEMY_POOL,
    STREAM_FLOOR,
    STREAM_GENERAL,
    STREAM_HEAL,
    GameRNG,
)
from app.schemas.models import EnemyInstance, Floor, Node

ROW1_KEYS = ["L", "M", "R"]


def _row2_map(fl: dict) -> dict:
    if fl.get("fixed_layout"):
        return fl["nodes_layout"]["row2"]
    if fl["floor_number"] == 5:
        return fl["unlock_map"]["row1_to_row2"]
    return fl["unlock_map"]


def _sample_enemies(pool: list[str], k: int, data: GameData, stream) -> list[str]:
    """pool から k 体を抽選（row2 同一体験≤2 を満たす）。"""
    if k <= 0 or not pool:
        return []
    for _ in range(64):  # リジェクションサンプリング（少数なので十分収束）
        cand = stream.shuffle(list(pool))[:k]
        exp_count: dict[str, int] = {}
        ok = True
        for eid in cand:
            ex = data.enemy(eid)["experience"]
            exp_count[ex] = exp_count.get(ex, 0) + 1
            if exp_count[ex] > 2:
                ok = False
                break
        if ok:
            return cand
    return stream.shuffle(list(pool))[:k]  # 念のためのフォールバック


def _multi_drop_chance(enemy_id: str, data: GameData) -> float:
    """多親（関門ルート）敵の宝箱ドロップ率（GDD §11.4: 30%・強敵 +20pt）。"""
    base = data.config["treasure"]["base_chance_multi_parent"]
    bonus = data.config["strong_enemy"]["treasure_chance_bonus_pt"] if data.is_strong(data.enemy(enemy_id)) else 0.0
    return min(1.0, base + bonus)


def generate_floor(floor_number: int, data: GameData, rng: GameRNG) -> Floor:
    fl = data.floor(floor_number)
    s_floor = rng.stream(STREAM_FLOOR)
    s_pool = rng.stream(STREAM_ENEMY_POOL)
    s_heal = rng.stream(STREAM_HEAL)
    s_gen = rng.stream(STREAM_GENERAL)
    # 多親×enemy の撃破ドロップ（1F=fixed_layout は固定宝箱のみ＝除外）。
    drop_enabled = not fl.get("fixed_layout")

    nodes: dict[str, Node] = {}

    # ── row1（root 敵）──
    row1_pool = fl["row1_pool"]
    for i, key in enumerate(ROW1_KEYS):
        nodes[key] = Node(id=key, kind="enemy", row=1, parents=[], parent_type="root",
                          enemy_id=row1_pool[i])

    # ── row2 ──
    row2 = _row2_map(fl)
    multi_keys = [k for k, spec in row2.items() if spec["type"] == "multi"]
    single_keys = [k for k, spec in row2.items() if spec["type"] == "single"]

    # multi スロットに敵を割当（pool が空なら gate_route 通過ノード）
    row2_pool = fl.get("row2_pool", [])
    assigned = _sample_enemies(row2_pool, len(multi_keys), data, s_pool) if row2_pool else []
    for idx, key in enumerate(sorted(multi_keys)):
        spec = row2[key]
        if idx < len(assigned):
            node = Node(id=key, kind="enemy", row=2, parents=list(spec["parents"]),
                        parent_type="multi", enemy_id=assigned[idx])
            if drop_enabled:
                u = s_gen.random()
                node.treasure_roll = u
                node.has_treasure = u < _multi_drop_chance(assigned[idx], data)
            nodes[key] = node
        else:
            nodes[key] = Node(id=key, kind="gate_route", row=2,
                              parents=list(spec["parents"]), parent_type="multi")

    # 回復ノードを単親dead-endから1つ選ぶ（heal_node True のフロアのみ）
    heal_key = None
    if fl.get("heal_node") and single_keys:
        heal_key = single_keys[s_heal.randint(0, len(single_keys) - 1)]

    # 単親dead-end = 宝箱 or 回復
    for key in single_keys:
        spec = row2[key]
        parent = spec["parents"][0]
        if key == heal_key:
            nodes[key] = Node(id=key, kind="heal", row=2, parents=[parent], parent_type="single")
            continue
        # 1F A は反射確定宝箱
        content = spec.get("content", "")
        if content.startswith("treasure_guaranteed"):
            node = Node(id=key, kind="treasure", row=2, parents=[parent], parent_type="single",
                        treasure_roll=0.0, has_treasure=True)
            node.fixed_mod = content.split("_")[-1]  # 'hansha'
            nodes[key] = node
            continue
        # 宝箱presence: dead-end 60%（親が強敵なら +20pt）
        u = s_floor.random()
        base = data.config["treasure"]["base_chance_dead_end"]
        bonus = data.config["strong_enemy"]["treasure_chance_bonus_pt"] if data.is_strong(
            data.enemy(nodes[parent].enemy_id)) else 0.0
        eff = min(1.0, base + bonus)
        nodes[key] = Node(id=key, kind="treasure", row=2, parents=[parent], parent_type="single",
                          treasure_roll=u, has_treasure=(u < eff))

    final_enemy_row = 2

    # ── 5F row3 ──
    if floor_number == 5:
        r2r3 = fl["unlock_map"]["row2_to_row3"]
        row3_pool = fl["row3_pool"]
        keys3 = sorted(r2r3.keys())
        assigned3 = _sample_enemies(row3_pool, len(keys3), data, s_pool)
        for idx, key in enumerate(keys3):
            spec = r2r3[key]
            node = Node(id=key, kind="enemy", row=3, parents=list(spec["parents"]),
                        parent_type="multi", enemy_id=assigned3[idx])
            if drop_enabled:
                u = s_gen.random()
                node.treasure_roll = u
                node.has_treasure = u < _multi_drop_chance(assigned3[idx], data)
            nodes[key] = node
        final_enemy_row = 3

    # ── GATE（最終敵row の multi ノードを親に）──
    gate_parents = [n.id for n in nodes.values()
                    if n.row == final_enemy_row and n.parent_type == "multi"]
    nodes["GATE"] = Node(id="GATE", kind="gate", row=final_enemy_row + 1,
                         parents=gate_parents, parent_type="multi")

    return Floor(
        floor_number=floor_number, name=fl["name"], nodes=nodes,
        gate_result_table=fl["gate_result_table"], floor_multiplier=fl["floor_multiplier"],
    )


def build_enemy_instance(enemy_id: str, floor_number: int, data: GameData,
                         chaos_weights: dict[str, list[tuple[str, int]]] | None = None) -> EnemyInstance:
    """敵idから戦闘用インスタンスを構築（tier補正HP・カオスはラン別weight）。"""
    e = data.enemy(enemy_id)
    tier = floor_number
    hp = data.scaled_hp(e, tier)
    if e.get("chaos"):
        behaviors = [(t, w) for t, w in (chaos_weights or {}).get(enemy_id, [])]
    else:
        behaviors = [(b["type"], b["weight"]) for b in e["behaviors"]]
    return EnemyInstance(
        id=e["id"], name=e["name"], experience=e["experience"],
        max_hp=hp, hp=hp, attack=e["attack"], difficulty=e["difficulty"],
        gold_base=e["gold_base"], chaos=bool(e.get("chaos")), behaviors=behaviors,
        ramp_increment=e.get("ramp_increment", 0),
        heavy_factor=data.coeff(e, "heavy_factor"),
        counter_factor=data.coeff(e, "counter_factor"),
        is_strong=data.is_strong(e),
    )
