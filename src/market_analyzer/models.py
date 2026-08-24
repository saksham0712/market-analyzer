from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    US = "US"
    INDEX = "INDEX"
    GLOBAL = "GLOBAL"


class Signal(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass(frozen=True)
class SymbolInfo:
    input_symbol: str
    yahoo_symbol: str
    exchange: Exchange
    display_name: str


@dataclass
class OHLCVBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class IndicatorSnapshot:
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    avg_volume_20: float | None
    volume_ratio: float | None
    pct_from_52w_high: float | None
    pct_from_52w_low: float | None
    return_1m_pct: float | None
    return_3m_pct: float | None


@dataclass
class SignalDetail:
    factor: str
    score: int
    weight: int
    note: str


@dataclass
class TradePlan:
    entry_low: float | None
    entry_high: float | None
    stop_loss: float | None
    target_1: float | None
    target_2: float | None
    risk_reward_ratio: float | None


@dataclass
class AnalysisResult:
    symbol: SymbolInfo
    price: float
    previous_close: float | None
    day_change_pct: float | None
    volume: float | None
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None
    currency: str
    indicators: IndicatorSnapshot
    signal: Signal
    raw_signal: Signal
    confidence: int
    score: int
    conviction_met: bool
    action_advice: str
    trade_plan: TradePlan
    signal_details: list[SignalDetail]
    recent_bars: list[OHLCVBar]
    summary: str
    risks: list[str]
    resolved_from: str | None = None
    data_providers: list[str] | None = None
    quote_agreement_pct: float | None = None
    market_insight: dict | None = None
    beginner_guide: dict | None = None
