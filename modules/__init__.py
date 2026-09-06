"""Recovered FAST teaching modules."""

from .educational import (
    binomial_option, black_scholes, capm_statistics, macaulay_duration,
    option_payoff, risk_premium_bound,
)
from .workshops import run_module

__all__ = [
    "binomial_option", "black_scholes", "capm_statistics", "macaulay_duration",
    "option_payoff", "risk_premium_bound", "run_module",
]
