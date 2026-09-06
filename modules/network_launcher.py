"""Small in-app launcher for the three local-network roles."""
import getpass
from pathlib import Path
import time

from market.config import read_par
from market.generator import generate_scenario
from market.network import DEFAULT_PORT, LanClient, LanServer, local_address
from .display import open_scaled_display, present_scaled
from .network_ui import run_network_client
from .theme import COLORS, card, font, label, rounded


ROOT = Path(__file__).resolve().parents[1]


def _endpoint(value):
    host, separator, port = value.rpartition(':')
    return ((host, int(port)) if separator and port.isdigit()
            else (value, DEFAULT_PORT))


def run_network_launcher(scale=1.0):
    import pygame as pg

    pg.init()
    screen, window = open_scaled_display(pg, (960, 600), scale,
                                          'FAST — локальная сеть')
    body = font(pg, 18)
    small = font(pg, 14)
    title = font(pg, 29, bold=True)
    choices = (
        ('Игра преподавателя', 'B01 · 8 мест · 2 робота'),
        ('Быстрая игра', 'Сбалансированный случайный сценарий'),
        ('Подключиться', 'Введите адрес компьютера-хоста'),
    )
    selected = 0
    form = False
    field = 0
    address = ''
    player_name = getpass.getuser()[:24]
    status = ''
    running = True
    clock = pg.time.Clock()

    def write(value, x, y, color=None, face=None):
        label(pg, screen, face or body, value, (x, y),
              color or COLORS['text'])

    def play_local(generated):
        scenario = (generate_scenario(int(time.time()), 'normal') if generated
                    else read_par(ROOT / 'data/original/B01.PAR'))
        players, bots = (4, 4) if generated else (8, 2)
        server = LanServer(scenario, port=DEFAULT_PORT,
                           human_slots=players, bots=bots,
                           seed=int(time.time())).start()
        role = 'host' if generated else 'admin'
        name = player_name if generated else 'Преподаватель'
        client = None
        try:
            client = LanClient('127.0.0.1', server.address[1], name, role,
                               server.admin_key)
            run_network_client(
                client, role, scale, close_display=False,
                room_label=f'{local_address()}:{server.address[1]}')
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

    while running:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
                continue
            if event.type != pg.KEYDOWN:
                continue
            if form:
                if event.key == pg.K_ESCAPE:
                    form = False
                elif event.key == pg.K_TAB:
                    field = 1 - field
                elif event.key == pg.K_BACKSPACE:
                    if field == 0:
                        address = address[:-1]
                    else:
                        player_name = player_name[:-1]
                elif event.key == pg.K_RETURN:
                    if field == 0:
                        field = 1
                    elif address and player_name:
                        try:
                            join()
                            running = False
                        except (OSError, ValueError, ConnectionError) as error:
                            status = str(error)
                            screen, window = open_scaled_display(
                                pg, (960, 600), scale,
                                'FAST — локальная сеть')
                elif event.unicode and event.unicode.isprintable():
                    if field == 0 and event.unicode in '0123456789.:-_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ':
                        address = (address + event.unicode)[:64]
                    elif field == 1:
                        player_name = (player_name + event.unicode)[:24]
                continue
            if event.key == pg.K_ESCAPE:
                running = False
            elif event.key == pg.K_UP:
                selected = (selected - 1) % len(choices)
            elif event.key == pg.K_DOWN:
                selected = (selected + 1) % len(choices)
            elif event.key == pg.K_RETURN:
                if selected == 2:
                    form = True
                else:
                    try:
                        play_local(selected == 1)
                        running = False
                    except (OSError, ValueError, ConnectionError) as error:
                        status = str(error)
                        screen, window = open_scaled_display(
                            pg, (960, 600), scale,
                            'FAST — локальная сеть')

        screen.fill(COLORS['background'])
        pg.draw.circle(screen, (27, 64, 103), (900, 0), 260)
        rounded(pg, screen, pg.Rect(24, 18, 912, 58), COLORS['panel'], 15)
        write('Сетевая игра', 48, 30, COLORS['accent'], title)
        write('Локальная студенческая сеть', 650, 39, COLORS['muted'], small)
        if form:
            card(pg, screen, pg.Rect(100, 116, 760, 350),
                 COLORS['panel'], COLORS['border'])
            write('Подключение к комнате', 142, 150, COLORS['text'], title)
            for index, (caption, value) in enumerate((('IP или IP:порт', address),
                                                       ('Имя игрока', player_name))):
                y = 228 + index * 92
                write(caption, 148, y - 28, COLORS['muted'], small)
                rounded(pg, screen, pg.Rect(142, y, 672, 52),
                        COLORS['background_alt'], 9)
                rounded(pg, screen, pg.Rect(142, y, 672, 52),
                        COLORS['accent'] if field == index else COLORS['border'],
                        9, 2)
                shown = value or ('192.168.1.25:8765' if index == 0 else '')
                write(shown + ('_' if field == index else ''), 160, y + 14,
                      COLORS['text'], body)
            write('Tab — другое поле · Enter — продолжить · Esc — назад',
                  142, 414, COLORS['muted'], small)
        else:
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
        if status:
            write(status[:100], 110, 530, COLORS['danger'], small)
        present_scaled(pg, screen, window)
        clock.tick(60)
