from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    symbol: str
    name: str
    market_type: str
    exchange: str
    aliases: tuple[str, ...] = ()
    yahoo_symbol: str | None = None


def _yahoo_for(entry: CatalogEntry) -> str:
    if entry.yahoo_symbol:
        return entry.yahoo_symbol
    if entry.exchange == "BSE":
        return f"{entry.symbol}.BO"
    if entry.exchange == "INDEX":
        return entry.symbol if entry.symbol.startswith("^") else entry.symbol
    return f"{entry.symbol}.NS"


# Popular Indian indices, stocks, and ETFs with human-readable names.
CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry("^NSEI", "Nifty 50", "index", "INDEX", ("nifty", "nifty50", "nifty 50", "nse nifty")),
    CatalogEntry("^NSEBANK", "Nifty Bank", "index", "INDEX", ("banknifty", "bank nifty", "nifty bank")),
    CatalogEntry("^BSESN", "BSE Sensex", "index", "INDEX", ("sensex", "bse sensex")),
    CatalogEntry("RELIANCE", "Reliance Industries", "nse_stock", "NSE", ("reliance", "ril")),
    CatalogEntry("TCS", "Tata Consultancy Services", "nse_stock", "NSE", ("tcs", "tata consultancy")),
    CatalogEntry("INFY", "Infosys", "nse_stock", "NSE", ("infy", "infosys")),
    CatalogEntry("HDFCBANK", "HDFC Bank", "nse_stock", "NSE", ("hdfc bank", "hdfcbank")),
    CatalogEntry("ICICIBANK", "ICICI Bank", "nse_stock", "NSE", ("icici bank", "icicibank")),
    CatalogEntry("SBIN", "State Bank of India", "nse_stock", "NSE", ("sbi", "state bank")),
    CatalogEntry("TATAGOLD", "Tata Gold Exchange Traded Fund", "etf", "NSE", ("tata gold", "tata gold etf")),
    CatalogEntry("GOLDBEES", "Nippon India ETF Gold BeES", "etf", "NSE", ("gold bees", "goldbees", "nippon gold")),
    CatalogEntry(
        "GOLDBETA",
        "UTI Gold Exchange Traded Fund",
        "etf",
        "NSE",
        (
            "uti gold",
            "uti gold etf",
            "uti gold exchange traded fund",
            "goldshare",
            "uti goldshare",
            "utigold",
        ),
    ),
    CatalogEntry("NIFTYBEES", "Nippon India ETF Nifty BeES", "etf", "NSE", ("nifty bees", "niftybees")),
    CatalogEntry("SETFGOLD", "SBI Gold Exchange Traded Scheme", "etf", "NSE", ("sbi gold", "setfgold")),
    CatalogEntry("HDFCGOLD", "HDFC Gold Exchange Traded Fund", "etf", "NSE", ("hdfc gold", "hdfcgold")),
    CatalogEntry("SILVERBEES", "Nippon India Silver ETF", "etf", "NSE", ("silver bees", "silverbees")),
    CatalogEntry("TATSILV", "Tata Silver Exchange Traded Fund", "etf", "NSE", ("tata silver", "tata silver etf")),
    # US indices
    CatalogEntry("^GSPC", "S&P 500", "us_index", "INDEX", ("s&p 500", "sp500", "snp 500")),
    CatalogEntry("^DJI", "Dow Jones Industrial Average", "us_index", "INDEX", ("dow jones", "dow", "djia")),
    CatalogEntry("^IXIC", "NASDAQ Composite", "us_index", "INDEX", ("nasdaq", "nasdaq composite")),
    # US stocks
    CatalogEntry("AAPL", "Apple Inc.", "us_stock", "US", ("apple", "apple inc")),
    CatalogEntry("MSFT", "Microsoft Corporation", "us_stock", "US", ("microsoft", "msft")),
    CatalogEntry("GOOGL", "Alphabet Inc.", "us_stock", "US", ("google", "alphabet")),
    CatalogEntry("AMZN", "Amazon.com Inc.", "us_stock", "US", ("amazon",)),
    CatalogEntry("NVDA", "NVIDIA Corporation", "us_stock", "US", ("nvidia",)),
    CatalogEntry("TSLA", "Tesla Inc.", "us_stock", "US", ("tesla",)),
    CatalogEntry("META", "Meta Platforms Inc.", "us_stock", "US", ("meta", "facebook")),
    # US ETFs
    CatalogEntry("SPY", "SPDR S&P 500 ETF Trust", "us_etf", "US", ("spy etf", "spdr s&p 500")),
    CatalogEntry("QQQ", "Invesco QQQ Trust", "us_etf", "US", ("qqq", "nasdaq etf")),
    CatalogEntry("GLD", "SPDR Gold Shares", "us_etf", "US", ("gold etf us", "spdr gold")),
)


def _normalize_text(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def _entry_terms(entry: CatalogEntry) -> set[str]:
    terms = {_normalize_text(entry.symbol), _normalize_text(entry.name)}
    terms.update(_normalize_text(alias) for alias in entry.aliases)
    return {term for term in terms if term}


def _score_query(query: str, entry: CatalogEntry) -> int:
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return 0

    score = 0
    symbol = entry.symbol.upper()
    if normalized_query.replace(" ", "") == symbol.lower().replace("^", ""):
        return 1000
    if normalized_query == _normalize_text(entry.name):
        return 950

    for term in _entry_terms(entry):
        if normalized_query == term:
            score = max(score, 900)
        elif term.startswith(normalized_query) or normalized_query.startswith(term):
            score = max(score, 700 + min(len(normalized_query), 50))
        elif normalized_query in term or term in normalized_query:
            score = max(score, 500 + min(len(term), 40))

    query_tokens = set(normalized_query.split())
    if not query_tokens:
        return score

    for term in _entry_terms(entry):
        term_tokens = set(term.split())
        overlap = query_tokens & term_tokens
        if overlap:
            score = max(score, 200 + len(overlap) * 80)

    return score


def search_catalog(query: str, market_type: str | None = None, limit: int = 8) -> list[dict]:
    ranked: list[tuple[int, CatalogEntry]] = []
    for entry in CATALOG:
        if market_type and entry.market_type != market_type:
            continue
        score = _score_query(query, entry)
        if score > 0:
            ranked.append((score, entry))

    ranked.sort(key=lambda item: (-item[0], item[1].name))
    results: list[dict] = []
    for score, entry in ranked[:limit]:
        results.append(
            {
                "symbol": entry.symbol.lstrip("^"),
                "name": entry.name,
                "market_type": entry.market_type,
                "exchange": entry.exchange,
                "yahoo_symbol": _yahoo_for(entry),
                "score": score,
            }
        )
    return results


def resolve_from_catalog(query: str, market_type: str | None = None) -> CatalogEntry | None:
    matches = search_catalog(query, market_type=market_type, limit=1)
    if not matches:
        return None
    top = matches[0]
    if top["score"] < 200:
        return None
    for entry in CATALOG:
        if entry.symbol.lstrip("^") == top["symbol"]:
            return entry
    return None
