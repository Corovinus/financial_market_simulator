"""Case-specific information panels shown beside the shared order book."""
from market.calculations import bond_value
from market.classic import ca_portfolio_statistics, private_value_range
from .theme import COLORS, label, rounded


def _text(pg, surface, face, value, position, color=None):
    label(pg, surface, face, str(value), position, color or COLORS['text'])


def _box(pg, surface, rect, fill, border=None, radius=10):
    rounded(pg, surface, rect, fill, radius)
    rounded(pg, surface, rect, border or COLORS['border'], radius, 1)


def _draw_ca(pg, surface, rect, hud, market, fonts):
    body, small, title = fonts
    portfolio = market.portfolios[0]
    mean, risk = ca_portfolio_statistics(
        portfolio.cash, portfolio.positions, hud.price_scenarios)
    yellow = (255, 246, 91)
    ink = (25, 30, 43)
    for index, (caption, value, marker) in enumerate((
            ('Среднее', mean, (184, 50, 44)),
            ('Дисперсия', risk, (52, 79, 214)))):
        panel = pg.Rect(rect.x, rect.y + index * 178, rect.w, 166)
        _box(pg, surface, panel, yellow, marker, 9)
        _text(pg, surface, title, caption,
              (panel.centerx - title.size(caption)[0] // 2, panel.y + 14), ink)
        pg.draw.line(surface, ink, (panel.x + 14, panel.y + 56),
                     (panel.right - 14, panel.y + 56), 1)
        graph = pg.Rect(panel.x + 18, panel.y + 68, panel.w - 36, 42)
        pg.draw.line(surface, (125, 125, 80), graph.bottomleft,
                     graph.bottomright, 2)
        x = graph.x + round(graph.w * max(0, min(1, value / 10000)))
        pg.draw.line(surface, marker, (x, graph.y), (x, graph.bottom), 3)
        shown = f'{value:.1f}'
        _text(pg, surface, body, shown,
              (panel.centerx - body.size(shown)[0] // 2, panel.y + 122), ink)


def _matrix(pg, surface, rect, name, codes, values, face):
    rows = len(codes)
    columns = rows + 1
    cell_w = rect.w // columns
    cell_h = rect.h // (rows + 1)
    _box(pg, surface, rect, COLORS['background_alt'], COLORS['accent_alt'], 5)
    for row in range(rows + 2):
        y = min(rect.bottom, rect.y + row * cell_h)
        pg.draw.line(surface, COLORS['border'], (rect.x, y), (rect.right, y), 1)
    for column in range(1, columns):
        x = rect.x + column * cell_w
        pg.draw.line(surface, COLORS['border'], (x, rect.y), (x, rect.bottom), 1)
    headers = (name,) + tuple(code.upper() for code in codes)
    for column, value in enumerate(headers):
        _text(pg, surface, face, value,
              (rect.x + column * cell_w + 6, rect.y + 4), COLORS['warning'])
    for row, (code, values_row) in enumerate(zip(codes, values), 1):
        _text(pg, surface, face, code.upper(),
              (rect.x + 6, rect.y + row * cell_h + 4), COLORS['warning'])
        for column, value in enumerate(values_row, 1):
            _text(pg, surface, face, value,
                  (rect.x + column * cell_w + 6,
                   rect.y + row * cell_h + 4), COLORS['text'])


def _draw_re(pg, surface, rect, hud, market, fonts):
    _body, small, _title = fonts
    count = len(hud.payoff_matrices)
    range_height = 84
    table_area = rect.h - range_height - 8
    table_height = table_area // count
    for index, (codes, values) in enumerate(zip(hud.event_codes,
                                                hud.payoff_matrices)):
        matrix_rect = pg.Rect(rect.x, rect.y + index * table_height,
                              rect.w, table_height - 6)
        _matrix(pg, surface, matrix_rect, market.scenario.names[index],
                codes, values, small)
    range_rect = pg.Rect(rect.x, rect.bottom - range_height, rect.w,
                         range_height)
    _box(pg, surface, range_rect, (111, 37, 137), (193, 112, 214), 8)
    _text(pg, surface, small, 'Диапазон по вашей информации',
          (range_rect.x + 12, range_rect.y + 8), (245, 224, 255))
    private = hud.private_information[0]
    for index, (codes, matrix, excluded) in enumerate(zip(
            hud.event_codes, hud.payoff_matrices, private)):
        low, high = private_value_range(matrix, codes, *excluded)
        name = market.scenario.names[index]
        shown = f'{name}: {low} .. {high}'
        column = index % 2
        row = index // 2
        _text(pg, surface, small, shown,
              (range_rect.x + 12 + column * (range_rect.w // 2),
               range_rect.y + 34 + row * 20), (255, 255, 255))


def _draw_option(pg, surface, rect, hud, market, period, fonts):
    body, small, title = fonts
    spot, strike, sigma, up, down, probability = hud.option_parameters
    _box(pg, surface, rect, COLORS['panel'], COLORS['accent_alt'], 10)
    _text(pg, surface, body, 'Параметры опциона',
          (rect.x + 18, rect.y + 16), COLORS['accent_alt'])
    current = hud.option_path[min(period, len(hud.option_path) - 1)]
    rows = (
        ('Текущая цена акции', current),
        ('Цена исполнения K', f'{strike:g}'),
        ('Волатильность σ', f'{sigma:g}'),
        ('Рост u', f'{up:.3f}'),
        ('Падение d', f'{down:.3f}'),
        ('Вероятность p', f'{probability:.3f}'),
    )
    for index, (caption, value) in enumerate(rows):
        y = rect.y + 68 + index * 34
        _text(pg, surface, small, caption, (rect.x + 18, y), COLORS['muted'])
        _text(pg, surface, body, value, (rect.right - 82, y - 3),
              COLORS['text'])
    path = ' → '.join(map(str, hud.option_path[:period + 1]))
    _text(pg, surface, small, 'Путь: ' + path, (rect.x + 18, rect.bottom - 62),
          COLORS['warning'])
    _text(pg, surface, small, 'Put=max(K−S,0) · Call=max(S−K,0)',
          (rect.x + 18, rect.bottom - 34), COLORS['accent_alt'])


def _draw_bond(pg, surface, rect, hud, market, selected, period, fonts):
    body, small, title = fonts
    scenario = market.scenario
    _box(pg, surface, rect, COLORS['panel'], COLORS['accent_alt'], 10)
    _text(pg, surface, title, hud.label, (rect.x + 18, rect.y + 16),
          COLORS['accent_alt'])
    _text(pg, surface, body, scenario.names[selected],
          (rect.x + 18, rect.y + 58), COLORS['text'])
    _text(pg, surface, small, 'Потоки по периодам',
          (rect.x + 18, rect.y + 98), COLORS['muted'])
    for index, payment in enumerate(scenario.payments[selected]):
        y = rect.y + 128 + (index // 2) * 30
        color = COLORS['warning'] if index == period else COLORS['text']
        _text(pg, surface, small, f'{index + 1}: {payment}',
              (rect.x + 24 + (index % 2) * 116, y), color)
    value = bond_value(scenario, selected, period)
    _text(pg, surface, small, 'Расчётная цена F9',
          (rect.x + 18, rect.bottom - 72), COLORS['muted'])
    _text(pg, surface, title, f'{value:.3f}',
          (rect.x + 18, rect.bottom - 44), COLORS['warning'])


def draw_case_panel(pg, surface, rect, hud, market, selected, period, fonts):
    """Draw the HUD belonging to one original executable/case."""
    if hud.label.startswith('Case CA'):
        _draw_ca(pg, surface, rect, hud, market, fonts)
    elif hud.label.startswith('Case RE'):
        _draw_re(pg, surface, rect, hud, market, fonts)
    elif hud.label.startswith('Case OP'):
        _draw_option(pg, surface, rect, hud, market, period, fonts)
    else:
        _draw_bond(pg, surface, rect, hud, market, selected, period, fonts)


def case_information_line(hud):
    if not hud:
        return ''
    if hud.label == 'Case CA1':
        return 'Короткие позиции запрещены · денежный кредит разрешён'
    if hud.label == 'Case CA2':
        return 'Фиксированные цены 28 / 26 / 25 · собственные заявки недоступны'
    if hud.label == 'Case CA3':
        return 'Короткие позиции и денежный кредит разрешены'
    if hud.label in ('Case OP1', 'Case OP2'):
        return 'Акция: внешняя цена · облигация и опционы: двойной аукцион'
    if hud.label == 'Case OP3':
        return 'Акция: внешняя цена · выписанные опционы закрыты для торговли'
    if hud.label.startswith('Case B'):
        return 'F9 показывает расчётные цены будущих денежных потоков'
    if not hud.label.startswith('Case RE'):
        return ''
    names = ('ABC', 'CRA') if hud.label == 'Case RE1' else ()
    parts = []
    for index, excluded in enumerate(hud.private_information[0]):
        name = names[index] if index < len(names) else f'Фирма {index + 1}'
        parts.append(f'{name}: NOT {excluded[0].upper()}; NOT {excluded[1].upper()}')
    return '   •   '.join(parts)
