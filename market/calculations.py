"""Recovered BIDASK formulas, using Python float, NOT bit-exact Real48 arithmetic.

No trading/robot behaviour is invented here. Period indices are zero-based.
"""
import math
from .config import Scenario


def bond_value(scenario: Scenario, instrument: int, period: int = 0) -> float:
    if not 0 <= instrument < len(scenario.names) or not 0 <= period < scenario.periods:
        raise ValueError('Неверный индекс бумаги или периода')
    # Original 0x1722: compound numerator and denominator, then divide once.
    numerator = 0.0
    denominator = 1.0
    for step in range(period, scenario.periods):
        multiplier = 1 + scenario.rates[step] * 0.01
        numerator = numerator * multiplier + scenario.payments[instrument][step]
        denominator *= multiplier
    return numerator / denominator


def settle(scenario: Scenario, cash: float, positions: tuple[int, ...], period: int) -> float:
    if not 0 <= period < scenario.periods or len(positions) != len(scenario.names):
        raise ValueError('Неверный период или размер портфеля')
    if not math.isfinite(cash) or any(type(q) is not int for q in positions):
        raise ValueError('Неверные деньги или позиции')
    cash *= 1 + scenario.rates[period] * 0.01
    for quantity, payments in zip(positions, scenario.payments):
        # BIDASK executes an unsigned word MUL and then CWD before converting
        # AX to Real48 (0x72D9..0x72E0). The observable result is the signed
        # low 16 bits of the product, even for short positions/large coupons.
        product = (quantity * payments[period]) & 0xFFFF
        if product & 0x8000:
            product -= 0x10000
        cash += product
    return cash


def future_capital(scenario: Scenario, cash: float, positions: tuple[int, ...], period: int = 0) -> float:
    if not 0 <= period < scenario.periods:
        raise ValueError('Неверный период')
    for step in range(period, scenario.periods):
        cash = settle(scenario, cash, positions, step)
    return cash
