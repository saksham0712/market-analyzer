from __future__ import annotations

import re

from .models import Exchange, SymbolInfo
from .symbol_catalog import CatalogEntry, _yahoo_for, resolve_from_catalog, search_catalog
from .symbols import normalize_symbol


class SymbolResolutionError(ValueError):
    def __init__(self, message: str, suggestions: list[dict] | None = None) -> None:
        super().__init__(message)
        self.suggestions = suggestions or []


MARKET_TYPE_EXCHANGE = {
    "index": "INDEX",
    "nse_stock": "NSE",
    "bse_stock": "BSE",
    "etf": "NSE",
    "us_stock": "US",
    "us_etf": "US",
    "us_index": "INDEX",
    "global_index": "INDEX",
}


def looks_like_ticker(raw: str) -> bool:
    cleaned = raw.strip().upper()
    if not cleaned:
        return False
    if cleaned.startswith("^"):
        return True
    if cleaned.endswith(".NS") or cleaned.endswith(".BO") or cleaned.endswith(".L"):
        return True
    return bool(re.fullmatch(r"[A-Z0-9&.-]+", cleaned))


def resolve_user_symbol(
    raw: str,
    exchange: str | None = None,
    market_type: str | None = None,
) -> tuple[SymbolInfo, str | None]:
    query = raw.strip()
    if not query:
        raise SymbolResolutionError("Symbol cannot be empty")

    catalog_entry = resolve_from_catalog(query, market_type=_catalog_market_type(market_type))
    if catalog_entry:
        return _symbol_from_catalog(catalog_entry), query

    if looks_like_ticker(query):
        try:
            return _resolve_ticker(query, exchange=exchange, market_type=market_type), None
        except ValueError:
            pass

    yahoo_match = _search_yahoo(query, market_type=market_type)
    if yahoo_match:
        return yahoo_match, query

    suggestions = search_catalog(query, market_type=_catalog_market_type(market_type), limit=5)
    if suggestions:
        labels = ", ".join(f"{item['symbol']} ({item['name']})" for item in suggestions[:3])
        raise SymbolResolutionError(
            f"Could not match '{query}' exactly. Did you mean: {labels}? "
            "Pick a suggestion or enter the exchange ticker.",
            suggestions=suggestions,
        )

    raise SymbolResolutionError(
        f"Could not find '{query}'. Enter a ticker (e.g. TATAGOLD, AAPL, ^GSPC) "
        "or type the company/fund name to see suggestions.",
        suggestions=[],
    )


def _resolve_ticker(query: str, exchange: str | None, market_type: str | None) -> SymbolInfo:
    if market_type in {"us_stock", "us_etf", "us_index", "global_index"}:
        cleaned = query.strip().upper()
        if market_type == "us_index" and not cleaned.startswith("^"):
            cleaned = f"^{cleaned}"
        return SymbolInfo(
            input_symbol=cleaned.lstrip("^"),
            yahoo_symbol=cleaned if cleaned.startswith("^") else cleaned,
            exchange=Exchange.US if market_type != "us_index" and market_type != "global_index" else Exchange.INDEX,
            display_name=cleaned.lstrip("^"),
        )

    if exchange:
        return normalize_symbol(query, exchange=exchange)

    return normalize_symbol(query, exchange=_default_exchange(market_type))


def _default_exchange(market_type: str | None) -> str:
    mapping = {
        "bse_stock": "BSE",
        "nse_stock": "NSE",
        "etf": "NSE",
        "index": "INDEX",
    }
    return mapping.get(market_type or "", "NSE")


def _catalog_market_type(market_type: str | None) -> str | None:
    if market_type in {"us_stock", "us_etf", "us_index", "global_index"}:
        return None
    return market_type


def _symbol_from_catalog(entry: CatalogEntry) -> SymbolInfo:
    exchange = Exchange(entry.exchange) if entry.exchange in Exchange._value2member_map_ else Exchange.NSE
    return SymbolInfo(
        input_symbol=entry.symbol.lstrip("^"),
        yahoo_symbol=_yahoo_for(entry),
        exchange=exchange,
        display_name=entry.name,
    )


def _search_yahoo(query: str, market_type: str | None) -> SymbolInfo | None:
    try:
        import yfinance as yf

        search = yf.Search(query, max_results=8)
        quotes = getattr(search, "quotes", None) or []
        if not quotes and isinstance(search, dict):
            quotes = search.get("quotes", [])

        for quote in quotes:
            symbol = quote.get("symbol") or quote.get("ticker")
            if not symbol:
                continue
            if not _quote_matches_market_type(quote, market_type):
                continue
            name = quote.get("shortname") or quote.get("longname") or symbol
            exchange = _exchange_from_quote(quote, market_type)
            return SymbolInfo(
                input_symbol=str(symbol).lstrip("^"),
                yahoo_symbol=str(symbol),
                exchange=exchange,
                display_name=str(name),
            )
    except Exception:
        return None
    return None


def _quote_matches_market_type(quote: dict, market_type: str | None) -> bool:
    if not market_type:
        return True

    symbol = str(quote.get("symbol", "")).upper()
    exchange = str(quote.get("exchange", "")).upper()
    quote_type = str(quote.get("quoteType", "")).upper()

    if market_type == "us_stock":
        return exchange in {"NMS", "NYQ", "NGM", "NCM", "ASE"} or quote_type == "EQUITY"
    if market_type == "us_etf":
        return quote_type == "ETF" and ".NS" not in symbol and ".BO" not in symbol
    if market_type in {"us_index", "global_index", "index"}:
        return quote_type == "INDEX" or symbol.startswith("^")
    if market_type == "etf":
        return quote_type == "ETF" or "ETF" in symbol or exchange in {"NSI", "NSE"}
    if market_type == "nse_stock":
        return symbol.endswith(".NS") or exchange in {"NSI", "NSE"}
    if market_type == "bse_stock":
        return symbol.endswith(".BO") or exchange in {"BSE", "BO"}
    return True


def _exchange_from_quote(quote: dict, market_type: str | None) -> Exchange:
    symbol = str(quote.get("symbol", ""))
    if market_type in {"us_stock", "us_etf"}:
        return Exchange.US
    if market_type in {"us_index", "global_index", "index"} or symbol.startswith("^"):
        return Exchange.INDEX
    if symbol.endswith(".BO") or market_type == "bse_stock":
        return Exchange.BSE
    return Exchange.NSE
