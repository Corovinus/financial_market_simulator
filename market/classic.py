"""Trading scenarios reconstructed from the CA, OP and RE manuals."""
from dataclasses import dataclass
import logging
import math
import random
import time

from .config import Scenario


LOGGER = logging.getLogger('fast.classic')

CLASSIC_LABELS = tuple(
    f'Case {prefix}{number}'
    for prefix in ('CA', 'OP', 'RE')
    for number in range(1, 4)
)


@dataclass(frozen=True)
class ClassicLevel:
    scenario: Scenario
    title: str
    info: tuple[str, ...]
    result: tuple[str, ...]
    seed: int
    hud: 'CaseHUD'


@dataclass(frozen=True)
class CaseHUD:
    label: str
    price_scenarios: tuple[tuple[int, ...], ...] = ()
    payoff_matrices: tuple[tuple[tuple[int, ...], ...], ...] = ()
    event_codes: tuple[tuple[str, ...], ...] = ()
    private_information: tuple[tuple[tuple[str, str], ...], ...] = ()
    option_parameters: tuple[float, ...] = ()
    option_path: tuple[int, ...] = ()


def ca_portfolio_statistics(cash, positions, price_scenarios):
    """Return the CA screen's mean and mislabeled sample deviation."""
    wealth = tuple(
        cash * 1.12 + sum(quantity * prices[state]
                          for quantity, prices in zip(positions,
                                                      price_scenarios))
        for state in range(len(price_scenarios[0])))
    mean = sum(wealth) / len(wealth)
    risk = math.sqrt(sum((value - mean) ** 2 for value in wealth) /
                     (len(wealth) - 1))
    return mean, risk


def private_value_range(matrix, codes, excluded_first, excluded_second):
    """Calculate the visible RE range after both private exclusions."""
    values = tuple(
        value
        for row_code, row in zip(codes, matrix)
        if row_code != excluded_first
        for column_code, value in zip(codes, row)
        if column_code != excluded_second)
    if not values:
        raise ValueError('Приватная информация исключила все состояния')
    return min(values), max(values)


def bond_hud(label):
    return CaseHUD(label=label)


def _signal(rng, codes, actual):
    return rng.choice(tuple(code for code in codes if code != actual))


def _scenario(*, periods, rates, names, payments, cash, positions,
              short_sales=True, tradable=(), fixed_prices=(), robots=5,
              score=(0, 0, 10000, 5)):
    return Scenario(
        periods=periods, duration_ticks=1800, rates=tuple(rates),
        names=tuple(names), payments=tuple(tuple(row) for row in payments),
        cash=cash, positions=tuple(positions), score_parameters=score,
        queue=True, robots=robots, wolves=1 if robots > 1 else 0,
        reaction_ticks=30, strategy=1, hints=False,
        robot_style='balanced', robot_value_spread=.2,
        robot_max_quantity=25, short_sales=short_sales,
        tradable=tuple(tradable), fixed_prices=tuple(fixed_prices))


