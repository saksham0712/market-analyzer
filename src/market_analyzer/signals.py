from __future__ import annotations

from dataclasses import dataclass

from .models import IndicatorSnapshot, Signal, SignalDetail


@dataclass
class SignalConfig:
    rsi_oversold: float = 30
    rsi_overbought: float = 70
    volume_spike_multiplier: float = 1.5
    min_confidence: int = 50


class SignalEngine:
    def __init__(self, config: SignalConfig | None = None) -> None:
        self.config = config or SignalConfig()

    def generate(self, price: float, indicators: IndicatorSnapshot) -> tuple[Signal, int, int, list[SignalDetail]]:
        details: list[SignalDetail] = []
        total_score = 0
        total_weight = 0

        def add(factor: str, score: int, weight: int, note: str) -> None:
            nonlocal total_score, total_weight
            details.append(SignalDetail(factor=factor, score=score, weight=weight, note=note))
            total_score += score * weight
            total_weight += weight

        self._score_trend(price, indicators, add)
        self._score_momentum(indicators, add)
        self._score_macd(indicators, add)
        self._score_volume(indicators, add)
        self._score_position(indicators, add)

        if total_weight == 0:
            return Signal.HOLD, 0, 0, details

        normalized = total_score / total_weight
        raw_signal = self._map_score(normalized)
        confidence = self._compute_confidence(normalized, details)
        return raw_signal, confidence, int(round(normalized)), details

    def _compute_confidence(self, normalized: float, details: list[SignalDetail]) -> int:
        if not details:
            return 0

        magnitude = min(100, int(abs(normalized) * 35))
        direction = 1 if normalized > 0 else -1 if normalized < 0 else 0

        if direction == 0:
            non_zero = [detail for detail in details if detail.score != 0]
            if not non_zero:
                return 10
            positive = sum(1 for detail in non_zero if detail.score > 0)
            negative = sum(1 for detail in non_zero if detail.score < 0)
            agreement = max(positive, negative) / len(non_zero) * 100
            return int(min(45, agreement * 0.45))

        agreeing_weight = sum(detail.weight for detail in details if detail.score * direction > 0)
        total_weight = sum(detail.weight for detail in details if detail.score != 0)
        agreement = (agreeing_weight / total_weight * 100) if total_weight else 0
        return min(100, int(agreement * 0.55 + magnitude * 0.45))

    def _score_trend(self, price: float, indicators: IndicatorSnapshot, add) -> None:
        sma_20 = indicators.sma_20
        sma_50 = indicators.sma_50
        sma_200 = indicators.sma_200

        if sma_20 is not None:
            if price > sma_20:
                add("Trend (SMA20)", 1, 2, f"Price {price:.2f} is above SMA20 {sma_20:.2f}")
            else:
                add("Trend (SMA20)", -1, 2, f"Price {price:.2f} is below SMA20 {sma_20:.2f}")

        if sma_50 is not None:
            if price > sma_50:
                add("Trend (SMA50)", 1, 2, f"Price is above SMA50 {sma_50:.2f}")
            else:
                add("Trend (SMA50)", -1, 2, f"Price is below SMA50 {sma_50:.2f}")

        if sma_20 is not None and sma_50 is not None:
            if sma_20 > sma_50:
                add("Trend alignment", 1, 1, "SMA20 above SMA50 (bullish structure)")
            else:
                add("Trend alignment", -1, 1, "SMA20 below SMA50 (bearish structure)")

        if sma_200 is not None:
            if price > sma_200:
                add("Long trend (SMA200)", 1, 1, f"Price above SMA200 {sma_200:.2f}")
            else:
                add("Long trend (SMA200)", -1, 1, f"Price below SMA200 {sma_200:.2f}")

    def _score_momentum(self, indicators: IndicatorSnapshot, add) -> None:
        rsi = indicators.rsi_14
        if rsi is None:
            return

        if rsi < self.config.rsi_oversold:
            add("RSI", 2, 2, f"RSI {rsi:.1f} is oversold")
        elif rsi > self.config.rsi_overbought:
            add("RSI", -2, 2, f"RSI {rsi:.1f} is overbought")
        elif 45 <= rsi <= 60:
            add("RSI", 1, 1, f"RSI {rsi:.1f} shows healthy momentum")
        elif rsi < 45:
            add("RSI", -1, 1, f"RSI {rsi:.1f} is weak")
        else:
            add("RSI", 0, 1, f"RSI {rsi:.1f} is neutral-to-hot")

    def _score_macd(self, indicators: IndicatorSnapshot, add) -> None:
        macd = indicators.macd
        signal = indicators.macd_signal
        hist = indicators.macd_histogram
        if macd is None or signal is None or hist is None:
            return

        if macd > signal and hist > 0:
            add("MACD", 2, 2, "MACD above signal with positive histogram")
        elif macd > signal:
            add("MACD", 1, 2, "MACD above signal")
        elif macd < signal and hist < 0:
            add("MACD", -2, 2, "MACD below signal with negative histogram")
        else:
            add("MACD", -1, 2, "MACD below signal")

    def _score_volume(self, indicators: IndicatorSnapshot, add) -> None:
        ratio = indicators.volume_ratio
        if ratio is None:
            return

        if ratio >= self.config.volume_spike_multiplier:
            add("Volume", 1, 1, f"Volume is {ratio:.2f}x the 20-day average")
        elif ratio <= 0.7:
            add("Volume", -1, 1, f"Volume is weak at {ratio:.2f}x average")
        else:
            add("Volume", 0, 1, f"Volume is normal at {ratio:.2f}x average")

    def _score_position(self, indicators: IndicatorSnapshot, add) -> None:
        high_pct = indicators.pct_from_52w_high
        low_pct = indicators.pct_from_52w_low

        if high_pct is not None:
            if high_pct > -3:
                add("52W position", -1, 1, f"Only {abs(high_pct):.1f}% below 52W high (limited upside)")
            elif high_pct < -20:
                add("52W position", 1, 1, f"{abs(high_pct):.1f}% below 52W high (room to recover)")

        if low_pct is not None and low_pct > 40:
            add("Risk stretch", -1, 1, f"Price is {low_pct:.1f}% above 52W low (extended move)")

    def _map_score(self, normalized: float) -> Signal:
        if normalized >= 2:
            return Signal.STRONG_BUY
        if normalized >= 0.75:
            return Signal.BUY
        if normalized <= -2:
            return Signal.STRONG_SELL
        if normalized <= -0.75:
            return Signal.SELL
        return Signal.HOLD
