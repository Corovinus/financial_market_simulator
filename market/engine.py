"""BIDASK market state for a single original PAR scenario."""
from dataclasses import dataclass
from .calculations import future_capital, settle
from .config import Scenario
from .orderbook import OrderBook, OrderError, Quote, Trade


def _word(value):
    """Store a Pascal ``word`` exactly as BIDASK does (two's-complement wrap)."""
    value = int(value) & 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


@dataclass
class Portfolio:
    cash: float
    positions: list[int]


class Market:
    """Manual and robot-facing market state.

    Actor 0 is the human.  Actors 1..robots are initialized from the same PAR
    row, as the original BIDASK initialization does. ``RobotController`` calls
    the same ``submit``/``take`` methods for autonomous participants.
    """
    def __init__(self, scenario: Scenario):
        if not isinstance(scenario, Scenario):
            raise TypeError('Market expects a Scenario')
        self.scenario = scenario
        self.portfolios = [Portfolio(scenario.cash, list(scenario.positions))
                           for _ in range(scenario.robots + 1)]
        self.book = OrderBook(len(scenario.names), scenario.queue)
        self._recent_trades = [[] for _ in scenario.names]
        self.period = 0
        self.started = False
        self.replay_frames = []

    @property
    def history(self):
        return self.book._history

    def _actor(self, actor):
        if type(actor) is not int or not 0 <= actor < len(self.portfolios):
            raise OrderError('Неверный номер участника')

    def start_period(self, period=None):
        if period is not None:
            if type(period) is not int or not 0 <= period < self.scenario.periods:
                raise ValueError('Неверный период')
            self.period = period
        self.book.reset()
        for trades in self._recent_trades:
            trades.clear()
        for instrument, prices in enumerate(self.scenario.fixed_prices):
            price = prices[self.period]
            if price is not None and self.scenario.tradable[instrument]:
                self.book.submit(1, instrument, 'bid', price, 99)
                self.book.submit(1, instrument, 'ask', price, 99)
        self.started = True
        self._record_replay('start_period')

    def submit(self, actor, instrument, side, price, quantity):
        self._actor(actor)
        self._instrument_available(instrument)
        if self.scenario.fixed_prices[instrument][self.period] is not None:
            raise OrderError('На этом рынке цена задаётся извне')
        quote = self.book.submit(actor, instrument, side, price, quantity)
        self._record_replay(side, actor, instrument, quote.price,
                            quote.quantity)
        return quote

    def take(self, actor, instrument, side, quantity):
        self._actor(actor)
        self._instrument_available(instrument)
        if side not in ('buy', 'sell'):
            raise OrderError('Сторона должна быть buy или sell')
        column = 'ask' if side == 'buy' else 'bid'
        quote = self.book.best(instrument, column)
        seller = quote.owner if side == 'buy' and quote is not None else actor
        fixed = self.scenario.fixed_prices[instrument][self.period]
        if (quote is not None and not self.scenario.short_sales and
                not (fixed is not None and seller == 1) and
                self.portfolios[seller].positions[instrument] < quantity):
            raise OrderError('Короткая позиция на этом рынке запрещена')
        trade = self.book.take(actor, instrument, side, quantity)
        self._recent_trades[instrument].insert(0, trade)
        buyer, seller = trade.buyer, trade.seller
        value = trade.price * trade.quantity
        self.portfolios[buyer].cash -= value
        self.portfolios[buyer].positions[instrument] = _word(self.portfolios[buyer].positions[instrument] + trade.quantity)
        self.portfolios[seller].cash += value
        self.portfolios[seller].positions[instrument] = _word(self.portfolios[seller].positions[instrument] - trade.quantity)
        if fixed is not None and self.book.best(instrument, column) is None:
            self.book.submit(1, instrument, column, fixed, 99)
        self._record_replay(side, actor, instrument, trade.price,
                            trade.quantity, trade.buyer, trade.seller)
        return trade

    def _instrument_available(self, instrument):
        if (type(instrument) is not int or
                not 0 <= instrument < len(self.scenario.names)):
            raise OrderError('Неверный номер бумаги')
        if not self.scenario.tradable[instrument]:
            raise OrderError('Торговля этой бумагой в данном режиме запрещена')

    def quotes(self, instrument, side):
        return self.book.quotes(instrument, side)

    def history_for(self, instrument, side):
        return self.book.history(instrument, side)

    def recent_trades(self, instrument):
        if (type(instrument) is not int or
                not 0 <= instrument < len(self.scenario.names)):
            raise OrderError('Неверный номер бумаги')
        return tuple(self._recent_trades[instrument][:3])

    def finish_period(self):
        """Apply the original cash interest and signed-16-bit payout products.

        The player's future capital is returned before mutating portfolios, as
        the result screen needs that valuation.  Current period portfolios are
        then settled for every actor.  The caller chooses whether to advance to
        another attempt.
        """
        if not self.started:
            raise RuntimeError('Период ещё не начат')
        player = self.portfolios[0]
        projected = future_capital(self.scenario, player.cash,
                                   tuple(player.positions), self.period)
        for portfolio in self.portfolios:
            portfolio.cash = settle(self.scenario, portfolio.cash,
                                     tuple(portfolio.positions), self.period)
        self.book.clear_quotes()
        self.started = False
        self._record_replay('period_result')
        return projected

    def _record_replay(self, kind, actor=None, instrument=None, price=None,
                       quantity=None, buyer=None, seller=None):
        """Capture the exact book and portfolios after an accepted action."""
        book = []
        for number in range(len(self.scenario.names)):
            row = []
            for side in ('bid', 'ask'):
                quote = self.book.best(number, side)
                row.append(None if quote is None else
                           (quote.owner, quote.price, quote.quantity))
            book.append(tuple(row))
        self.replay_frames.append({
            'sequence': len(self.replay_frames) + 1,
            'period': self.period,
            'kind': kind,
            'actor': actor,
            'instrument': instrument,
            'price': price,
            'quantity': quantity,
            'buyer': buyer,
            'seller': seller,
            'book': tuple(book),
            'portfolios': tuple(
                (portfolio.cash, tuple(portfolio.positions))
                for portfolio in self.portfolios),
        })

    def score(self, capital):
        """Score thresholds stored in PAR (B01/B02: 0, 0, 10000, 6)."""
        low, _unused, upper, maximum = self.scenario.score_parameters
        if capital <= low:
            return 0.0
        if capital >= upper:
            return maximum
        return capital / upper * maximum