def _ca(label, rng, seed):
    prices = (
        (5, 5, 5, 24, 25, 30, 32, 68, 75, 75),
        (4, 5, 10, 21, 66, 65, 65, 20, 20, 20),
        (55, 55, 49, 22, 22, 20, 10, 10, 10, 10),
    )
    portfolios = ((-8084, (316, 24, 52)), (-3354, (78, 100, 52)),
                  (-5364, (78, 24, 210)), (4200, (0, 0, 0)))
    event = rng.randrange(10)
    investor = 0
    cash, positions = portfolios[investor]
    fixed = label == 'Case CA2'
    short_sales = label == 'Case CA3'
    means = tuple(sum(row) / len(row) for row in prices)
    variances = tuple(sum((value - mean) ** 2 for value in row) / len(row)
                      for row, mean in zip(prices, means))
    scenario = _scenario(
        periods=1, rates=(12,), names=('Ак.Co.1', 'Ак.Co.2', 'Ак.Co.3'),
        payments=tuple((row[event],) for row in prices), cash=cash,
        positions=positions, short_sales=short_sales,
        fixed_prices=(((28,), (26,), (25,)) if fixed else ()),
        score=(0, 0, 10000, 5))
    restriction = ('фиксированные цены 28 / 26 / 25' if fixed else
                   'короткие позиции разрешены' if short_sales else
                   'короткие позиции запрещены')
    info = (f'10 равновероятных сценариев · тип {investor + 1}',
            'средние: ' + ' / '.join(f'{value:.1f}' for value in means),
            'дисперсии: ' + ' / '.join(f'{value:.0f}' for value in variances),
            restriction)
    result = (f'реализован сценарий {event + 1}',
              'цены: ' + ' / '.join(str(row[event]) for row in prices),
              'процент на деньги: 12%', restriction)
    hud = CaseHUD(label=label, price_scenarios=prices)
    return ClassicLevel(scenario, f'Рынок акций · {label[-3:]}', info,
                        result, seed, hud)


def _option(label, rng, seed):
    if label == 'Case OP1':
        steps, spot, strike, sigma = 1, 20, 25, 2.40
    elif label == 'Case OP2':
        steps, spot, strike, sigma = 2, 20, 25, 2.40
    else:
        steps, spot, strike, sigma = 3, 400, 410, .30
    u = math.exp(sigma / math.sqrt(12))
    d = 1 / u
    probability = (math.exp(.12 / 12) - d) / (u - d)
    movements = tuple(rng.random() < probability for _ in range(steps))
    path = [spot]
    for up in movements:
        path.append(max(1, round(path[-1] * (u if up else d))))
    final = path[-1]
    bond = 100 + steps
    put, call = max(strike - final, 0), max(final - strike, 0)
    names = ('Акция', f'Обл/{bond}', f'Put/{strike}', f'Call/{strike}')
    payments = tuple(
        (0,) * (steps - 1) + (value,)
        for value in (final, bond, put, call)
    )
    fixed_stock = tuple(path[:-1])
    fixed_prices = (fixed_stock,) + ((None,) * steps,) * 3
    if label == 'Case OP3':
        option_type = rng.randrange(2)
        positions = ((0, 0, -1210, 0) if option_type == 0 else
                     (0, 0, 0, -1220))
        cash = 30031 if option_type == 0 else 32855
        tradable = (True, True, False, False)
        score = (500, 0, 10000, 9)
    else:
        positions, cash = (100, 10, 0, 0), 1000
        tradable = (True,) * 4
        score = (0, 0, 9999, 4)
    scenario = _scenario(
        periods=steps, rates=(1,) * steps, names=names,
        payments=payments, cash=cash, positions=positions,
        tradable=tradable, fixed_prices=fixed_prices, score=score)
    info = (f'S₀={spot} · K={strike} · периодов: {steps}',
            f'u={u:.3f} · d={d:.3f} · p={probability:.3f}',
            'акция: внешняя цена',
            ('опционы не торгуются' if label == 'Case OP3' else
             'облигация и опционы: аукцион'))
    result = ('путь акции: ' + ' → '.join(map(str, path)),
              f'финальная акция: {final}', f'Put: {put} · Call: {call}',
              f'облигация: {bond}')
    hud = CaseHUD(label=label,
                  option_parameters=(spot, strike, sigma, u, d, probability),
                  option_path=tuple(path))
    return ClassicLevel(scenario, f'Рынок опционов · {label[-3:]}', info,
                        result, seed, hud)


