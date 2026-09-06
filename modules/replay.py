"""Shared renderer for local and teacher trading-session replays."""
from .theme import COLORS, card, font, label, rounded


def draw_replay_frame(pygame, screen, frame, index, total, names,
                      players=None, observed=0, faces=None):
    """Draw one immutable market snapshot on the standard 960×600 canvas."""
    body, small, title = faces or (
        font(pygame, 17), font(pygame, 13), font(pygame, 27, bold=True))
    players = players or {}

    def write(value, x, y, color=None, face=None):
        label(pygame, screen, face or body, value, (x, y),
              color or COLORS['text'])

    def player_name(actor):
        if actor is None:
            return 'Система'
        return players.get(str(actor), players.get(actor, f'ID {actor + 1}'))

    screen.fill(COLORS['background'])
    pygame.draw.circle(screen, (27, 64, 103), (900, 0), 260)
    rounded(pygame, screen, pygame.Rect(24, 18, 912, 58),
            COLORS['panel'], 15)
    write('Повтор сессии', 48, 30, COLORS['accent'], title)
    write(f'Событие {index + 1} / {total}', 730, 35,
          COLORS['warning'], body)
    progress = (index + 1) / max(1, total)
    pygame.draw.rect(screen, COLORS['background_alt'], (48, 86, 864, 7),
                     border_radius=4)
    pygame.draw.rect(screen, COLORS['accent'],
                     (48, 86, round(864 * progress), 7), border_radius=4)

    event_actor = frame.get('actor')
    kind_names = {
        'start_period': 'Начало периода', 'period_result': 'Итоги периода',
        'bid': 'Новая заявка Bid', 'ask': 'Новая заявка Ask',
        'buy': 'Покупка по Ask', 'sell': 'Продажа по Bid',
    }
    detail = kind_names.get(frame.get('kind'), str(frame.get('kind', '')))
    if event_actor is not None:
        detail += f' · {player_name(event_actor)}'
    instrument = frame.get('instrument')
    if instrument is not None and 0 <= instrument < len(names):
        detail += f' · {names[instrument]}'
    if frame.get('price') is not None:
        detail += f' · {frame["price"]}.{frame["quantity"]:02d}'
    write(detail[:90], 48, 110, COLORS['accent_alt'], body)
    write(f'Период {frame["period"] + 1}', 48, 139, COLORS['muted'], small)

    card(pygame, screen, pygame.Rect(28, 170, 588, 332),
         COLORS['panel'], COLORS['border'])
    write('Инструмент', 48, 188, COLORS['muted'], small)
    write('Bid', 246, 188, COLORS['buy'], small)
    write('Ask', 414, 188, COLORS['sell'], small)
    book = frame['book']
    focus = instrument if instrument is not None else 0
    start = min(max(0, focus - 3), max(0, len(book) - 4))
    for offset, number in enumerate(range(start, min(start + 4, len(book)))):
        y = 222 + offset * 64
        if number == instrument:
            rounded(pygame, screen, pygame.Rect(40, y - 7, 560, 48),
                    COLORS['background_alt'], 8)
        write(names[number][:16], 52, y + 5, COLORS['text'], body)
        for side_index, (x, color) in enumerate(((220, COLORS['buy']),
                                                 (388, COLORS['sell']))):
            quote = book[number][side_index]
            rounded(pygame, screen, pygame.Rect(x, y - 2, 150, 36),
                    COLORS['panel_alt'], 7)
            if quote is None:
                write('—', x + 12, y + 5, COLORS['muted'], small)
            else:
                owner, price, quantity = quote
                write(f'{price}.{quantity:02d}', x + 10, y + 5, color, small)
                write(f'ID {owner + 1}', x + 92, y + 5,
                      COLORS['muted'], small)

    card(pygame, screen, pygame.Rect(636, 170, 296, 332),
         COLORS['panel'], COLORS['border'])
    portfolios = frame['portfolios']
    observed = max(0, min(observed, len(portfolios) - 1))
    cash, positions = portfolios[observed]
    write('Портфель', 658, 190, COLORS['text'], body)
    write(f'ID {observed + 1} · {player_name(observed)}'[:30], 658, 222,
          COLORS['accent_alt'], small)
    write(f'Деньги: {cash:.2f}', 658, 254, COLORS['text'], body)
    for number, quantity in enumerate(positions[:7]):
        write(f'{names[number][:13]}: {quantity}', 658, 294 + number * 25,
              COLORS['muted'], small)

    rounded(pygame, screen, pygame.Rect(24, 530, 912, 52),
            COLORS['panel'], 10)
    write('← → шаг · Home/End начало/конец · Tab участник · Esc закрыть',
          46, 549, COLORS['muted'], small)
