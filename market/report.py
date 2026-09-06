"""Final trading-session statistics and dependency-free exports."""
import csv
from datetime import datetime
from html import escape
from pathlib import Path

from .calculations import future_capital
from .config import Scenario


def _word_product(quantity, payment):
    value = (quantity * payment) & 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _growth(scenario, first_period):
    result = 1.0
    for period in range(first_period, scenario.periods):
        result *= 1 + scenario.rates[period] / 100
    return result


def _projected_capital(scenario, frame, actor):
    cash, positions = frame['portfolios'][actor]
    first = frame['period'] + (frame['kind'] == 'period_result')
    return (cash if first >= scenario.periods else
            future_capital(scenario, cash, tuple(positions), first))


def build_report(scenario, frames, actor=0, player_names=None):
    """Build exact final-capital attribution for one session participant."""
    if not isinstance(scenario, Scenario) or not frames:
        raise ValueError('Для отчёта нужна завершённая сессия')
    final = frames[-1]
    portfolios = final['portfolios']
    if (final.get('kind') != 'period_result' or
            final.get('period') != scenario.periods - 1):
        raise ValueError('Итоговый отчёт доступен после последнего периода')
    if type(actor) is not int or not 0 <= actor < len(portfolios):
        raise ValueError('Неверный участник отчёта')
    names = player_names or {}
    initial = future_capital(scenario, scenario.cash, scenario.positions)
    finals = [float(portfolio[0]) for portfolio in portfolios]
    order = sorted(range(len(finals)), key=lambda number: (-finals[number], number))
    rank = order.index(actor) + 1
    score = scenario.score_parameters[3] if finals[actor] >= scenario.score_parameters[2] else (
        0.0 if finals[actor] <= scenario.score_parameters[0] else
        finals[actor] / scenario.score_parameters[2] * scenario.score_parameters[3])

    trades = [frame for frame in frames
              if frame.get('kind') in ('buy', 'sell')]
    instrument_rows = []
    total_bought = total_sold = 0
    buy_value = sell_value = 0.0
    for instrument, name in enumerate(scenario.names):
        relevant = [frame for frame in trades
                    if frame.get('instrument') == instrument]
        bought = sum(frame['quantity'] for frame in relevant
                     if frame.get('buyer') == actor)
        sold = sum(frame['quantity'] for frame in relevant
                   if frame.get('seller') == actor)
        bought_value = sum(frame['price'] * frame['quantity'] for frame in relevant
                           if frame.get('buyer') == actor)
        sold_value = sum(frame['price'] * frame['quantity'] for frame in relevant
                         if frame.get('seller') == actor)
        trade_cash = 0.0
        for frame in relevant:
            value = frame['price'] * frame['quantity'] * _growth(
                scenario, frame['period'])
            if frame.get('buyer') == actor:
                trade_cash -= value
            if frame.get('seller') == actor:
                trade_cash += value
        payout_change = 0.0
        for period in range(scenario.periods):
            result_frame = next(
                frame for frame in reversed(frames)
                if frame.get('kind') == 'period_result' and
                frame.get('period') == period)
            position = result_frame['portfolios'][actor][1][instrument]
            payment = scenario.payments[instrument][period]
            difference = (_word_product(position, payment) -
                          _word_product(scenario.positions[instrument], payment))
            payout_change += difference * _growth(scenario, period + 1)
        pnl = trade_cash + payout_change
        total_bought += bought
        total_sold += sold
        buy_value += bought_value
        sell_value += sold_value
        instrument_rows.append({
            'name': name, 'trades': len(relevant), 'bought': bought,
            'sold': sold,
            'average_buy': bought_value / bought if bought else None,
            'average_sell': sold_value / sold if sold else None,
            'result': pnl, 'position': portfolios[actor][1][instrument],
        })

    actor_trades = [frame for frame in trades
                    if actor in (frame.get('buyer'), frame.get('seller'))]
    curve = [_projected_capital(scenario, frame, actor) for frame in frames]
    if len(curve) > 240:
        curve = [curve[round(index * (len(curve) - 1) / 239)]
                 for index in range(240)]
    standings = [
        {'actor': number, 'name': names.get(str(number),
                                           names.get(number, f'ID {number + 1}')),
         'capital': finals[number], 'rank': order.index(number) + 1}
        for number in order
    ]
    return {
        'actor': actor,
        'name': names.get(str(actor), names.get(actor, f'ID {actor + 1}')),
        'initial_capital': initial,
        'final_capital': finals[actor],
        'change': finals[actor] - initial,
        'score': score,
        'rank': rank,
        'participants': len(portfolios),
        'trade_count': len(actor_trades),
        'bought': total_bought,
        'sold': total_sold,
        'average_buy': buy_value / total_bought if total_bought else None,
        'average_sell': sell_value / total_sold if total_sold else None,
        'realized': sum(row['result'] for row in instrument_rows),
        'unrealized': 0.0,
        'instruments': instrument_rows,
        'capital_curve': curve,
        'standings': standings,
    }


