"""決定論的乱数 — SFC32（32bit）と9本の独立ストリーム。

不変条件（CLAUDE.md）:
- 同一 master seed → 同一結果（golden test で凍結）。
- 用途別に9本の独立ストリーム（config.rng_streams）。**ストリームを混ぜない。**
- 1本のストリームから引いた乱数が他ストリームに影響しない。

将来 TS 版を実装する際は、この golden vector（tests/test_rng.py）に一致させること。
"""
from __future__ import annotations

MASK = 0xFFFFFFFF


def _splitmix32_next(state: int) -> tuple[int, int]:
    """splitmix32: 32bit 種を撹拌して次の語と新しい state を返す。"""
    state = (state + 0x9E3779B9) & MASK
    z = state
    z = ((z ^ (z >> 16)) * 0x21F0AAAD) & MASK
    z = ((z ^ (z >> 15)) * 0x735A2D97) & MASK
    z = (z ^ (z >> 16)) & MASK
    return z, state


class Sfc32:
    """SFC32 1ストリーム。state = (a, b, c, d)。"""

    __slots__ = ("a", "b", "c", "d")

    def __init__(self, seed: int):
        # splitmix32 で a,b,c,d を充填 → warmup でよく混ぜる
        s = seed & MASK
        words = []
        for _ in range(4):
            w, s = _splitmix32_next(s)
            words.append(w)
        self.a, self.b, self.c, self.d = words
        for _ in range(15):  # warmup
            self.next_u32()

    def next_u32(self) -> int:
        a, b, c, d = self.a, self.b, self.c, self.d
        t = (((a + b) & MASK) + d) & MASK
        d = (d + 1) & MASK
        a = b ^ (b >> 9)
        b = (c + ((c << 3) & MASK)) & MASK
        c = (((c << 21) & MASK) | (c >> 11)) & MASK
        c = (c + t) & MASK
        self.a, self.b, self.c, self.d = a & MASK, b & MASK, c & MASK, d & MASK
        return t & MASK

    def random(self) -> float:
        """[0, 1) の float。"""
        return self.next_u32() / 4294967296.0

    def randint(self, lo: int, hi: int) -> int:
        """[lo, hi]（両端含む）の整数。"""
        if hi < lo:
            raise ValueError("hi < lo")
        span = hi - lo + 1
        return lo + (self.next_u32() % span)

    def choice(self, seq):
        return seq[self.randint(0, len(seq) - 1)]

    def weighted_index(self, weights: list[float]) -> int:
        """weight 比でインデックスを抽選。"""
        total = float(sum(weights))
        if total <= 0:
            raise ValueError("weights sum must be > 0")
        r = self.random() * total
        for i, w in enumerate(weights):
            if r < w:
                return i
            r -= w
        return len(weights) - 1  # 浮動小数の端数対策

    def shuffle(self, seq: list) -> list:
        """Fisher-Yates（in place、同 seq を返す）。"""
        for i in range(len(seq) - 1, 0, -1):
            j = self.randint(0, i)
            seq[i], seq[j] = seq[j], seq[i]
        return seq


class GameRNG:
    """master seed から9本の独立ストリームを導出して保持する。

    ストリームは config.rng_streams のIDで参照（0..8）。各ストリームは
    seed = master_seed ^ (stream_id * 0x9E3779B9) から構成され、互いに独立。
    """

    NUM_STREAMS = 9

    def __init__(self, master_seed: int):
        self.master_seed = master_seed & MASK
        self._streams: dict[int, Sfc32] = {}

    def stream(self, stream_id: int) -> Sfc32:
        if not (0 <= stream_id < self.NUM_STREAMS):
            raise ValueError(f"stream_id out of range: {stream_id}")
        st = self._streams.get(stream_id)
        if st is None:
            derived = (self.master_seed ^ ((stream_id * 0x9E3779B9) & MASK)) & MASK
            st = Sfc32(derived)
            self._streams[stream_id] = st
        return st


# config.rng_streams の用途名 → ID（参照しやすい定数）
STREAM_FLOOR = 0
STREAM_ENEMY_POOL = 1
STREAM_BEHAVIOR = 2
STREAM_TREASURE = 3
STREAM_HEAL = 4
STREAM_GATE = 5
STREAM_TOPOLOGY = 6  # フロア接続トポロジー生成（旧stance予約枠を転用。9本不変条件を維持）
STREAM_GENERAL = 7
STREAM_CHAOS = 8
