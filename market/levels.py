"""Small, editable registry for user-defined FAST trading levels.

Add another :class:`CustomLevel` to ``CUSTOM_LEVELS`` and it will appear in
the ``Свои уровни`` menu.  The same ``Scenario`` object is accepted by the
normal BIDASK screen, so no second configuration format is needed.
"""
from dataclasses import dataclass
import json
from pathlib import Path

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


def load_levels(path: str | Path) -> tuple[CustomLevel, ...]:
    """Load optional user levels stored beside a packaged executable."""
    source = Path(path)
    if not source.exists():
        return ()
    data = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('levels.json должен содержать список уровней')
    levels = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get('scenario'), dict):
            raise ValueError('Каждому уровню нужны name и scenario')
        name = str(item.get('name', '')).strip()
        if not name:
            raise ValueError('У уровня нет названия')
        levels.append(CustomLevel(name[:60], Scenario(**item['scenario'])))
    return tuple(levels)
