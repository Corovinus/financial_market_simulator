"""Reproducible, bounded scenarios for a player-hosted LAN game."""
import random

from .calculations import future_capital
from .config import Goal, Scenario


def generate_scenario(seed: int, difficulty: str = 'normal') -> Scenario:
    """Build a valid market whose initial portfolio has a useful scale."""
    if type(seed) is not int:
        raise ValueError('Seed должен быть целым числом')
    settings = {
        'easy': (2, 2, 900, 80),
        'normal': (3, 3, 600, 50),
        'hard': (3, 4, 450, 35),
    }
    if difficulty not in settings:
        raise ValueError('Сложность: easy, normal или hard')
    periods, instruments, duration, reaction = settings[difficulty]
    rng = random.Random(seed)
    rates = tuple(rng.randint(3, 20) for _ in range(periods))
    payments = []
    for instrument in range(instruments):
        row = [rng.randint(0, 15) for _ in range(periods)]
        row[-1] += rng.randint(70, 150) + instrument * 5
        payments.append(tuple(row))
    positions = tuple(rng.randint(5, 20) for _ in range(instruments))
    cash = float(rng.randrange(800, 1601, 50))
    temporary = Scenario(
        periods=periods, duration_ticks=duration, rates=rates,
        names=tuple(f'Актив {index + 1}' for index in range(instruments)),
        payments=tuple(payments), cash=cash, positions=positions,
        score_parameters=(0, 0, 10000, 6), queue=True, robots=4,
        wolves=1, reaction_ticks=reaction, strategy=1, hints=True)
    baseline = future_capital(temporary, cash, positions)
    upper = max(1000, round(baseline * 1.8 / 100) * 100)
    return Scenario(**{**temporary.__dict__,
                       'score_parameters': (0, 0, upper, 6),
                       'goals': (
                           Goal('trades', {'easy': 1, 'normal': 2, 'hard': 3}[difficulty],
                                title='Совершите несколько сделок'),
                           Goal('profit', 0,
                                title='Не уступите стратегии без торговли'),
                       )})
