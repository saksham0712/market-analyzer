from __future__ import annotations

from .models import IndicatorSnapshot, OHLCVBar, Signal, TradePlan


def build_trade_plan(
    price: float,
    indicators: IndicatorSnapshot,
    signal: Signal,
    raw_signal: Signal,
    fifty_two_week_high: float | None,
    fifty_two_week_low: float | None,
    recent_bars: list[OHLCVBar],
) -> TradePlan:
    sma_20 = indicators.sma_20
    sma_50 = indicators.sma_50
    rsi = indicators.rsi_14
    swing_low = _recent_swing_low(recent_bars, price)
    swing_high = _recent_swing_high(recent_bars, price)

    bullish = raw_signal in {Signal.BUY, Signal.STRONG_BUY} or (
        raw_signal == Signal.HOLD and sma_20 and sma_50 and sma_20 > sma_50
    )
    bearish = raw_signal in {Signal.SELL, Signal.STRONG_SELL}

    entry_low, entry_high = _entry_zone(
        price=price,
        sma_20=sma_20,
        sma_50=sma_50,
        rsi=rsi,
        bullish=bullish,
        bearish=bearish,
    )

    entry_mid = _mid(entry_low, entry_high, price)
    stop_loss = _stop_loss(
        entry_mid=entry_mid,
        sma_50=sma_50,
        swing_low=swing_low,
        swing_high=swing_high,
        bullish=bullish,
        bearish=bearish,
    )
    target_1, target_2 = _targets(
        price=price,
        entry_mid=entry_mid,
        fifty_two_week_high=fifty_two_week_high,
        fifty_two_week_low=fifty_two_week_low,
        swing_high=swing_high,
        swing_low=swing_low,
        bullish=bullish,
        bearish=bearish,
    )

    risk_reward = None
    if entry_mid and stop_loss and target_1 and entry_mid != stop_loss:
        if bullish:
            risk = entry_mid - stop_loss
            reward = target_1 - entry_mid
        elif bearish:
            risk = stop_loss - entry_mid
            reward = entry_mid - target_1
        else:
            risk = abs(entry_mid - stop_loss)
            reward = abs(target_1 - entry_mid)
        if risk > 0:
            risk_reward = round(reward / risk, 2)

    return TradePlan(
        entry_low=entry_low,
        entry_high=entry_high,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        risk_reward_ratio=risk_reward,
    )


def build_action_advice(
    signal: Signal,
    raw_signal: Signal,
    confidence: int,
    conviction_met: bool,
    indicators: IndicatorSnapshot,
) -> str:
    rsi = indicators.rsi_14

    if not conviction_met and raw_signal != Signal.HOLD:
        if rsi is not None and rsi > 70:
            return "Wait for dip — trend is up but overbought; conviction is below threshold."
        if rsi is not None and rsi < 30:
            return "Wait for confirmation — oversold bounce possible but conviction is low."
        return "Stay on sidelines — mixed signals; no high-conviction trade yet."

    if signal == Signal.STRONG_BUY:
        return "Breakout buy — enter with momentum above the entry zone."
    if signal == Signal.BUY:
        return "Buy on dips — place limit orders inside the entry zone."
    if signal == Signal.STRONG_SELL:
        return "Reduce or exit — bearish setup with high conviction."
    if signal == Signal.SELL:
        return "Avoid new buys — consider trimming if already holding."

    if rsi is not None and rsi > 70:
        return "Wait for dip — do not chase; price is overbought."
    if rsi is not None and rsi < 35:
        return "Watch for reversal — oversold, but wait for confirmation."
    if (
        indicators.sma_20 is not None
        and indicators.sma_50 is not None
        and indicators.sma_20 < indicators.sma_50
    ):
        return "Stay on sidelines — short-term trend is weak."
    return "Stay on sidelines — no clear edge right now."


def apply_conviction_filter(
    raw_signal: Signal,
    confidence: int,
    min_confidence: int,
) -> tuple[Signal, bool]:
    actionable = {Signal.BUY, Signal.SELL, Signal.STRONG_BUY, Signal.STRONG_SELL}
    if raw_signal in actionable and confidence < min_confidence:
        return Signal.HOLD, False
    return raw_signal, True


def _entry_zone(
    price: float,
    sma_20: float | None,
    sma_50: float | None,
    rsi: float | None,
    bullish: bool,
    bearish: bool,
) -> tuple[float | None, float | None]:
    if bearish:
        anchor = sma_20 or price
        return round(anchor * 1.00, 2), round(anchor * 1.02, 2)

    if bullish and rsi is not None and rsi > 70 and sma_20:
        return round(sma_20 * 0.99, 2), round(sma_20 * 1.01, 2)

    if bullish and sma_20 and price > sma_20:
        return round(sma_20 * 0.995, 2), round(price * 1.005, 2)

    if bullish:
        return round(price * 0.99, 2), round(price * 1.01, 2)

    if rsi is not None and rsi > 70 and sma_20:
        return round(sma_20 * 0.99, 2), round(sma_20 * 1.01, 2)

    if sma_20:
        return round(sma_20 * 0.995, 2), round(sma_20 * 1.01, 2)

    return round(price * 0.99, 2), round(price * 1.01, 2)


def _stop_loss(
    entry_mid: float,
    sma_50: float | None,
    swing_low: float | None,
    swing_high: float | None,
    bullish: bool,
    bearish: bool,
) -> float | None:
    if bearish:
        candidates = [entry_mid * 1.03]
        if swing_high:
            candidates.append(swing_high * 1.01)
        return round(max(candidates), 2)

    candidates = [entry_mid * 0.95]
    if sma_50:
        candidates.append(sma_50 * 0.99)
    if swing_low:
        candidates.append(swing_low * 0.995)
    return round(min(candidates), 2)


def _targets(
    price: float,
    entry_mid: float,
    fifty_two_week_high: float | None,
    fifty_two_week_low: float | None,
    swing_high: float | None,
    swing_low: float | None,
    bullish: bool,
    bearish: bool,
) -> tuple[float | None, float | None]:
    if bearish:
        target_1 = swing_low or fifty_two_week_low or entry_mid * 0.95
        target_2 = (fifty_two_week_low or target_1) * 0.97 if fifty_two_week_low else target_1 * 0.97
        return round(target_1, 2), round(target_2, 2)

    target_1 = fifty_two_week_high or swing_high or entry_mid * 1.05
    extension = max(target_1 - entry_mid, entry_mid * 0.03)
    target_2 = target_1 + extension * 0.5
    return round(target_1, 2), round(target_2, 2)


def _recent_swing_low(bars: list[OHLCVBar], price: float) -> float | None:
    if not bars:
        return price * 0.97
    return min(bar.low for bar in bars[-10:])


def _recent_swing_high(bars: list[OHLCVBar], price: float) -> float | None:
    if not bars:
        return price * 1.03
    return max(bar.high for bar in bars[-10:])


def _mid(low: float | None, high: float | None, fallback: float) -> float:
    if low is not None and high is not None:
        return (low + high) / 2
    return fallback
