from __future__ import annotations

from ..models import SymbolInfo
from .alpha_vantage import AlphaVantageProvider
from .base import MarketData, ProviderQuote
from .yahoo import YahooProvider


class CompositeDataProvider:
    def __init__(self) -> None:
        self.providers = [YahooProvider(), AlphaVantageProvider()]

    def fetch(self, symbol: SymbolInfo, history_range: str, interval: str) -> MarketData:
        primary = self.providers[0]
        data = primary.fetch(symbol, history_range=history_range, interval=interval)
        if data is None:
            raise ValueError(
                f"No market data found for {symbol.input_symbol} ({symbol.yahoo_symbol})"
            )

        providers_used = list(data.providers_used)
        quote_agreement = _cross_validate_quotes(symbol, data, self.providers[1:])
        data.providers_used = providers_used
        data.quote_agreement_pct = quote_agreement
        data.provider = "composite" if len(providers_used) > 1 else data.provider
        return data


def _cross_validate_quotes(
    symbol: SymbolInfo,
    primary_data: MarketData,
    secondary_providers,
) -> float | None:
    if primary_data.frame.empty:
        return None

    primary_price = float(primary_data.frame.iloc[-1]["Close"])
    quotes: list[ProviderQuote] = [
        ProviderQuote(provider=primary_data.provider, price=primary_price, currency=primary_data.currency)
    ]

    for provider in secondary_providers:
        if hasattr(provider, "quote"):
            quote = provider.quote(symbol)
            if quote and quote.price:
                quotes.append(quote)
                primary_data.providers_used.append(provider.name)

    if len(quotes) < 2:
        return None

    prices = [quote.price for quote in quotes if quote.price]
    avg_price = sum(prices) / len(prices)
    if avg_price == 0:
        return None
    max_dev = max(abs(price - avg_price) / avg_price for price in prices)
    return round(max(0.0, (1 - max_dev) * 100), 2)
