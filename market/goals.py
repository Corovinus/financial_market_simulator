"""Progress calculation for goals embedded in a trading scenario."""
from .calculations import future_capital
from .config import Goal, Scenario


def evaluate_goals(scenario, frames, actor=0):
    if not isinstance(scenario, Scenario) or not frames:
        raise ValueError('Для проверки целей нужна торговая сессия')
    frame = frames[-1]
    portfolios = frame['portfolios']
    if type(actor) is not int or not 0 <= actor < len(portfolios):
        raise ValueError('Неверный участник')
    cash, positions = portfolios[actor]
    first_period = frame['period'] + (frame['kind'] == 'period_result')
    capital = (cash if first_period >= scenario.periods else
               future_capital(scenario, cash, tuple(positions), first_period))
    baseline = future_capital(scenario, scenario.cash, scenario.positions)
    trade_count = sum(
        actor in (item.get('buyer'), item.get('seller'))
        for item in frames if item.get('kind') in ('buy', 'sell'))
    finished = (frame.get('kind') == 'period_result' and
                frame.get('period') == scenario.periods - 1)
    result = []
    for goal in scenario.goals:
        if goal.kind == 'capital':
            current = capital
            passed = current >= goal.target
            label = goal.title or f'Итоговый капитал не ниже {goal.target:g}'
            progress = f'{current:.2f} / {goal.target:.2f}'
        elif goal.kind == 'profit':
            current = capital - baseline
            passed = current >= goal.target
            label = goal.title or f'Прибыль не ниже {goal.target:g}'
            progress = f'{current:+.2f} / {goal.target:+.2f}'
        elif goal.kind == 'trades':
            current = trade_count
            passed = current >= goal.target
            label = goal.title or f'Совершить не менее {goal.target} сделок'
            progress = f'{current} / {goal.target}'
        else:
            current = positions[goal.instrument]
            passed = (current >= goal.target and
                      (goal.maximum is None or current <= goal.maximum))
            if goal.maximum is None:
                condition = f'не меньше {goal.target:g}'
                target = f'≥ {goal.target:g}'
            else:
                condition = f'от {goal.target:g} до {goal.maximum:g}'
                target = f'{goal.target:g}…{goal.maximum:g}'
            label = (goal.title or
                     f'Позиция «{scenario.names[goal.instrument]}» {condition}')
            progress = f'{current} / {target}'
        result.append({
            'kind': goal.kind, 'label': label, 'current': current,
            'target': goal.target, 'maximum': goal.maximum,
            'passed': passed, 'progress': progress,
        })
    return {'actor': actor, 'finished': finished, 'capital': capital,
            'baseline': baseline, 'all_passed': bool(result) and
            all(item['passed'] for item in result), 'items': result}
