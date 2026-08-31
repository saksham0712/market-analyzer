"""Fetch and normalize NSE index option chain data (Nifty 50 paper trading)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPCookieProcessor, Request, build_opener

NIFTY_LOT_SIZE = 50
NIFTY_SYMBOL = "NIFTY"
DEFAULT_STARTING_CASH = 100_000.0

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = 45

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

_WARMUP_URLS = (
    "https://www.nseindia.com/option-chain",
    "https://www.nseindia.com/market-data/equity-derivatives-watch",
)


@dataclass(frozen=True)
class OptionLegQuote:
    ltp: float | None
    change: float | None
    oi: int | None
    volume: int | None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
        if number != number:
            return None
        return number
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    parsed = _safe_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _parse_leg(raw: dict | None) -> OptionLegQuote | None:
    if not raw:
        return None
    return OptionLegQuote(
        ltp=_safe_float(raw.get("lastPrice")),
        change=_safe_float(raw.get("change")),
        oi=_safe_int(raw.get("openInterest")),
        volume=_safe_int(raw.get("totalTradedVolume")),
    )


def _leg_to_dict(leg: OptionLegQuote | None) -> dict | None:
    if leg is None:
        return None
    return {
        "ltp": leg.ltp,
        "change": leg.change,
        "oi": leg.oi,
        "volume": leg.volume,
    }


def _normalize_expiry_label(value: str) -> str:
    """Normalize NSE expiry strings for comparison (01-Sep-2026 vs 01-09-2026)."""
    text = value.strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%d-%b-%Y")
        except ValueError:
            continue
    return text


def _expiry_matches(left: str, right: str) -> bool:
    return _normalize_expiry_label(left) == _normalize_expiry_label(right)


def _build_opener():
    return build_opener(HTTPCookieProcessor())


def _warmup_session(opener) -> None:
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    for url in _WARMUP_URLS:
        try:
            opener.open(Request(url, headers=headers), timeout=15).read()
        except (HTTPError, URLError, TimeoutError):
            continue


def _api_headers() -> dict[str, str]:
    return {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/option-chain",
    }


def _fetch_json(opener, url: str) -> dict:
    request = Request(url, headers=_api_headers())
    with opener.open(request, timeout=25) as response:
        body = response.read()
    if not body or body.strip() in {b"{}", b"[]"}:
        raise ValueError(f"Empty response from NSE for {url}")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Unexpected NSE response shape")
    return payload


def _fetch_expiries(opener, symbol: str) -> list[str]:
    url = f"https://www.nseindia.com/api/option-chain-contract-info?symbol={quote(symbol)}"
    payload = _fetch_json(opener, url)
    expiries = payload.get("expiryDates") or []
    if not expiries:
        raise ValueError(f"No expiries returned for {symbol}")
    return [str(item) for item in expiries]


def _fetch_chain_payload(opener, symbol: str, expiry: str) -> dict:
    expiry_q = quote(expiry, safe="")
    urls = (
        f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={symbol}&expiry={expiry_q}",
        f"https://www.nseindia.com/api/option-chain-v3?symbol={symbol}&expiry={expiry_q}",
    )
    last_error: Exception | None = None
    for url in urls:
        try:
            return _fetch_json(opener, url)
        except (HTTPError, URLError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
    raise ValueError(f"Could not load option chain for {symbol} {expiry}") from last_error


def _parse_nse_payload(
    payload: dict,
    symbol: str,
    expiry: str,
    expiries: list[str],
) -> dict:
    records = payload.get("records") or {}
    available_expiries = list(records.get("expiryDates") or expiries)
    if not available_expiries:
        available_expiries = expiries

    selected_expiry = expiry
    if not any(_expiry_matches(item, selected_expiry) for item in available_expiries):
        raise ValueError(
            f"Expiry {selected_expiry} not available. Choose one of: {', '.join(available_expiries[:5])}"
        )

    spot = _safe_float(records.get("underlyingValue"))
    timestamp = records.get("timestamp") or records.get("underlying")

    rows: list[dict] = []
    for item in records.get("data") or []:
        row_expiry = item.get("expiryDate")
        if row_expiry and not _expiry_matches(str(row_expiry), selected_expiry):
            continue
        strike = _safe_float(item.get("strikePrice"))
        if strike is None:
            continue
        ce = _parse_leg(item.get("CE"))
        pe = _parse_leg(item.get("PE"))
        rows.append(
            {
                "strike": strike,
                "ce": _leg_to_dict(ce),
                "pe": _leg_to_dict(pe),
            }
        )

    rows.sort(key=lambda row: row["strike"])
    if not rows:
        raise ValueError(f"No strikes for {symbol} expiry {selected_expiry}")

    canonical_expiry = next(
        (item for item in available_expiries if _expiry_matches(item, selected_expiry)),
        selected_expiry,
    )

    return {
        "symbol": symbol,
        "spot": spot,
        "lot_size": NIFTY_LOT_SIZE,
        "expiry": canonical_expiry,
        "expiries": available_expiries,
        "timestamp": timestamp,
        "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": "nse",
        "rows": rows,
    }


def _fetch_spot_fallback() -> float | None:
    try:
        from .runtime import ensure_yfinance_cache

        ensure_yfinance_cache()
        import yfinance as yf

        ticker = yf.Ticker("^NSEI")
        try:
            fast = dict(ticker.fast_info or {})
            price = fast.get("lastPrice") or fast.get("last_price")
            if price is not None:
                return float(price)
        except Exception:
            pass

        frame = ticker.history(period="1d", interval="1m")
        if not frame.empty:
            return float(frame.iloc[-1]["Close"])
        frame = ticker.history(period="5d", interval="1d")
        if frame.empty:
            return None
        return float(frame.iloc[-1]["Close"])
    except Exception:
        return None


def _build_demo_chain(expiry: str | None = None) -> dict:
    """Synthetic chain for offline practice when NSE is unreachable."""
    spot = _fetch_spot_fallback() or 24000.0
    atm = round(spot / 50) * 50
    strikes = [atm + step * 50 for step in range(-10, 11)]
    selected = expiry or "Demo"

    def synth_premium(strike: float, is_call: bool) -> float:
        distance = abs(strike - spot)
        base = max(5.0, 350.0 - distance * 0.85)
        if is_call and strike < spot:
            base = max(5.0, base * 0.35 + (spot - strike) * 0.15)
        if not is_call and strike > spot:
            base = max(5.0, base * 0.35 + (strike - spot) * 0.15)
        return round(base, 2)

    rows = []
    for strike in strikes:
        rows.append(
            {
                "strike": float(strike),
                "ce": {"ltp": synth_premium(strike, True), "change": 0.0, "oi": None, "volume": None},
                "pe": {"ltp": synth_premium(strike, False), "change": 0.0, "oi": None, "volume": None},
            }
        )

    return {
        "symbol": NIFTY_SYMBOL,
        "spot": spot,
        "lot_size": NIFTY_LOT_SIZE,
        "expiry": selected,
        "expiries": [selected, "Demo +1W"],
        "timestamp": None,
        "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": "demo",
        "warning": (
            "NSE chain unavailable — showing demo premiums from Nifty spot for practice only. "
            "Tap Refresh to retry live NSE data."
        ),
        "rows": rows,
    }


def fetch_nifty_option_chain(
    expiry: str | None = None,
    use_cache: bool = True,
    allow_demo_fallback: bool = True,
) -> dict:
    """Return normalized Nifty 50 option chain from NSE (with short-lived cache)."""
    cache_key = f"{NIFTY_SYMBOL}:{expiry or 'default'}"
    now = time.time()
    if use_cache and cache_key in _CACHE:
        cached_at, cached_payload = _CACHE[cache_key]
        if now - cached_at < _CACHE_TTL_SECONDS:
            return {**cached_payload, "cached": True}

    last_error: Exception | None = None
    try:
        opener = _build_opener()
        _warmup_session(opener)
        expiries = _fetch_expiries(opener, NIFTY_SYMBOL)
        selected_expiry = expiry or expiries[0]
        if expiry and not any(_expiry_matches(item, expiry) for item in expiries):
            raise ValueError(f"Expiry {expiry} not available. Choose one of: {', '.join(expiries[:5])}")
        if not expiry:
            selected_expiry = expiries[0]

        payload = _fetch_chain_payload(opener, NIFTY_SYMBOL, selected_expiry)
        normalized = _parse_nse_payload(payload, NIFTY_SYMBOL, selected_expiry, expiries)
        if normalized.get("spot") is None:
            fallback_spot = _fetch_spot_fallback()
            if fallback_spot is not None:
                normalized["spot"] = fallback_spot
        _CACHE[cache_key] = (now, normalized)
        return {**normalized, "cached": False}
    except (HTTPError, URLError, ValueError, json.JSONDecodeError, KeyError) as exc:
        last_error = exc

    if cache_key in _CACHE and allow_demo_fallback:
        cached_at, cached_payload = _CACHE[cache_key]
        return {
            **cached_payload,
            "cached": True,
            "stale": True,
            "warning": "Live fetch failed; showing last cached chain. Try Refresh again.",
        }

    demo = _build_demo_chain(expiry=expiry)
    _CACHE[cache_key] = (now, demo)
    if not allow_demo_fallback:
        message = "Could not load live NSE option chain for order fill."
        if last_error is not None:
            message = f"{message} ({type(last_error).__name__})"
        raise ValueError(message) from last_error
    return {**demo, "cached": False, "fallback": True, "error_detail": str(last_error) if last_error else None}


def _find_row_ltp(chain: dict, strike: float, option_type: str) -> float:
    normalized_type = option_type.upper().strip()
    if normalized_type not in {"CE", "PE"}:
        raise ValueError("option_type must be CE or PE")

    target_strike = float(strike)
    for row in chain.get("rows") or []:
        row_strike = float(row.get("strike", 0))
        if abs(row_strike - target_strike) >= 0.001:
            continue
        leg = row.get("ce") if normalized_type == "CE" else row.get("pe")
        ltp = leg.get("ltp") if leg else None
        if ltp is None or float(ltp) <= 0:
            raise ValueError(f"No live LTP for NIFTY {row_strike} {normalized_type}")
        return float(ltp)

    raise ValueError(f"Strike {target_strike} not found for expiry {chain.get('expiry')}")


def fetch_option_ltp(expiry: str, strike: float, option_type: str) -> dict:
    """Fetch fresh NSE chain and return live LTP for one option leg (order fill)."""
    chain = fetch_nifty_option_chain(
        expiry=expiry,
        use_cache=False,
        allow_demo_fallback=False,
    )
    ltp = _find_row_ltp(chain, strike, option_type)
    normalized_type = option_type.upper().strip()
    return {
        "symbol": NIFTY_SYMBOL,
        "expiry": chain.get("expiry", expiry),
        "strike": float(strike),
        "type": normalized_type,
        "ltp": ltp,
        "spot": chain.get("spot"),
        "source": chain.get("source", "nse"),
        "live": chain.get("source") == "nse" and not chain.get("fallback"),
        "fetched_at": chain.get("fetched_at"),
        "timestamp": chain.get("timestamp"),
    }


def fetch_nifty_spot() -> dict:
    """Spot price for Nifty 50 — prefers option-chain underlying, else Yahoo."""
    try:
        chain = fetch_nifty_option_chain(use_cache=True)
        if chain.get("spot") is not None:
            return {
                "symbol": NIFTY_SYMBOL,
                "spot": chain["spot"],
                "source": chain.get("source", "nse"),
                "timestamp": chain.get("timestamp"),
            }
    except ValueError:
        pass

    spot = _fetch_spot_fallback()
    if spot is None:
        raise ValueError("Could not fetch Nifty spot price")
    return {
        "symbol": NIFTY_SYMBOL,
        "spot": spot,
        "source": "yahoo",
        "timestamp": None,
    }
