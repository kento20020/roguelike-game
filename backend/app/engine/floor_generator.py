"""フロア生成 — 可変深度×あみだくじ型格子（分岐/合流）＋敵割当・宝箱/回復配置・tier/深度補正。

不変条件（validate_floor が生成のたびに強制する）:
- アンロック: 多親=格子内の隣接2親 / 単親=1親 / dead-end（treasure/heal）は必ず単親。
- 全ノードが root（row1）から到達可能。GATE の親は最終rowの main ノード全部（≥2）。
- 最終rowには非カオス敵を最低1体。row内は同一体験タイプ≤2・同一敵の重複なし（プール枯渇時のみ解禁）。
- 1F は fixed_layout（敵固定・反射確定宝箱・回復なし）。
- 接続トポロジーは stream6(floor_topology) のみを消費し、既存ストリームの消費契約（§17.2）を変えない。

格子の作り方（構成的に不変条件を保証する）:
- row幅列: row1=3固定。以降は main_width_min..max から抽選（前rowとの差≤1・最終rowは≥2）。
- 接続: 「単調ステアケースの長さ2窓」— row r+1 の子 j に row r の隣接親 {s_j, s_j+1} を割当。
  s は非減少で 0 から始まり row r の右端-1 で終わるため、全親が最低1子に接続される（到達可能性）。
"""
from __future__ import annotations

from app.data.loader import DataError, GameData
from app.engine.rng import (
    STREAM_ENEMY_POOL,
    STREAM_FLOOR,
    STREAM_GENERAL,
    STREAM_HEAL,
    STREAM_TOPOLOGY,
    GameRNG,
)
from app.schemas.models import EnemyInstance, Floor, Node

ROW1_KEYS = ["L", "M", "R"]  # 1F fixed_layout 用
ROW1_WIDTH = 3               # 生成フロアの row1 幅（3択の開幕は全フロア共通）


class _EnemyBag:
    """統合プールから重複最小で引く袋。枯渇したら再シャッフルして重複を解禁する
    （敵コンテンツ不足への対応: proposals/floor_depth_randomization.md §4.2 の案(a)）。"""

    def __init__(self, pool: list[str], stream):
        self._pool = list(pool)
        self._stream = stream
        self._bag: list[str] = stream.shuffle(list(pool))

    def _refill(self) -> None:
        self._bag = self._stream.shuffle(list(self._pool))

    def draw_row(self, k: int, data: GameData, *, require_non_chaos: bool = False) -> list[str]:
        """row 1本ぶんの敵を引く。row内: 同一体験≤2・同一敵なし（64回の後回しで満たせなければ解禁）。"""
        row: list[str] = []
        exp_count: dict[str, int] = {}
        deferred = 0
        while len(row) < k:
            if not self._bag:
                self._refill()
            eid = self._bag.pop(0)
            ex = data.enemy(eid)["experience"]
            ok = exp_count.get(ex, 0) < 2 and eid not in row
            if not ok and deferred < 64:
                self._bag.append(eid)  # 後回しにして別候補を試す
                deferred += 1
                continue
            row.append(eid)
            exp_count[ex] = exp_count.get(ex, 0) + 1
            deferred = 0
        if require_non_chaos and all(data.enemy(e).get("chaos") for e in row):
            # 最終rowの非カオス保証（プールに非カオスが必ずいることは loader が検証済み）
            if not any(not data.enemy(e).get("chaos") for e in self._bag):
                self._refill()
            for i, eid in enumerate(self._bag):
                if not data.enemy(eid).get("chaos"):
                    self._bag.pop(i)
                    self._bag.append(row.pop())
                    row.append(eid)
                    break
        return row


def _widths(depth: int, gen_cfg: dict, s_topo) -> list[int]:
    """各rowの main 幅。row1=3固定・以降は抽選（前rowとの差≤1・最終rowは≥2）。"""
    lo, hi = gen_cfg["main_width_min"], gen_cfg["main_width_max"]
    widths = [ROW1_WIDTH]
    for r in range(2, depth + 1):
        prev = widths[-1]
        cand = [w for w in range(lo, hi + 1) if abs(w - prev) <= 1]
        if r == depth:
            cand = [w for w in cand if w >= 2] or [2]
        widths.append(cand[s_topo.randint(0, len(cand) - 1)])
    return widths


def _staircase(parent_w: int, child_w: int, s_topo) -> list[int]:
    """row r → r+1 の窓開始位置列。子 j の親は {s_j, s_j+1}。
    s は非減少・s_0=0・s_last=parent_w-2 なので隣接2親＋全親被覆が構成的に成立する。"""
    if parent_w <= 2:
        return [0] * child_w
    # parent_w == 3: 増分1を child_w-1 個の隙間のどこかに置く（一様抽選）
    gap = s_topo.randint(0, child_w - 2)
    return [0 if j <= gap else 1 for j in range(child_w)]


