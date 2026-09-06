"""Pure calculations used by the non-BIDASK FAST teaching modules.

The old programs are small stand-alone DOS lessons.  Keeping their arithmetic
here makes the screens testable and keeps the pygame code concerned only with
navigation and display.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def macaulay_duration(cashflows: Sequence[float], rate: float) -> tuple[float, float]:
    """Return present value and Macaulay duration (periods).

    ``rate`` is a percentage per period and cashflows start one period from
    now.  This is the calculation demonstrated by TutBO.
    """
    if not cashflows or rate <= -100:
        raise ValueError("Неверные потоки или ставка")
    discount = 1.0 + rate / 100.0
    present = [float(value) / discount ** (index + 1)
               for index, value in enumerate(cashflows)]
    value = sum(present)
    if value == 0:
        raise ValueError("Нулевая текущая стоимость")
    duration = sum((index + 1) * amount for index, amount in enumerate(present)) / value
    return value, duration


def immunization_ratio(asset_duration: float, liability_duration: float) -> float:
    """Share of the portfolio invested in the asset bond for immunization."""
    if asset_duration == liability_duration:
        return 1.0
    if asset_duration == 0:
        raise ValueError("Нулевая дюрация актива")
    return liability_duration / asset_duration


def capm_statistics(returns: Sequence[Sequence[float]],
                    probabilities: Sequence[float] | None = None,
                    risk_free: float = 0.0) -> dict[str, object]:
    """Compute expected returns, market return and beta for a return table."""
    if not returns or not returns[0]:
        raise ValueError("Пустая таблица доходностей")
    observations = [tuple(float(value) for value in row) for row in returns]
    assets = len(observations[0])
    if any(len(row) != assets for row in observations):
        raise ValueError("Строки таблицы имеют разный размер")
    if probabilities is None:
        probabilities = tuple(1.0 / len(observations) for _ in observations)
    probabilities = tuple(float(value) for value in probabilities)
    if len(probabilities) != len(observations) or any(value < 0 for value in probabilities):
        raise ValueError("Неверные вероятности")
    total = sum(probabilities)
    if total <= 0:
        raise ValueError("Сумма вероятностей должна быть положительной")
    probabilities = tuple(value / total for value in probabilities)
    expected = tuple(sum(probabilities[state] * observations[state][asset]
                         for state in range(len(observations)))
                     for asset in range(assets))
    market = sum(expected) / assets
    market_var = sum(probabilities[state] *
                      (sum(observations[state]) / assets - market) ** 2
                      for state in range(len(observations)))
    betas = tuple(
        (sum(probabilities[state] *
             (observations[state][asset] - expected[asset]) *
             ((sum(observations[state]) / assets) - market)
             for state in range(len(observations))) / market_var)
        if market_var else 0.0
        for asset in range(assets)
    )
    return {"expected": expected, "market": market, "market_variance": market_var,
            "beta": betas, "risk_premium": market - risk_free,
            "risk_free": float(risk_free)}


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def black_scholes(spot: float, strike: float, rate: float, volatility: float,
                  years: float, kind: str = "call") -> float:
    """European Black-Scholes value, with percentages for rate/volatility."""
    if min(spot, strike, volatility, years) <= 0 or rate <= -100:
        raise ValueError("Неверные параметры опциона")
    r = rate / 100.0
    sigma = volatility / 100.0
    d1 = (math.log(spot / strike) + (r + sigma * sigma / 2) * years) / (sigma * math.sqrt(years))
    d2 = d1 - sigma * math.sqrt(years)
    if kind.lower() == "put":
        return strike * math.exp(-r * years) * _normal_cdf(-d2) - spot * _normal_cdf(-d1)
    if kind.lower() != "call":
        raise ValueError("Вид опциона: call или put")
    return spot * _normal_cdf(d1) - strike * math.exp(-r * years) * _normal_cdf(d2)


def binomial_option(spot: float, strike: float, rate: float, volatility: float,
                    periods: int, kind: str = "call") -> float:
    """Cox-Ross-Rubinstein European option value."""
    if min(spot, strike, volatility) <= 0 or periods <= 0 or rate <= -100:
        raise ValueError("Неверные параметры биномиальной модели")
    dt = 1.0 / periods
    r = rate / 100.0
    sigma = volatility / 100.0
    up = math.exp(sigma * math.sqrt(dt))
    down = 1.0 / up
    growth = math.exp(r * dt)
    probability = (growth - down) / (up - down)
    probability = min(1.0, max(0.0, probability))
    values = []
    for down_moves in range(periods + 1):
        terminal = spot * up ** (periods - down_moves) * down ** down_moves
        values.append(max(strike - terminal, 0.0) if kind.lower() == "put"
                       else max(terminal - strike, 0.0))
    for step in range(periods, 0, -1):
        values = [(probability * values[index] + (1 - probability) * values[index + 1]) / growth
                  for index in range(step)]
    return values[0]


def option_payoff(spot: float, strike: float, kind: str = "call") -> float:
    if kind.lower() == "put":
        return max(strike - spot, 0.0)
    if kind.lower() == "call":
        return max(spot - strike, 0.0)
    raise ValueError("Вид опциона: call или put")


def risk_premium_bound(capital: float, risk_averse: bool = True,
                       investor_type: int = 1) -> int:
    """CA1/CA3 premium lottery boundary from FAST.DOC.

    Types 1--3 and type 4 use separate coefficients in the original lesson.
    ``risk_averse=False`` selects CA3's risk-seeking schedule.
    """
    c = float(capital)
    if investor_type not in (1, 2, 3, 4):
        raise ValueError("Тип инвестора должен быть от 1 до 4")
    if investor_type == 4:
        coefficient, quadratic = ((1.282015, -0.000022) if risk_averse
                                  else (0.3125215, 0.00022))
    else:
        coefficient, quadratic = ((2.105031, -0.0000525) if risk_averse
                                  else (0.6557603, 0.0000525))
    value = coefficient * (c + quadratic * c * c)
    return max(0, min(10000, round(value)))


def information_expected_value(matrix: Sequence[Sequence[float]],
                               probabilities: Sequence[float] | None = None) -> float:
    """Expected value of a finite information-market payoff table."""
    rows = [tuple(float(value) for value in row) for row in matrix]
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("Неверная таблица выплат")
    if probabilities is None:
        probabilities = tuple(1.0 / len(rows) for _ in rows)
    if len(probabilities) != len(rows):
        raise ValueError("Неверное число вероятностей")
    return sum(float(probabilities[index]) * sum(row) / len(row)
               for index, row in enumerate(rows))
