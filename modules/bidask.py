"""DOS-like pygame front end for the recovered BIDASK engine.

The market rules live in :mod:`market`; this module only handles the keyboard
and the 640x480 text-mode presentation used by B01/B02.
"""
from pathlib import Path
import time

from market.calculations import bond_value
from market.config import parse_offer, read_par, Scenario
from market.engine import Market
from market.orderbook import OrderError
from .display import cp866_bytes, open_scaled_display, present_scaled


ROOT = Path(__file__).resolve().parents[1]


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


def run_session(scenario: Scenario | str | Path, speed: float = 1.0, scale: float = 1.0):
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
    screen, window = open_scaled_display(pg, (640, 480), scale, 'FAST — BIDASK')
    glyphs = _font(pg, ROOT / 'data/fonts/keyrus_8x16.bin')
    blue, white, black = (0, 0, 170), (255, 255, 255), (0, 0, 0)
    yellow, green, red, cyan = (255, 255, 0), (0, 255, 0), (255, 0, 0), (0, 255, 255)
    grey, magenta = (170, 170, 170), (170, 0, 170)
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

    def write(value, x, y, color=white):
        for code in cp866_bytes(value):
            glyph = glyphs[code].copy()
            glyph.fill((*color, 255), special_flags=pg.BLEND_RGBA_MULT)
            screen.blit(glyph, (x, y))
            x += 9

    def message(value, seconds=2.5):
        nonlocal status, status_until
        status, status_until = value, time.monotonic() + seconds

    def quote_text(quote):
        return '' if quote is None else f'{quote.price}.{quote.quantity:02d}'

    def draw():
        screen.fill(black)
        pg.draw.rect(screen, white, (0, 0, 640, 20))
        write('Торговая сессия', 72, 1, red)
        write('Рынок облигаций', 340, 1, black)
        pg.draw.rect(screen, yellow, (78, 20, 102, 17))
        write(f'Попытка  1', 83, 21, black)
        write(f'Период  {period + 1}', 207, 21, yellow)
        write(f'Осталось (сек.): {max(0, int(remaining / 10))}', 362, 21, yellow)
        write('Заявки на', 120, 40, yellow)
        write('покупку', 84, 56, yellow)
        write('продажу', 164, 56, yellow)
        write('Кол-во', 249, 40, yellow)
        write('бумаг', 258, 56, yellow)
        for index, name in enumerate(scenario.names):
            y = 76 + index * 32
            write(name[:8], 9, y + 8, yellow)
            bid = market.book.best(index, 'bid')
            ask = market.book.best(index, 'ask')
            for side, quote, x in (('bid', bid, 81), ('ask', ask, 165)):
                color = green if quote is not None and quote.owner == 0 else yellow
                field = pg.Rect(x, y, 73, 22)
                pg.draw.rect(screen, blue if (index == selected_instrument and side == selected_side) else grey,
                             field)
                pg.draw.rect(screen, red if (index == selected_instrument and side == selected_side) else black,
                             field, 1)
                write(quote_text(quote), x + 5, y + 3, color)
            write(str(market.portfolios[0].positions[index]), 262, y + 8, white)
            if scenario.hints and show_hints:
                pg.draw.rect(screen, magenta, (322, y - 4, 77, 29))
                write(f'{bond_value(scenario, index, period):.3f}', 330, y + 3, white)
        pg.draw.rect(screen, grey, (12, 154, 172, 11))
        write(f'Деньги       {market.portfolios[0].cash:.0f}', 20, 153, white)
        pg.draw.rect(screen, grey, (196, 154, 143, 11))
        write(f'Процент      {scenario.rates[period]}', 204, 153, white)
        write('Последние сделки :', 216, 182, cyan)
        history = market.history_for(selected_instrument, 'ask') + market.history_for(selected_instrument, 'bid')
        for n, trade in enumerate(history[:3]):
            write(f'{trade.price}.{trade.quantity:02d}', 225 + n * 90, 202, white)
        if result_screen:
            pg.draw.rect(screen, white, (95, 260, 450, 96))
            write('Достигнутые результаты', 205, 270, black)
            write(f'Будущий капитал: {projected:.2f}', 150, 294, black)
            if period + 1 == scenario.periods:
                write(f'Очки: {market.score(projected):.2f}', 150, 310, black)
        write(('Enter — следующий период   Esc — выход'
                   if period + 1 < scenario.periods else
                   'Enter — завершить попытку   Esc — выход'), 125, 326, red)
        if input_mode:
            label = 'Покупаю: ' if input_mode == 'buy' else 'Продаю: ' if input_mode == 'sell' else 'Заявка: '
            pg.draw.rect(screen, grey, (8, 407, 624, 28))
            pg.draw.rect(screen, red, (8, 407, 624, 28), 1)
            write(label + input_text + '_', 12, 416, yellow)
        elif status and time.monotonic() < status_until:
            pg.draw.rect(screen, grey, (8, 407, 624, 28))
            pg.draw.rect(screen, red, (8, 407, 624, 28), 1)
            write(status[:68], 12, 416, yellow)
        pg.draw.rect(screen, white, (0, 448, 640, 32))
        write('↑ ↓ ← → Выбор  B Покупка  S Продажа  + Быстро  - Медленно  F9 Цены  E Выход',
              23, 464, black)

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
    pg.quit()
    return final_capital
