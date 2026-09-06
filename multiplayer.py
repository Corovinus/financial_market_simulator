"""Run a FAST game over a local student network."""
import argparse
from dataclasses import replace
import getpass
import logging
from pathlib import Path
import sys
import time

from main import configure_logging
from market.config import read_par
from market.generator import generate_scenario
from market.network import (
    DEFAULT_PORT, LanClient, LanServer, local_address, parse_endpoint,
)
from modules.network_ui import run_network_client


ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger('fast.multiplayer')


def host_game(args, generated=False):
    seed = args.seed if args.seed is not None else int(time.time())
    if generated:
        scenario = generate_scenario(seed, args.difficulty)
    else:
        scenario = read_par(args.scenario)
        if args.duration is not None:
            scenario = replace(scenario, duration_ticks=round(args.duration * 10))
        if args.reaction is not None:
            scenario = replace(scenario, reaction_ticks=round(args.reaction * 10))
    server = LanServer(scenario, args.bind, args.port, args.players,
                       args.bots, seed, room_name=args.room_name).start()
    address = local_address()
    print(f'Комната: {address}:{server.address[1]}')
    print(f'Ключ администратора: {server.admin_key}')
    if generated:
        print(f'Seed сценария: {seed}')
    role = 'host' if generated else 'admin'
    name = args.name if generated else 'Преподаватель'
    client = None
    try:
        client = LanClient('127.0.0.1', server.address[1], name, role,
                           server.admin_key)
        run_network_client(client, role, args.scale,
                           room_label=f'{address}:{server.address[1]}')
    finally:
        if client is not None:
            client.close()
        server.stop()


def join_game(args):
    host, port = parse_endpoint(args.address, args.port)
    client = LanClient(host, port, args.name, 'player')
    try:
        run_network_client(client, 'player', args.scale,
                           room_label=f'{host}:{port}')
    finally:
        client.close()


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest='command', required=True)

    admin = commands.add_parser('admin', help='Создать игру преподавателя')
    admin.add_argument('--scenario', type=Path,
                       default=ROOT / 'data/original/B01.PAR')
    admin.add_argument('--players', type=int, default=8)
    admin.add_argument('--bots', type=int, default=2)
    admin.add_argument('--duration', type=float, help='Длительность периода, сек.')
    admin.add_argument('--reaction', type=float, help='Реакция роботов, сек.')
    admin.add_argument('--room-name', default='Занятие FAST')

    host = commands.add_parser('host', help='Создать игру с умным рандомом')
    host.add_argument('--name', default=getpass.getuser())
    host.add_argument('--difficulty', choices=('easy', 'normal', 'hard'),
                      default='normal')
    host.add_argument('--seed', type=int)
    host.add_argument('--players', type=int, default=4)
    host.add_argument('--bots', type=int, default=4)
    host.add_argument('--room-name', default='Быстрая игра FAST')

    join = commands.add_parser('join', help='Подключиться к комнате')
    join.add_argument('address', help='IP сервера или IP:порт')
    join.add_argument('--name', default=getpass.getuser())

    for command in (admin, host):
        command.add_argument('--bind', default='0.0.0.0')
        command.add_argument('--port', type=int, default=DEFAULT_PORT)
        command.add_argument('--scale', type=float, default=1.25)
        if command is admin:
            command.add_argument('--seed', type=int)
    join.add_argument('--port', type=int, default=DEFAULT_PORT)
    join.add_argument('--scale', type=float, default=1.25)
    return result


def main():
    configure_logging()
    args = parser().parse_args()
    if args.command == 'admin':
        host_game(args)
    elif args.command == 'host':
        host_game(args, generated=True)
    else:
        join_game(args)


if __name__ == '__main__':
    configure_logging()
    try:
        main()
    except Exception:
        LOGGER.exception('Unhandled multiplayer error')
        print(f'Ошибка сетевой игры. Подробности записаны в {ROOT / "fast.log"}',
              file=sys.stderr)
        raise
