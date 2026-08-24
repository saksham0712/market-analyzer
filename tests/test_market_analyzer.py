from __future__ import annotations

import unittest

from market_analyzer.indicators import compute_indicators
from market_analyzer.models import Exchange, IndicatorSnapshot, OHLCVBar, Signal
from market_analyzer.signals import SignalEngine
from market_analyzer.symbol_resolver import resolve_user_symbol, SymbolResolutionError
from market_analyzer.strategies import build_market_strategies
from market_analyzer.trade_plan import (
    apply_conviction_filter,
    build_action_advice,
    build_trade_plan,
)


def _sample_indicators(**overrides) -> IndicatorSnapshot:
    defaults = {
        "sma_20": 14.5,
        "sma_50": 14.0,
        "sma_200": None,
        "rsi_14": 55.0,
        "macd": 0.3,
        "macd_signal": 0.2,
        "macd_histogram": 0.1,
        "avg_volume_20": 1000.0,
        "volume_ratio": 1.2,
        "pct_from_52w_high": -12.0,
        "pct_from_52w_low": 30.0,
        "return_1m_pct": 5.0,
        "return_3m_pct": 8.0,
    }
    defaults.update(overrides)
    return IndicatorSnapshot(**defaults)


def _sample_bars(price: float = 15.0) -> list[OHLCVBar]:
    return [
        OHLCVBar(
            date=f"2026-08-{10 + index:02d}",
            open=price - 0.2,
            high=price + 0.3,
            low=price - 0.4,
            close=price,
            volume=1_000_000,
        )
        for index in range(5)
    ]


class SymbolTests(unittest.TestCase):
    def test_nse_symbol(self) -> None:
        info, _ = resolve_user_symbol("tatagold", exchange="NSE", market_type="etf")
        self.assertEqual(info.yahoo_symbol, "TATAGOLD.NS")
        self.assertEqual(info.exchange.value, "NSE")

    def test_nifty_index(self) -> None:
        info, _ = resolve_user_symbol("NIFTY", market_type="index")
        self.assertEqual(info.yahoo_symbol, "^NSEI")
        self.assertEqual(info.exchange.value, "INDEX")

    def test_resolve_uti_gold_by_name(self) -> None:
        info, resolved_from = resolve_user_symbol(
            "UTI Gold Exchange Traded Fund",
            market_type="etf",
        )
        self.assertEqual(info.input_symbol, "GOLDBETA")
        self.assertEqual(resolved_from, "UTI Gold Exchange Traded Fund")

    def test_resolve_us_stock_by_name(self) -> None:
        info, _ = resolve_user_symbol("Apple", market_type="us_stock")
        self.assertEqual(info.input_symbol, "AAPL")
        self.assertEqual(info.exchange.value, "US")


class SignalEngineTests(unittest.TestCase):
    def test_strong_buy_on_bullish_setup(self) -> None:
        engine = SignalEngine()
        indicators = IndicatorSnapshot(
            sma_20=90,
            sma_50=85,
            sma_200=70,
            rsi_14=55,
            macd=1.2,
            macd_signal=0.8,
            macd_histogram=0.4,
            avg_volume_20=1000,
            volume_ratio=1.8,
            pct_from_52w_high=-12,
            pct_from_52w_low=25,
            return_1m_pct=4,
            return_3m_pct=8,
        )
        signal, confidence, score, details = engine.generate(100, indicators)
        self.assertIn(signal, {Signal.BUY, Signal.STRONG_BUY})
        self.assertGreater(confidence, 0)
        self.assertTrue(details)

    def test_sell_on_bearish_setup(self) -> None:
        engine = SignalEngine()
        indicators = IndicatorSnapshot(
            sma_20=110,
            sma_50=120,
            sma_200=130,
            rsi_14=78,
            macd=-1.0,
            macd_signal=-0.5,
            macd_histogram=-0.5,
            avg_volume_20=1000,
            volume_ratio=0.6,
            pct_from_52w_high=-1,
            pct_from_52w_low=60,
            return_1m_pct=12,
            return_3m_pct=20,
        )
        signal, _, _, _ = engine.generate(100, indicators)
        self.assertIn(signal, {Signal.SELL, Signal.STRONG_SELL, Signal.HOLD})


