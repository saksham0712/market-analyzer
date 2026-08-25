from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from market_analyzer.analyzer import MarketAnalyzer
from market_analyzer.chart_data import chart_range_options, fetch_chart_data
from market_analyzer.models import TradePlan
from market_analyzer.report import analysis_to_dict
from market_analyzer.strategies import build_market_strategies
from market_analyzer.symbol_catalog import search_catalog
from market_analyzer.symbol_resolver import MARKET_TYPE_EXCHANGE, SymbolResolutionError

STATIC_DIR = Path(__file__).resolve().parent / "static"

_analyzer: MarketAnalyzer | None = None


def get_analyzer() -> MarketAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = MarketAnalyzer()
    return _analyzer


class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, description="Ticker or company/fund name")
    market_type: str = Field(
        ...,
        description="index, nse_stock, bse_stock, etf, us_stock, us_etf, us_index, global_index",
    )


def create_app() -> FastAPI:
    application = FastAPI(title="Market Analyzer By Saksham", version="0.2.0")

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {exc}"},
        )

    @application.get("/")
    async def index() -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        if not index_path.is_file():
            raise HTTPException(status_code=500, detail="index.html not found in deployment bundle")
        return FileResponse(index_path)

    @application.get("/static/{asset_path:path}")
    async def static_asset(asset_path: str) -> FileResponse:
        file_path = (STATIC_DIR / asset_path).resolve()
        if not file_path.is_file() or STATIC_DIR.resolve() not in file_path.parents:
            raise HTTPException(status_code=404, detail="Static asset not found")
        return FileResponse(file_path)

    @application.get("/api/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "market_types": list(MARKET_TYPE_EXCHANGE.keys()),
            "chart_ranges": chart_range_options(),
            "static_dir": str(STATIC_DIR),
            "static_exists": STATIC_DIR.is_dir(),
        }

    @application.get("/api/chart")
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

            symbol_info, _ = resolve_user_symbol(
                symbol.strip(), exchange=exchange, market_type=normalized_type
            )
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

    @application.get("/api/search")
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

    @application.post("/api/analyze")
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
            result = get_analyzer().analyze(symbol, exchange=exchange, market_type=market_type)
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

    return application
