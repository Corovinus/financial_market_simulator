"""Pygame screens for a LAN player, player-host, or administrator."""
import queue
import threading
import time

from market.config import parse_offer
from market.report import default_report_folder, export_report
from .display import open_scaled_display, present_scaled
from .replay import draw_replay_frame
from .report import draw_report
from .theme import COLORS, card, font, label, rounded


def run_network_client(client, role='player', scale=1.0,
                       close_display=True, room_label='LAN'):
    import pygame as pg

    pg.init()
    screen, window = open_scaled_display(pg, (960, 600), scale,
                                          'FAST — сетевая игра')
    body = font(pg, 17)
    small = font(pg, 13)
    title = font(pg, 27, bold=True)
    clock = pg.time.Clock()
    selected = 0
    selected_side = 'bid'
    observed = client.actor or 0
    input_mode = None
    input_text = ''
    show_hints = False
    status = ''
    status_until = 0.0
    running = True
    is_admin = role in ('admin', 'host')
    state = client.state
    commands = queue.Queue(maxsize=64)
    updates = queue.SimpleQueue()
    network_stop = threading.Event()
    network_failed = False
    replay_data = None
    replay_observed = 0
    report_data = None
    report_instrument = 0
    report_notice = ''

    def write(value, x, y, color=None, face=None):
        label(pg, screen, face or body, value, (x, y),
              color or COLORS['text'])

    def message(value, seconds=3):
        nonlocal status, status_until
        status, status_until = str(value), time.monotonic() + seconds

    def send(payload):
        if network_failed:
            return False
        try:
            commands.put_nowait(payload)
            return True
        except queue.Full:
            message('Слишком много команд', 3)
            return False

    def exchange():
        """Own the blocking socket so a lost server never freezes Pygame."""
        next_poll = 0.0
        while not network_stop.is_set():
            timeout = max(0.0, next_poll - time.monotonic())
            try:
                payload = commands.get(timeout=timeout)
            except queue.Empty:
                payload = {'type': 'state'}
            try:
                response = client.request(payload)
                if 'state' in response:
                    updates.put(('state', response['state']))
                elif 'replay' in response:
                    updates.put(('replay', response['replay']))
                elif 'report' in response:
                    updates.put(('report', response['report']))
            except ValueError as error:
                updates.put(('error', str(error)))
            except (OSError, ConnectionError) as error:
                updates.put(('fatal', str(error)))
                return
            next_poll = time.monotonic() + 0.15

    network_thread = threading.Thread(target=exchange, name='fast-lan-client',
                                      daemon=True)
    network_thread.start()

    def owner_name(state, owner):
        return state['players'].get(str(owner), f'ID {owner + 1}')

    def draw(state):
        nonlocal observed
        if report_data is not None:
            draw_report(pg, screen, report_data, report_instrument,
                        (body, small, title), report_notice,
                        can_switch=is_admin)
            return
        if replay_data is not None:
            names = tuple(row['name'] for row in state['book'])
            draw_replay_frame(
                pg, screen, replay_data['frame'], replay_data['index'],
                replay_data['total'], names, state['players'],
                replay_observed, (body, small, title))
            return
        screen.fill(COLORS['background'])
        pg.draw.circle(screen, (27, 64, 103), (900, 0), 260)
        rounded(pg, screen, pg.Rect(24, 18, 912, 58), COLORS['panel'], 15)
        write('FAST LAN', 48, 30, COLORS['accent'], title)
        phase_names = {'lobby': 'Ожидание', 'running': 'Торги',
                       'paused': 'Пауза', 'result': 'Итоги периода',
                       'finished': 'Завершено'}
        write(phase_names.get(state['phase'], state['phase']), 700, 34,
              COLORS['warning'], body)
        write(room_label, 760, 58, COLORS['muted'], small)
        write(f'Seed {state["seed"]}', 570, 42, COLORS['muted'], small)

        if state['phase'] == 'lobby':
            card(pg, screen, pg.Rect(36, 104, 888, 410),
                 COLORS['panel'], COLORS['border'])
            write('Участники комнаты', 64, 132, COLORS['text'], title)
            write(f'Мест: {state["human_slots"]} · постоянных роботов: {state["bots"]}',
                  560, 150, COLORS['muted'], small)
            connected = set(state['connected'])
            humans = [(int(actor), name) for actor, name in state['players'].items()
                      if not name.startswith('Робот ')]
            for index, (actor, name) in enumerate(humans[:16]):
                column, row = divmod(index, 8)
                x = 72 + column * 416
                y = 198 + row * 32
                color = COLORS['accent_alt'] if actor in connected else COLORS['muted']
                write(f'ID {actor + 1}  {name}'[:24], x, y,
                      COLORS['text'], small)
                write('•' if actor in connected else '○', x + 360, y, color, body)
            if is_admin:
                write('Enter — начать игру', 64, 460, COLORS['accent'], body)
            else:
                write('Ожидайте запуска преподавателем или хостом', 64, 460,
                      COLORS['muted'], body)
        else:
            card(pg, screen, pg.Rect(28, 96, 588, 386),
                 COLORS['panel'], COLORS['border'])
            write(f'Период {state["period"] + 1}/{state["periods"]}',
                  48, 116, COLORS['text'], body)
            write(f'Ставка {state["rates"][state["period"]]}%',
                  300, 116, COLORS['muted'], body)
            write(f'{max(0, int(state["remaining"] / 10))} сек.',
                  500, 116, COLORS['warning'], body)
            write('Инструмент', 48, 158, COLORS['muted'], small)
            write('Bid', 246, 158, COLORS['buy'], small)
            write('Ask', 400, 158, COLORS['sell'], small)
            book_start = min(max(0, selected - 3),
                             max(0, len(state['book']) - 4))
            if len(state['book']) > 4:
                write(f'{selected + 1}/{len(state["book"])}', 540, 158,
                      COLORS['muted'], small)
            for offset, row in enumerate(state['book'][book_start:book_start + 4]):
                index = book_start + offset
                y = 188 + offset * 64
                if index == selected:
                    rounded(pg, screen, pg.Rect(42, y - 7, 554, 50),
                            COLORS['background_alt'], 9)
                write(row['name'][:16], 52, y + 6, COLORS['text'], body)
                if show_hints and state.get('hints'):
                    write(f'≈{state["fair_values"][index]:.3f}', 124, y + 29,
                          COLORS['accent'], small)
                for side, x, color in (('bid', 220, COLORS['buy']),
                                       ('ask', 374, COLORS['sell'])):
                    quote = row[side]
                    active = index == selected and side == selected_side
                    rounded(pg, screen, pg.Rect(x, y - 3, 140, 38),
                            COLORS['panel_alt'], 8)
                    rounded(pg, screen, pg.Rect(x, y - 3, 140, 38),
                            COLORS['accent'] if active else COLORS['border'],
                            8, 2 if active else 1)
                    if quote:
                        own = quote['owner'] == client.actor
                        write(f'{quote["price"]}.{quote["quantity"]:02d}',
                              x + 10, y + 5,
                              COLORS['white'] if own else color, small)
                        write(f'ID {quote["owner"] + 1}', x + 88, y + 5,
                              COLORS['muted'], small)
                    else:
                        write('—', x + 12, y + 5, COLORS['muted'], small)

            card(pg, screen, pg.Rect(636, 96, 296, 386),
                 COLORS['panel'], COLORS['border'])
            actor_ids = sorted(int(value) for value in state['players'])
            if observed not in actor_ids:
                observed = actor_ids[0] if actor_ids else 0
            write('Наблюдение', 658, 116, COLORS['text'], body)
            write(f'ID {observed + 1} · {owner_name(state, observed)}'[:30],
                  658, 150, COLORS['accent_alt'], small)
            portfolio = state['portfolios'].get(str(observed))
            if portfolio:
                write(f'Деньги: {portfolio["cash"]:.2f}', 658, 184,
                      COLORS['text'], body)
                for index, quantity in enumerate(portfolio['positions'][:6]):
                    write(f'{state["book"][index]["name"][:13]}: {quantity}',
                          658, 220 + index * 24, COLORS['muted'], small)
            write('Последние действия', 658, 372, COLORS['text'], small)
            actions = [event for event in state['actions']
                       if event['kind'] in ('bid', 'ask', 'buy', 'sell')][-3:]
            for row, event in enumerate(reversed(actions)):
                actor = event['actor']
                write(f'ID {actor + 1} {event["kind"]} '
                      f'{event["price"]}.{event["quantity"]:02d}',
                      658, 398 + row * 22, COLORS['muted'], small)

            if state['phase'] in ('result', 'finished'):
                rounded(pg, screen, pg.Rect(170, 214, 520, 170),
                        COLORS['background_alt'], 14)
                write('Игра завершена' if state['phase'] == 'finished'
                      else 'Период завершён', 220, 242, COLORS['text'], title)
                result = state['result'].get(str(observed))
                if result is not None:
                    write(f'Капитал ID {observed + 1}: {result:.2f}',
                          220, 298, COLORS['accent_alt'], body)
                    score = state['scores'].get(str(observed))
                    write(f'Очки: {score:.2f}', 500, 300,
                          COLORS['warning'], body)
                if is_admin and state['phase'] == 'result':
                    write('Enter — следующий период', 220, 340,
                          COLORS['warning'], small)
                if is_admin:
                    write('R — повтор сессии', 220, 362,
                          COLORS['accent_alt'], small)
                if state['period'] + 1 == state['periods']:
                    write('F2 — итоговый отчёт', 430, 362,
                          COLORS['accent_alt'], small)

        rounded(pg, screen, pg.Rect(24, 530, 912, 52), COLORS['panel'], 10)
        if input_mode:
            prompt = {'quote': 'Заявка цена.количество: ',
                      'buy': 'Купить количество: ',
                      'sell': 'Продать количество: '}[input_mode]
            write(prompt + input_text + '_', 42, 548, COLORS['text'], body)
        elif status and time.monotonic() < status_until:
            write(status[:105], 42, 548, COLORS['warning'], small)
        elif state['phase'] == 'running':
            help_text = '↑↓ инструмент  ←→ Bid/Ask  цифра — заявка  B/S — сделка  F9 — оценка'
            if is_admin:
                help_text += '  Space — пауза  E — итог  Tab — участник'
            write(help_text, 42, 548, COLORS['muted'], small)
        elif state['phase'] == 'paused':
            write('Торги приостановлены' + (' · Space — продолжить' if is_admin else ''),
                  42, 548, COLORS['warning'], small)
        else:
            write('Esc — выход', 42, 548, COLORS['muted'], small)

    while running:
        while True:
            try:
                update, value = updates.get_nowait()
            except queue.Empty:
                break
            if update == 'state':
                state = value
            elif update == 'replay':
                replay_data = value
            elif update == 'report':
                report_data = value
                report_notice = ''
            elif update == 'error':
                message(value, 5)
            else:
                network_failed = True
                message('Связь с сервером потеряна: ' + value, 30)
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
                continue
            if event.type != pg.KEYDOWN:
                continue
            key = event.key
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
                elif key == pg.K_TAB and is_admin:
                    actors = sorted(int(value) for value in state['players'])
                    current = report_data['actor']
                    target = actors[(actors.index(current) + 1) % len(actors)]
                    send({'type': 'report', 'actor': target})
                elif key == pg.K_F3:
                    paths = export_report(report_data,
                                          default_report_folder())
                    report_notice = f'Сохранено: {paths[0].parent}'
                continue
            if replay_data is not None:
                if key in (pg.K_ESCAPE, pg.K_r):
                    replay_data = None
                elif key in (pg.K_LEFT, pg.K_RIGHT, pg.K_HOME, pg.K_END):
                    if key == pg.K_HOME:
                        target = 0
                    elif key == pg.K_END:
                        target = -1
                    else:
                        target = replay_data['index'] + (-1 if key == pg.K_LEFT else 1)
                        target = max(0, min(replay_data['total'] - 1, target))
                    send({'type': 'replay', 'index': target})
                elif key == pg.K_TAB:
                    replay_observed = ((replay_observed + 1) %
                                       len(replay_data['frame']['portfolios']))
                continue
            if input_mode:
                if key == pg.K_ESCAPE:
                    input_mode, input_text = None, ''
                elif key == pg.K_BACKSPACE:
                    input_text = input_text[:-1]
                elif key == pg.K_RETURN:
                    try:
                        payload = {'type': 'trade', 'kind': input_mode,
                                   'instrument': selected}
                        if input_mode == 'quote':
                            price, quantity = parse_offer(input_text)
                            payload.update(kind=selected_side, price=price,
                                           quantity=quantity)
                        else:
                            quantity = int(input_text)
                            if not 1 <= quantity <= 99:
                                raise ValueError('Количество должно быть от 1 до 99')
                            payload['quantity'] = quantity
                        if send(payload):
                            message('Команда отправлена')
                        input_mode, input_text = None, ''
                    except ValueError as error:
                        message(error)
                elif event.unicode and event.unicode in '0123456789.':
                    input_text += event.unicode
                continue
            if key == pg.K_ESCAPE:
                running = False
            elif (key == pg.K_r and is_admin and
                  state['phase'] in ('running', 'paused', 'result', 'finished')):
                send({'type': 'replay', 'index': -1})
            elif (key == pg.K_F2 and state['phase'] in ('result', 'finished') and
                  state['period'] + 1 == state['periods']):
                send({'type': 'report', 'actor': observed})
            elif is_admin and state['phase'] in ('lobby', 'result') and key == pg.K_RETURN:
                send({'type': 'start'})
            elif is_admin and state['phase'] in ('running', 'paused') and key == pg.K_SPACE:
                send({'type': 'pause'})
            elif is_admin and state['phase'] in ('running', 'paused') and key == pg.K_e:
                send({'type': 'end_period'})
            elif is_admin and key == pg.K_TAB:
                actors = sorted(int(value) for value in state['players'])
                if actors:
                    observed = actors[(actors.index(observed) + 1) % len(actors)]
            elif client.actor is not None and state['phase'] == 'running':
                if key == pg.K_UP:
                    selected = (selected - 1) % len(state['book'])
                elif key == pg.K_DOWN:
                    selected = (selected + 1) % len(state['book'])
                elif key == pg.K_LEFT:
                    selected_side = 'bid'
                elif key == pg.K_RIGHT:
                    selected_side = 'ask'
                elif key == pg.K_b:
                    input_mode, input_text = 'buy', ''
                elif key == pg.K_s:
                    input_mode, input_text = 'sell', ''
                elif key == pg.K_F9 and state.get('hints'):
                    show_hints = not show_hints
                elif event.unicode and event.unicode.isdigit():
                    input_mode, input_text = 'quote', event.unicode
        draw(state)
        present_scaled(pg, screen, window)
        clock.tick(30)
    network_stop.set()
    network_thread.join(timeout=0.25)
    if close_display:
        pg.quit()