class IndicatorTests(unittest.TestCase):
    def test_compute_indicators_on_sample_frame(self) -> None:
        import pandas as pd

        from market_analyzer.providers.base import MarketData

        dates = pd.date_range("2025-01-01", periods=120, freq="B")
        closes = pd.Series(range(100, 220), index=dates, dtype=float)
        frame = pd.DataFrame(
            {
                "Open": closes - 1,
                "High": closes + 1,
                "Low": closes - 2,
                "Close": closes,
                "Volume": 1000,
            },
            index=dates,
        )
        data = MarketData(
            frame=frame,
            currency="INR",
            fifty_two_week_high=float(closes.max()),
            fifty_two_week_low=float(closes.min()),
            regular_market_volume=1000,
            provider="test",
        )
        snapshot, enriched, advanced = compute_indicators(data)
        self.assertIsNotNone(snapshot.sma_20)
        self.assertIsNotNone(snapshot.rsi_14)
        self.assertIn("RSI_14", enriched.columns)
        self.assertIsNotNone(advanced.market_regime)


class TradePlanTests(unittest.TestCase):
    def test_build_trade_plan_for_overbought_bullish_setup(self) -> None:
        indicators = _sample_indicators(rsi_14=79.0, sma_20=14.49, sma_50=14.13)
        plan = build_trade_plan(
            price=15.61,
            indicators=indicators,
            signal=Signal.HOLD,
            raw_signal=Signal.HOLD,
            fifty_two_week_high=17.70,
            fifty_two_week_low=9.58,
            recent_bars=_sample_bars(15.61),
        )

        self.assertIsNotNone(plan.entry_low)
        self.assertIsNotNone(plan.entry_high)
        self.assertLess(plan.entry_high, 15.61)
        self.assertIsNotNone(plan.stop_loss)
        self.assertLess(plan.stop_loss, plan.entry_low)
        self.assertEqual(plan.target_1, 17.70)
        self.assertGreater(plan.target_2, plan.target_1)
        self.assertIsNotNone(plan.risk_reward_ratio)

    def test_build_trade_plan_for_bearish_setup(self) -> None:
        indicators = _sample_indicators(rsi_14=78.0, sma_20=110.0, sma_50=120.0)
        plan = build_trade_plan(
            price=100.0,
            indicators=indicators,
            signal=Signal.SELL,
            raw_signal=Signal.SELL,
            fifty_two_week_high=130.0,
            fifty_two_week_low=80.0,
            recent_bars=_sample_bars(100.0),
        )

        self.assertGreater(plan.entry_low, 100.0)
        self.assertGreater(plan.stop_loss, plan.entry_high)
        self.assertLess(plan.target_1, 100.0)


class ConvictionFilterTests(unittest.TestCase):
    def test_downgrades_low_confidence_buy_to_hold(self) -> None:
        signal, conviction_met = apply_conviction_filter(Signal.BUY, confidence=35, min_confidence=50)
        self.assertEqual(signal, Signal.HOLD)
        self.assertFalse(conviction_met)

    def test_keeps_high_confidence_buy(self) -> None:
        signal, conviction_met = apply_conviction_filter(Signal.BUY, confidence=65, min_confidence=50)
        self.assertEqual(signal, Signal.BUY)
        self.assertTrue(conviction_met)

    def test_hold_is_not_filtered(self) -> None:
        signal, conviction_met = apply_conviction_filter(Signal.HOLD, confidence=10, min_confidence=50)
        self.assertEqual(signal, Signal.HOLD)
        self.assertTrue(conviction_met)


class ActionAdviceTests(unittest.TestCase):
    def test_overbought_hold_advice(self) -> None:
        advice = build_action_advice(
            signal=Signal.HOLD,
            raw_signal=Signal.HOLD,
            confidence=20,
            conviction_met=True,
            indicators=_sample_indicators(rsi_14=79.0),
        )
        self.assertIn("Wait for dip", advice)

    def test_downgraded_buy_advice(self) -> None:
        advice = build_action_advice(
            signal=Signal.HOLD,
            raw_signal=Signal.BUY,
            confidence=35,
            conviction_met=False,
            indicators=_sample_indicators(rsi_14=79.0),
        )
        self.assertIn("conviction is below threshold", advice)

    def test_high_conviction_buy_advice(self) -> None:
        advice = build_action_advice(
            signal=Signal.BUY,
            raw_signal=Signal.BUY,
            confidence=70,
            conviction_met=True,
            indicators=_sample_indicators(rsi_14=52.0),
        )
        self.assertIn("Buy on dips", advice)


