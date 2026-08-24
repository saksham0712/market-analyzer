from __future__ import annotations

import unittest

from market_analyzer.beginner_guide import DISCLAIMER, build_beginner_guide
from market_analyzer.models import (
    AnalysisResult,
    Exchange,
    IndicatorSnapshot,
    Signal,
    SignalDetail,
    SymbolInfo,
    TradePlan,
)


def _hold_result(**overrides) -> AnalysisResult:
    defaults = {
        "symbol": SymbolInfo("TATAGOLD", "TATAGOLD.NS", Exchange.NSE, "Tata Gold ETF"),
        "price": 15.61,
        "previous_close": 15.40,
        "day_change_pct": 1.36,
        "volume": 1_200_000,
        "fifty_two_week_high": 17.70,
        "fifty_two_week_low": 9.58,
        "currency": "INR",
        "indicators": IndicatorSnapshot(
            sma_20=14.49,
            sma_50=14.13,
            sma_200=12.50,
            rsi_14=79.0,
            macd=0.15,
            macd_signal=0.20,
            macd_histogram=-0.05,
            avg_volume_20=900_000,
            volume_ratio=1.1,
            pct_from_52w_high=-12.0,
            pct_from_52w_low=63.0,
            return_1m_pct=5.0,
            return_3m_pct=12.0,
        ),
        "signal": Signal.HOLD,
        "raw_signal": Signal.HOLD,
        "confidence": 20,
        "score": 2,
        "conviction_met": True,
        "action_advice": "Wait for dip — do not chase; price is overbought.",
        "trade_plan": TradePlan(
            entry_low=14.35,
            entry_high=14.63,
            stop_loss=13.63,
            target_1=17.70,
            target_2=19.24,
            risk_reward_ratio=2.1,
        ),
        "signal_details": [
            SignalDetail("Trend (SMA20)", 1, 2, "Price 15.61 is above SMA20 14.49"),
            SignalDetail("Momentum (RSI)", -1, 2, "RSI 79.0 is overbought"),
        ],
        "recent_bars": [],
        "summary": "Tata Gold ETF: Wait for dip. Final signal HOLD at 20% confidence. RSI 79.0.",
        "risks": ["RSI is overbought; short-term pullback risk is elevated."],
        "market_insight": {
            "regime": "trending_up",
            "trend_strength": 65,
            "support_level": 14.20,
            "resistance_level": 16.00,
            "atr_pct": 1.8,
            "thesis": "Tata Gold ETF is in an uptrend with 65% trend strength.",
            "provider_summary": "Data sourced from yahoo.",
            "fundamentals": {},
        },
    }
    defaults.update(overrides)
    return AnalysisResult(**defaults)


SECTION_KEYS = (
    "disclaimer",
    "verdict",
    "why_yes",
    "why_no",
    "checklist",
    "signal_explained",
    "key_levels_explained",
    "analysis_in_plain_terms",
    "risks_plain",
    "next_steps",
    "glossary_snippets",
)


