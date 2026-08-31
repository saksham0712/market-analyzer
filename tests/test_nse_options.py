"""Tests for NSE option chain parsing."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from market_analyzer.nse_options import (
    DEFAULT_STARTING_CASH,
    NIFTY_LOT_SIZE,
    _parse_nse_payload,
    fetch_nifty_option_chain,
    fetch_option_ltp,
)


SAMPLE_PAYLOAD = {
    "records": {
        "underlyingValue": 24300.5,
        "timestamp": "31-Aug-2026 10:00:00",
        "expiryDates": ["02-Sep-2026", "09-Sep-2026"],
        "data": [
            {
                "expiryDate": "02-Sep-2026",
                "strikePrice": 24200,
                "CE": {"lastPrice": 180.5, "change": 5.0, "openInterest": 1000, "totalTradedVolume": 200},
                "PE": {"lastPrice": 95.25, "change": -2.0, "openInterest": 800, "totalTradedVolume": 150},
            },
            {
                "expiryDate": "02-Sep-2026",
                "strikePrice": 24300,
                "CE": {"lastPrice": 120.0, "change": 3.0, "openInterest": 1200, "totalTradedVolume": 300},
                "PE": {"lastPrice": 115.0, "change": 1.0, "openInterest": 900, "totalTradedVolume": 180},
            },
            {
                "expiryDate": "09-Sep-2026",
                "strikePrice": 24300,
                "CE": {"lastPrice": 200.0, "change": 0.0, "openInterest": 500, "totalTradedVolume": 50},
                "PE": {"lastPrice": 180.0, "change": 0.0, "openInterest": 400, "totalTradedVolume": 40},
            },
        ],
    }
}


class NseOptionsTests(unittest.TestCase):
    def test_constants(self) -> None:
        self.assertEqual(NIFTY_LOT_SIZE, 50)
        self.assertEqual(DEFAULT_STARTING_CASH, 100_000.0)

    def test_parse_nse_payload_default_expiry(self) -> None:
        result = _parse_nse_payload(SAMPLE_PAYLOAD, "NIFTY", "02-Sep-2026", ["02-Sep-2026", "09-Sep-2026"])
        self.assertEqual(result["symbol"], "NIFTY")
        self.assertEqual(result["spot"], 24300.5)
        self.assertEqual(result["expiry"], "02-Sep-2026")
        self.assertEqual(len(result["expiries"]), 2)
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["rows"][0]["strike"], 24200)
        self.assertEqual(result["rows"][0]["ce"]["ltp"], 180.5)

    def test_parse_nse_payload_selected_expiry(self) -> None:
        result = _parse_nse_payload(SAMPLE_PAYLOAD, "NIFTY", "09-Sep-2026", ["02-Sep-2026", "09-Sep-2026"])
        self.assertEqual(result["expiry"], "09-Sep-2026")
        self.assertEqual(len(result["rows"]), 1)

    def test_fetch_uses_cache(self) -> None:
        with patch("market_analyzer.nse_options._fetch_expiries", return_value=["02-Sep-2026"]), patch(
            "market_analyzer.nse_options._fetch_chain_payload", return_value=SAMPLE_PAYLOAD
        ), patch("market_analyzer.nse_options._warmup_session"), patch(
            "market_analyzer.nse_options._build_opener", return_value=MagicMock()
        ) as mock_fetch:
            first = fetch_nifty_option_chain(use_cache=True)
            second = fetch_nifty_option_chain(use_cache=True)
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(first["source"], "nse")

    def test_fetch_option_ltp_live(self) -> None:
        with patch("market_analyzer.nse_options._fetch_expiries", return_value=["02-Sep-2026"]), patch(
            "market_analyzer.nse_options._fetch_chain_payload", return_value=SAMPLE_PAYLOAD
        ), patch("market_analyzer.nse_options._warmup_session"), patch(
            "market_analyzer.nse_options._build_opener", return_value=MagicMock()
        ):
            quote = fetch_option_ltp("02-Sep-2026", 24300, "CE")
        self.assertEqual(quote["ltp"], 120.0)
        self.assertEqual(quote["type"], "CE")
        self.assertTrue(quote["live"])

    def test_fetch_option_ltp_raises_without_demo(self) -> None:
        with patch("market_analyzer.nse_options._fetch_expiries", side_effect=URLError("blocked")), patch(
            "market_analyzer.nse_options._warmup_session"
        ), patch("market_analyzer.nse_options._build_opener", return_value=MagicMock()):
            with self.assertRaises(ValueError):
                fetch_option_ltp("02-Sep-2026", 24300, "CE")


if __name__ == "__main__":
    unittest.main()
