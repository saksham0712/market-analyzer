from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Serverless hosts (e.g. Vercel) need a writable cache directory for yfinance.
_yf_cache = os.environ.get("YFINANCE_CACHE_DIR", "/tmp/py-yfinance")
os.makedirs(_yf_cache, exist_ok=True)
try:
    import yfinance as yf

    yf.set_tz_cache_location(_yf_cache)
except Exception:
    pass

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from market_analyzer.analyzer import MarketAnalyzer
from market_analyzer.chart_data import chart_range_options, fetch_chart_data
from market_analyzer.models import TradePlan
from market_analyzer.report import analysis_to_dict
from market_analyzer.strategies import build_market_strategies
from market_analyzer.symbol_catalog import search_catalog
from market_analyzer.symbol_resolver import MARKET_TYPE_EXCHANGE, SymbolResolutionError

STATIC_DIR = Path(__file__).resolve().parent / "static"

analyzer = MarketAnalyzer()
app = FastAPI(title="Market Analyzer By Saksham", version="0.2.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, description="Ticker or company/fund name")
    market_type: str = Field(
        ...,
        description="index, nse_stock, bse_stock, etf, us_stock, us_etf, us_index, global_index",
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "market_types": list(MARKET_TYPE_EXCHANGE.keys()),
        "chart_ranges": chart_range_options(),
    }


@app.get("/api/chart")
async def chart(
    symbol: str = Query(..., min_length=1),
    market_type: str = Query(...),
    chart_range: str = Query("6m"),
    entry_low: float | None = Query(None),
    entry_high: float | None = Query(None),
    stop_loss: float | None = Query(None),
    target_1: float | None = Query(None),
    target_2: float | None = Query(None),
) -> dict:
    normalized_type = market_type.lower().strip()
    if normalized_type not in MARKET_TYPE_EXCHANGE:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid market_type. Use one of: {', '.join(MARKET_TYPE_EXCHANGE)}",
        )

    exchange = MARKET_TYPE_EXCHANGE[normalized_type]
    try:
        from market_analyzer.symbol_resolver import resolve_user_symbol

        symbol_info, _ = resolve_user_symbol(symbol.strip(), exchange=exchange, market_type=normalized_type)
        trade_plan = TradePlan(
            entry_low=entry_low,
            entry_high=entry_high,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            risk_reward_ratio=None,
        )
        return fetch_chart_data(symbol_info, chart_range=chart_range, trade_plan=trade_plan)
    except SymbolResolutionError as exc:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "suggestions": exc.suggestions},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch chart data: {exc}") from exc


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=1),
    market_type: str | None = Query(None),
) -> dict:
    query = q.strip()
    if not query:
        return {"results": []}
    normalized_type = market_type.lower().strip() if market_type else None
    if normalized_type and normalized_type not in MARKET_TYPE_EXCHANGE:
        raise HTTPException(status_code=400, detail=f"Invalid market_type: {market_type}")
    results = search_catalog(query, market_type=normalized_type, limit=8)
    return {"query": query, "results": results}


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest) -> dict:
    market_type = request.market_type.lower().strip()
    if market_type not in MARKET_TYPE_EXCHANGE:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid market_type. Use one of: {', '.join(MARKET_TYPE_EXCHANGE)}",
        )

    symbol = request.symbol.strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol cannot be empty")

    exchange = MARKET_TYPE_EXCHANGE[market_type]
    try:
        result = analyzer.analyze(symbol, exchange=exchange, market_type=market_type)
    except SymbolResolutionError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "detail": str(exc),
                "suggestions": exc.suggestions,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch market data: {exc}") from exc

    payload = analysis_to_dict(result)
    payload["market_type"] = market_type
    payload["market_strategies"] = build_market_strategies(result)
    return payload
