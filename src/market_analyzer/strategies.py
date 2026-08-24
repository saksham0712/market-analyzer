from __future__ import annotations

from dataclasses import dataclass

from .models import AnalysisResult, Exchange, Signal


@dataclass(frozen=True)
class MarketStrategy:
    id: str
    title: str
    description: str
    suitability: str  # high | medium | low
    rationale: str


def build_market_strategies(result: AnalysisResult) -> list[dict]:
    """Return contextual strategy suggestions based on the analysis."""
    strategies: list[MarketStrategy] = []
    indicators = result.indicators
    rsi = indicators.rsi_14
    is_index = result.symbol.exchange == Exchange.INDEX

    if result.signal in {Signal.STRONG_BUY, Signal.BUY} and result.conviction_met:
        if rsi is not None and rsi > 70:
            strategies.append(
                MarketStrategy(
                    id="wait_for_dip",
                    title="Wait for Dip",
                    description="Trend is bullish but RSI is stretched. Scale in on pullbacks to the entry zone.",
                    suitability="high",
                    rationale="Overbought momentum with a buy signal — chasing adds risk.",
                )
            )
        elif indicators.pct_from_52w_high is not None and indicators.pct_from_52w_high > -3:
            strategies.append(
                MarketStrategy(
                    id="breakout",
                    title="Breakout Play",
                    description="Price is near 52-week highs with conviction. Enter on a clean breakout above resistance.",
                    suitability="high",
                    rationale="Strong signal near highs suggests continuation potential.",
                )
            )
        else:
            strategies.append(
                MarketStrategy(
                    id="swing_trade",
                    title="Swing Trade",
                    description="Use the entry zone for limit orders; trail stop below SMA 50 or recent swing low.",
                    suitability="high",
                    rationale=f"Conviction {result.confidence}% buy with favorable risk/reward setup.",
                )
            )

    if not result.conviction_met and result.raw_signal in {
        Signal.BUY,
        Signal.STRONG_BUY,
        Signal.SELL,
        Signal.STRONG_SELL,
    }:
        strategies.append(
            MarketStrategy(
                id="wait_for_confirmation",
                title="Wait for Confirmation",
                description="Raw signal exists but confidence is below threshold. Stay flat until conviction improves.",
                suitability="high",
                rationale="Conviction filter downgraded actionable signal to HOLD.",
            )
        )

    if (
        result.signal in {Signal.BUY, Signal.STRONG_BUY}
        and indicators.return_1m_pct is not None
        and indicators.return_1m_pct > 10
    ):
        strategies.append(
            MarketStrategy(
                id="avoid_chase",
                title="Avoid Chase",
                description="Strong 1-month rally already in place. Do not add at current levels without a pullback plan.",
                suitability="high",
                rationale=f"1-month return is {indicators.return_1m_pct:.1f}% — extended move.",
            )
        )

    if result.signal == Signal.HOLD and rsi is not None and rsi > 70:
        strategies.append(
            MarketStrategy(
                id="wait_for_dip",
                title="Wait for Dip",
                description="Overbought with no clear edge. Let price cool off toward SMA 20 before considering entries.",
                suitability="medium",
                rationale="RSI above 70 without a high-conviction buy signal.",
            )
        )

    if result.signal in {Signal.SELL, Signal.STRONG_SELL} and result.conviction_met:
        strategies.append(
            MarketStrategy(
                id="reduce_exposure",
                title="Reduce Exposure",
                description="Bearish setup with conviction. Trim positions or hedge; avoid new longs.",
                suitability="high",
                rationale=f"{result.signal.value} signal at {result.confidence}% confidence.",
            )
        )

    if is_index and result.signal == Signal.HOLD:
        strategies.append(
            MarketStrategy(
                id="index_neutral",
                title="Index Neutral",
                description="No strong directional bias on the index. Prefer stock-specific setups or range strategies.",
                suitability="medium",
                rationale="Index in HOLD — breadth may be mixed; stock selection matters more.",
            )
        )

    if (
        result.trade_plan.risk_reward_ratio is not None
        and result.trade_plan.risk_reward_ratio >= 2
        and result.signal in {Signal.BUY, Signal.STRONG_BUY}
    ):
        strategies.append(
            MarketStrategy(
                id="risk_reward_favorable",
                title="Favorable Risk/Reward",
                description="Projected reward exceeds risk by 2:1 or better. Size position accordingly.",
                suitability="medium",
                rationale=f"Risk/reward ratio 1:{result.trade_plan.risk_reward_ratio:.2f}.",
            )
        )

    if (
        indicators.sma_20 is not None
        and indicators.sma_50 is not None
        and indicators.sma_20 > indicators.sma_50
        and result.signal == Signal.HOLD
        and rsi is not None
        and 40 <= rsi <= 65
    ):
        strategies.append(
            MarketStrategy(
                id="accumulate_on_dips",
                title="Accumulate on Dips",
                description="Uptrend intact but no trigger yet. Build positions gradually near support levels.",
                suitability="medium",
                rationale="SMA 20 above SMA 50 with neutral RSI — trend up, timing unclear.",
            )
        )

    if not strategies:
        strategies.append(
            MarketStrategy(
                id="stay_sidelines",
                title="Stay on Sidelines",
                description="No compelling strategy right now. Monitor for a clearer setup.",
                suitability="low",
                rationale="Mixed or neutral technical picture.",
            )
        )

    seen: set[str] = set()
    unique: list[dict] = []
    for strategy in strategies:
        if strategy.id in seen:
            continue
        seen.add(strategy.id)
        unique.append(
            {
                "id": strategy.id,
                "title": strategy.title,
                "description": strategy.description,
                "suitability": strategy.suitability,
                "rationale": strategy.rationale,
            }
        )
    return unique
