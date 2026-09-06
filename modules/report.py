"""Renderer for the final local and network session report."""
from .theme import COLORS, card, label, rounded


def draw_report(pygame, screen, report, instrument, faces, notice='',
                can_switch=True):
    body, small, title = faces

    def write(value, x, y, color=None, face=None):
        label(pygame, screen, face or body, value, (x, y),
              color or COLORS['text'])

    screen.fill(COLORS['background'])
    pygame.draw.circle(screen, COLORS['decor_top'], (900, 0), 260)
    rounded(pygame, screen, pygame.Rect(24, 18, 912, 58),
            COLORS['panel'], 15)
    write('Итоговый отчёт', 48, 30, COLORS['accent'], title)
    write(f'{report["name"]} · место {report["rank"]}/{report["participants"]}',
          570, 80, COLORS['warning'], small)

    cards = (
        ('Начальный капитал', report['initial_capital'], COLORS['muted']),
        ('Итоговый капитал', report['final_capital'], COLORS['accent_alt']),
        ('Изменение', report['change'],
         COLORS['buy'] if report['change'] >= 0 else COLORS['sell']),
        ('Сделки', report['trade_count'], COLORS['text']),
    )
    for index, (caption, value, color) in enumerate(cards):
        rect = pygame.Rect(28 + index * 226, 100, 208, 72)
        card(pygame, screen, rect, COLORS['panel'], COLORS['border'])
        write(caption, rect.x + 14, rect.y + 10, COLORS['muted'], small)
        shown = (str(value) if isinstance(value, int) else
                 f'{value:+.2f}' if caption == 'Изменение' else f'{value:.2f}')
        write(shown, rect.x + 14, rect.y + 36, color, body)

    card(pygame, screen, pygame.Rect(28, 190, 588, 190),
         COLORS['panel'], COLORS['border'])
    write('Прогноз итогового капитала по событиям', 48, 207,
          COLORS['text'], small)
    curve = report['capital_curve']
    low, high = min(curve), max(curve)
    span = high - low or 1.0
    points = []
    for index, value in enumerate(curve):
        x = 50 + index * 540 / max(1, len(curve) - 1)
        y = 352 - (value - low) * 112 / span
        points.append((round(x), round(y)))
    if len(points) > 1:
        pygame.draw.lines(screen, COLORS['accent'], False, points, 3)
    elif points:
        pygame.draw.circle(screen, COLORS['accent'], points[0], 4)
    write(f'{high:.2f}', 48, 229, COLORS['muted'], small)
    write(f'{low:.2f}', 48, 350, COLORS['muted'], small)

    rows = report['instruments']
    instrument = max(0, min(instrument, len(rows) - 1))
    row = rows[instrument]
    card(pygame, screen, pygame.Rect(28, 396, 588, 106),
         COLORS['panel'], COLORS['border'])
    write(f'{instrument + 1}/{len(rows)}  {row["name"]}', 48, 414,
          COLORS['accent_alt'], body)
    write(f'Сделок: {row["trades"]}   Куплено: {row["bought"]}   Продано: {row["sold"]}',
          48, 448, COLORS['text'], small)
    average_buy = '—' if row['average_buy'] is None else f'{row["average_buy"]:.2f}'
    average_sell = '—' if row['average_sell'] is None else f'{row["average_sell"]:.2f}'
    write(f'Средняя покупка: {average_buy}   продажа: {average_sell}',
          48, 475, COLORS['muted'], small)
    write(f'Результат: {row["result"]:+.2f}', 430, 475,
          COLORS['buy'] if row['result'] >= 0 else COLORS['sell'], small)

    card(pygame, screen, pygame.Rect(636, 190, 296, 312),
         COLORS['panel'], COLORS['border'])
    write('Таблица участников', 658, 210, COLORS['text'], body)
    standings = report['standings']
    standings_start = min(max(0, report['rank'] - 4),
                          max(0, len(standings) - 7))
    for index, participant in enumerate(
            standings[standings_start:standings_start + 7]):
        active = participant['actor'] == report['actor']
        color = COLORS['accent_alt'] if active else COLORS['muted']
        write(f'{participant["rank"]}. {participant["name"]}'[:22],
              658, 250 + index * 25, color, small)
        write(f'{participant["capital"]:.2f}', 842, 250 + index * 25,
              color, small)
    write(f'Реализовано: {report["realized"]:+.2f}', 658, 432,
          COLORS['text'], small)
    write(f'Нереализовано: {report["unrealized"]:+.2f}', 658, 454,
          COLORS['muted'], small)
    write(f'Очки: {report["score"]:.2f}', 658, 476,
          COLORS['warning'], body)

    rounded(pygame, screen, pygame.Rect(24, 530, 912, 52),
            COLORS['panel'], 10)
    controls = '↑ ↓ инструмент · '
    if can_switch:
        controls += 'Tab участник · '
    controls += 'F3 экспорт CSV/HTML · Esc закрыть'
    footer = notice or controls
    write(footer[:105], 44, 549,
          COLORS['accent_alt'] if notice else COLORS['muted'], small)