def _multi_drop_chance(enemy_id: str, data: GameData) -> float:
    """多親（関門ルート）敵の宝箱ドロップ率（GDD §11.4: 30%・強敵 +20pt）。"""
    base = data.config["treasure"]["base_chance_multi_parent"]
    bonus = data.config["strong_enemy"]["treasure_chance_bonus_pt"] if data.is_strong(data.enemy(enemy_id)) else 0.0
    return min(1.0, base + bonus)


def _dead_end_node(nid: str, row: int, parent: str, nodes: dict[str, Node],
                   data: GameData, s_floor) -> Node:
    """単親dead-endの宝箱ノード（presence: 60%・親が強敵なら+20pt・stream0）。"""
    u = s_floor.random()
    base = data.config["treasure"]["base_chance_dead_end"]
    bonus = data.config["strong_enemy"]["treasure_chance_bonus_pt"] if data.is_strong(
        data.enemy(nodes[parent].enemy_id)) else 0.0
    eff = min(1.0, base + bonus)
    return Node(id=nid, kind="treasure", row=row, parents=[parent], parent_type="single",
                treasure_roll=u, has_treasure=(u < eff))


def _generate_fixed(fl: dict, data: GameData) -> Floor:
    """1F チュートリアル: floors.json の nodes_layout どおりの固定レイアウト。"""
    nodes: dict[str, Node] = {}
    row1 = fl["nodes_layout"]["row1"]
    for key in ROW1_KEYS:
        nodes[key] = Node(id=key, kind="enemy", row=1, parents=[], parent_type="root",
                          enemy_id=row1[key])
    for key, spec in fl["nodes_layout"]["row2"].items():
        content = spec.get("content", "")
        if spec["type"] == "single" and content.startswith("treasure_guaranteed"):
            node = Node(id=key, kind="treasure", row=2, parents=list(spec["parents"]),
                        parent_type="single", treasure_roll=0.0, has_treasure=True)
            node.fixed_mod = content.split("_")[-1]  # 'hansha'
            nodes[key] = node
        else:
            nodes[key] = Node(id=key, kind="gate_route", row=2,
                              parents=list(spec["parents"]), parent_type="multi")
    gate_parents = [n.id for n in nodes.values() if n.row == 2 and n.parent_type == "multi"]
    nodes["GATE"] = Node(id="GATE", kind="gate", row=3, parents=gate_parents, parent_type="multi")
    return Floor(floor_number=fl["floor_number"], name=fl["name"], nodes=nodes,
                 gate_result_table=fl["gate_result_table"], floor_multiplier=fl["floor_multiplier"])


