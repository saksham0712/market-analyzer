from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Writable cache for yfinance on serverless (Vercel/Lambda).
_yf_cache = os.environ.get("YFINANCE_CACHE_DIR", "/tmp/py-yfinance")
os.makedirs(_yf_cache, exist_ok=True)
try:
    import yfinance as yf

    yf.set_tz_cache_location(_yf_cache)
except Exception:
    pass

from web.app import create_app

app = create_app()
