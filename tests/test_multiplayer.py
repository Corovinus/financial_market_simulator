from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import socket
import unittest
from unittest.mock import patch

from market.config import read_par
from market.generator import generate_scenario
from market.network import (
    GameSession, LanClient, LanServer, discover_games, parse_endpoint,
)
from modules.network_launcher import teacher_scenario


ROOT = Path(__file__).resolve().parents[1]


class MultiplayerTests(unittest.TestCase):
    def test_endpoint_validation(self):
        self.assertEqual(parse_endpoint('192.168.1.5'),
                         ('192.168.1.5', 8765))
        self.assertEqual(parse_endpoint('localhost:9000'),
                         ('localhost', 9000))
        for value in ('', ':8765', 'localhost:no', 'localhost:70000'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_endpoint(value)

    def test_discovery_ignores_rejected_vpn_route(self):
        class Probe:
            calls = 0

            def setsockopt(self, *_args):
                pass

            def bind(self, *_args):
                pass

            def sendto(self, *_args):
                pass

            def settimeout(self, *_args):
                pass

            def recvfrom(self, *_args):
                self.calls += 1
                if self.calls == 1:
                    error = OSError(10054, 'VPN route rejected the probe')
                    error.winerror = 10054
                    raise error
                raise socket.timeout

            def close(self):
                pass

        with patch('market.network.socket.socket', return_value=Probe()):
            self.assertEqual(discover_games(.1, targets=('192.168.1.255',)), [])

    def test_teacher_settings_change_pacing_without_changing_payments(self):
        settings = {'scenario': 'B02', 'duration': 90, 'reaction': 4,
                    'queue': False, 'hints': False}
        scenario = teacher_scenario(settings)
        original = read_par(ROOT / 'data/original/B02.PAR')
        self.assertEqual((scenario.duration_ticks, scenario.reaction_ticks),
                         (900, 40))
        self.assertEqual(scenario.payments, original.payments)
        self.assertFalse(scenario.queue)
        self.assertFalse(scenario.hints)

    def test_open_room_is_discovered_on_local_network(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        server = LanServer(scenario, host='127.0.0.1', port=0,
                           human_slots=5, bots=2, room_name='Семинар 7').start()
        try:
            rooms = discover_games(timeout=1, targets=('127.0.0.1',))
            room = next(value for value in rooms
                        if value['port'] == server.address[1])
            self.assertEqual(room['name'], 'Семинар 7')
            self.assertEqual((room['players'], room['capacity'], room['bots']),
                             (0, 5, 2))
            server.session.join('Участник')
            server.session.start_or_continue()
            rooms = discover_games(timeout=.3, targets=('127.0.0.1',))
            self.assertFalse(any(value['port'] == server.address[1]
                                 for value in rooms))
        finally:
            server.stop()

    def test_smart_scenario_is_reproducible_and_valid(self):
        first = generate_scenario(12345, 'normal')
        second = generate_scenario(12345, 'normal')
        self.assertEqual(first, second)
        self.assertEqual((first.periods, len(first.names)), (3, 3))
        self.assertTrue(all(payment[-1] > 0 for payment in first.payments))
        self.assertGreater(first.score_parameters[2], first.cash)

    def test_session_separates_people_from_robots(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        game = GameSession(scenario, human_slots=2, bots=2, seed=7)
        alice = game.join('Алиса')
        bob = game.join('Борис')
        self.assertEqual((alice, bob), (0, 1))
        duplicate = GameSession(scenario, human_slots=2, bots=0)
        duplicate.join('Алиса')
        with self.assertRaisesRegex(ValueError, 'занято'):
            duplicate.join('Алиса')
        game.start_or_continue()
        self.assertEqual(game._robots.actors, (2, 3))
        game.trade(alice, {'kind': 'bid', 'instrument': 0,
                           'price': 100, 'quantity': 2})
        game.trade(bob, {'kind': 'sell', 'instrument': 0, 'quantity': 1})
        self.assertEqual(game.market.portfolios[alice].positions[0], 16)
        self.assertEqual(game.market.portfolios[bob].positions[0], 14)
        self.assertEqual(set(game.state(False, alice)['portfolios']), {'0'})
        self.assertEqual(len(game.state(True)['portfolios']), 4)
        game.tick(scenario.duration_ticks / 10)
        self.assertEqual(game.phase, 'result')
        self.assertEqual(len(game.result), 4)

    def test_started_session_requires_private_reconnect_token(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        game = GameSession(scenario, human_slots=1, bots=0)
        actor = game.join('Алиса')
        token = game.reconnect_tokens[actor]
        game.start_or_continue()
        game.disconnect(actor)
        with self.assertRaisesRegex(ValueError, 'ключ'):
            game.join('Алиса')
        with self.assertRaisesRegex(ValueError, 'ключ'):
            game.join('Алиса', 'чужой ключ')
        self.assertEqual(game.join('Алиса', token), actor)

    def test_simultaneous_quotes_are_serialized(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        game = GameSession(scenario, human_slots=4, bots=0)
        actors = [game.join(f'Игрок {number}') for number in range(4)]
        game.start_or_continue()

        def submit(pair):
            actor, price = pair
            try:
                game.trade(actor, {'kind': 'bid', 'instrument': 0,
                                   'price': price, 'quantity': 1})
            except ValueError:
                pass

        with ThreadPoolExecutor(max_workers=4) as pool:
            tuple(pool.map(submit, zip(actors, (80, 90, 100, 110))))
        self.assertEqual(game.market.book.best(0, 'bid').price, 110)

    def test_tcp_server_keeps_clients_synchronized_after_rejected_order(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        server = LanServer(scenario, host='127.0.0.1', port=0,
                           human_slots=2, bots=0, seed=1,
                           discovery=False).start()
        port = server.address[1]
        admin = first = second = None
        try:
            admin = LanClient('127.0.0.1', port, role='admin',
                              key=server.admin_key)
            first = LanClient('127.0.0.1', port, name='Первый')
            second = LanClient('127.0.0.1', port, name='Второй')
            admin.request({'type': 'start'})
            with self.assertRaisesRegex(ValueError, 'Нет заявок'):
                second.request({'type': 'trade', 'kind': 'sell',
                                'instrument': 0, 'quantity': 1})
            first.request({'type': 'trade', 'kind': 'bid', 'instrument': 0,
                           'price': 90, 'quantity': 2})
            second.request({'type': 'trade', 'kind': 'sell',
                            'instrument': 0, 'quantity': 1})
            replay = admin.request({'type': 'replay', 'index': -1})['replay']
            self.assertEqual(replay['index'], replay['total'] - 1)
            self.assertEqual(replay['frame']['kind'], 'sell')
            with self.assertRaisesRegex(ValueError, 'преподавателю'):
                first.request({'type': 'replay', 'index': 0})
            admin_state = admin.request({'type': 'state'})['state']
            first_state = first.request({'type': 'state'})['state']
            self.assertEqual(admin_state['portfolios']['0']['positions'][0], 16)
            self.assertEqual(admin_state['portfolios']['1']['positions'][0], 14)
            self.assertEqual(set(first_state['portfolios']), {'0'})
            second.close()
            second = LanClient('127.0.0.1', port, name='Второй')
            self.assertEqual(second.actor, 1)
            admin.request({'type': 'end_period'})
            result = admin.request({'type': 'state'})['state']['result']
            self.assertEqual(len(result), 2)
            self.assertEqual(len(admin.state['scores']), 2)
            player_result = second.request({'type': 'state'})['state']['result']
            self.assertEqual(set(player_result), {'1'})
        finally:
            for client in (second, first, admin):
                if client is not None:
                    client.close()
            server.stop()


if __name__ == '__main__':
    unittest.main()
