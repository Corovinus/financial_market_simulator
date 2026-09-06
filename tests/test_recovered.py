import json
from pathlib import Path
import tempfile
import unittest

from market.config import Goal, Scenario, read_par, parse_offer
from market.goals import evaluate_goals
from market.calculations import bond_value, settle, future_capital
from market.rng import OriginalRNG
from market.engine import Market
from market.orderbook import OrderError
from market.report import build_report, export_report
from market.robots import RobotController
from modules.educational import (
    binomial_option, capm_statistics, information_expected_value,
    macaulay_duration, risk_premium_bound,
)
from modules.document import (
    DocumentLine, Fraction, document_lines, is_formula, line_text,
    page_scroll, pretty_formula, table_of_contents,
)
from market.levels import CUSTOM_LEVELS, CustomLevel, add_level, load_levels
from main import build_groups, wrapped_index

ROOT = Path(__file__).resolve().parents[1]


class OriginalCases(unittest.TestCase):
    def test_scenario_and_external_level_validation(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        with self.assertRaises(ValueError):
            Scenario(**{**scenario.__dict__, 'names': (object(),)})
        with self.assertRaises(ValueError):
            Scenario(**{**scenario.__dict__,
                        'score_parameters': (100, 0, 100, 6)})
        for field, value in (('robot_style', 'unknown'),
                             ('robot_value_spread', .6),
                             ('robot_max_quantity', 100)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                Scenario(**{**scenario.__dict__, field: value})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'levels.json'
            payload = {'name': 'Внешний уровень',
                       'scenario': {**scenario.__dict__}}
            path.write_text(json.dumps([payload], ensure_ascii=False),
                            encoding='utf-8')
            loaded = load_levels(path)
            self.assertEqual(loaded[0].name, 'Внешний уровень')
            self.assertEqual(loaded[0].scenario, scenario)

    def test_visual_page_scroll_does_not_skip_variable_rows(self):
        lines = [DocumentLine('text', str(index)) for index in range(4)]
        lines.insert(2, DocumentLine('formula', 'x', (Fraction('1', '2'),)))
        next_page = page_scroll(lines, 0, 1, 60)
        self.assertEqual(next_page, 2)
        self.assertEqual(page_scroll(lines, next_page, -1, 60), 0)

    def test_manual_contents_and_formula_formatting(self):
        sections = json.loads(
            (ROOT / 'data/converted/manual_sections.json').read_text(
                encoding='utf-8'))
        contents = table_of_contents(sections['Оглавление'], sections)
        self.assertEqual(len(contents), 22)
        self.assertEqual(contents[0], 'Программа F A S T')
        self.assertEqual(contents[-1],
                         'Описание RE3.Роль производных бумаг - опционов')
        formula = pretty_formula('u = exp(2.40/sqrt(12)); sigma^2 * Delta t')
        self.assertEqual(formula, 'u = exp(2.40/√(12)); σ² · Δt')
        self.assertTrue(is_formula(formula))
        self.assertTrue(is_formula('Стоимость = Цена · Количество'))
        self.assertFalse(is_formula('Time = 0'))
        self.assertNotIn('│', ''.join(map(line_text,
                                         document_lines('│ текст │'))))
        table = document_lines('┌───┬───┐\n│ A │ B │\n└───┴───┘')
        self.assertEqual([line.kind for line in table], ['table'])
        unboxed = document_lines('Деньги    Очки    Приращение\n0         0       0')
        self.assertEqual([line.kind for line in unboxed],
                         ['table_header', 'table'])

        formulas = [line for text in sections.values()
                    for line in document_lines(text)
                    if line.kind == 'formula']
        self.assertTrue(any(any(isinstance(part, Fraction)
                                 for part in line.parts)
                            for line in formulas))
        for line in formulas:
            for part in line.parts:
                if isinstance(part, Fraction):
                    self.assertNotIn('/', part.numerator)
                    self.assertNotIn('/', part.denominator)
                else:
                    self.assertNotIn('/', part)

    def test_dos_no_trade_results(self):
        for filename in ('b01_no_trades.json', 'b02_no_trades.json'):
            with self.subTest(case=filename):
                case = json.loads((ROOT / 'tests/reference_cases' / filename).read_text())
                scenario = read_par(ROOT / 'data/original' / case['scenario'])
                cash = scenario.cash
                for period, expected in enumerate(case['derived_from_manual']['cash_after_period']):
                    cash = settle(scenario, cash, scenario.positions, period)
                    self.assertAlmostEqual(cash, expected)
                self.assertEqual(f'{cash:.0f}', case['observed']['final_capital_display'])
                self.assertAlmostEqual(future_capital(scenario, scenario.cash, scenario.positions), cash)

    def test_f9_observation(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        self.assertEqual([f'{bond_value(scenario, i):.3f}' for i in range(2)], ['90.240', '51.200'])

    def test_original_configuration_and_short_positions(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        self.assertEqual((scenario.robots, scenario.wolves, scenario.duration_ticks, scenario.reaction_ticks), (10, 3, 1200, 60))
        self.assertEqual(scenario.score_parameters, (0, 0, 10000, 6))
        self.assertTrue(scenario.queue)
        self.assertEqual(settle(scenario, -1000, (-15, 0), 0), -1550)

    def test_offer_is_not_decimal(self):
        self.assertEqual(parse_offer('20.50'), (20, 50))
        for value in ('20', '20.0', '0.50', '20.5.0', '-20.50', 'nan.1'):
            with self.assertRaises(ValueError):
                parse_offer(value)

    def test_reject_unknown_par(self):
        with self.assertRaises(ValueError):
            read_par(ROOT / 'data/original/B03.PAR')
        original = (ROOT / 'data/original/B01.PAR').read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bad.par'
            for data in (original + b'\r\nUnexpected 1', original[:70], original.replace(b'1000', b'nan ')):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    read_par(path)

    def test_rng_known_transition_and_no_draw_branch(self):
        rng = OriginalRNG(0)
        self.assertEqual(rng.random(), 1 / 2**32)
        self.assertEqual(rng.random(), 0x08088406 / 2**32)
        state = rng.state
        self.assertEqual(rng.interval(10, 5), 10)
        self.assertEqual(rng.state, state)
        rng = OriginalRNG(0)
        self.assertEqual(rng.randbelow(10), 0)
        self.assertEqual(rng.state, 1)
        self.assertEqual(rng.interval_int(5, 5), 5)
        self.assertEqual(rng.state, 1)
        with self.assertRaises(ValueError):
            OriginalRNG(-1)

    def test_bidask_book_has_no_crossing_and_lifo_queue(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        market = Market(scenario)
        market.start_period(0)
        market.submit(0, 0, 'bid', 100, 2)
        market.submit(1, 0, 'ask', 101, 2)
        # Crossing is not an automatic match in the original.
        self.assertEqual(market.portfolios[0].positions[0], 15)
        self.assertEqual(market.portfolios[1].positions[0], 15)
        with self.assertRaises(OrderError):
            market.submit(2, 0, 'bid', 100, 1)
        market.submit(2, 0, 'bid', 110, 1)
        market.submit(3, 0, 'bid', 120, 1)
        self.assertEqual([q.price for q in market.quotes(0, 'bid')], [120, 110, 100])
        trade = market.take(4, 0, 'sell', 1)
        self.assertEqual((trade.price, trade.buyer, trade.seller), (120, 3, 4))
        self.assertEqual(market.quotes(0, 'bid')[0].price, 110)
        self.assertEqual(market.portfolios[3].positions[0], 16)
        self.assertEqual(market.portfolios[4].positions[0], 14)
        # B is only a buy action against an ask; self-trade is rejected.
        with self.assertRaises(OrderError):
            market.take(1, 0, 'buy', 1)

    def test_replay_captures_each_accepted_market_action(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        market = Market(scenario)
        market.start_period(0)
        self.assertEqual(market.replay_frames[-1]['kind'], 'start_period')
        market.submit(0, 0, 'bid', 100, 2)
        bid_frame = market.replay_frames[-1]
        self.assertEqual((bid_frame['kind'], bid_frame['actor']), ('bid', 0))
        self.assertEqual(bid_frame['book'][0][0], (0, 100, 2))
        before_rejected = len(market.replay_frames)
        with self.assertRaises(OrderError):
            market.submit(1, 0, 'bid', 90, 1)
        self.assertEqual(len(market.replay_frames), before_rejected)
        market.take(1, 0, 'sell', 1)
        trade_frame = market.replay_frames[-1]
        self.assertEqual((trade_frame['kind'], trade_frame['price'],
                          trade_frame['quantity']), ('sell', 100, 1))
        self.assertEqual(trade_frame['book'][0][0], (0, 100, 1))
        self.assertEqual(trade_frame['portfolios'][0][1][0], 16)
        self.assertEqual(trade_frame['portfolios'][1][1][0], 14)
        # Earlier frames are snapshots and do not change with the live market.
        self.assertEqual(bid_frame['book'][0][0], (0, 100, 2))

    def test_final_report_attributes_trade_result_and_exports(self):
        scenario = Scenario(
            periods=1, duration_ticks=10, rates=(10,), names=('Бумага',),
            payments=((150,),), cash=1000, positions=(0,),
            score_parameters=(0, 0, 2000, 10), queue=True, robots=1,
            wolves=0, reaction_ticks=10, strategy=0, hints=True)
        market = Market(scenario)
        market.start_period(0)
        market.submit(0, 0, 'bid', 100, 1)
        market.take(1, 0, 'sell', 1)
        market.finish_period()
        buyer = build_report(scenario, market.replay_frames, 0,
                             {'0': 'Покупатель', '1': 'Продавец'})
        seller = build_report(scenario, market.replay_frames, 1,
                              {'0': 'Покупатель', '1': 'Продавец'})
        self.assertEqual((buyer['initial_capital'], buyer['final_capital']),
                         (1100, 1140))
        self.assertAlmostEqual(buyer['change'], 40)
        self.assertAlmostEqual(buyer['realized'], 40)
        self.assertAlmostEqual(seller['realized'], -40)
        self.assertEqual((buyer['rank'], seller['rank']), (1, 2))
        self.assertEqual((buyer['trade_count'], buyer['average_buy']), (1, 100))
        with tempfile.TemporaryDirectory() as folder:
            csv_path, html_path = export_report(buyer, folder)
            self.assertIn('Покупатель', csv_path.read_text(encoding='utf-8-sig'))
            self.assertIn('<svg', html_path.read_text(encoding='utf-8'))

    def test_trading_goals_validate_and_track_final_progress(self):
        goals = (
            Goal('capital', 1140), Goal('profit', 40), Goal('trades', 1),
            Goal('position', 1, instrument=0, maximum=1),
        )
        scenario = Scenario(
            periods=1, duration_ticks=10, rates=(10,), names=('Бумага',),
            payments=((150,),), cash=1000, positions=(0,),
            score_parameters=(0, 0, 2000, 10), queue=True, robots=1,
            wolves=0, reaction_ticks=10, strategy=0, hints=True,
            goals=goals)
        market = Market(scenario)
        market.start_period(0)
        market.submit(0, 0, 'bid', 100, 1)
        market.take(1, 0, 'sell', 1)
        live = evaluate_goals(scenario, market.replay_frames, 0)
        self.assertFalse(live['finished'])
        self.assertTrue(live['all_passed'])
        market.finish_period()
        final = evaluate_goals(scenario, market.replay_frames, 0)
        self.assertTrue(final['finished'])
        self.assertTrue(final['all_passed'])
        self.assertEqual([item['passed'] for item in final['items']],
                         [True, True, True, True])
        with self.assertRaises(ValueError):
            Scenario(**{**scenario.__dict__,
                        'goals': (Goal('position', 1, instrument=4),)})
        from_mapping = Scenario(**{
            **scenario.__dict__,
            'goals': ({'kind': 'trades', 'target': 2,
                       'title': 'Две сделки'},),
        })
        self.assertEqual(from_mapping.goals,
                         (Goal('trades', 2, title='Две сделки'),))

    def test_book_without_ranked_queue_drops_superseded_quote(self):
        from market.orderbook import OrderBook
        book = OrderBook(1, ranked_queue=False)
        book.submit(1, 0, 'bid', 100, 1)
        book.submit(2, 0, 'bid', 110, 1)
        self.assertEqual([q.price for q in book.quotes(0, 'bid')], [110])
        book.take(3, 0, 'sell', 1)
        self.assertIsNone(book.best(0, 'bid'))

    def test_original_robots_react_and_trade(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        market = Market(scenario)
        market.start_period(0)
        robots = RobotController(market, seed=0)
        fair = [bond_value(scenario, instrument, 0)
                for instrument in range(len(scenario.names))]
        self.assertEqual(robots.values[0], tuple(fair))
        self.assertTrue(all(0.8 * expected <= actual <= 1.2 * expected
                            for actual, expected in zip(robots.values[-1], fair)))
        self.assertEqual(robots.step(scenario.reaction_ticks), ())
        events = robots.step(0.001)
        self.assertTrue(events)
        self.assertTrue(any(market.book.best(instrument, side) is not None
                            for instrument in range(len(scenario.names))
                            for side in ('bid', 'ask')))
        for _ in range(30):
            events += robots.step(scenario.reaction_ticks)
        self.assertTrue(any(event.action in ('buy', 'sell') for event in events))
        self.assertTrue(any(market.history_for(instrument, side)
                            for instrument in range(len(scenario.names))
                            for side in ('bid', 'ask')))

    def test_configurable_robot_style_and_order_size(self):
        base = Scenario(
            periods=1, duration_ticks=100, rates=(10,), names=('Bond',),
            payments=((110,),), cash=1000, positions=(10,),
            score_parameters=(0, 0, 2000, 6), queue=True, robots=1,
            wolves=1, reaction_ticks=10, strategy=1, hints=True,
            robot_style='aggressive', robot_value_spread=.1,
            robot_max_quantity=3)
        market = Market(base)
        market.start_period()
        market.submit(0, 0, 'ask', 100, 10)
        controller = RobotController(market, seed=0)
        event = controller._act(1, (100.0,))
        self.assertEqual(event.action, 'buy')
        self.assertLessEqual(event.quantity, 3)
        self.assertEqual(controller._quote_bounds('bid', 100, None, None),
                         (90, 103))
        self.assertEqual(controller._quote_bounds('ask', 100, None, None),
                         (97, 110))

    def test_settlement_preserves_word_products_and_positions(self):
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        market = Market(scenario)
        market.portfolios[0].positions[0] = 2000
        market.portfolios[0].positions[1] = -2000
        market.start_period(0)
        market.finish_period()
        # 2000*20 is truncated to a signed 16-bit product (40000 -> -25536).
        # Cash itself is not a word and remains a Real value.
        self.assertEqual(market.portfolios[0].cash, -24286.0)

    def test_teaching_calculations(self):
        value, duration = macaulay_duration((100, 1100), 10)
        self.assertAlmostEqual(value, 1000)
        self.assertAlmostEqual(duration, 1.9090909)
        self.assertAlmostEqual(binomial_option(20, 25, 12, 240, 1), 16.4406396)
        stats = capm_statistics(((.10, .06), (.02, .04)), risk_free=.01)
        self.assertEqual(len(stats['beta']), 2)
        self.assertEqual(risk_premium_bound(1000, True, 4), 1254)
        self.assertEqual(risk_premium_bound(1000, False, 4), 381)
        self.assertEqual(information_expected_value(((1, 3), (5, 7)),
                                                    (2, 2)), 4)
        with self.assertRaises(ValueError):
            binomial_option(20, 25, 1000, 1, 1)
        with self.assertRaises(ValueError):
            capm_statistics(((.1,), (.2,)), probabilities=(float('nan'),
                                                               float('nan')))

    def test_custom_level_is_exposed_in_menu_registry(self):
        before = len(CUSTOM_LEVELS)
        scenario = read_par(ROOT / 'data/original/B01.PAR')
        level = add_level('Тестовый уровень', scenario)
        try:
            self.assertIsInstance(level, CustomLevel)
            custom_group = next(items for name, items in build_groups()
                                if name == 'Свои уровни')
            self.assertIn(('Тестовый уровень', ''), custom_group)
        finally:
            del CUSTOM_LEVELS[before:]

    def test_menu_navigation_handles_empty_sections(self):
        self.assertEqual(wrapped_index(0, 1, 0), 0)
        index = 0
        for _ in range(1000):
            index = wrapped_index(index, 1, 8)
        self.assertEqual(index, 0)
        self.assertEqual(wrapped_index(0, -1, 8), 7)


if __name__ == '__main__':
    unittest.main()
