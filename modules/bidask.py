"""DOS-like pygame front end for the recovered BIDASK engine.

The market rules live in :mod:`market`; this module only handles the keyboard
and the 640x480 text-mode presentation used by B01/B02.
"""
from pathlib import Path
import logging
import time

from market.calculations import bond_value
from market.config import parse_offer, read_par, Scenario
from market.engine import Market
from market.orderbook import OrderError
from .display import open_scaled_display, present_scaled
from .theme import COLORS, card, font, label, mouse_position, rounded


ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger('fast.bidask')


def _font(pygame, path: Path):
    data = path.read_bytes()
    if len(data) != 4096:
        raise ValueError('Неверный размер оригинального шрифта')
    glyphs = []
    for code in range(256):
        glyph = pygame.Surface((9, 16), pygame.SRCALPHA)
        for y, row in enumerate(data[code * 16:(code + 1) * 16]):
            for x in range(8):
                if row & (0x80 >> x):
                    glyph.set_at((x, y), (255, 255, 255))
            if 0xC0 <= code <= 0xDF and row & 1:
                glyph.set_at((8, y), (255, 255, 255))
        glyphs.append(glyph)
    return glyphs


def run_session(scenario: Scenario | str | Path, speed: float = 1.0,
                scale: float = 1.0, close_display: bool = True):
    """Run one B01/B02 attempt and return the final capital.

    ``speed`` scales the original decisecond clock.  The default therefore
    keeps the original pace; ``--speed 100`` is convenient for a quick check.
    The recovered robot decision tree is intentionally not called here until
    its remaining Real48 branches are verified against DOS.
    """
    if isinstance(scenario, (str, Path)):
        scenario = read_par(scenario)
    if not isinstance(scenario, Scenario):
        raise TypeError('Ожидался Scenario или путь к PAR')
    if not isinstance(speed, (int, float)) or speed <= 0:
        raise ValueError('Скорость должна быть положительной')

    import pygame as pg

    pg.init()
    screen, window = open_scaled_display(pg, (960, 600), scale, 'FAST — BIDASK')
    body_font = font(pg, 18)
    small_font = font(pg, 14)
    title_font = font(pg, 28, bold=True)
    market = Market(scenario)
    market.start_period(0)
    period = 0
    remaining = float(scenario.duration_ticks)
    selected_instrument = 0
    selected_side = 'bid'
    show_hints = False
    input_mode = None
    input_text = ''
    status = ''
    status_until = 0.0
    projected = None
    result_screen = False
    running = True
    clock = pg.time.Clock()

    def write(value, x, y, color=None, face=None):
        label(pg, screen, face or body_font, value, (x, y), color or COLORS['text'])

    def message(value, seconds=2.5):
        nonlocal status, status_until
        status, status_until = value, time.monotonic() + seconds

    def quote_text(quote):
        return '' if quote is None else f'{quote.price}.{quote.quantity:02d}'

    def quote_rects():
        for index in range(len(scenario.names)):
            y = 202 + index * 72
            yield index, 'bid', pg.Rect(204, y, 150, 42)
            yield index, 'ask', pg.Rect(372, y, 150, 42)

    buy_button = pg.Rect(654, 482, 132, 38)
    sell_button = pg.Rect(804, 482, 132, 38)

    def draw():
        screen.fill(COLORS['background'])
        pg.draw.circle(screen, (22, 58, 92), (920, 0), 250)
        rounded(pg, screen, pg.Rect(24, 18, 912, 58), COLORS['panel'], 15)
        write('Торговая сессия', 48, 30, COLORS['accent'], title_font)
        write('BID / ASK', 288, 38, COLORS['muted'], small_font)
        write(f'Период {period + 1} / {scenario.periods}', 660, 34, COLORS['text'], body_font)
        write(f'{max(0, int(remaining / 10))} сек.', 820, 34, COLORS['warning'], body_font)
        pg.draw.rect(screen, COLORS['background_alt'], (48, 84, 580, 8), border_radius=4)
        progress = max(0, min(1, remaining / max(1, scenario.duration_ticks)))
        pg.draw.rect(screen, COLORS['accent'], (48, 84, int(580 * progress), 8), border_radius=4)
        card(pg, screen, pg.Rect(36, 112, 592, 356), COLORS['panel'], COLORS['border'])
        write('Книга заявок', 58, 132, COLORS['text'], body_font)
        write('Bid', 234, 172, COLORS['buy'], small_font)
        write('Ask', 402, 172, COLORS['sell'], small_font)
        write('Позиция', 520, 172, COLORS['muted'], small_font)
        for index, name in enumerate(scenario.names):
            y = 202 + index * 72
            write(name[:12], 58, y + 15, COLORS['text'], body_font)
            bid = market.book.best(index, 'bid')
            ask = market.book.best(index, 'ask')
            for side, quote, x, side_color in (('bid', bid, 204, COLORS['buy']), ('ask', ask, 372, COLORS['sell'])):
                selected = index == selected_instrument and side == selected_side
                field = pg.Rect(x, y, 150, 42)
                rounded(pg, screen, field, COLORS['background_alt'], 9)
                rounded(pg, screen, field, COLORS['accent'] if selected else COLORS['border'], 9, 2 if selected else 1)
                write(quote_text(quote) or '—', x + 14, y + 9,
                      COLORS['white'] if quote and quote.owner == 0 else side_color, body_font)
            write(str(market.portfolios[0].positions[index]), 536, y + 12, COLORS['text'], body_font)
            if scenario.hints and show_hints:
                rounded(pg, screen, pg.Rect(536, y + 44, 84, 24), COLORS['accent'], 6)
                write(f'{bond_value(scenario, index, period):.3f}', 544, y + 47, COLORS['white'], small_font)
        card(pg, screen, pg.Rect(654, 112, 282, 166), COLORS['panel'], COLORS['border'])
        write('Счёт участника', 676, 132, COLORS['text'], body_font)
        write('Деньги', 676, 178, COLORS['muted'], small_font)
        write(f'{market.portfolios[0].cash:.0f}', 820, 174, COLORS['text'], body_font)
        write('Ставка', 676, 218, COLORS['muted'], small_font)
        write(f'{scenario.rates[period]}%', 820, 214, COLORS['text'], body_font)
        card(pg, screen, pg.Rect(654, 300, 282, 168), COLORS['panel'], COLORS['border'])
        write('Последние сделки', 676, 320, COLORS['text'], body_font)
        history = market.history_for(selected_instrument, 'ask') + market.history_for(selected_instrument, 'bid')
        for n, trade in enumerate(history[:3]):
            write(f'{trade.price}.{trade.quantity:02d}', 676, 366 + n * 28, COLORS['accent_alt'], body_font)
        if result_screen:
            rounded(pg, screen, pg.Rect(164, 222, 560, 188), COLORS['panel_alt'], 16)
            rounded(pg, screen, pg.Rect(164, 222, 560, 188), COLORS['accent'], 2, 2)
            write('Период завершён', 210, 250, COLORS['text'], title_font)
            write(f'Будущий капитал: {projected:.2f}', 210, 304, COLORS['accent_alt'], body_font)
            if period + 1 == scenario.periods:
                write(f'Очки: {market.score(projected):.2f}', 210, 340, COLORS['warning'], body_font)
        action_text = ('Enter — следующий период   Esc — выход' if period + 1 < scenario.periods
                       else 'Enter — завершить попытку   Esc — выход')
        write(action_text, 54, 494, COLORS['muted'], small_font)
        if not result_screen:
            rounded(pg, screen, buy_button, COLORS['buy'], 9)
            rounded(pg, screen, sell_button, COLORS['sell'], 9)
            write('B  Купить', buy_button.x + 20, buy_button.y + 9, COLORS['black'], small_font)
            write('S  Продать', sell_button.x + 18, sell_button.y + 9, COLORS['black'], small_font)
        if input_mode:
            prompt = 'Покупаю: ' if input_mode == 'buy' else 'Продаю: ' if input_mode == 'sell' else 'Заявка: '
            rounded(pg, screen, pg.Rect(36, 526, 900, 46), COLORS['panel_alt'], 10)
            rounded(pg, screen, pg.Rect(36, 526, 900, 46), COLORS['accent'], 1, 2)
            write(prompt + input_text + '_', 54, 538, COLORS['text'], body_font)
        elif status and time.monotonic() < status_until:
            rounded(pg, screen, pg.Rect(36, 526, 900, 46), COLORS['panel_alt'], 10)
            rounded(pg, screen, pg.Rect(36, 526, 900, 46), COLORS['warning'], 1, 2)
            write(status[:86], 54, 538, COLORS['warning'], body_font)

    while running:
        elapsed = clock.tick(60) / 1000.0
        if not result_screen and input_mode is None:
            remaining -= elapsed * 10.0 * float(speed)
            if remaining <= 0:
                projected = market.finish_period()
                result_screen = True
                message(f'Период завершён. Будущий капитал: {projected:.2f}', 30)
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
                continue
            if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                position = mouse_position(pg, event, window, screen)
                if position and not result_screen:
                    selected_quote = next(((index, side) for index, side, rect in quote_rects()
                                           if rect.collidepoint(position)), None)
                    if selected_quote:
                        selected_instrument, selected_side = selected_quote
                        LOGGER.info('Quote selected via mouse: instrument=%s side=%s',
                                    selected_instrument, selected_side)
                    elif buy_button.collidepoint(position):
                        input_mode, input_text = 'buy', ''
                    elif sell_button.collidepoint(position):
                        input_mode, input_text = 'sell', ''
                continue
            if event.type != pg.KEYDOWN:
                continue
            key = event.key
            if result_screen:
                if key in (pg.K_ESCAPE, pg.K_e):
                    running = False
                elif key in (pg.K_RETURN, pg.K_SPACE):
                    if period + 1 < scenario.periods:
                        period += 1
                        market.start_period(period)
                        remaining = float(scenario.duration_ticks)
                        result_screen = False
                    else:
                        running = False
                continue
            if input_mode:
                if key == pg.K_ESCAPE:
                    input_mode, input_text = None, ''
                elif key == pg.K_BACKSPACE:
                    input_text = input_text[:-1]
                elif key == pg.K_RETURN:
                    try:
                        if input_mode == 'quote':
                            price, quantity = parse_offer(input_text)
                            market.submit(0, selected_instrument, selected_side, price, quantity)
                            message('Заявка принята')
                        else:
                            quantity = int(input_text)
                            market.take(0, selected_instrument, input_mode, quantity)
                            message('Сделка совершена')
                        input_mode, input_text = None, ''
                    except (ValueError, OrderError) as error:
                        message(str(error), 3)
                        input_mode, input_text = None, ''
                elif event.unicode and event.unicode in '0123456789.':
                    input_text += event.unicode
                continue
            if key == pg.K_ESCAPE or key == pg.K_e:
                running = False
            elif key == pg.K_UP:
                selected_instrument = (selected_instrument - 1) % len(scenario.names)
            elif key == pg.K_DOWN:
                selected_instrument = (selected_instrument + 1) % len(scenario.names)
            elif key == pg.K_LEFT:
                selected_side = 'bid'
            elif key == pg.K_RIGHT:
                selected_side = 'ask'
            elif key == pg.K_b:
                input_mode, input_text = 'buy', ''
            elif key == pg.K_s:
                input_mode, input_text = 'sell', ''
            elif key == pg.K_F9 and scenario.hints:
                show_hints = not show_hints
                message('F9 — цены будущих выплат' if show_hints else 'F9 — цены скрыты')
            elif key in (pg.K_PLUS, pg.K_KP_PLUS):
                speed = float(speed) * 2
                message(f'Скорость: {speed:g}')
            elif key in (pg.K_MINUS, pg.K_KP_MINUS):
                speed = max(0.125, float(speed) / 2)
                message(f'Скорость: {speed:g}')
            elif event.unicode and event.unicode in '0123456789.':
                input_mode, input_text = 'quote', event.unicode
        draw()
        present_scaled(pg, screen, window)
    final_capital = market.portfolios[0].cash
    if close_display:
        pg.quit()
    return final_capital
