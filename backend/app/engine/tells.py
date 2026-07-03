"""テル（行動の前兆）システム試作: 敵ごとの固定「気配信頼度」ラベル（混同行列較正は範囲外・v2.x候補）。"""

TELL_RELIABILITY = {
    # ── 削り合い: counter主体で堅実 → 読みやすい。ただし高層ほどheavy_blowが混ざり始め崩れてくる。
    "f1_fixed_a": "high",  # counter60/none40 の2択でパターンが単純
    "f2_r1_a": "high",  # counter70/none30 とさらに純粋
    "f3_r1_a": "high",  # counter65/heavy5/none30 まだcounterが支配的
    "f4_r1_a": "mid",  # counter60/heavy10/none30 で3択化・揺らぎ増
    "f5_r3_a": "mid",  # counter45/heavy20/none35 と最も均された配分（頂上格）

    # ── 賭け: heavy_blow/none の二択で「大当たりか空振り」を体験させる設計 → 常に中程度に寄せる
    "f1_fixed_c": "mid",  # heavy_blow50/none50 の完全五分
    "f2_r1_b": "mid",  # heavy_blow40/none60
    "f3_r1_b": "mid",  # heavy_blow45/none55
    "f5_r3_b": "mid",  # heavy_blow70/none30 と偏っても体験の核（賭け）は崩さない

    # ── レース: ramp_hit中心の型がフロア問わず一貫 → 中程度で安定
    "f2_r1_c": "mid",  # ramp_hit60/counter30/none10
    "f3_r2_c": "mid",  # 同型・ramp_increment のみ増加
    "f4_r1_c": "mid",  # 同型
    "f5_r2_c": "mid",  # 同型

    # ── ずれ: evade中心で読みを外しにくる体験 → 信頼度低め
    "f2_r2_d": "low",  # evade50/counter30/none20
    "f3_r1_c": "low",  # evade55/counter25/none20
    "f4_r2_d": "low",  # evade65/counter15/none20

    # ── カオス: chaos:trueでランごとにweightがシード決定される → 最も読みにくい
    "f3_r2_e": "low",
    "f4_r2_e": "low",
    "f5_r2_d": "low",
    "f5_r3_c": "low",
}

DEFAULT_RELIABILITY = "mid"


def tell_reliability(enemy_id: str) -> str:
    return TELL_RELIABILITY.get(enemy_id, DEFAULT_RELIABILITY)