def generate_floor(floor_number: int, data: GameData, rng: GameRNG) -> Floor:
    fl = data.floor(floor_number)
    if fl.get("fixed_layout"):
        floor = _generate_fixed(fl, data)
        validate_floor(floor, data)
        return floor

    s_floor = rng.stream(STREAM_FLOOR)
    s_pool = rng.stream(STREAM_ENEMY_POOL)
    s_heal = rng.stream(STREAM_HEAL)
    s_gen = rng.stream(STREAM_GENERAL)
    s_topo = rng.stream(STREAM_TOPOLOGY)

    depth = fl["depth"]
    gen_cfg = fl["generation"]
    widths = _widths(depth, gen_cfg, s_topo)
    bag = _EnemyBag(fl["enemy_pool"], s_pool)

    nodes: dict[str, Node] = {}
    grid: list[list[str]] = []  # row順の main ノードid列（列順=格子の位置）

    for r in range(1, depth + 1):
        w = widths[r - 1]
        ids = [f"r{r}_{c}" for c in range(w)]
        enemies = bag.draw_row(w, data, require_non_chaos=(r == depth))
        if r == 1:
            for c, nid in enumerate(ids):
                nodes[nid] = Node(id=nid, kind="enemy", row=1, parents=[], parent_type="root",
                                  enemy_id=enemies[c])
        else:
            starts = _staircase(widths[r - 2], w, s_topo)
            for c, nid in enumerate(ids):
                s = starts[c]
                node = Node(id=nid, kind="enemy", row=r,
                            parents=[grid[-1][s], grid[-1][s + 1]],
                            parent_type="multi", enemy_id=enemies[c])
                # 多親×enemy の撃破ドロップ（GDD §11.4・stream7）
                u = s_gen.random()
                node.treasure_roll = u
                node.has_treasure = u < _multi_drop_chance(enemies[c], data)
                nodes[nid] = node
        grid.append(ids)

    # ── dead-end（単親・宝箱/回復）: 各row遷移で 0..max 個 ──
    dead_ends: list[str] = []
    de_max = gen_cfg.get("dead_ends_max_per_row", 2)
    for r in range(1, depth):  # 親=row r、dead-end は row r+1 に置く
        for i in range(s_topo.randint(0, de_max)):
            parent = grid[r - 1][s_topo.randint(0, len(grid[r - 1]) - 1)]
            nid = f"r{r + 1}_d{i}"
            nodes[nid] = _dead_end_node(nid, r + 1, parent, nodes, data, s_floor)
            dead_ends.append(nid)

    # 回復フロアで dead-end が1つも出なかったら1つ保証する（回復ノード=単親dead-end の維持）
    if fl.get("heal_node") and not dead_ends:
        pr = s_topo.randint(0, depth - 2)
        parent = grid[pr][s_topo.randint(0, len(grid[pr]) - 1)]
        nid = f"r{pr + 2}_dh"
        nodes[nid] = _dead_end_node(nid, pr + 2, parent, nodes, data, s_floor)
        dead_ends.append(nid)

    # 回復ノードを dead-end から1つ選ぶ（stream4）
    if fl.get("heal_node") and dead_ends:
        heal_id = dead_ends[s_heal.randint(0, len(dead_ends) - 1)]
        old = nodes[heal_id]
        nodes[heal_id] = Node(id=heal_id, kind="heal", row=old.row,
                              parents=list(old.parents), parent_type="single")

    # ── GATE（最終rowの main 全部を親に＝最低2本がゲートへ接続） ──
    nodes["GATE"] = Node(id="GATE", kind="gate", row=depth + 1,
                         parents=list(grid[-1]), parent_type="multi")

    floor = Floor(floor_number=floor_number, name=fl["name"], nodes=nodes,
                  gate_result_table=fl["gate_result_table"], floor_multiplier=fl["floor_multiplier"])
    validate_floor(floor, data)
    return floor


def validate_floor(floor: Floor, data: GameData) -> None:
    """生成済みフロアの不変条件チェック（多親=2/単親=1/dead-end単親/GATE親≥2/全ノード到達可能/最終row非カオス≥1）。"""
    errs: list[str] = []
    for n in floor.nodes.values():
        if n.id == "GATE":
            if len(n.parents) < 2:
                errs.append(f"GATE parents {len(n.parents)} < 2")
            continue
        if n.parent_type == "multi" and len(n.parents) != 2:
            errs.append(f"{n.id}: multi must have 2 parents")
        if n.parent_type == "single" and len(n.parents) != 1:
            errs.append(f"{n.id}: single must have 1 parent")
        if n.kind in ("treasure", "heal") and n.parents and n.parent_type != "single":
            errs.append(f"{n.id}: dead-end must be single-parent")
        for p in n.parents:
            if p not in floor.nodes:
                errs.append(f"{n.id}: unknown parent {p}")

    # 到達可能性（アンロック規則: 親のいずれか1つが解決すれば開く → 有向グラフのBFSと同値）
    reachable = {n.id for n in floor.nodes.values() if not n.parents}
    changed = True
    while changed:
        changed = False
        for n in floor.nodes.values():
            if n.id not in reachable and n.parents and any(p in reachable for p in n.parents):
                reachable.add(n.id)
                changed = True
    unreachable = sorted(set(floor.nodes) - reachable)
    if unreachable:
        errs.append(f"unreachable nodes: {unreachable}")

    enemy_rows = [n.row for n in floor.nodes.values() if n.kind == "enemy"]
    if enemy_rows:
        last = max(enemy_rows)
        last_row = [n for n in floor.nodes.values() if n.kind == "enemy" and n.row == last]
        if all(data.enemy(n.enemy_id).get("chaos") for n in last_row):
            errs.append(f"final enemy row {last} has no non-chaos enemy")

    if errs:
        raise DataError(f"floor {floor.floor_number}: " + "; ".join(errs))


def build_enemy_instance(enemy_id: str, floor_number: int, data: GameData,
                         chaos_weights: dict[str, list[tuple[str, int]]] | None = None,
                         row: int = 1) -> EnemyInstance:
    """敵idから戦闘用インスタンスを構築（tier補正＋row深度補正HP・カオスはラン別weight）。"""
    e = data.enemy(enemy_id)
    tier = floor_number
    hp = data.scaled_hp(e, tier, row)
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
