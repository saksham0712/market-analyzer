from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

from ..models import SymbolInfo


@dataclass
class ProviderQuote:
    provider: str
    price: float | None
    currency: str | None = None
    volume: float | None = None


@dataclass
class MarketData:
    frame: pd.DataFrame
    currency: str
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None
    regular_market_volume: float | None
    provider: str
    providers_used: list[str] = field(default_factory=list)
    quote_agreement_pct: float | None = None
    fundamentals: dict = field(default_factory=dict)


class MarketDataProvider(Protocol):
    name: str

    def fetch(self, symbol: SymbolInfo, history_range: str, interval: str) -> MarketData | None:
        ...
