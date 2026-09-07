"""Live classroom overview for a LAN administrator."""
import csv
from datetime import datetime
from pathlib import Path

from .theme import COLORS, card, label, rounded


SORT_NAMES = ('Имя', 'Капитал', 'Сделки', 'Статус')


def dashboard_rows(state, sort_index):
    rows = list(state.get('dashboard') or ())
    keys = (
        lambda row: (not row['human'], row['name'].casefold()),
        lambda row: (-row['capital'], row['actor']),
        lambda row: (-row['trades'], row['actor']),
        lambda row: (not row['connected'], not row['ready'], row['actor']),
    )
    return sorted(rows, key=keys[sort_index % len(keys)])


def export_dashboard(rows, folder):
    destination = Path(folder)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f'FAST_class_{datetime.now():%Y%m%d_%H%M%S}.csv'
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.writer(stream, delimiter=';')
        writer.writerow(('ID', 'Имя', 'Тип', 'Статус', 'Готов', 'Версия',
                         'Деньги', 'Капитал', 'Риск', 'Сделки', 'Позиции'))
        for row in rows:
            writer.writerow((
                row['actor'] + 1, row['name'],
                'Игрок' if row['human'] else 'Робот',
                'В сети' if row['connected'] else 'Не в сети',
                'Да' if row['ready'] else 'Нет', row['version'],
                f'{row["cash"]:.2f}', f'{row["capital"]:.2f}',
                '' if row['risk'] is None else f'{row["risk"]:.2f}',
                row['trades'], ' / '.join(map(str, row['positions']))))
    return path


def draw_teacher_dashboard(pg, screen, state, selected, sort_index, faces,
                           notice=''):
    body, small, title = faces

    def write(value, x, y, color=None, face=None):
        label(pg, screen, face or body, str(value), (x, y),
              color or COLORS['text'])

    rows = dashboard_rows(state, sort_index)
    selected = max(0, min(selected, max(0, len(rows) - 1)))
    screen.fill(COLORS['background'])
    pg.draw.circle(screen, COLORS['decor_top'], (900, 0), 260)
    rounded(pg, screen, pg.Rect(24, 18, 912, 58), COLORS['panel'], 15)
    write('Панель преподавателя', 48, 30, COLORS['accent'], title)
    write(f'Сортировка: {SORT_NAMES[sort_index % len(SORT_NAMES)]}',
          700, 41, COLORS['accent_alt'], small)

    card(pg, screen, pg.Rect(24, 92, 912, 326),
         COLORS['panel'], COLORS['border'])
    headers = (('ID / участник', 44), ('Статус', 290), ('Деньги', 410),
               ('Капитал', 545), ('Риск', 680), ('Сделки', 815))
    for caption, x in headers:
        write(caption, x, 108, COLORS['muted'], small)
    start = min(max(0, selected - 6), max(0, len(rows) - 8))
    for offset, row in enumerate(rows[start:start + 8]):
        index = start + offset
        y = 138 + offset * 32
        active = index == selected
        if active:
            rounded(pg, screen, pg.Rect(36, y - 5, 888, 29),
                    COLORS['background_alt'], 7)
        kind = 'И' if row['human'] else 'Р'
        write(f'{row["actor"] + 1:>2} {kind} · {row["name"]}'[:28], 44, y,
              COLORS['accent_alt'] if active else COLORS['text'], small)
        if row['human']:
            status = ('Готов' if row['ready'] else 'В сети') if row['connected'] else 'Нет связи'
            status_color = (COLORS['buy'] if row['ready'] else
                            COLORS['warning'] if row['connected'] else
                            COLORS['danger'])
        else:
            status, status_color = 'Робот', COLORS['muted']
        write(status, 290, y, status_color, small)
        write(f'{row["cash"]:.2f}', 410, y, COLORS['text'], small)
        write(f'{row["capital"]:.2f}', 545, y, COLORS['accent_alt'], small)
        risk = '—' if row['risk'] is None else f'{row["risk"]:.1f}'
        write(risk, 680, y, COLORS['muted'], small)
        write(row['trades'], 835, y, COLORS['text'], small)

    card(pg, screen, pg.Rect(24, 432, 912, 92),
         COLORS['panel'], COLORS['border'])
    if rows:
        row = rows[selected]
        names = tuple(item['name'] for item in state['book'])
        positions = ' · '.join(f'{name}: {value}'
                               for name, value in zip(names, row['positions']))
        write(f'ID {row["actor"] + 1} · версия {row["version"]}',
              44, 446, COLORS['accent_alt'], small)
        write(positions[:115], 44, 473, COLORS['text'], small)
        hud = state.get('case_hud') or {}
        private = hud.get('private_information') or ()
        if row['human'] and private and hud.get('label', '').startswith('Case RE'):
            signals = private[row['actor'] % len(private)]
            info = ' · '.join(
                f'{state["book"][index]["name"]}: NOT {pair[0].upper()}; NOT {pair[1].upper()}'
                for index, pair in enumerate(signals))
            write(info[:115], 44, 496, COLORS['warning'], small)

    rounded(pg, screen, pg.Rect(24, 538, 912, 44), COLORS['panel'], 10)
    footer = notice or ('↑↓ участник · ←→ сортировка · F3 CSV · Delete удалить '
                        'отключённого · Space пауза · E итог · F6 закрыть')
    write(footer[:118], 42, 551,
          COLORS['accent_alt'] if notice else COLORS['muted'], small)
    return rows, selected
