"""テル（行動の前兆）システム試作: 敵ごとの固定「気配信頼度」ラベル（混同行列較正は範囲外・v2.x候補）。"""

TELL_RELIABILITY = {
    # 削り合い(f1_fixed_a): counter/none の2択でパターンが単純 → 読みやすい
    "f1_fixed_a": "high",
    # 賭け(f1_fixed_c): heavy_blow/none の五分 → 中程度
    "f1_fixed_c": "mid",
    # レース(f2_r1_c): ramp_hit中心だがcounter混在 → 中程度
    "f2_r1_c": "mid",
    # ずれ(f2_r2_d): evade中心で読みを外しにくる体験 → 信頼度低め
    "f2_r2_d": "low",
    # カオス(f3_r2_e): ランごとにweightがシード決定される → 最も読みにくい
    "f3_r2_e": "low",
}

DEFAULT_RELIABILITY = "mid"


def tell_reliability(enemy_id: str) -> str:
    return TELL_RELIABILITY.get(enemy_id, DEFAULT_RELIABILITY)