def _re(label, rng, seed):
    if label == 'Case RE1':
        codes = (('x', 'y', 'z'), ('w', 'x', 'y', 'z'))
        dividends = ((0, 12, 24), (0, 12, 12, 24))
        terminal = (
            ((0, 0, 12), (0, 12, 24), (12, 24, 24)),
            ((8, 8, 12, 18),) * 4,
        )
        names, positions = ('ABC', 'CRA'), (100, 0)
    elif label == 'Case RE2':
        codes = (('x', 'y', 'z'),) * 3
        dividends = ((0, 12, 24), (0, 15, 30), (30, 15, 0))
        terminal = (
            ((50, 50, 50), (50, 100, 150), (50, 150, 150)),
            ((0, 50, 100), (0, 75, 150), (50, 100, 150)),
            ((150, 100, 50), (150, 75, 0), (100, 50, 0)),
        )
        names, positions = ('Фирма 1', 'Фирма 2', 'Фирма 3'), (100, 0, 0)
    else:
        codes = (('x', 'y', 'z'), ('x', 'y', 'z'))
        dividends = ((0, 0, 0), (0, 0, 0))
        shared = ((0, 20, 40), (0, 25, 45), (0, 35, 60))
        terminal = (shared, shared)
        names, positions = ('Фирма 1', 'Фирма 2', 'Put/30', 'Call/30'), (100, 100, 0, 0)
    first = tuple(rng.randrange(len(company_codes)) for company_codes in codes)
    second = tuple(rng.randrange(len(company_codes)) for company_codes in codes)
    if label == 'Case RE2':
        first = (first[0], first[1], first[1])
        second = (second[0], second[1], second[1])
    payoff_matrices = tuple(
        tuple(tuple(dividends[instrument][row] + value for value in values)
              for row, values in enumerate(matrix))
        for instrument, matrix in enumerate(terminal))
    payments = [(dividends[i][first[i]], terminal[i][first[i]][second[i]])
                for i in range(len(codes))]
    private_information = tuple(
        tuple(
            (_signal(rng, codes[i], codes[i][first[i]]),
             _signal(rng, codes[i], codes[i][second[i]]))
            for i in range(len(codes)))
        for _actor in range(6))
    if label == 'Case RE3':
        final_stock = payments[0][1]
        payments.extend(((0, max(30 - final_stock, 0)),
                         (0, max(final_stock - 30, 0))))
    scenario = _scenario(
        periods=2, rates=(0, 0), names=names, payments=payments,
        cash=2500, positions=positions, score=(0, 0, 10000, 5))
    info = ('независимые события двух периодов',
            *tuple(f'{names[i]}: не {private_information[0][i][0]}; '
                   f'не {private_information[0][i][1]}'
                   for i in range(min(2, len(codes)))),
            'кредит и короткие позиции разрешены')
    outcomes = tuple(f'{names[i]}: {codes[i][first[i]]}/{codes[i][second[i]]}'
                     for i in range(len(codes)))
    result = ('реализованные события', *outcomes,
              'выплаты: ' + ' / '.join(str(row[1]) for row in payments))
    hud = CaseHUD(label=label, payoff_matrices=payoff_matrices,
                  event_codes=codes,
                  private_information=private_information)
    return ClassicLevel(scenario, f'Эффект. рынка · {label[-3:]}',
                        info[:4], result[:4], seed, hud)


def classic_level(label, seed=None):
    if label not in CLASSIC_LABELS:
        raise KeyError(label)
    seed = time.time_ns() & 0xFFFFFFFF if seed is None else int(seed)
    rng = random.Random(seed)
    if label.startswith('Case CA'):
        return _ca(label, rng, seed)
    if label.startswith('Case OP'):
        return _option(label, rng, seed)
    return _re(label, rng, seed)


def run_classic_session(label, speed=1.0, scale=1.0, close_display=True,
                        seed=None):
    from modules.bidask import run_session
    level = classic_level(label, seed)
    LOGGER.info('Starting reconstructed market: label=%s seed=%s', label,
                level.seed)
    return run_session(
        level.scenario, speed, scale, close_display,
        session_title=level.title, info_lines=level.info,
        result_lines=level.result, case_hud=level.hud)
