"""BIDASK.EXE 0xC758 recurrence and 0xC71F real Random() conversion.

Seed zero is present in the data image; complete startup/call-order equivalence
has not been established. This is not the C-library rand() algorithm.
"""


class OriginalRNG:
    def __init__(self, seed: int = 0):
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError('Seed must be an unsigned 32-bit integer')
        self.state = seed

    def random(self) -> float:
        self.state = (self.state * 0x08088405 + 1) & 0xFFFFFFFF
        return self.state / 2**32

    def randbelow(self, count: int) -> int:
        """Integer Random(count) from BIDASK A60:11E9 (0 <= result < count)."""
        if type(count) is not int or count < 0:
            raise ValueError('Count must be a non-negative integer')
        self.state = (self.state * 0x08088405 + 1) & 0xFFFFFFFF
        return 0 if count == 0 else ((self.state >> 16) % count)

    def interval_int(self, lower: int, upper: int) -> int:
        """Inclusive integer interval used by BIDASK 0x4245."""
        if type(lower) is not int or type(upper) is not int:
            raise ValueError('Bounds must be integers')
        return lower + self.randbelow(upper + 1 - lower) if upper > lower else lower

    def interval(self, lower: float, upper: float) -> float:
        # 0x123F returns lower without consuming RNG if upper <= lower.
        return lower + self.random() * (upper - lower) if upper > lower else lower
