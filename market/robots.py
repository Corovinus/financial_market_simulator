"""Autonomous BIDASK participants recovered from the original event loop."""
from dataclasses import dataclass
import math

from .calculations import bond_value
from .engine import Market
from .orderbook import OrderError
from .rng import OriginalRNG


@dataclass(frozen=True)
class RobotEvent:
    actor: int
    instrument: int
    action: str
    price: int
    quantity: int


class RobotController:
    """Run actors 1..N at the reaction interval stored in the PAR file.

    BIDASK 0x6F2E checks every robot against ``reaction_ticks``. Its four
    handlers at 0x4D2E, 0x5129, 0x4B7C and 0x4C55 are respectively sell,
    buy, bid and ask. The original uses six-byte Real values; Python uses
    float here, so exact rounding at decision boundaries is not promised.
    """

    def __init__(self, market: Market, seed: int = 0, actors=None):
        if not isinstance(market, Market):
            raise TypeError('RobotController expects a Market')
        self.market = market
        self.scenario = market.scenario
        self.rng = OriginalRNG(seed)
        self.actors = (tuple(range(1, self.scenario.robots + 1))
                       if actors is None else tuple(actors))
        if (any(type(actor) is not int or actor <= 0 or
                actor >= len(market.portfolios) for actor in self.actors) or
                len(set(self.actors)) != len(self.actors)):
            raise ValueError('Неверные номера участников-роботов')
        self.elapsed_ticks = 0.0
        self.next_actions = []
        self.values = []
        self.start_period(market.period)

    def start_period(self, period: int):
        if type(period) is not int or not 0 <= period < self.scenario.periods:
            raise ValueError('Неверный период роботов')
        self.elapsed_ticks = 0.0
        self.next_actions = [float(self.scenario.reaction_ticks)
                             for _ in self.actors]
        fair = [bond_value(self.scenario, instrument, period)
                for instrument in range(len(self.scenario.names))]
        self.values = []
        for robot, _actor in enumerate(self.actors):
            if robot < self.scenario.wolves:
                self.values.append(tuple(fair))
            else:
                spread = self.scenario.robot_value_spread
                self.values.append(tuple(
                    self.rng.interval(value * (1 - spread),
                                      value * (1 + spread))
                    for value in fair))

    def step(self, elapsed_ticks: float) -> tuple[RobotEvent, ...]:
        if (not isinstance(elapsed_ticks, (int, float)) or
                not math.isfinite(elapsed_ticks) or elapsed_ticks < 0):
            raise ValueError('Время роботов должно быть неотрицательным')
        self.elapsed_ticks += elapsed_ticks
        if self.scenario.strategy != 1:
            return ()
        events = []
        for index, actor in enumerate(self.actors):
            if self.elapsed_ticks <= self.next_actions[index]:
                continue
            event = self._act(actor, self.values[index])
            if event is not None:
                events.append(event)
            self.next_actions[index] = (self.elapsed_ticks +
                                        self.scenario.reaction_ticks)
        return tuple(events)

    def _act(self, actor: int, values: tuple[float, ...]):
        active = [index for index, value in enumerate(values) if value > 0]
        if not active:
            return None
        instrument = active[self.rng.randbelow(len(active))]
        value = values[instrument]
        bid = self.market.book.best(instrument, 'bid')
        ask = self.market.book.best(instrument, 'ask')

        tolerance = {'cautious': -0.02, 'balanced': 0.0,
                     'aggressive': 0.03}[self.scenario.robot_style]
        can_buy = (ask is not None and ask.owner != actor and
                   ask.price <= value * (1 + tolerance))
        can_sell = (bid is not None and bid.owner != actor and
                    bid.price >= value * (1 - tolerance))
        if can_buy or can_sell:
            if can_buy and can_sell:
                side = 'buy' if value - ask.price >= bid.price - value else 'sell'
            else:
                side = 'buy' if can_buy else 'sell'
            quote = ask if side == 'buy' else bid
            quantity = self.rng.interval_int(
                1, min(quote.quantity, self.scenario.robot_max_quantity))
            try:
                trade = self.market.take(actor, instrument, side, quantity)
            except OrderError:
                return None
            return RobotEvent(actor, instrument, side, trade.price, trade.quantity)

        preferred = 'bid' if self.rng.randbelow(2) == 0 else 'ask'
        for side in (preferred, 'ask' if preferred == 'bid' else 'bid'):
            bounds = self._quote_bounds(side, value, bid, ask)
            if bounds is None:
                continue
            price = self.rng.interval_int(*bounds)
            quantity = self.rng.interval_int(
                1, self.scenario.robot_max_quantity)
            try:
                self.market.submit(actor, instrument, side, price, quantity)
            except OrderError:
                continue
            return RobotEvent(actor, instrument, side, price, quantity)
        return None

    def _quote_bounds(self, side, value, bid, ask):
        tolerance = {'cautious': -0.02, 'balanced': 0.0,
                     'aggressive': 0.03}[self.scenario.robot_style]
        bid_limit = value * (1 + tolerance)
        ask_limit = value * (1 - tolerance)
        spread = self.scenario.robot_value_spread
        if side == 'bid':
            lower = (bid.price + 1 if bid else
                     max(1, math.floor(value * (1 - spread) + 1e-9)))
            upper = min(998, math.floor(bid_limit + 1e-9),
                        ask.price - 1 if ask else 998)
        else:
            lower = max(2, math.ceil(ask_limit - 1e-9),
                        bid.price + 1 if bid else 2)
            upper = (ask.price - 1 if ask else
                     min(999, math.ceil(value * (1 + spread) - 1e-9)))
        return (lower, upper) if lower <= upper else None
