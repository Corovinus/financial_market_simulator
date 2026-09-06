"""In-app launcher, room browser and teacher settings for LAN games."""
from dataclasses import replace
import getpass
import logging
from pathlib import Path
import threading
import time

from market.config import read_par
from market.generator import generate_scenario
from market.network import (
    DEFAULT_PORT, LanClient, LanServer, discover_games, local_address,
)
from .display import open_scaled_display, present_scaled
from .network_ui import run_network_client
from .theme import COLORS, card, font, label, mouse_position, rounded


ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger('fast.network.launcher')


def _endpoint(value):
    host, separator, port = value.rpartition(':')
    return ((host, int(port)) if separator and port.isdigit()
            else (value, DEFAULT_PORT))


def teacher_scenario(settings):
    """Apply classroom pacing and visibility settings to B01 or B02."""
    scenario = read_par(ROOT / f'data/original/{settings["scenario"]}.PAR')
    return replace(
        scenario, duration_ticks=settings['duration'] * 10,
        reaction_ticks=settings['reaction'] * 10,
        queue=settings['queue'], hints=settings['hints'])


def run_network_launcher(scale=1.0):
    import pygame as pg

    pg.init()
    screen, window = open_scaled_display(pg, (960, 600), scale,
                                          'FAST — локальная сеть')
    body = font(pg, 18)
    small = font(pg, 14)
    title = font(pg, 29, bold=True)
    choices = (
        ('Игра преподавателя', 'Настроить сценарий и открыть аудиторию'),
        ('Быстрая игра', 'Сбалансированный случайный сценарий'),
        ('Подключиться', 'Выбрать открытую игру в локальной сети'),
    )
    selected = 0
    mode = 'menu'
    field = -1
    address = ''
    own_address = local_address()
    player_name = getpass.getuser()[:24]
    rooms = []
    room_index = 0
    searching = False
    last_search = 0.0
    status = ''
    settings = {
        'name': 'Занятие FAST', 'scenario': 'B01', 'players': 8, 'bots': 2,
        'duration': 120, 'reaction': 6, 'queue': True, 'hints': True,
    }
    setting_index = 0
    editing_name = False
    running = True
    clock = pg.time.Clock()
    connect_button = pg.Rect(712, 489, 164, 38)
    start_button = pg.Rect(706, 492, 170, 38)
    back_button = pg.Rect(804, 30, 104, 34)
    address_field = pg.Rect(92, 354, 776, 46)
    name_field = pg.Rect(92, 421, 776, 46)

    def write(value, x, y, color=None, face=None):
        label(pg, screen, face or body, value, (x, y),
              color or COLORS['text'])

    def reset_display():
        nonlocal screen, window
        screen, window = open_scaled_display(pg, (960, 600), scale,
                                              'FAST — локальная сеть')

    def refresh_rooms():
        nonlocal searching, last_search
        if searching:
            return
        searching = True
        last_search = time.monotonic()

        def search():
            nonlocal rooms, room_index, searching, status
            try:
                rooms = discover_games()
                room_index = min(room_index, max(0, len(rooms) - 1))
                status = '' if rooms else 'Открытые игры пока не найдены'
            except OSError:
                LOGGER.warning('Room discovery failed', exc_info=True)
                status = 'Поиск недоступен. Адрес сервера можно ввести вручную.'
            finally:
                searching = False

        threading.Thread(target=search, name='fast-room-browser',
                         daemon=True).start()

    def play_local(generated, teacher=None):
        seed = int(time.time())
        if generated:
            scenario = generate_scenario(seed, 'normal')
            players, bots = 4, 4
            room_name = f'Быстрая игра · {player_name}'
        else:
            scenario = teacher_scenario(teacher)
            players, bots = teacher['players'], teacher['bots']
            room_name = teacher['name']
        server = LanServer(
            scenario, port=DEFAULT_PORT, human_slots=players, bots=bots,
            seed=seed, room_name=room_name).start()
        role = 'host' if generated else 'admin'
        name = player_name if generated else 'Преподаватель'
        client = None
        try:
            client = LanClient('127.0.0.1', server.address[1], name, role,
                               server.admin_key)
            run_network_client(
                client, role, scale, close_display=False,
                room_label=f'{room_name} · {local_address()}:{server.address[1]}')
        finally:
            if client is not None:
                client.close()
            server.stop()

    def join():
        host, port = _endpoint(address)
        client = LanClient(host, port, player_name, 'player')
        try:
            run_network_client(client, 'player', scale, close_display=False,
                               room_label=f'{host}:{port}')
        finally:
            client.close()

    def try_action(action):
        nonlocal running, status
        try:
            action()
            running = False
        except (OSError, ValueError, ConnectionError) as error:
            status = str(error)
            reset_display()

    setting_rows = (
        ('Название комнаты', 'name'), ('Сценарий', 'scenario'),
        ('Мест для игроков', 'players'), ('Постоянных роботов', 'bots'),
        ('Время периода, сек.', 'duration'), ('Реакция роботов, сек.', 'reaction'),
        ('Очередь заявок', 'queue'), ('Подсказки F9', 'hints'),
    )

    def change_setting(delta):
        key = setting_rows[setting_index][1]
        if key == 'scenario':
            settings[key] = 'B02' if settings[key] == 'B01' else 'B01'
        elif key in ('queue', 'hints'):
            settings[key] = not settings[key]
        else:
            limits = {'players': (1, 16, 1), 'bots': (0, 16, 1),
                      'duration': (30, 300, 30), 'reaction': (1, 15, 1)}
            if key in limits:
                low, high, step = limits[key]
                settings[key] = max(low, min(high,
                                              settings[key] + delta * step))

    while running:
        if mode == 'connect' and time.monotonic() - last_search > 2:
            refresh_rooms()
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
                continue
            if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                position = mouse_position(pg, event, window, screen)
                if position and mode != 'menu' and back_button.collidepoint(position):
                    if editing_name:
                        editing_name = False
                    else:
                        mode, status = 'menu', ''
                    continue
                if position and mode == 'menu':
                    for index in range(len(choices)):
                        if pg.Rect(110, 124 + index * 112, 740, 88).collidepoint(position):
                            selected = index
                elif position and mode == 'connect':
                    room_start = max(0, min(room_index, len(rooms) - 3))
                    for offset, room in enumerate(rooms[room_start:room_start + 3]):
                        if pg.Rect(92, 154 + offset * 58, 776, 48).collidepoint(position):
                            room_index, field = room_start + offset, -1
                            address = room['address']
                    if address_field.collidepoint(position):
                        field = 0
                    elif name_field.collidepoint(position):
                        field = 1
                    elif connect_button.collidepoint(position) and address and player_name:
                        try_action(join)
                elif position and mode == 'teacher':
                    for index in range(len(setting_rows)):
                        if pg.Rect(82, 136 + index * 42, 796, 34).collidepoint(position):
                            setting_index = index
                    if start_button.collidepoint(position):
                        try_action(lambda: play_local(False, settings))
                continue
            if event.type != pg.KEYDOWN:
                continue
            if mode == 'menu':
                if event.key == pg.K_ESCAPE:
                    running = False
                elif event.key == pg.K_UP:
                    selected = (selected - 1) % len(choices)
                elif event.key == pg.K_DOWN:
                    selected = (selected + 1) % len(choices)
                elif event.key == pg.K_RETURN:
                    if selected == 0:
                        mode, status = 'teacher', ''
                    elif selected == 2:
                        mode, field, status = 'connect', -1, ''
                        refresh_rooms()
                    else:
                        try_action(lambda: play_local(True))
            elif mode == 'connect':
                if event.key == pg.K_ESCAPE:
                    mode, status = 'menu', ''
                elif event.key == pg.K_F5:
                    refresh_rooms()
                elif event.key == pg.K_TAB:
                    field = 0 if field == -1 else (field + 1) % 2
                elif event.key == pg.K_DELETE and field >= 0:
                    if field == 0:
                        address = ''
                    else:
                        player_name = ''
                elif event.key == pg.K_a and event.mod & pg.KMOD_CTRL and field >= 0:
                    if field == 0:
                        address = ''
                    else:
                        player_name = ''
                elif field == -1 and event.key in (pg.K_UP, pg.K_DOWN) and rooms:
                    room_index = (room_index + (1 if event.key == pg.K_DOWN else -1)) % len(rooms)
                    address = rooms[room_index]['address']
                elif event.key == pg.K_BACKSPACE and field >= 0:
                    if field == 0:
                        address = address[:-1]
                    else:
                        player_name = player_name[:-1]
                elif event.key == pg.K_RETURN:
                    if field == -1 and rooms:
                        address = rooms[room_index]['address']
                        if player_name:
                            try_action(join)
                    elif field == 0:
                        field = 1
                    elif address and player_name:
                        try_action(join)
                elif event.unicode and event.unicode.isprintable() and field >= 0:
                    if field == 0 and event.unicode in '0123456789.:-_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ':
                        address = (address + event.unicode)[:64]
                    elif field == 1:
                        player_name = (player_name + event.unicode)[:24]
            elif mode == 'teacher':
                key = setting_rows[setting_index][1]
                if editing_name:
                    if event.key in (pg.K_RETURN, pg.K_ESCAPE):
                        editing_name = False
                    elif event.key == pg.K_BACKSPACE:
                        settings['name'] = settings['name'][:-1]
                    elif event.unicode and event.unicode.isprintable():
                        settings['name'] = (settings['name'] + event.unicode)[:40]
                elif event.key == pg.K_ESCAPE:
                    mode, status = 'menu', ''
                elif event.key == pg.K_UP:
                    setting_index = (setting_index - 1) % len(setting_rows)
                elif event.key == pg.K_DOWN:
                    setting_index = (setting_index + 1) % len(setting_rows)
                elif event.key in (pg.K_LEFT, pg.K_RIGHT):
                    change_setting(1 if event.key == pg.K_RIGHT else -1)
                elif event.key == pg.K_RETURN and key == 'name':
                    editing_name = True
                elif event.key in (pg.K_RETURN, pg.K_F5):
                    try_action(lambda: play_local(False, settings))

        screen.fill(COLORS['background'])
        pg.draw.circle(screen, (27, 64, 103), (900, 0), 260)
        rounded(pg, screen, pg.Rect(24, 18, 912, 58), COLORS['panel'], 15)
        write('Сетевая игра', 48, 30, COLORS['accent'], title)
        if mode == 'menu':
            write(f'Ваш IP: {own_address}', 682, 39, COLORS['muted'], small)
        else:
            write(f'Ваш IP: {own_address}', 590, 39, COLORS['muted'], small)
            rounded(pg, screen, back_button, COLORS['background_alt'], 8)
            rounded(pg, screen, back_button, COLORS['border'], 8, 1)
            write('← Назад', back_button.x + 14, back_button.y + 8,
                  COLORS['text'], small)

        if mode == 'menu':
            for index, (caption, detail) in enumerate(choices):
                rect = pg.Rect(110, 124 + index * 112, 740, 88)
                active = index == selected
                card(pg, screen, rect,
                     COLORS['accent'] if active else COLORS['panel'],
                     COLORS['accent_alt'] if active else COLORS['border'])
                write(caption, 142, rect.y + 18,
                      COLORS['white'] if active else COLORS['text'], body)
                write(detail, 142, rect.y + 51,
                      COLORS['white'] if active else COLORS['muted'], small)
            write('↑ ↓ — выбрать · Enter — открыть · Esc — назад',
                  110, 486, COLORS['muted'], small)
        elif mode == 'connect':
            card(pg, screen, pg.Rect(60, 96, 840, 448),
                 COLORS['panel'], COLORS['border'])
            write('Открытые игры', 88, 112, COLORS['text'], body)
            write('поиск…' if searching else 'F5 — обновить', 750, 116,
                  COLORS['accent'] if searching else COLORS['muted'], small)
            room_start = max(0, min(room_index, len(rooms) - 3))
            for offset, room in enumerate(rooms[room_start:room_start + 3]):
                index = room_start + offset
                rect = pg.Rect(92, 154 + offset * 58, 776, 48)
                active = field == -1 and index == room_index
                rounded(pg, screen, rect,
                        COLORS['accent'] if active else COLORS['background_alt'], 8)
                write(room['name'][:30], 108, rect.y + 7,
                      COLORS['white'] if active else COLORS['text'], small)
                write(f'{room["players"]}/{room["capacity"]} игроков · {room["bots"]} роботов · {room["address"]}',
                      420, rect.y + 7,
                      COLORS['white'] if active else COLORS['muted'], small)
            if not rooms:
                write('Комнаты появятся здесь автоматически', 108, 174,
                      COLORS['muted'], small)
            for index, (caption, value) in enumerate((('Адрес сервера (IP или IP:порт)', address),
                                                       ('Имя игрока', player_name))):
                y = 354 + index * 67
                write(caption, 96, y - 20, COLORS['muted'], small)
                input_rect = address_field if index == 0 else name_field
                rounded(pg, screen, input_rect,
                        COLORS['background_alt'], 8)
                rounded(pg, screen, input_rect,
                        COLORS['accent'] if field == index else COLORS['border'],
                        8, 2)
                shown = value or ('например, 192.168.1.25:8765' if index == 0 else '')
                write(shown + ('_' if field == index else ''), 108, y + 12,
                      COLORS['muted'] if not value else COLORS['text'], small)
            can_connect = bool(address and player_name)
            rounded(pg, screen, connect_button,
                    COLORS['accent'] if can_connect else COLORS['background_alt'], 8)
            write('Подключиться', 730, 499,
                  COLORS['white'] if can_connect else COLORS['muted'], small)
            write('↑↓ игра · Tab поля · Ctrl+A / Delete — очистить · Esc назад',
                  88, 518, COLORS['muted'], small)
        else:
            card(pg, screen, pg.Rect(60, 96, 840, 448),
                 COLORS['panel'], COLORS['border'])
            write('Настройки преподавателя', 88, 105, COLORS['text'], body)
            for index, (caption, key) in enumerate(setting_rows):
                rect = pg.Rect(82, 136 + index * 42, 796, 34)
                active = index == setting_index
                rounded(pg, screen, rect,
                        COLORS['accent'] if active else COLORS['background_alt'], 7)
                value = settings[key]
                shown = ('Да' if value is True else 'Нет' if value is False
                         else str(value))
                if key == 'name' and editing_name:
                    shown += '_'
                write(caption, 98, rect.y + 7,
                      COLORS['white'] if active else COLORS['muted'], small)
                write(shown, 570, rect.y + 7,
                      COLORS['white'] if active else COLORS['accent_alt'], small)
            rounded(pg, screen, start_button, COLORS['accent'], 8)
            write('Создать игру', 724, 502, COLORS['white'], small)
            write('↑↓ параметр · ←→ изменить · Enter имя/старт · F5 старт',
                  82, 506, COLORS['muted'], small)

        if status:
            status_color = (COLORS['muted'] if status == 'Открытые игры пока не найдены'
                            else COLORS['danger'])
            write(status[:100], 72, 558, status_color, small)
        present_scaled(pg, screen, window)
        clock.tick(60)