class AnalysisResultIntegrationTests(unittest.TestCase):
    def test_analyzer_returns_actionable_fields(self) -> None:
        from market_analyzer.analyzer import MarketAnalyzer

        analyzer = MarketAnalyzer(history_range="6mo")
        try:
            result = analyzer.analyze("TATAGOLD", market_type="etf")
        except Exception as exc:
            self.skipTest(f"Live data unavailable: {exc}")

        self.assertIsNotNone(result.action_advice)
        self.assertIsNotNone(result.trade_plan.entry_low)
        self.assertIsNotNone(result.trade_plan.stop_loss)
        self.assertIsNotNone(result.trade_plan.target_1)
        self.assertIsNotNone(result.market_insight)
        self.assertIsNotNone(result.data_providers)
        self.assertIn(result.signal.value, {item.value for item in Signal})
        self.assertIn(result.raw_signal.value, {item.value for item in Signal})
        self.assertIsInstance(result.conviction_met, bool)


class StrategyTests(unittest.TestCase):
    def test_index_neutral_strategy(self) -> None:
        from market_analyzer.models import AnalysisResult, SymbolInfo, TradePlan

        result = AnalysisResult(
            symbol=SymbolInfo("NIFTY", "^NSEI", Exchange.INDEX, "Nifty 50"),
            price=24000,
            previous_close=23900,
            day_change_pct=0.4,
            volume=1_000_000,
            fifty_two_week_high=25000,
            fifty_two_week_low=21000,
            currency="INR",
            indicators=IndicatorSnapshot(
                sma_20=23800,
                sma_50=23500,
                sma_200=22000,
                rsi_14=52,
                macd=10,
                macd_signal=8,
                macd_histogram=2,
                avg_volume_20=900_000,
                volume_ratio=1.1,
                pct_from_52w_high=-4,
                pct_from_52w_low=14,
                return_1m_pct=2,
                return_3m_pct=5,
            ),
            signal=Signal.HOLD,
            raw_signal=Signal.HOLD,
            confidence=45,
            score=5,
            conviction_met=True,
            action_advice="Stay on sidelines",
            trade_plan=TradePlan(23800, 24100, 23000, 25000, 25500, 1.5),
            signal_details=[],
            recent_bars=[],
            summary="test",
            risks=["No major flags"],
        )
        strategies = build_market_strategies(result)
        ids = {s["id"] for s in strategies}
        self.assertIn("index_neutral", ids)


class BeginnerGuideTests(unittest.TestCase):
    def test_beginner_guide_has_required_sections(self) -> None:
        from market_analyzer.beginner_guide import build_beginner_guide
        from market_analyzer.models import AnalysisResult, SymbolInfo, TradePlan

        result = AnalysisResult(
            symbol=SymbolInfo("TATAGOLD", "TATAGOLD.NS", Exchange.NSE, "Tata Gold ETF"),
            price=15.6,
            previous_close=15.4,
            day_change_pct=1.3,
            volume=1_000_000,
            fifty_two_week_high=17.7,
            fifty_two_week_low=9.5,
            currency="INR",
            indicators=_sample_indicators(rsi_14=79.0),
            signal=Signal.HOLD,
            raw_signal=Signal.HOLD,
            confidence=46,
            score=0,
            conviction_met=True,
            action_advice="Wait for dip",
            trade_plan=TradePlan(14.3, 14.6, 13.7, 17.7, 19.0, 4.0),
            signal_details=[],
            recent_bars=_sample_bars(15.6),
            summary="test",
            risks=["RSI overbought"],
        )
        guide = build_beginner_guide(result)
        self.assertIn("english", guide)
        self.assertIn("hinglish", guide)
        for lang in ("english", "hinglish"):
            self.assertIn("verdict", guide[lang])
            self.assertIn("checklist", guide[lang])
            self.assertIn("signal_explained", guide[lang])
        self.assertEqual(guide["english"]["verdict"]["recommendation"], "wait")
        self.assertTrue(guide["english"]["verdict"]["headline"])
        self.assertTrue(guide["hinglish"]["verdict"]["headline"])


if __name__ == "__main__":
    unittest.main()
