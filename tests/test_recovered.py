import json
from pathlib import Path
import tempfile
import unittest

from market.config import read_par, parse_offer
from market.calculations import bond_value, settle, future_capital
from market.rng import OriginalRNG
from market.engine import Market
from market.orderbook import OrderError
from market.robots import RobotController
from modules.educational import (
    binomial_option, capm_statistics, macaulay_duration, risk_premium_bound,
)
from market.levels import CUSTOM_LEVELS, CustomLevel, add_level
from main import build_groups, wrapped_index

ROOT = Path(__file__).resolve().parents[1]


class OriginalCases(unittest.TestCase):
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