class BeginnerGuideTests(unittest.TestCase):
    def test_guide_has_english_and_hinglish(self) -> None:
        guide = build_beginner_guide(_hold_result())
        self.assertIn("english", guide)
        self.assertIn("hinglish", guide)

    def test_hold_verdict_recommends_wait(self) -> None:
        guide = build_beginner_guide(_hold_result())["english"]
        self.assertEqual(guide["verdict"]["recommendation"], "wait")
        self.assertIn("Wait", guide["verdict"]["headline"])
        self.assertIn("Tata Gold ETF", guide["verdict"]["simple_summary"])

    def test_required_sections_present_english(self) -> None:
        guide = build_beginner_guide(_hold_result())["english"]
        for key in SECTION_KEYS:
            self.assertIn(key, guide, f"Missing English section: {key}")

    def test_required_sections_present_hinglish(self) -> None:
        guide = build_beginner_guide(_hold_result())["hinglish"]
        for key in SECTION_KEYS:
            self.assertIn(key, guide, f"Missing Hinglish section: {key}")

    def test_disclaimer_always_included(self) -> None:
        guide = build_beginner_guide(_hold_result())
        self.assertEqual(guide["english"]["disclaimer"], DISCLAIMER)
        self.assertIn("not financial advice", guide["english"]["disclaimer"].lower())
        self.assertIn("learning", guide["hinglish"]["disclaimer"].lower())

    def test_hold_signal_explained_for_beginners(self) -> None:
        guide = build_beginner_guide(_hold_result())["english"]
        explained = guide["signal_explained"]
        self.assertEqual(explained["signal"], "HOLD")
        self.assertIn("sit on your hands", explained["what_it_means"].lower())
        self.assertIn("BUY", explained["buy_sell_hold_plain"])
        self.assertIn("Tata Gold ETF", explained["for_this_symbol"])

    def test_hinglish_verdict_uses_hinglish(self) -> None:
        guide = build_beginner_guide(_hold_result())["hinglish"]
        self.assertIn("Wait", guide["verdict"]["headline"])
        self.assertIn("HOLD", guide["verdict"]["simple_summary"])

    def test_hinglish_signal_explained(self) -> None:
        guide = build_beginner_guide(_hold_result())["hinglish"]
        explained = guide["signal_explained"]
        self.assertEqual(explained["signal"], "HOLD")
        self.assertIn("wait", explained["what_it_means"].lower())

    def test_overbought_checklist_flags_fail(self) -> None:
        guide = build_beginner_guide(_hold_result())["english"]
        rsi_items = [c for c in guide["checklist"] if "RSI" in c["item"]]
        self.assertTrue(rsi_items)
        self.assertEqual(rsi_items[0]["status"], "fail")

    def test_hinglish_overbought_checklist_flags_fail(self) -> None:
        guide = build_beginner_guide(_hold_result())["hinglish"]
        rsi_items = [c for c in guide["checklist"] if "RSI" in c["item"]]
        self.assertTrue(rsi_items)
        self.assertEqual(rsi_items[0]["status"], "fail")

    def test_hold_next_steps_say_do_nothing(self) -> None:
        guide = build_beginner_guide(_hold_result())["english"]
        first_step = guide["next_steps"][0]
        self.assertEqual(first_step["step"], 1)
        self.assertIn("nothing", first_step["action"].lower())

    def test_hinglish_hold_next_steps(self) -> None:
        guide = build_beginner_guide(_hold_result())["hinglish"]
        first_step = guide["next_steps"][0]
        self.assertIn("mat karo", first_step["action"].lower())

    def test_buy_verdict_when_signal_is_buy(self) -> None:
        result = _hold_result(
            signal=Signal.BUY,
            raw_signal=Signal.BUY,
            confidence=70,
            conviction_met=True,
            action_advice="Buy on dips — place limit orders inside the entry zone.",
            indicators=IndicatorSnapshot(
                sma_20=14.0,
                sma_50=13.5,
                sma_200=12.0,
                rsi_14=55.0,
                macd=0.3,
                macd_signal=0.2,
                macd_histogram=0.1,
                avg_volume_20=900_000,
                volume_ratio=1.3,
                pct_from_52w_high=-15.0,
                pct_from_52w_low=30.0,
                return_1m_pct=3.0,
                return_3m_pct=8.0,
            ),
        )
        guide = build_beginner_guide(result)["english"]
        self.assertEqual(guide["verdict"]["recommendation"], "consider_buying")
        self.assertTrue(any("stop-loss" in step["action"].lower() for step in guide["next_steps"]))

    def test_glossary_includes_relevant_terms(self) -> None:
        guide = build_beginner_guide(_hold_result())["english"]
        terms = {entry["term"] for entry in guide["glossary_snippets"]}
        self.assertIn("HOLD", terms)
        self.assertIn("RSI", terms)

    def test_analysis_to_dict_includes_beginner_guide(self) -> None:
        from market_analyzer.report import analysis_to_dict

        payload = analysis_to_dict(_hold_result(beginner_guide=build_beginner_guide(_hold_result())))
        self.assertIn("beginner_guide", payload)
        self.assertEqual(payload["beginner_guide"]["english"]["signal_explained"]["signal"], "HOLD")
        self.assertEqual(payload["beginner_guide"]["hinglish"]["signal_explained"]["signal"], "HOLD")


if __name__ == "__main__":
    unittest.main()
