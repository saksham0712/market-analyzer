from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data_provider import MarketData
from .models import IndicatorSnapshot


@dataclass
class AdvancedIndicators:
    atr_14: float | None
    atr_pct: float | None
    bollinger_upper: float | None
    bollinger_lower: float | None
    support_level: float | None
    resistance_level: float | None
    trend_strength: int | None
    market_regime: str | None


def compute_indicators(data: MarketData) -> tuple[IndicatorSnapshot, pd.DataFrame, AdvancedIndicators]:
    frame = data.frame.copy()
    closes = frame["Close"]
    highs = frame["High"]
    lows = frame["Low"]
    volumes = frame["Volume"].fillna(0)

    frame["SMA_20"] = closes.rolling(window=20).mean()
    frame["SMA_50"] = closes.rolling(window=50).mean()
    frame["SMA_200"] = closes.rolling(window=200).mean()
    frame["RSI_14"] = _rsi(closes, period=14)
    frame["MACD"], frame["MACD_SIGNAL"], frame["MACD_HIST"] = _macd(closes)
    frame["AVG_VOLUME_20"] = volumes.rolling(window=20).mean()
    frame["ATR_14"] = _atr(highs, lows, closes, period=14)
    frame["BB_UPPER"], frame["BB_LOWER"] = _bollinger(closes, period=20)

    latest = frame.iloc[-1]
    latest_close = float(latest["Close"])
    latest_volume = float(latest.get("Volume", 0) or 0)
    avg_volume_20 = _latest_value(latest.get("AVG_VOLUME_20"))
    volume_ratio = None
    if avg_volume_20 and avg_volume_20 > 0:
        volume_ratio = latest_volume / avg_volume_20

    pct_from_52w_high = None
    pct_from_52w_low = None
    if data.fifty_two_week_high:
        pct_from_52w_high = ((latest_close - data.fifty_two_week_high) / data.fifty_two_week_high) * 100
    if data.fifty_two_week_low:
        pct_from_52w_low = ((latest_close - data.fifty_two_week_low) / data.fifty_two_week_low) * 100

    atr_14 = _latest_value(latest.get("ATR_14"))
    atr_pct = (atr_14 / latest_close * 100) if atr_14 and latest_close else None
    support, resistance = _support_resistance(frame.tail(60))
    trend_strength, regime = _trend_profile(latest_close, frame)

    snapshot = IndicatorSnapshot(
        sma_20=_latest_value(latest.get("SMA_20")),
        sma_50=_latest_value(latest.get("SMA_50")),
        sma_200=_latest_value(latest.get("SMA_200")),
        rsi_14=_latest_value(latest.get("RSI_14")),
        macd=_latest_value(latest.get("MACD")),
        macd_signal=_latest_value(latest.get("MACD_SIGNAL")),
        macd_histogram=_latest_value(latest.get("MACD_HIST")),
        avg_volume_20=avg_volume_20,
        volume_ratio=volume_ratio,
        pct_from_52w_high=pct_from_52w_high,
        pct_from_52w_low=pct_from_52w_low,
        return_1m_pct=_period_return(closes, sessions=22),
        return_3m_pct=_period_return(closes, sessions=66),
    )
    advanced = AdvancedIndicators(
        atr_14=atr_14,
        atr_pct=round(atr_pct, 2) if atr_pct is not None else None,
        bollinger_upper=_latest_value(latest.get("BB_UPPER")),
        bollinger_lower=_latest_value(latest.get("BB_LOWER")),
        support_level=support,
        resistance_level=resistance,
        trend_strength=trend_strength,
        market_regime=regime,
    )
    return snapshot, frame, advanced


def _latest_value(value: object) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return float(value)


def _period_return(closes: pd.Series, sessions: int) -> float | None:
    if len(closes) <= sessions:
        return None
    start = float(closes.iloc[-sessions - 1])
    end = float(closes.iloc[-1])
    if start == 0:
        return None
    return ((end - start) / start) * 100


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.where(avg_loss > 0, 100.0)


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    return macd, macd_signal, macd - macd_signal


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def _bollinger(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple[pd.Series, pd.Series]:
    mid = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return mid + std_dev * std, mid - std_dev * std


def _support_resistance(frame: pd.DataFrame) -> tuple[float | None, float | None]:
    if frame.empty:
        return None, None
    lows = frame["Low"].tail(20)
    highs = frame["High"].tail(20)
    return round(float(lows.min()), 2), round(float(highs.max()), 2)


def _trend_profile(price: float, frame: pd.DataFrame) -> tuple[int | None, str | None]:
    if len(frame) < 50:
        return None, None

    sma_20 = frame["SMA_20"].iloc[-1]
    sma_50 = frame["SMA_50"].iloc[-1]
    if np.isnan(sma_20) or np.isnan(sma_50):
        return None, None

    score = 0
    if price > sma_20:
        score += 1
    else:
        score -= 1
    if price > sma_50:
        score += 1
    else:
        score -= 1
    if sma_20 > sma_50:
        score += 1
    else:
        score -= 1

    atr = frame["ATR_14"].iloc[-1] if "ATR_14" in frame else np.nan
    atr_pct = (atr / price * 100) if atr and not np.isnan(atr) else 0

    if score >= 2:
        regime = "trending_up"
    elif score <= -2:
        regime = "trending_down"
    elif atr_pct > 3:
        regime = "volatile"
    else:
        regime = "ranging"

    strength = min(100, max(0, int(abs(score) / 3 * 100 + min(atr_pct * 5, 20))))
    return strength, regime
