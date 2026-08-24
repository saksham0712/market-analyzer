from __future__ import annotations

import re

from .models import Exchange, SymbolInfo

KNOWN_INDICES = {
    "NIFTY": ("^NSEI", "Nifty 50"),
    "NIFTY50": ("^NSEI", "Nifty 50"),
    "NSEI": ("^NSEI", "Nifty 50"),
    "BANKNIFTY": ("^NSEBANK", "Nifty Bank"),
    "NSEBANK": ("^NSEBANK", "Nifty Bank"),
    "SENSEX": ("^BSESN", "BSE Sensex"),
    "BSESN": ("^BSESN", "BSE Sensex"),
}


def normalize_symbol(raw: str, exchange: str | None = None) -> SymbolInfo:
    cleaned = raw.strip().upper()
    if not cleaned:
        raise ValueError("Symbol cannot be empty")

    if cleaned.startswith("^"):
        return SymbolInfo(
            input_symbol=raw.strip(),
            yahoo_symbol=cleaned,
            exchange=Exchange.INDEX,
            display_name=cleaned,
        )

    if cleaned in KNOWN_INDICES:
        yahoo_symbol, display_name = KNOWN_INDICES[cleaned]
        return SymbolInfo(
            input_symbol=cleaned,
            yahoo_symbol=yahoo_symbol,
            exchange=Exchange.INDEX,
            display_name=display_name,
        )

    if cleaned.endswith(".NS") or cleaned.endswith(".BO"):
        suffix = ".NS" if cleaned.endswith(".NS") else ".BO"
        base = cleaned[: -len(suffix)]
        resolved_exchange = Exchange.NSE if suffix == ".NS" else Exchange.BSE
        return SymbolInfo(
            input_symbol=base,
            yahoo_symbol=cleaned,
            exchange=resolved_exchange,
            display_name=base,
        )

    if exchange:
        resolved = Exchange(exchange.upper())
    else:
        resolved = Exchange.NSE

    if resolved == Exchange.BSE:
        yahoo_symbol = f"{cleaned}.BO"
    elif resolved == Exchange.INDEX:
        yahoo_symbol, display_name = KNOWN_INDICES.get(cleaned, (cleaned, cleaned))
        return SymbolInfo(
            input_symbol=cleaned,
            yahoo_symbol=yahoo_symbol,
            exchange=Exchange.INDEX,
            display_name=display_name,
        )
    else:
        yahoo_symbol = f"{cleaned}.NS"

    if not re.fullmatch(r"[A-Z0-9&.-]+", cleaned):
        raise ValueError(f"Unsupported symbol format: {raw}")

    return SymbolInfo(
        input_symbol=cleaned,
        yahoo_symbol=yahoo_symbol,
        exchange=resolved,
        display_name=cleaned,
    )
