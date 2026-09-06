"""BIDASK PAR reader. B03/OP*.PAR use a different, not yet recovered format."""
from dataclasses import dataclass
from pathlib import Path
import math
import re


@dataclass(frozen=True)
class Scenario:
    periods: int
    duration_ticks: int
    rates: tuple[int, ...]
    names: tuple[str, ...]
    payments: tuple[tuple[int, ...], ...]
    cash: float
    positions: tuple[int, ...]
    score_parameters: tuple[float, ...]
    queue: bool
    robots: int
    wolves: int
    reaction_ticks: int
    strategy: int
    hints: bool

    def __post_init__(self):
        """Reject malformed built-in, generated and user-authored levels early."""
        tuple_fields = ('rates', 'names', 'payments', 'positions',
                        'score_parameters')
        for field in tuple_fields:
            object.__setattr__(self, field, tuple(getattr(self, field)))
        object.__setattr__(self, 'payments',
                           tuple(tuple(row) for row in self.payments))
        if type(self.periods) is not int or self.periods <= 0:
            raise ValueError('Число периодов должно быть положительным')
        if type(self.duration_ticks) is not int or self.duration_ticks <= 0:
            raise ValueError('Длительность периода должна быть положительной')
        if len(self.rates) != self.periods or any(
                not isinstance(value, (int, float)) or
                not math.isfinite(value) or value <= -100
                for value in self.rates):
            raise ValueError('Для каждого периода нужна конечная ставка выше -100%')
        if (not self.names or any(not isinstance(name, str) or not name.strip()
                                  for name in self.names)):
            raise ValueError('Нужна хотя бы одна бумага с названием')
        object.__setattr__(self, 'names', tuple(name.strip() for name in self.names))
        if (len(self.payments) != len(self.names) or
                any(len(row) != self.periods or
                    any(type(value) is not int for value in row)
                    for row in self.payments)):
            raise ValueError('Таблица выплат должна совпадать с бумагами и периодами')
        if (len(self.positions) != len(self.names) or
                any(type(value) is not int for value in self.positions)):
            raise ValueError('Начальные позиции должны быть целыми и совпадать с бумагами')
        if (not isinstance(self.cash, (int, float)) or
                not math.isfinite(self.cash)):
            raise ValueError('Начальные деньги должны быть конечным числом')
        if (len(self.score_parameters) != 4 or
                any(not isinstance(value, (int, float)) or
                    not math.isfinite(value) for value in self.score_parameters)):
            raise ValueError('Для очков нужны четыре конечных числа')
        low, _unused, upper, maximum = self.score_parameters
        if upper <= low or maximum < 0:
            raise ValueError('Верхняя граница очков должна быть выше нижней')
        if (type(self.robots) is not int or self.robots < 0 or
                type(self.wolves) is not int or not 0 <= self.wolves <= self.robots):
            raise ValueError('Неверное число роботов или волков')
        if type(self.reaction_ticks) is not int or self.reaction_ticks <= 0:
            raise ValueError('Реакция роботов должна быть положительной')
        if self.strategy not in (0, 1) or type(self.strategy) is not int:
            raise ValueError('Стратегия роботов должна быть 0 или 1')
        if type(self.queue) is not bool or type(self.hints) is not bool:
            raise ValueError('Очередь и подсказки должны быть True или False')


def read_par(path: str | Path) -> Scenario:
    lines = iter(line.strip() for line in Path(path).read_bytes().decode('cp866').splitlines() if line.strip())

    def line():
        try:
            return next(lines)
        except StopIteration as error:
            raise ValueError('PAR: неожиданный конец файла') from error

    def heading(expected):
        actual = line()
        if actual != expected:
            raise ValueError(f'PAR: ожидалось «{expected}», получено «{actual}»')

    def numbers(count, kind=int):
        try:
            values = tuple(kind(s) for s in line().split())
        except ValueError as error:
            raise ValueError('PAR: неверные числовые данные') from error
        if len(values) != count or not all(math.isfinite(v) for v in values):
            raise ValueError(f'PAR: требуется {count} конечных чисел')
        return values

    def scalar(label):
        heading(label)
        return numbers(1)[0]

    periods = scalar('Число периодов')
    if periods <= 0:
        raise ValueError('PAR: число периодов должно быть положительным')
    duration = scalar('Длительность периода (0.1 сек)')
    heading('Процентная ставка')
    rates = numbers(periods)
    count = scalar('Число ценных бумаг')
    if count <= 0:
        raise ValueError('PAR: число бумаг должно быть положительным')
    heading('Выплаты по периодам')
    payments, names = [], []
    for _ in range(count):
        fields = line().split(maxsplit=periods)
        if len(fields) != periods + 1 or not fields[-1]:
            raise ValueError('PAR: неверная строка выплат/названия')
        payments.append(tuple(int(s) for s in fields[:periods]))
        names.append(fields[-1])
    heading('Начальные данные')
    initial = numbers(count + 1, float)
    if any(v != int(v) for v in initial[1:]):
        raise ValueError('PAR: позиции должны быть целыми')
    heading('Очки')
    score = numbers(4, float)
    queue = scalar('Очередь 1-есть 0 нет')
    robots = scalar('Число роботов')
    wolves = scalar('Из них Волки')
    reaction = scalar('Реакция роботов (0.1 сек)')
    strategy = scalar('Hомер стратегии роботов [0..1]')
    hints = scalar('Подсказка F9')
    if next(lines, None) is not None:
        raise ValueError('PAR: неизвестные дополнительные поля')
    if duration <= 0 or reaction <= 0 or robots < 0 or not 0 <= wolves <= robots:
        raise ValueError('PAR: неверные параметры времени/роботов')
    if any(x not in (0, 1) for x in (queue, strategy, hints)):
        raise ValueError('PAR: переключатели должны быть 0 или 1')
    if any(rate <= -100 for rate in rates):
        raise ValueError('PAR: невозможно дисконтировать при ставке <= -100%')
    return Scenario(periods, duration, rates, tuple(names), tuple(payments),
                    initial[0], tuple(int(v) for v in initial[1:]), score,
                    bool(queue), robots, wolves, reaction, strategy, bool(hints))


def parse_offer(text: str) -> tuple[int, int]:
    """Documented p.q notation, not a decimal monetary price."""
    if not re.fullmatch(r'[0-9]+\.[0-9]+', text):
        raise ValueError('Введите цену и количество в формате 20.50')
    price, quantity = map(int, text.split('.'))
    if price <= 0 or quantity <= 0:
        raise ValueError('Цена и количество должны быть положительными')
    return price, quantity
