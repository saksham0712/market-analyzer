from __future__ import annotations

import pandas as pd
import yfinance as yf

from ..models import SymbolInfo
from .base import MarketData, MarketDataProvider


class YahooProvider:
    name = "yahoo"

    def fetch(self, symbol: SymbolInfo, history_range: str, interval: str) -> MarketData | None:
        ticker = yf.Ticker(symbol.yahoo_symbol)
        frame = ticker.history(period=history_range, interval=interval)
        if frame.empty:
            return None

        frame = frame.dropna(subset=["Close"]).copy()
        frame.index = pd.to_datetime(frame.index).tz_localize(None)

        info: dict = {}
        try:
            info = dict(ticker.info or {})
        except Exception:
            info = {}

        try:
            fast = dict(ticker.fast_info or {})
        except Exception:
            fast = {}

        currency = str(info.get("currency") or fast.get("currency") or "USD")
        fifty_two_week_high = _safe_float(
            info.get("fiftyTwoWeekHigh") or fast.get("yearHigh") or fast.get("fiftyTwoWeekHigh")
        )
        fifty_two_week_low = _safe_float(
            info.get("fiftyTwoWeekLow") or fast.get("yearLow") or fast.get("fiftyTwoWeekLow")
        )
        volume = _safe_float(info.get("volume") or fast.get("lastVolume") or fast.get("regularMarketVolume"))

        if fifty_two_week_high is None and not frame.empty:
            fifty_two_week_high = float(frame["High"].max())
        if fifty_two_week_low is None and not frame.empty:
            fifty_two_week_low = float(frame["Low"].min())

        fundamentals = {
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "name": info.get("shortName") or info.get("longName"),
        }

        return MarketData(
            frame=frame,
            currency=currency,
            fifty_two_week_high=fifty_two_week_high,
            fifty_two_week_low=fifty_two_week_low,
            regular_market_volume=volume,
            provider=self.name,
            providers_used=[self.name],
            fundamentals={k: v for k, v in fundamentals.items() if v is not None},
        )


def _safe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
