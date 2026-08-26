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
    default_interval: str
    max_points: int


@dataclass(frozen=True)
class ChartIntervalConfig:
    key: str
    label: str
    yahoo_interval: str
    resample_rule: str | None = None


CHART_RANGES: dict[str, ChartRangeConfig] = {
    "1d": ChartRangeConfig("1d", "1 Day", "1d", "5m", 120),
    "1w": ChartRangeConfig("1w", "1 Week", "5d", "15m", 120),
    "1m": ChartRangeConfig("1m", "1 Month", "1mo", "1d", 31),
    "3m": ChartRangeConfig("3m", "3 Months", "3mo", "1d", 90),
    "6m": ChartRangeConfig("6m", "6 Months", "6mo", "1d", 120),
    "1y": ChartRangeConfig("1y", "1 Year", "1y", "1d", 252),
}

CHART_INTERVALS: dict[str, ChartIntervalConfig] = {
    "5m": ChartIntervalConfig("5m", "5 min", "5m"),
    "10m": ChartIntervalConfig("10m", "10 min", "5m", "10min"),
    "15m": ChartIntervalConfig("15m", "15 min", "15m"),
    "30m": ChartIntervalConfig("30m", "30 min", "30m"),
    "1h": ChartIntervalConfig("1h", "1 hour", "1h"),
    "1d": ChartIntervalConfig("1d", "1 day", "1d"),
}

RANGE_ALLOWED_INTERVALS: dict[str, list[str]] = {
    "1d": ["5m", "10m", "15m", "30m"],
    "1w": ["5m", "10m", "15m", "30m", "1h"],
    "1m": ["15m", "30m", "1h", "1d"],
    "3m": ["1h", "1d"],
    "6m": ["1d"],
    "1y": ["1d"],
}

DEFAULT_CHART_RANGE = "6m"


def get_chart_range_config(chart_range: str) -> ChartRangeConfig:
    key = chart_range.lower().strip()
    return CHART_RANGES.get(key, CHART_RANGES[DEFAULT_CHART_RANGE])


def resolve_chart_interval(chart_range: str, interval: str | None) -> str:
    config = get_chart_range_config(chart_range)
    allowed = RANGE_ALLOWED_INTERVALS.get(config.key, ["1d"])
    if interval:
        key = interval.lower().strip()
        if key in allowed:
            return key
    if config.default_interval in allowed:
        return config.default_interval
    return allowed[0]


def chart_interval_options(chart_range: str) -> list[dict]:
    config = get_chart_range_config(chart_range)
    allowed = RANGE_ALLOWED_INTERVALS.get(config.key, ["1d"])
    return [
        {"key": CHART_INTERVALS[key].key, "label": CHART_INTERVALS[key].label}
        for key in allowed
        if key in CHART_INTERVALS
    ]


def chart_range_options() -> list[dict]:
    return [{"key": cfg.key, "label": cfg.label} for cfg in CHART_RANGES.values()]


def _nullable(value) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return float(value)


def _format_timestamp(index) -> str:
    ts = pd.Timestamp(index)
    if ts.hour or ts.minute:
        return ts.strftime("%Y-%m-%d %H:%M")
    return ts.strftime("%Y-%m-%d")


def _resample_ohlc(frame: pd.DataFrame, rule: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    working = frame.copy()
    if not isinstance(working.index, pd.DatetimeIndex):
        working.index = pd.to_datetime(working.index)
    aggregated = working.resample(rule).agg(
        {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
    )
    if "SMA_20" in working.columns:
        aggregated["SMA_20"] = working["SMA_20"].resample(rule).last()
    if "SMA_50" in working.columns:
        aggregated["SMA_50"] = working["SMA_50"].resample(rule).last()
    return aggregated.dropna(subset=["Close"])


def build_chart_data(
    frame: pd.DataFrame,
    trade_plan: TradePlan | None = None,
    max_points: int = 120,
    chart_range: str = DEFAULT_CHART_RANGE,
    interval_key: str = "1d",
) -> dict:
    """Build OHLC + SMA series and optional trade-plan levels for the web chart."""
    range_config = get_chart_range_config(chart_range)
    interval_config = CHART_INTERVALS.get(interval_key, CHART_INTERVALS["1d"])
    tail = frame.tail(max_points)
    series: list[dict] = []

    for index, row in tail.iterrows():
        series.append(
            {
                "date": _format_timestamp(index),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
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
        "chart_range": range_config.key,
        "chart_range_label": range_config.label,
        "interval": interval_config.key,
        "interval_label": interval_config.label,
        "available_intervals": chart_interval_options(range_config.key),
    }


def fetch_chart_data(
    symbol_info: SymbolInfo,
    chart_range: str = DEFAULT_CHART_RANGE,
    trade_plan: TradePlan | None = None,
    interval: str | None = None,
) -> dict:
    """Fetch Yahoo history for the selected window and bar size."""
    range_config = get_chart_range_config(chart_range)
    interval_key = resolve_chart_interval(chart_range, interval)
    interval_config = CHART_INTERVALS[interval_key]

    provider = YahooProvider()
    market_data = provider.fetch(
        symbol_info,
        history_range=range_config.period,
        interval=interval_config.yahoo_interval,
    )
    if market_data is None or market_data.frame.empty:
        raise ValueError(
            f"No chart data for {symbol_info.yahoo_symbol} ({range_config.label}, {interval_config.label})"
        )

    _, enriched_frame, _ = compute_indicators(market_data)
    if interval_config.resample_rule:
        enriched_frame = _resample_ohlc(enriched_frame, interval_config.resample_rule)
        if enriched_frame.empty:
            raise ValueError(
                f"No chart data after resampling to {interval_config.label} for {symbol_info.yahoo_symbol}"
            )

    return build_chart_data(
        enriched_frame,
        trade_plan=trade_plan,
        max_points=range_config.max_points,
        chart_range=range_config.key,
        interval_key=interval_key,
    )
