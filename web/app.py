from __future__ import annotations

import os
import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

STATIC_DIR = Path(__file__).resolve().parent / "static"

_analyzer = None


def _user_facing_error(exc: Exception, fallback: str) -> str:
    if os.getenv("VERCEL_ENV") == "production":
        return fallback
    return f"{fallback} ({type(exc).__name__}: {exc})"


class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, description="Ticker or company/fund name")
    market_type: str = Field(
        ...,
        description="index, nse_stock, bse_stock, etf, us_stock, us_etf, us_index, global_index",
    )


def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        from market_analyzer.analyzer import MarketAnalyzer

        _analyzer = MarketAnalyzer()
    return _analyzer


def create_app() -> FastAPI:
    application = FastAPI(title="Market Analyzer By Saksham", version="0.2.0")

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException):
            detail = exc.detail
            if not isinstance(detail, str):
                detail = str(detail)
            return JSONResponse(status_code=exc.status_code, content={"detail": detail})
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "detail": _user_facing_error(
                    exc,
                    "Something went wrong on the server. Please try again in a moment.",
                )
            },
        )

    @application.get("/")
    async def index() -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        if not index_path.is_file():
            raise HTTPException(
                status_code=500,
                detail=f"index.html missing (static dir: {STATIC_DIR})",
            )
        return FileResponse(index_path)

    @application.get("/trade")
    async def trade_page() -> FileResponse:
        trade_path = STATIC_DIR / "trade.html"
        if not trade_path.is_file():
            raise HTTPException(status_code=500, detail="trade.html missing")
        return FileResponse(trade_path)

    @application.get("/api/trade/chain")
    async def trade_chain(
        expiry: str | None = Query(None, description="NSE expiry label e.g. 02-Sep-2026"),
        refresh: bool = Query(False, description="Bypass server cache and fetch live from NSE"),
    ) -> dict:
        from market_analyzer.nse_options import fetch_nifty_option_chain

        try:
            return fetch_nifty_option_chain(expiry=expiry, use_cache=not refresh)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=_user_facing_error(
                    exc,
                    "Could not load option chain. Tap Refresh to try again.",
                ),
            ) from exc

    @application.get("/api/trade/quote")
    async def trade_quote(
        expiry: str = Query(..., min_length=1, description="NSE expiry e.g. 01-Sep-2026"),
        strike: float = Query(..., gt=0),
        option_type: str = Query(..., alias="type", description="CE or PE"),
    ) -> dict:
        from market_analyzer.nse_options import fetch_option_ltp

        try:
            return fetch_option_ltp(expiry=expiry, strike=strike, option_type=option_type)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=_user_facing_error(exc, "Could not fetch live option price."),
            ) from exc

    @application.get("/api/trade/spot")
    async def trade_spot() -> dict:
        from market_analyzer.nse_options import fetch_nifty_spot

        try:
            return fetch_nifty_spot()
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=_user_facing_error(exc, "Could not load Nifty spot price."),
            ) from exc

    @application.get("/static/{asset_path:path}")
    async def static_asset(asset_path: str) -> FileResponse:
        file_path = (STATIC_DIR / asset_path).resolve()
        if not file_path.is_file() or STATIC_DIR.resolve() not in file_path.parents:
            raise HTTPException(status_code=404, detail="Static asset not found")
        return FileResponse(file_path)

    @application.get("/api/ping")
    async def ping() -> dict:
        return {"status": "pong"}

    @application.get("/api/health")
    async def health() -> dict:
        from market_analyzer.chart_data import chart_range_options
        from market_analyzer.symbol_resolver import MARKET_TYPE_EXCHANGE

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
        interval: str | None = Query(None, description="Bar size: 5m, 10m, 15m, 30m, 1h, 1d"),
        entry_low: float | None = Query(None),
        entry_high: float | None = Query(None),
        stop_loss: float | None = Query(None),
        target_1: float | None = Query(None),
        target_2: float | None = Query(None),
    ) -> dict:
        from market_analyzer.chart_data import fetch_chart_data
        from market_analyzer.models import TradePlan
        from market_analyzer.symbol_resolver import MARKET_TYPE_EXCHANGE, SymbolResolutionError, resolve_user_symbol

        normalized_type = market_type.lower().strip()
        if normalized_type not in MARKET_TYPE_EXCHANGE:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid market_type. Use one of: {', '.join(MARKET_TYPE_EXCHANGE)}",
            )

        exchange = MARKET_TYPE_EXCHANGE[normalized_type]
        try:
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
            return fetch_chart_data(
                symbol_info,
                chart_range=chart_range,
                trade_plan=trade_plan,
                interval=interval,
            )
        except SymbolResolutionError as exc:
            return JSONResponse(
                status_code=400,
                content={"detail": str(exc), "suggestions": exc.suggestions},
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=_user_facing_error(
                    exc,
                    "Could not load chart data right now. Try a different time range or symbol.",
                ),
            ) from exc

    @application.get("/api/search")
    async def search(
        q: str = Query(..., min_length=1),
        market_type: str | None = Query(None),
    ) -> dict:
        from market_analyzer.symbol_catalog import search_catalog
        from market_analyzer.symbol_resolver import MARKET_TYPE_EXCHANGE

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
        from market_analyzer.report import analysis_to_dict
        from market_analyzer.strategies import build_market_strategies
        from market_analyzer.symbol_resolver import MARKET_TYPE_EXCHANGE, SymbolResolutionError

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
            result = _get_analyzer().analyze(symbol, exchange=exchange, market_type=market_type)
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
            raise HTTPException(
                status_code=502,
                detail=_user_facing_error(
                    exc,
                    "Could not fetch market data right now. Please try again in a moment.",
                ),
            ) from exc

        payload = analysis_to_dict(result)
        payload["market_type"] = market_type
        payload["market_strategies"] = build_market_strategies(result)
        return payload

    return application