def export_report(report, folder):
    """Write CSV and standalone HTML copies, returning both paths."""
    destination = Path(folder)
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    stem = f'FAST_report_ID{report["actor"] + 1}_{stamp}'
    csv_path = destination / f'{stem}.csv'
    html_path = destination / f'{stem}.html'
    with csv_path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.writer(stream, delimiter=';')
        writer.writerow(('Участник', report['name']))
        writer.writerow(('Начальный капитал', f'{report["initial_capital"]:.2f}'))
        writer.writerow(('Итоговый капитал', f'{report["final_capital"]:.2f}'))
        writer.writerow(('Изменение', f'{report["change"]:.2f}'))
        writer.writerow(('Место', f'{report["rank"]}/{report["participants"]}'))
        writer.writerow(('Сделки', report['trade_count']))
        writer.writerow(('Куплено', report['bought']))
        writer.writerow(('Продано', report['sold']))
        writer.writerow(('Средняя покупка', _format_optional(report['average_buy'])))
        writer.writerow(('Средняя продажа', _format_optional(report['average_sell'])))
        writer.writerow(('Реализованный результат', f'{report["realized"]:.2f}'))
        writer.writerow(('Нереализованный результат', f'{report["unrealized"]:.2f}'))
        writer.writerow(())
        writer.writerow(('Инструмент', 'Сделок', 'Куплено', 'Продано',
                         'Средняя покупка', 'Средняя продажа', 'Результат'))
        for row in report['instruments']:
            writer.writerow((row['name'], row['trades'], row['bought'],
                             row['sold'], _format_optional(row['average_buy']),
                             _format_optional(row['average_sell']),
                             f'{row["result"]:.2f}'))

    curve = report['capital_curve']
    low, high = min(curve), max(curve)
    span = high - low or 1.0
    points = ' '.join(
        f'{20 + index * 760 / max(1, len(curve) - 1):.1f},'
        f'{180 - (value - low) * 150 / span:.1f}'
        for index, value in enumerate(curve))
    rows = ''.join(
        '<tr>' + ''.join(f'<td>{escape(str(value))}</td>' for value in (
            row['name'], row['trades'], row['bought'], row['sold'],
            _format_optional(row['average_buy']),
            _format_optional(row['average_sell']), f'{row["result"]:.2f}')) +
        '</tr>' for row in report['instruments'])
    html_path.write_text(f'''<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Отчёт FAST — {escape(report['name'])}</title>
<style>body{{font:16px Segoe UI,Arial;background:#0b1220;color:#e8eef8;max-width:900px;margin:40px auto}}
.cards{{display:flex;gap:12px;flex-wrap:wrap}}.card{{background:#192439;padding:16px 22px;border-radius:12px}}
table{{width:100%;border-collapse:collapse;margin-top:24px}}th,td{{padding:9px;border-bottom:1px solid #3d5170;text-align:right}}
th:first-child,td:first-child{{text-align:left}}svg{{background:#0f192b;border-radius:12px;margin-top:20px}}</style>
<h1>Итоговый отчёт FAST</h1><h2>{escape(report['name'])}</h2>
<div class="cards"><div class="card">Капитал<br><b>{report['final_capital']:.2f}</b></div>
<div class="card">Изменение<br><b>{report['change']:+.2f}</b></div>
<div class="card">Место<br><b>{report['rank']} / {report['participants']}</b></div>
<div class="card">Сделки<br><b>{report['trade_count']}</b></div>
<div class="card">Реализовано<br><b>{report['realized']:+.2f}</b></div>
<div class="card">Нереализовано<br><b>{report['unrealized']:+.2f}</b></div></div>
<svg viewBox="0 0 800 200" width="100%"><polyline fill="none" stroke="#4ea6ff" stroke-width="3" points="{points}"/></svg>
<table><thead><tr><th>Инструмент</th><th>Сделок</th><th>Куплено</th><th>Продано</th><th>Ср. покупка</th><th>Ср. продажа</th><th>Результат</th></tr></thead><tbody>{rows}</tbody></table>
</html>''', encoding='utf-8')
    return csv_path, html_path


def default_report_folder():
    return Path.home() / 'Documents' / 'FAST reports'


def _format_optional(value):
    return '—' if value is None else f'{value:.2f}'
