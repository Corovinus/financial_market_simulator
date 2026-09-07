"""Authoritative local-network session and a small JSON-over-TCP protocol."""
from dataclasses import asdict, replace
import ipaddress
import json
import logging
import math
import secrets
import socket
import socketserver
import threading
import time

from .config import Scenario
from .calculations import bond_value, future_capital
from .engine import Market
from .goals import evaluate_goals
from .orderbook import OrderError
from .report import build_report
from .robots import RobotController


LOGGER = logging.getLogger('fast.network')
DEFAULT_PORT = 8765
DISCOVERY_PORT = 8766
DISCOVERY_REQUEST = b'FAST_DISCOVER_V1'
MAX_MESSAGE = 65_536


def parse_endpoint(value, default_port=DEFAULT_PORT):
    """Parse an IPv4/hostname endpoint accepted by both launchers."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Введите адрес сервера')
    value = value.strip()
    host, separator, port_text = value.rpartition(':')
    if separator:
        if not host or not port_text.isdigit():
            raise ValueError('Адрес должен иметь вид IP или IP:порт')
        port = int(port_text)
    else:
        host, port = value, default_port
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Порт должен быть от 1 до 65535')
    return host, port


class GameSession:
    """One synchronized market shared by player and administrator clients."""

    def __init__(self, scenario: Scenario, human_slots=4, bots=4, seed=0,
                 case_hud=None):
        if not isinstance(scenario, Scenario):
            raise TypeError('Ожидался Scenario')
        if type(human_slots) is not int or not 1 <= human_slots <= 16:
            raise ValueError('Число мест игроков должно быть от 1 до 16')
        if type(bots) is not int or not 0 <= bots <= 32:
            raise ValueError('Число роботов должно быть от 0 до 32')
        has_fixed_prices = any(any(price is not None for price in row)
                               for row in scenario.fixed_prices)
        market_makers = 1 if has_fixed_prices else 0
        total = human_slots + bots + market_makers
        self.scenario = replace(scenario, robots=total - 1,
                                wolves=min(scenario.wolves, bots))
        self.human_slots = human_slots
        self.bot_count = bots + market_makers
        self.seed = seed
        self.case_hud = case_hud
        fixed_owner = total - 1 if market_makers else 1
        self.market = Market(self.scenario, fixed_owner)
        self.market.start_period(0)
        self.period = 0
        self.remaining = float(self.scenario.duration_ticks)
        self.phase = 'lobby'
        self.players = {}
        self.reconnect_tokens = {}
        self.connected = set()
        self.actions = []
        self.result = None
        self.scores = None
        self._robots = None
        self._sequence = 0
        self._lock = threading.RLock()
        self._fair_values = self._calculate_fair_values()

    def join(self, name, reconnect_token=None):
        clean = str(name).strip()[:24]
        if not clean:
            raise ValueError('Введите имя игрока')
        with self._lock:
            if self.phase != 'lobby':
                actor = next((number for number, saved in self.players.items()
                              if saved == clean and number not in self.connected),
                             None)
                if actor is None:
                    raise ValueError('Игра уже началась')
                expected = self.reconnect_tokens.get(actor, '')
                supplied = str(reconnect_token or '').encode('utf-8')
                if not secrets.compare_digest(expected.encode('utf-8'), supplied):
                    raise ValueError('Неверный ключ переподключения')
                self.connected.add(actor)
                self._record(actor, 'reconnect')
                return actor
            if clean in self.players.values():
                raise ValueError('Это имя уже занято')
            actor = next((index for index in range(self.human_slots)
                          if index not in self.players), None)
            if actor is None:
                raise ValueError('Свободных мест нет')
            self.players[actor] = clean
            self.reconnect_tokens[actor] = secrets.token_urlsafe(24)
            self.connected.add(actor)
            self._record(actor, 'join')
            return actor

    def disconnect(self, actor):
        with self._lock:
            self.connected.discard(actor)
            if self.phase == 'lobby':
                self.players.pop(actor, None)
                self.reconnect_tokens.pop(actor, None)
            self._record(actor, 'disconnect')

    def start_or_continue(self):
        with self._lock:
            if self.phase == 'lobby':
                if not self.players:
                    raise ValueError('Нужен хотя бы один игрок')
                robot_actors = tuple(actor for actor in range(len(self.market.portfolios))
                                     if actor not in self.players)
                self._robots = RobotController(self.market, self.seed,
                                               robot_actors)
                self.phase = 'running'
                self._record(None, 'start')
            elif self.phase == 'paused':
                self.phase = 'running'
                self._record(None, 'resume')
            elif self.phase == 'result':
                if self.period + 1 >= self.scenario.periods:
                    self.phase = 'finished'
                else:
                    self.period += 1
                    self.market.start_period(self.period)
                    self._robots.start_period(self.period)
                    self._fair_values = self._calculate_fair_values()
                    self.remaining = float(self.scenario.duration_ticks)
                    self.result = None
                    self.scores = None
                    self.phase = 'running'
                    self._record(None, 'next_period')
            return self.phase

    def toggle_pause(self):
        with self._lock:
            if self.phase == 'running':
                self.phase = 'paused'
                self._record(None, 'pause')
            elif self.phase == 'paused':
                self.phase = 'running'
                self._record(None, 'resume')
            else:
                raise ValueError('Пауза доступна только во время торгов')
            return self.phase

    def tick(self, seconds):
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('Неверный интервал времени')
        with self._lock:
            if self.phase != 'running':
                return
            elapsed = min(self.remaining, seconds * 10)
            self.remaining -= elapsed
            if self._robots:
                for event in self._robots.step(elapsed):
                    self._record(event.actor, event.action, event.instrument,
                                 event.price, event.quantity)
            if self.remaining <= 0:
                self._finish_period()

    def end_period(self):
        with self._lock:
            if self.phase not in ('running', 'paused'):
                raise ValueError('Период сейчас не идёт')
            self.remaining = 0
            self._finish_period()

    def _finish_period(self):
        self.result = {
            str(actor): future_capital(
                self.scenario, portfolio.cash,
                tuple(portfolio.positions), self.period)
            for actor, portfolio in enumerate(self.market.portfolios)
        }
        self.market.finish_period()
        self.scores = {actor: self.market.score(value)
                       for actor, value in self.result.items()}
        self.phase = 'result'
        self._record(None, 'period_result')

    def trade(self, actor, command):
        with self._lock:
            if self.phase != 'running':
                raise ValueError('Торги сейчас не идут')
            if actor not in self.players or actor not in self.connected:
                raise ValueError('Игрок не подключён')
            kind = command.get('kind')
            instrument = command.get('instrument')
            quantity = command.get('quantity')
            if kind in ('bid', 'ask'):
                price = command.get('price')
                quote = self.market.submit(actor, instrument, kind, price,
                                           quantity)
                self._record(actor, kind, instrument, quote.price,
                             quote.quantity)
            elif kind in ('buy', 'sell'):
                trade = self.market.take(actor, instrument, kind, quantity)
                self._record(actor, kind, instrument, trade.price,
                             trade.quantity)
            else:
                raise ValueError('Неизвестная торговая команда')

    def state(self, admin=False, actor=None):
        with self._lock:
            book = []
            for instrument, name in enumerate(self.scenario.names):
                row = {'name': name}
                for side in ('bid', 'ask'):
                    quote = self.market.book.best(instrument, side)
                    row[side] = (None if quote is None else
                                 {'owner': quote.owner, 'price': quote.price,
                                  'quantity': quote.quantity})
                book.append(row)
            visible = range(len(self.market.portfolios)) if admin else (() if actor is None else (actor,))
            portfolios = {
                str(index): {'cash': portfolio.cash,
                             'positions': tuple(portfolio.positions)}
                for index in visible
                for portfolio in (self.market.portfolios[index],)
            }
            names = {str(index): self.players.get(index, f'Робот {index + 1}')
                     for index in range(len(self.market.portfolios))}
            result = self.result
            scores = self.scores
            if result is not None and not admin:
                result = ({str(actor): result[str(actor)]}
                          if actor is not None else {})
                scores = ({str(actor): scores[str(actor)]}
                          if actor is not None else {})
            case_hud = asdict(self.case_hud) if self.case_hud else None
            if (case_hud and not admin and actor is not None and
                    case_hud['label'].startswith('Case RE')):
                private = case_hud['private_information']
                case_hud['private_information'] = (
                    private[actor % len(private)],) if private else ()
            hidden_case = bool(case_hud and case_hud['label'].startswith(
                ('Case CA', 'Case OP', 'Case RE')))
            payments = self.scenario.payments
            fair_values = self._fair_values
            visible_seed = self.seed
            visible_hints = self.scenario.hints
            if hidden_case and not admin:
                payments = tuple((0,) * self.scenario.periods
                                 for _ in self.scenario.names)
                fair_values = ()
                visible_seed = None
                visible_hints = False
                if case_hud['label'].startswith('Case OP'):
                    case_hud['option_path'] = case_hud['option_path'][
                        :self.period + 1]
            return {
                'phase': self.phase, 'period': self.period,
                'periods': self.scenario.periods,
                'remaining': self.remaining, 'book': book,
                'human_slots': self.human_slots, 'bots': self.bot_count,
                'seed': visible_seed,
                'players': names, 'connected': tuple(sorted(self.connected)),
                'portfolios': portfolios, 'actions': tuple(self.actions[-30:]),
                'result': result, 'scores': scores,
                'rates': self.scenario.rates,
                'payments': payments,
                'hints': visible_hints,
                'goal_count': len(self.scenario.goals),
                'fair_values': fair_values,
                'case_hud': case_hud,
            }

    def replay_frame(self, index):
        """Return one compact replay snapshot for an administrator."""
        with self._lock:
            total = len(self.market.replay_frames)
            if not total:
                raise ValueError('Повтор пока пуст')
            if index == -1:
                index = total - 1
            if type(index) is not int or not 0 <= index < total:
                raise ValueError('Неверный номер события повтора')
            return {'index': index, 'total': total,
                    'frame': self.market.replay_frames[index]}

    def final_report(self, actor):
        with self._lock:
            names = {str(index): self.players.get(index, f'Робот {index + 1}')
                     for index in range(len(self.market.portfolios))}
            return build_report(self.scenario, self.market.replay_frames,
                                actor, names)

    def goal_progress(self, actor):
        with self._lock:
            return evaluate_goals(self.scenario, self.market.replay_frames,
                                  actor)

    def _calculate_fair_values(self):
        return tuple(bond_value(self.scenario, instrument, self.period)
                     for instrument in range(len(self.scenario.names)))

    def _record(self, actor, kind, instrument=None, price=None, quantity=None,
                value=None):
        self._sequence += 1
        event = {'sequence': self._sequence, 'actor': actor, 'kind': kind,
                 'instrument': instrument, 'price': price,
                 'quantity': quantity, 'value': value}
        self.actions.append(event)
        if len(self.actions) > 200:
            del self.actions[:-200]
        LOGGER.info('Game event: %s', event)


class _RequestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        role = None
        actor = None
        try:
            first = self._read()
            if first.get('type') != 'join':
                raise ValueError('Первое сообщение должно быть join')
            role = first.get('role', 'player')
            if role == 'admin':
                if first.get('key') != self.server.admin_key:
                    raise ValueError('Неверный ключ администратора')
            elif role in ('player', 'host'):
                if role == 'host' and first.get('key') != self.server.admin_key:
                    raise ValueError('Неверный ключ хоста')
                actor = self.server.session.join(
                    first.get('name', ''), first.get('reconnect_token'))
            else:
                raise ValueError('Неизвестная роль')
            self._send({'ok': True, 'actor': actor,
                        'reconnect_token': (self.server.session.reconnect_tokens.get(actor)
                                            if actor is not None else None),
                        'state': self.server.session.state(role in ('admin', 'host'), actor)})
            while True:
                request = self._read()
                try:
                    kind = request.get('type')
                    is_admin = role in ('admin', 'host')
                    if kind == 'state':
                        result = self.server.session.state(is_admin, actor)
                    elif kind == 'replay':
                        if not is_admin:
                            raise ValueError('Повтор доступен преподавателю')
                        replay = self.server.session.replay_frame(
                            request.get('index'))
                        self._send({'ok': True, 'replay': replay})
                        continue
                    elif kind == 'report':
                        report_actor = request.get('actor') if is_admin else actor
                        report = self.server.session.final_report(report_actor)
                        self._send({'ok': True, 'report': report})
                        continue
                    elif kind == 'goals':
                        goal_actor = request.get('actor') if is_admin else actor
                        progress = self.server.session.goal_progress(goal_actor)
                        self._send({'ok': True, 'goals': progress})
                        continue
                    elif kind == 'trade':
                        if actor is None:
                            raise ValueError('Наблюдатель не может торговать')
                        self.server.session.trade(actor, request)
                        result = self.server.session.state(is_admin, actor)
                    elif kind == 'start' and is_admin:
                        self.server.session.start_or_continue()
                        result = self.server.session.state(True, actor)
                    elif kind == 'pause' and is_admin:
                        self.server.session.toggle_pause()
                        result = self.server.session.state(True, actor)
                    elif kind == 'end_period' and is_admin:
                        self.server.session.end_period()
                        result = self.server.session.state(True, actor)
                    else:
                        raise ValueError('Недоступная команда')
                    self._send({'ok': True, 'state': result})
                except (ValueError, TypeError, OrderError) as error:
                    self._send({'ok': False, 'error': str(error)})
        except EOFError:
            pass
        except (ValueError, TypeError, OrderError) as error:
            self._send({'ok': False, 'error': str(error)})
        except (ConnectionError, OSError):
            pass
        finally:
            if actor is not None:
                self.server.session.disconnect(actor)

    def _read(self):
        data = self.rfile.readline(MAX_MESSAGE + 1)
        if not data:
            raise EOFError
        if len(data) > MAX_MESSAGE:
            raise ValueError('Слишком большое сообщение')
        try:
            value = json.loads(data.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError('Неверный формат сообщения') from error
        if not isinstance(value, dict):
            raise ValueError('Сообщение должно быть объектом')
        return value

    def _send(self, value):
        try:
            self.wfile.write(json.dumps(value, ensure_ascii=False,
                                        separators=(',', ':')).encode('utf-8') + b'\n')
            self.wfile.flush()
        except OSError:
            pass


class _ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class LanServer:
    def __init__(self, scenario, host='0.0.0.0', port=DEFAULT_PORT,
                 human_slots=4, bots=4, seed=0, admin_key=None,
                 room_name='Игра FAST', discovery=True, case_hud=None):
        self.session = GameSession(scenario, human_slots, bots, seed,
                                   case_hud)
        self.admin_key = admin_key or secrets.token_urlsafe(6)
        self.room_name = str(room_name).strip()[:40] or 'Игра FAST'
        self.discovery = discovery
        self._server = _ThreadingServer((host, port), _RequestHandler)
        self._server.session = self.session
        self._server.admin_key = self.admin_key
        self._stop = threading.Event()
        self._threads = []
        self._discovery_socket = None

    @property
    def address(self):
        return self._server.server_address

    def start(self):
        server_thread = threading.Thread(target=self._server.serve_forever,
                                         name='fast-lan-server', daemon=True)
        timer_thread = threading.Thread(target=self._timer,
                                        name='fast-lan-timer', daemon=True)
        server_thread.start()
        timer_thread.start()
        self._threads = [server_thread, timer_thread]
        if self.discovery:
            self._start_discovery()
        LOGGER.info('LAN server started on %s:%s', *self.address)
        return self

    def stop(self):
        self._stop.set()
        if self._discovery_socket is not None:
            self._discovery_socket.close()
        self._server.shutdown()
        self._server.server_close()
        for thread in self._threads:
            thread.join(timeout=2)
        LOGGER.info('LAN server stopped')

    def _start_discovery(self):
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('', DISCOVERY_PORT))
            probe.settimeout(0.2)
        except OSError:
            LOGGER.warning('LAN discovery is unavailable', exc_info=True)
            return
        self._discovery_socket = probe
        thread = threading.Thread(target=self._answer_discovery,
                                  name='fast-lan-discovery', daemon=True)
        thread.start()
        self._threads.append(thread)

    def _answer_discovery(self):
        while not self._stop.is_set():
            try:
                data, address = self._discovery_socket.recvfrom(512)
                if data != DISCOVERY_REQUEST:
                    continue
                state = self.session.state()
                if (state['phase'] != 'lobby' or
                        len(state['connected']) >= state['human_slots']):
                    continue
                answer = {
                    'protocol': 'FAST_LAN_V1', 'name': self.room_name,
                    'port': self.address[1], 'phase': state['phase'],
                    'players': len(state['connected']),
                    'capacity': state['human_slots'], 'bots': state['bots'],
                    'instruments': len(state['book']),
                    'case': (state['case_hud']['label']
                             if state.get('case_hud') else 'Случайный'),
                }
                self._discovery_socket.sendto(
                    json.dumps(answer, ensure_ascii=False).encode('utf-8'),
                    address)
            except socket.timeout:
                pass
            except OSError:
                if not self._stop.is_set():
                    LOGGER.warning('LAN discovery response failed', exc_info=True)
                return

    def _timer(self):
        previous = time.monotonic()
        while not self._stop.wait(0.05):
            current = time.monotonic()
            try:
                self.session.tick(current - previous)
            except Exception:
                LOGGER.exception('LAN timer failed')
                return
            previous = current


class LanClient:
    _reconnect_tokens = {}

    def __init__(self, host, port=DEFAULT_PORT, name='Игрок', role='player',
                 key=None, timeout=3, reconnect_token=None):
        self.socket = socket.create_connection((host, port), timeout=timeout)
        self.socket.settimeout(timeout)
        self.file = self.socket.makefile('rwb')
        self._lock = threading.Lock()
        cache_key = (str(host), int(port), str(name))
        token = reconnect_token or self._reconnect_tokens.get(cache_key)
        try:
            welcome = self.request({'type': 'join', 'role': role, 'name': name,
                                    'key': key, 'reconnect_token': token})
        except Exception:
            self.close()
            raise
        self.actor = welcome.get('actor')
        self.reconnect_token = welcome.get('reconnect_token')
        if self.reconnect_token:
            self._reconnect_tokens[cache_key] = self.reconnect_token
        self.state = welcome['state']

    def request(self, value):
        with self._lock:
            self.file.write(json.dumps(value, ensure_ascii=False,
                                       separators=(',', ':')).encode('utf-8') + b'\n')
            self.file.flush()
            data = self.file.readline(MAX_MESSAGE + 1)
        if not data:
            raise ConnectionError('Сервер закрыл соединение')
        if len(data) > MAX_MESSAGE:
            raise ConnectionError('Сервер прислал слишком большой ответ')
        response = json.loads(data.decode('utf-8'))
        if not response.get('ok'):
            raise ValueError(response.get('error', 'Ошибка сервера'))
        if 'state' in response:
            self.state = response['state']
        return response

    def close(self):
        try:
            self.file.close()
        finally:
            self.socket.close()


def local_address():
    """Return the address classmates normally use to reach this computer."""
    candidates = set()
    try:
        candidates.update(item[4][0] for item in socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET))
    except OSError:
        pass
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(('192.0.2.1', 9))
        candidates.add(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()
    usable = [value for value in candidates
              if not ipaddress.ip_address(value).is_loopback]
    if not usable:
        return '127.0.0.1'
    # Most classroom routers use 192.168/16. Prefer it over addresses commonly
    # installed by VPN clients, while keeping all adapters in discovery below.
    return min(usable, key=lambda value: (
        0 if value.startswith('192.168.') else
        1 if value.startswith('10.') else
        2 if ipaddress.ip_address(value).is_private else 3,
        tuple(int(part) for part in value.split('.'))))


def discover_games(timeout=0.5, targets=None):
    """Return joinable FAST rooms which answer a UDP broadcast."""
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError('Время поиска должно быть положительным')
    if targets is None:
        destinations = {'255.255.255.255', '127.0.0.1'}
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(
                socket.gethostname(), None, socket.AF_INET)}
            addresses.add(local_address())
            for address in addresses:
                octets = address.split('.')
                if len(octets) == 4 and address != '127.0.0.1':
                    destinations.add('.'.join(octets[:3] + ['255']))
        except OSError:
            pass
    else:
        destinations = targets
    found = {}
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        probe.bind(('', 0))
        for target in destinations:
            try:
                probe.sendto(DISCOVERY_REQUEST, (target, DISCOVERY_PORT))
            except OSError:
                LOGGER.debug('Discovery request failed for %s', target,
                             exc_info=True)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            probe.settimeout(remaining)
            try:
                data, address = probe.recvfrom(4096)
            except socket.timeout:
                break
            except OSError as error:
                if getattr(error, 'winerror', None) == 10054:
                    LOGGER.debug('A discovery route rejected the UDP probe')
                    continue
                raise
            try:
                room = json.loads(data.decode('utf-8'))
                if (room.get('protocol') != 'FAST_LAN_V1' or
                        room.get('phase') != 'lobby'):
                    continue
                name = room.get('name')
                port = room.get('port')
                players = room.get('players')
                capacity = room.get('capacity')
                bots = room.get('bots')
                instruments = room.get('instruments')
                if (not isinstance(name, str) or not name.strip() or
                        type(port) is not int or not 1 <= port <= 65535 or
                        type(players) is not int or players < 0 or
                        type(capacity) is not int or not 1 <= capacity <= 16 or
                        players > capacity or type(bots) is not int or bots < 0 or
                        type(instruments) is not int or instruments <= 0):
                    continue
                room['name'] = name.strip()[:40]
                room['host'] = address[0]
                room['address'] = f'{address[0]}:{port}'
                found[room['address']] = room
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError,
                    TypeError, ValueError):
                continue
    finally:
        probe.close()
    return sorted(found.values(), key=lambda room: (room['name'],
                                                     room['address']))
