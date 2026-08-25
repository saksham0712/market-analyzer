from __future__ import annotations

import os

_CONFIGURED = False


def ensure_yfinance_cache() -> None:
    """Configure writable yfinance cache once (required on Vercel/serverless)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    cache_dir = os.environ.get("YFINANCE_CACHE_DIR", "/tmp/py-yfinance")
    os.makedirs(cache_dir, exist_ok=True)
    try:
        import yfinance as yf

        yf.set_tz_cache_location(cache_dir)
    except Exception:
        pass
    _CONFIGURED = True
