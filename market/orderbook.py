"""The deliberately unusual BIDASK quote book.

The original uses one active quote per side.  With the PAR ``queue`` flag set,
superseded quotes are kept in a LIFO list and reappear when the active quote is
filled.  There is no crossing engine and no cancellation operation.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    owner: int
    price: int
    quantity: int


@dataclass(frozen=True)
class Trade:
    price: int
    quantity: int
    buyer: int
    seller: int
    aggressor: str


class OrderError(ValueError):
    """A quote or a take request violates a documented BIDASK rule."""


class OrderBook:
    def __init__(self, instruments: int, ranked_queue: bool):
        if type(instruments) is not int or instruments <= 0:
            raise ValueError('Число рынков должно быть положительным')
        self.ranked_queue = bool(ranked_queue)
        self._active = [dict(bid=None, ask=None) for _ in range(instruments)]
        self._queued = [dict(bid=[], ask=[]) for _ in range(instruments)]
        self._history = [dict(bid=[], ask=[]) for _ in range(instruments)]

    @property
    def instruments(self):
        return len(self._active)

    def reset(self):
        for item in self._active:
            item['bid'] = item['ask'] = None
        for item in self._queued:
            item['bid'].clear()
            item['ask'].clear()
        for item in self._history:
            item['bid'].clear()
            item['ask'].clear()

    def _check_instrument(self, instrument):
        if type(instrument) is not int or not 0 <= instrument < self.instruments:
            raise OrderError('Неверный номер бумаги')

    def _check_quote(self, owner, price, quantity):
        if type(owner) is not int or owner < 0:
            raise OrderError('Неверный номер участника')
        if type(price) is not int or not 1 <= price <= 999:
            raise OrderError('Неверная цена')
        if type(quantity) is not int or not 1 <= quantity <= 99:
            raise OrderError('Неверное количество')

    def best(self, instrument, side):
        self._check_instrument(instrument)
        if side not in ('bid', 'ask'):
            raise OrderError('Сторона должна быть bid или ask')
        return self._active[instrument][side]

    def quotes(self, instrument, side):
        self._check_instrument(instrument)
        if side not in ('bid', 'ask'):
            raise OrderError('Сторона должна быть bid или ask')
        active = self._active[instrument][side]
        # The list is inspection-only. The active quote is first, followed by
        # the exact LIFO order in which the original can restore quotes.
        return tuple(q for q in (active, *reversed(self._queued[instrument][side])) if q is not None)

    def history(self, instrument, side):
        self._check_instrument(instrument)
        if side not in ('bid', 'ask'):
            raise OrderError('Сторона должна быть bid или ask')
        return tuple(self._history[instrument][side])

    def submit(self, owner, instrument, side, price, quantity):
        self._check_instrument(instrument)
        if side not in ('bid', 'ask'):
            raise OrderError('Сторона должна быть bid или ask')
        self._check_quote(owner, price, quantity)
        current = self._active[instrument][side]
        if current is not None:
            valid = price > current.price if side == 'bid' else price < current.price
            if not valid:
                raise OrderError('Цена не улучшает текущую заявку')
            if self.ranked_queue:
                self._queued[instrument][side].append(current)
        self._active[instrument][side] = Quote(owner, price, quantity)
        return self._active[instrument][side]

    def _restore(self, instrument, side):
        if self.ranked_queue and self._queued[instrument][side]:
            self._active[instrument][side] = self._queued[instrument][side].pop()
        else:
            self._active[instrument][side] = None

    def take(self, owner, instrument, side, quantity):
        """Accept the current opposite quote.

        ``side='buy'`` consumes an ask; ``side='sell'`` consumes a bid.  A
        trade is recorded in the list belonging to the quote column, matching
        the original's separate last-bid/last-ask displays.
        """
        self._check_instrument(instrument)
        if side not in ('buy', 'sell'):
            raise OrderError('Сторона должна быть buy или sell')
        if type(owner) is not int or owner < 0:
            raise OrderError('Неверный номер участника')
        if type(quantity) is not int or not 1 <= quantity <= 99:
            raise OrderError('Неверное количество')
        column = 'ask' if side == 'buy' else 'bid'
        quote = self._active[instrument][column]
        if quote is None:
            raise OrderError('Нет заявок на продажу' if side == 'buy' else 'Нет заявок на покупку')
        if quote.owner == owner:
            raise OrderError('Вы не можете торговать сами с собой')
        if quantity > quote.quantity:
            raise OrderError('Неверное количество')
        trade = Trade(quote.price, quantity,
                      owner if side == 'buy' else quote.owner,
                      quote.owner if side == 'buy' else owner,
                      side)
        self._history[instrument][column].insert(0, trade)
        remaining = quote.quantity - quantity
        self._active[instrument][column] = Quote(quote.owner, quote.price, remaining) if remaining else None
        if remaining == 0:
            self._restore(instrument, column)
        return trade

    def clear_quotes(self):
        """Remove active and queued quotes at a period boundary."""
        for instrument in range(self.instruments):
            self._active[instrument]['bid'] = self._active[instrument]['ask'] = None
            self._queued[instrument]['bid'].clear()
            self._queued[instrument]['ask'].clear()
