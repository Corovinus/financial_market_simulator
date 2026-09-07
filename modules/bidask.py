"""DOS-like pygame front end for the recovered BIDASK engine.

The market rules live in :mod:`market`; this module only handles the keyboard
and the 640x480 text-mode presentation used by B01/B02.
"""
from pathlib import Path
import logging
import time

from market.calculations import bond_value
from market.classic import bond_hud
from market.config import parse_offer, read_par, Scenario
from market.engine import Market
from market.goals import evaluate_goals
from market.orderbook import OrderError
from market.report import build_report, default_report_folder, export_report
from market.robots import RobotController
from .display import handle_window_event, open_scaled_display, present_scaled
from .case_panels import case_information_line, draw_case_panel
from .goals import draw_goals
from .replay import draw_replay_frame
from .report import draw_report
from .sound import play_sound
from .theme import (COLORS, back_button, card, draw_back_button,
                    draw_confirmation, draw_tooltip, font, label,
                    mouse_position, rounded)


LOGGER = logging.getLogger('fast.bidask')


def run_session(scenario: Scenario | str | Path, speed: float = 1.0,
                scale: float = 1.0, close_display: bool = True,
                session_title: str = 'Торговая сессия',
                info_lines: tuple[str, ...] = (),
                result_lines: tuple[str, ...] = (), case_hud=None):
    """Run one B01/B02 attempt and return the final capital.

    ``speed`` scales the original decisecond clock.  The default therefore
    keeps the original pace; ``--speed 100`` is convenient for a quick check.
    Autonomous participants use the original reaction interval, valuation
    initialization, action types and random-number generator.
    """
    if isinstance(scenario, (str, Path)):
        source = Path(scenario)
        scenario = read_par(source)
        if source.stem.upper() in ('B01', 'B02') and case_hud is None:
            case_hud = bond_hud(f'Case {source.stem.upper()}')
            session_title = f'Рынок облигаций · {source.stem.upper()}'
    if not isinstance(scenario, Scenario):
        raise TypeError('Ожидался Scenario или путь к PAR')
    if not isinstance(speed, (int, float)) or speed <= 0:
        raise ValueError('Скорость должна быть положительной')

    import pygame as pg

    pg.init()
    screen, window = open_scaled_display(pg, (960, 680), scale, 'FAST — BIDASK')
    body_font = font(pg, 18)
    small_font = font(pg, 14)
    title_font = font(pg, 28, bold=True)
    market = Market(scenario)
    market.start_period(0)
    robots = RobotController(market)
    LOGGER.info('Robot controller started: robots=%s wolves=%s reaction=%s '
                'strategy=%s style=%s spread=%s max_quantity=%s',
                scenario.robots, scenario.wolves, scenario.reaction_ticks,
                scenario.strategy, scenario.robot_style,
                scenario.robot_value_spread, scenario.robot_max_quantity)
    period = 0
    remaining = float(scenario.duration_ticks)
    selected_instrument = 0
    selected_side = 'bid'
    show_hints = False
    input_mode = None
    input_text = ''
    status = ''
    status_until = 0.0
    last_robot_event = ''
    projected = None
    result_screen = False
    replay_index = None
    replay_observed = 0
    report_data = None
    report_actor = 0
    report_instrument = 0
    report_notice = ''
    goals_data = None
    goals_actor = 0
    goals_selected = 0
    final_goals = None
    confirm_exit = False
    mouse = None
    running = True
    clock = pg.time.Clock()

    def write(value, x, y, color=None, face=None):
        label(pg, screen, face or body_font, value, (x, y), color or COLORS['text'])

    def message(value, seconds=2.5):
        nonlocal status, status_until
        status, status_until = value, time.monotonic() + seconds

    def can_start(action):
        if not scenario.tradable[selected_instrument]:
            message('Торговля этой бумагой в данном режиме запрещена')
            return False
        if (action == 'quote' and
                scenario.fixed_prices[selected_instrument][period] is not None):
            message('Цена задаётся извне: используйте B или S')
            return False
        return True

    def quote_text(quote):
        return '' if quote is None else f'{quote.price}.{quote.quantity}'

    def visible_instruments():
        start = min(max(0, selected_instrument - 3),
                    max(0, len(scenario.names) - 4))
        return range(start, min(start + 4, len(scenario.names)))

    def quote_rects():
        for row, index in enumerate(visible_instruments()):
            y = 202 + row * 64
            yield index, 'bid', pg.Rect(204, y, 150, 42)
            yield index, 'ask', pg.Rect(372, y, 150, 42)

    buy_button = pg.Rect(654, 528, 132, 42)
    sell_button = pg.Rect(804, 528, 132, 42)

    def draw():
        if goals_data is not None:
            player_name = ('Игрок' if goals_actor == 0 else
                           f'Робот {goals_actor + 1}')
            draw_goals(pg, screen, goals_data, player_name, goals_selected,
                       (body_font, small_font, title_font))
            draw_back_button(pg, screen, small_font)
            if confirm_exit:
                draw_confirmation(pg, screen, small_font, title_font,
                                  'Выйти из активной игры?',
                                  'Текущий период будет потерян.')
            return
        if report_data is not None:
            draw_report(pg, screen, report_data, report_instrument,
                        (body_font, small_font, title_font), report_notice)
            draw_back_button(pg, screen, small_font)
            if confirm_exit:
                draw_confirmation(pg, screen, small_font, title_font,
                                  'Выйти из активной игры?',
                                  'Текущий период будет потерян.')
            return
        if replay_index is not None:
            players = {str(actor): ('Игрок' if actor == 0 else
                                    f'Робот {actor + 1}')
                       for actor in range(len(market.portfolios))}
            draw_replay_frame(
                pg, screen, market.replay_frames[replay_index], replay_index,
                len(market.replay_frames), scenario.names, players,
                replay_observed, (body_font, small_font, title_font))
            draw_back_button(pg, screen, small_font)
            if confirm_exit:
                draw_confirmation(pg, screen, small_font, title_font,
                                  'Выйти из активной игры?',
                                  'Текущий период будет потерян.')
            return
        screen.fill(COLORS['background'])
        pg.draw.circle(screen, COLORS['decor_top'], (920, 0), 250)
        rounded(pg, screen, pg.Rect(24, 18, 912, 58), COLORS['panel'], 15)
        write(session_title[:28], 48, 30, COLORS['accent'], title_font)
        if scenario.goals:
            write(f'F4 · цели ({len(scenario.goals)})', 350, 38,
                  COLORS['accent_alt'], small_font)
        write('Попытка 1', 438, 36, COLORS['muted'], small_font)
        write('ID 1', 520, 36, COLORS['muted'], small_font)
        write(f'Период {period + 1} / {scenario.periods}', 570, 34,
              COLORS['text'], body_font)
        write(f'{max(0, int(remaining / 10))} сек.', 720, 34,
              COLORS['warning'], body_font)
        pg.draw.rect(screen, COLORS['background_alt'], (48, 84, 580, 8), border_radius=4)
        progress = max(0, min(1, remaining / max(1, scenario.duration_ticks)))
        pg.draw.rect(screen, COLORS['accent'], (48, 84, int(580 * progress), 8), border_radius=4)
        card(pg, screen, pg.Rect(36, 112, 592, 356), COLORS['panel'], COLORS['border'])
        write('Книга заявок', 58, 132, COLORS['text'], body_font)
        write('Bid', 234, 172, COLORS['buy'], small_font)
        write('Ask', 402, 172, COLORS['sell'], small_font)
        write('Позиция', 520, 172, COLORS['muted'], small_font)
        if len(scenario.names) > 4:
            write(f'{selected_instrument + 1}/{len(scenario.names)}', 568, 136,
                  COLORS['muted'], small_font)
        for row, index in enumerate(visible_instruments()):
            name = scenario.names[index]
            y = 202 + row * 64
            write(name[:12], 58, y + 15, COLORS['text'], body_font)
            bid = market.book.best(index, 'bid')
            ask = market.book.best(index, 'ask')
            for side, quote, x, side_color in (('bid', bid, 204, COLORS['buy']), ('ask', ask, 372, COLORS['sell'])):
                available = scenario.tradable[index]
                selected = (available and index == selected_instrument and
                            side == selected_side)
                field = pg.Rect(x, y, 150, 42)
                rounded(pg, screen, field, COLORS['background_alt'], 9)
                rounded(pg, screen, field, COLORS['accent'] if selected else COLORS['border'], 9, 2 if selected else 1)
                shown = quote_text(quote) or ('закрыт' if not available else '—')
                write(shown, x + 14, y + 9,
                      COLORS['muted'] if not available else
                      COLORS['white'] if quote and quote.owner == 0 else
                      side_color, small_font if not available else body_font)
            write(str(market.portfolios[0].positions[index]), 536, y + 12, COLORS['text'], body_font)
            if scenario.hints and show_hints:
                rounded(pg, screen, pg.Rect(536, y + 44, 84, 24), COLORS['accent'], 6)
                write(f'{bond_value(scenario, index, period):.3f}', 544, y + 47, COLORS['white'], small_font)
        if case_hud is not None:
            draw_case_panel(pg, screen, pg.Rect(654, 112, 282, 356),
                            case_hud, market, selected_instrument, period,
                            (body_font, small_font, title_font))
        else:
            card(pg, screen, pg.Rect(654, 112, 282, 356),
                 COLORS['panel'], COLORS['border'])
            write('Условия рынка', 676, 132, COLORS['text'], body_font)
            details = result_lines if result_screen and result_lines else info_lines
            for n, line in enumerate(details[:8]):
                write(line[:34], 676, 176 + n * 28,
                      COLORS['accent_alt'] if n == 0 else COLORS['muted'],
                      small_font)
        if result_screen:
            rounded(pg, screen, pg.Rect(164, 222, 560, 188), COLORS['panel_alt'], 16)
            rounded(pg, screen, pg.Rect(164, 222, 560, 188), COLORS['accent'], 2, 2)
            write('Период завершён', 210, 250, COLORS['text'], title_font)
            write(f'Будущий капитал: {projected:.2f}', 210, 304, COLORS['accent_alt'], body_font)
            if period + 1 == scenario.periods:
                write(f'Очки: {market.score(projected):.2f}', 210, 340, COLORS['warning'], body_font)
                if final_goals is not None:
                    goal_text = ('Цели выполнены' if final_goals['all_passed']
                                 else 'Есть невыполненные цели')
                    write(goal_text, 210, 374,
                          COLORS['buy'] if final_goals['all_passed'] else
                          COLORS['sell'], small_font)
        if result_screen:
            action_text = ('Enter — следующий период   Esc — выход'
                           if period + 1 < scenario.periods else
                           'Enter — завершить попытку   Esc — выход')
        else:
            action_text = '↑↓ бумага   ←→ Bid/Ask   цифры — заявка   Esc — выход'
        player = market.portfolios[0]
        card(pg, screen, pg.Rect(36, 478, 592, 42),
             COLORS['panel'], COLORS['border'])
        write(f'Cash  {player.cash:.0f}', 52, 490, COLORS['text'], small_font)
        write(f'Int  {scenario.rates[period]}%', 184, 490,
              COLORS['text'], small_font)
        write('ID  1', 282, 490, COLORS['text'], small_font)
        write(f'Бумага  {scenario.names[selected_instrument]}', 366, 490,
              COLORS['warning'], small_font)
        card(pg, screen, pg.Rect(36, 528, 592, 42),
             COLORS['panel'], COLORS['border'])
        write('Последние сделки:', 52, 540, COLORS['muted'], small_font)
        for n, trade in enumerate(market.recent_trades(selected_instrument)):
            write(f'{trade.price}.{trade.quantity}', 212 + n * 118, 540,
                  COLORS['accent_alt'], small_font)
        if not market.recent_trades(selected_instrument):
            write('—', 212, 540, COLORS['muted'], small_font)
        info_box = pg.Rect(36, 578, 900, 62)
        card(pg, screen, info_box, COLORS['panel_alt'], COLORS['border'])
        private_line = case_information_line(case_hud)
        if private_line:
            write(private_line[:105], 52, 588, COLORS['accent_alt'], small_font)
        help_y = 612 if private_line else 598
        explanation = ('Bid — предложение купить в формате price.quantity'
                       if selected_side == 'bid' else
                       'Ask — предложение продать в формате price.quantity')
        if mouse and buy_button.collidepoint(mouse):
            explanation = 'Купить — принять лучшую заявку Ask выбранной бумаги'
        elif mouse and sell_button.collidepoint(mouse):
            explanation = 'Продать — принять лучшую заявку Bid выбранной бумаги'
        elif mouse and back_button(pg).collidepoint(mouse):
            explanation = 'Назад — выйти из активной торговой сессии'
        if input_mode == 'buy':
            explanation = 'Введите количество бумаг для покупки'
        elif input_mode == 'sell':
            explanation = 'Введите количество бумаг для продажи'
        elif input_mode == 'quote':
            explanation = ('Введите price.quantity: после точки указывается '
                           'количество, а не дробная цена')
        shown_status = status if status and time.monotonic() < status_until else explanation
        write(shown_status[:100], 52, help_y,
              COLORS['warning'] if shown_status == status else COLORS['muted'],
              small_font)
        write(action_text, 54, 650, COLORS['muted'], small_font)
        if result_screen:
            write('R — посмотреть повтор', 682, 486,
                  COLORS['accent_alt'], small_font)
            if period + 1 == scenario.periods:
                write('F2 — итоговый отчёт', 682, 508,
                      COLORS['accent_alt'], small_font)
        if not result_screen:
            rounded(pg, screen, buy_button, COLORS['buy'], 9)
            rounded(pg, screen, sell_button, COLORS['sell'], 9)
            write('B  Купить', buy_button.x + 20, buy_button.y + 11, COLORS['black'], small_font)
            write('S  Продать', sell_button.x + 18, sell_button.y + 11, COLORS['black'], small_font)
        if input_mode:
            prompt = ('Покупаю: ' if input_mode == 'buy' else
                      'Продаю: ' if input_mode == 'sell' else 'Заявка: ')
            write(prompt + input_text + '_', 520, help_y,
                  COLORS['text'], small_font)
        elif last_robot_event and not private_line and shown_status != status:
            write(last_robot_event[:54], 470, help_y,
                  COLORS['muted'], small_font)
        draw_back_button(pg, screen, small_font)
        tooltip = None
        if mouse and back_button(pg).collidepoint(mouse):
            tooltip = ('Вернуться в меню' if result_screen else
                       'Выйти из активной игры')
        elif mouse and not result_screen and buy_button.collidepoint(mouse):
            tooltip = 'Принять лучшую заявку Ask'
        elif mouse and not result_screen and sell_button.collidepoint(mouse):
            tooltip = 'Принять лучшую заявку Bid'
        draw_tooltip(pg, screen, small_font, tooltip, mouse)
        if confirm_exit:
            draw_confirmation(pg, screen, small_font, title_font,
                              'Выйти из активной игры?',
                              'Текущий период будет потерян.')

    while running:
        elapsed = clock.tick(60) / 1000.0
        if (not result_screen and input_mode is None and goals_data is None and
                not confirm_exit):
            elapsed_ticks = min(remaining, elapsed * 10.0 * float(speed))
            remaining -= elapsed_ticks
            for robot_event in robots.step(elapsed_ticks):
                verb = {'bid': 'Bid', 'ask': 'Ask', 'buy': 'купил',
                        'sell': 'продал'}[robot_event.action]
                last_robot_event = (f'ID {robot_event.actor + 1}: {verb} '
                                    f'{scenario.names[robot_event.instrument]} '
                                    f'{robot_event.price}.{robot_event.quantity}')
                LOGGER.info('Robot action: actor=%s instrument=%s action=%s price=%s quantity=%s',
                            robot_event.actor, robot_event.instrument,
                            robot_event.action, robot_event.price,
                            robot_event.quantity)
                if robot_event.action in ('buy', 'sell'):
                    play_sound(pg, 'trade')
            if remaining <= 0:
                projected = market.finish_period()
                result_screen = True
                play_sound(pg, 'period')
                if period + 1 == scenario.periods and scenario.goals:
                    final_goals = evaluate_goals(
                        scenario, market.replay_frames, 0)
                message(f'Период завершён. Будущий капитал: {projected:.2f}', 30)
        for event in pg.event.get():
            window, handled = handle_window_event(pg, event, screen, window)
            if handled:
                continue
            if event.type == pg.QUIT:
                if result_screen:
                    running = False
                else:
                    confirm_exit = True
                continue
            if event.type == pg.MOUSEMOTION:
                mouse = mouse_position(pg, event, window, screen)
            if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                position = mouse_position(pg, event, window, screen)
                if confirm_exit and position:
                    yes, no = draw_confirmation(
                        pg, screen, small_font, title_font,
                        'Выйти из активной игры?', 'Текущий период будет потерян.')
                    if yes.collidepoint(position):
                        running = False
                    elif no.collidepoint(position):
                        confirm_exit = False
                elif position and back_button(pg).collidepoint(position):
                    if goals_data is not None:
                        goals_data = None
                    elif report_data is not None:
                        report_data = None
                    elif replay_index is not None:
                        replay_index = None
                    elif result_screen:
                        running = False
                    else:
                        confirm_exit = True
                elif position and not result_screen:
                    selected_quote = next(((index, side) for index, side, rect in quote_rects()
                                           if rect.collidepoint(position)), None)
                    if selected_quote:
                        selected_instrument, selected_side = selected_quote
                        LOGGER.info('Quote selected via mouse: instrument=%s side=%s',
                                    selected_instrument, selected_side)
                    elif buy_button.collidepoint(position):
                        if can_start('buy'):
                            selected_side, input_mode, input_text = 'ask', 'buy', ''
                    elif sell_button.collidepoint(position):
                        if can_start('sell'):
                            selected_side, input_mode, input_text = 'bid', 'sell', ''
                continue
            if event.type != pg.KEYDOWN:
                continue
            key = event.key
            if confirm_exit:
                if key in (pg.K_RETURN, pg.K_y):
                    running = False
                elif key in (pg.K_ESCAPE, pg.K_n):
                    confirm_exit = False
                continue
            if goals_data is not None:
                if key in (pg.K_ESCAPE, pg.K_F4):
                    goals_data = None
                elif key == pg.K_UP:
                    goals_selected = ((goals_selected - 1) %
                                      len(goals_data['items']))
                elif key == pg.K_DOWN:
                    goals_selected = ((goals_selected + 1) %
                                      len(goals_data['items']))
                elif key == pg.K_TAB:
                    goals_actor = ((goals_actor + 1) %
                                   len(market.portfolios))
                    goals_data = evaluate_goals(
                        scenario, market.replay_frames, goals_actor)
                continue
            if report_data is not None:
                if key == pg.K_ESCAPE:
                    report_data = None
                    report_notice = ''
                elif key == pg.K_UP:
                    report_instrument = ((report_instrument - 1) %
                                         len(report_data['instruments']))
                elif key == pg.K_DOWN:
                    report_instrument = ((report_instrument + 1) %
                                         len(report_data['instruments']))
                elif key == pg.K_TAB:
                    report_actor = ((report_actor + 1) %
                                    len(market.portfolios))
                    report_data = build_report(
                        scenario, market.replay_frames, report_actor,
                        {str(actor): ('Игрок' if actor == 0 else
                                     f'Робот {actor + 1}')
                         for actor in range(len(market.portfolios))})
                    report_notice = ''
                elif key == pg.K_F3:
                    paths = export_report(report_data,
                                          default_report_folder())
                    report_notice = f'Сохранено: {paths[0].parent}'
                continue
            if replay_index is not None:
                if key in (pg.K_ESCAPE, pg.K_r):
                    replay_index = None
                elif key == pg.K_LEFT:
                    replay_index = max(0, replay_index - 1)
                elif key == pg.K_RIGHT:
                    replay_index = min(len(market.replay_frames) - 1,
                                       replay_index + 1)
                elif key == pg.K_HOME:
                    replay_index = 0
                elif key == pg.K_END:
                    replay_index = len(market.replay_frames) - 1
                elif key == pg.K_TAB:
                    replay_observed = ((replay_observed + 1) %
                                       len(market.portfolios))
                continue
            if key == pg.K_F4 and scenario.goals:
                goals_data = evaluate_goals(
                    scenario, market.replay_frames, goals_actor)
                continue
            if result_screen:
                if key in (pg.K_ESCAPE, pg.K_e):
                    running = False
                elif key == pg.K_r:
                    replay_index = len(market.replay_frames) - 1
                elif key == pg.K_F2 and period + 1 == scenario.periods:
                    report_data = build_report(
                        scenario, market.replay_frames, report_actor,
                        {str(actor): ('Игрок' if actor == 0 else
                                     f'Робот {actor + 1}')
                         for actor in range(len(market.portfolios))})
                elif key in (pg.K_RETURN, pg.K_SPACE):
                    if period + 1 < scenario.periods:
                        period += 1
                        market.start_period(period)
                        robots.start_period(period)
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
                            trade_side = input_mode
                            market.take(0, selected_instrument, trade_side, quantity)
                            selected_side = ('ask' if trade_side == 'buy'
                                             else 'bid')
                            remainder = market.book.best(
                                selected_instrument, selected_side)
                            play_sound(pg, 'trade')
                            column = selected_side.capitalize()
                            message(
                                f'Сделка совершена · {column}: '
                                + (f'{remainder.price}.{remainder.quantity}'
                                   if remainder else
                                   'заявка исполнена полностью'))
                        input_mode, input_text = None, ''
                    except (ValueError, OrderError) as error:
                        message(str(error), 3)
                        input_mode, input_text = None, ''
                elif event.unicode and event.unicode in '0123456789.':
                    input_text += event.unicode
                continue
            if key == pg.K_ESCAPE or key == pg.K_e:
                confirm_exit = True
            elif key == pg.K_UP:
                selected_instrument = (selected_instrument - 1) % len(scenario.names)
            elif key == pg.K_DOWN:
                selected_instrument = (selected_instrument + 1) % len(scenario.names)
            elif key == pg.K_LEFT:
                selected_side = 'bid'
            elif key == pg.K_RIGHT:
                selected_side = 'ask'
            elif key == pg.K_b:
                if can_start('buy'):
                    selected_side, input_mode, input_text = 'ask', 'buy', ''
            elif key == pg.K_s:
                if can_start('sell'):
                    selected_side, input_mode, input_text = 'bid', 'sell', ''
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
                if can_start('quote'):
                    input_mode, input_text = 'quote', event.unicode
        draw()
        present_scaled(pg, screen, window)
    final_capital = market.portfolios[0].cash
    if close_display:
        pg.quit()
    return final_capital
