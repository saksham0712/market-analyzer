from __future__ import annotations

import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from ..models import SymbolInfo
from .base import MarketData, ProviderQuote


class AlphaVantageProvider:
    name = "alpha_vantage"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ALPHA_VANTAGE_API_KEY")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def fetch(self, symbol: SymbolInfo, history_range: str, interval: str) -> MarketData | None:
        if not self.enabled:
            return None

        av_symbol = _to_alpha_vantage_symbol(symbol)
        if not av_symbol:
            return None

        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": av_symbol,
            "outputsize": "compact" if history_range in {"1mo", "3mo"} else "full",
            "apikey": self.api_key,
        }
        payload = _get_json("https://www.alphavantage.co/query", params)
        series = payload.get("Time Series (Daily)")
        if not series:
            return None

        rows = []
        for date_str, values in series.items():
            rows.append(
                {
                    "Date": pd.to_datetime(date_str),
                    "Open": float(values["1. open"]),
                    "High": float(values["2. high"]),
                    "Low": float(values["3. low"]),
                    "Close": float(values["4. close"]),
                    "Volume": float(values["6. volume"]),
                }
            )

        frame = pd.DataFrame(rows).sort_values("Date").set_index("Date")
        if frame.empty:
            return None

        return MarketData(
            frame=frame,
            currency="USD",
            fifty_two_week_high=float(frame["High"].tail(252).max()),
            fifty_two_week_low=float(frame["Low"].tail(252).min()),
            regular_market_volume=float(frame["Volume"].iloc[-1]),
            provider=self.name,
            providers_used=[self.name],
        )

    def quote(self, symbol: SymbolInfo) -> ProviderQuote | None:
        if not self.enabled:
            return None
        av_symbol = _to_alpha_vantage_symbol(symbol)
        if not av_symbol:
            return None

        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": av_symbol,
            "apikey": self.api_key,
        }
        payload = _get_json("https://www.alphavantage.co/query", params)
        quote = payload.get("Global Quote") or {}
        price = quote.get("05. price")
        if not price:
            return None
        return ProviderQuote(provider=self.name, price=float(price), currency="USD")


def _to_alpha_vantage_symbol(symbol: SymbolInfo) -> str | None:
    if symbol.exchange.value == "US":
        return symbol.yahoo_symbol
    if symbol.exchange.value == "INDEX" and symbol.yahoo_symbol.startswith("^"):
        return symbol.yahoo_symbol
    return None


def _get_json(url: str, params: dict) -> dict:
    request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "market-analyzer/0.2"})
    with urlopen(request, timeout=20) as response:
        import json

        return json.loads(response.read().decode())
