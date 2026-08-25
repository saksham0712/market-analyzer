from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from .indicators import compute_indicators
from .models import SymbolInfo, TradePlan
from .providers.yahoo import YahooProvider


@dataclass(frozen=True)
class ChartRangeConfig:
    key: str
    label: str
    period: str
    interval: str
    max_points: int


CHART_RANGES: dict[str, ChartRangeConfig] = {
    "1d": ChartRangeConfig("1d", "1 Day", "1d", "15m", 96),
    "1w": ChartRangeConfig("1w", "1 Week", "5d", "1h", 120),
    "1m": ChartRangeConfig("1m", "1 Month", "1mo", "1d", 31),
    "3m": ChartRangeConfig("3m", "3 Months", "3mo", "1d", 90),
    "6m": ChartRangeConfig("6m", "6 Months", "6mo", "1d", 120),
    "1y": ChartRangeConfig("1y", "1 Year", "1y", "1d", 252),
}

DEFAULT_CHART_RANGE = "6m"


def get_chart_range_config(chart_range: str) -> ChartRangeConfig:
    key = chart_range.lower().strip()
    return CHART_RANGES.get(key, CHART_RANGES[DEFAULT_CHART_RANGE])


def _nullable(value) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return float(value)


def _format_timestamp(index) -> str:
    ts = pd.Timestamp(index)
    if ts.hour or ts.minute:
        return ts.strftime("%Y-%m-%d %H:%M")
    return ts.strftime("%Y-%m-%d")


def build_chart_data(
    frame: pd.DataFrame,
    trade_plan: TradePlan | None = None,
    max_points: int = 120,
    chart_range: str = DEFAULT_CHART_RANGE,
) -> dict:
    """Build price + SMA series and optional trade-plan levels for the web line chart."""
    config = get_chart_range_config(chart_range)
    tail = frame.tail(max_points)
    series: list[dict] = []

    for index, row in tail.iterrows():
        series.append(
            {
                "date": _format_timestamp(index),
                "close": float(row["Close"]),
                "sma_20": _nullable(row.get("SMA_20")),
                "sma_50": _nullable(row.get("SMA_50")),
            }
        )

    levels: dict[str, float] = {}
    if trade_plan:
        if trade_plan.entry_low is not None:
            levels["entry_low"] = trade_plan.entry_low
        if trade_plan.entry_high is not None:
            levels["entry_high"] = trade_plan.entry_high
        if trade_plan.stop_loss is not None:
            levels["stop_loss"] = trade_plan.stop_loss
        if trade_plan.target_1 is not None:
            levels["target_1"] = trade_plan.target_1
        if trade_plan.target_2 is not None:
            levels["target_2"] = trade_plan.target_2

    return {
        "series": series,
        "levels": levels,
        "chart_range": config.key,
        "chart_range_label": config.label,
        "interval": config.interval,
    }


def fetch_chart_data(
    symbol_info: SymbolInfo,
    chart_range: str = DEFAULT_CHART_RANGE,
    trade_plan: TradePlan | None = None,
) -> dict:
    """Fetch Yahoo history for the selected chart window and return chart payload."""
    config = get_chart_range_config(chart_range)
    provider = YahooProvider()
    market_data = provider.fetch(symbol_info, history_range=config.period, interval=config.interval)
    if market_data is None or market_data.frame.empty:
        raise ValueError(f"No chart data for {symbol_info.yahoo_symbol} ({config.label})")

    _, enriched_frame, _ = compute_indicators(market_data)
    return build_chart_data(
        enriched_frame,
        trade_plan=trade_plan,
        max_points=config.max_points,
        chart_range=config.key,
    )


def chart_range_options() -> list[dict]:
    return [{"key": cfg.key, "label": cfg.label} for cfg in CHART_RANGES.values()]
