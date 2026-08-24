from __future__ import annotations

from .models import OHLCVBar, SymbolInfo
from .providers.base import MarketData
from .providers.composite import CompositeDataProvider


class DataProvider:
    def __init__(self, history_range: str = "6mo", interval: str = "1d") -> None:
        self.history_range = history_range
        self.interval = interval
        self._composite = CompositeDataProvider()

    def fetch(self, symbol: SymbolInfo) -> MarketData:
        return self._composite.fetch(symbol, self.history_range, self.interval)

    def recent_bars(self, data: MarketData, count: int = 10) -> list[OHLCVBar]:
        tail = data.frame.tail(count)
        bars: list[OHLCVBar] = []
        for index, row in tail.iterrows():
            bars.append(
                OHLCVBar(
                    date=index.strftime("%Y-%m-%d"),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row.get("Volume", 0) or 0),
                )
            )
        return bars
