"""Small, editable registry for user-defined FAST trading levels.

Add another :class:`CustomLevel` to ``CUSTOM_LEVELS`` and it will appear in
the ``Свои уровни`` menu.  The same ``Scenario`` object is accepted by the
normal BIDASK screen, so no second configuration format is needed.
"""
from dataclasses import dataclass

from .config import Scenario


@dataclass(frozen=True)
class CustomLevel:
    name: str
    scenario: Scenario


CUSTOM_LEVELS = [
    CustomLevel(
        "Мой пример",
        Scenario(
            periods=2,
            duration_ticks=300,
            rates=(10, 15),
            names=("Акция", "Облигация"),
            payments=((0, 120), (50, 50)),
            cash=1000,
            positions=(10, 5),
            score_parameters=(0, 0, 10000, 6),
            queue=True,
            robots=2,
            wolves=0,
            reaction_ticks=30,
            strategy=1,
            hints=True,
        ),
    ),
]


def add_level(name: str, scenario: Scenario) -> CustomLevel:
    """Append a level during application setup and return the new definition."""
    if not name.strip() or not isinstance(scenario, Scenario):
        raise ValueError("Нужны имя и объект Scenario")
    level = CustomLevel(name.strip(), scenario)
    CUSTOM_LEVELS.append(level)
    return level
