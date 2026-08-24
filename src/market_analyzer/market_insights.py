from __future__ import annotations

from dataclasses import dataclass

from .indicators import AdvancedIndicators
from .models import AnalysisResult, IndicatorSnapshot, Signal
from .providers.base import MarketData


@dataclass
class MarketInsight:
    regime: str
    trend_strength: int
    support_level: float | None
    resistance_level: float | None
    atr_pct: float | None
    thesis: str
    provider_summary: str
    fundamentals: dict


def build_market_insight(
    result_partial: dict,
    market_data: MarketData,
    advanced: AdvancedIndicators,
    indicators: IndicatorSnapshot,
    signal: Signal,
    confidence: int,
) -> MarketInsight:
    fundamentals = dict(market_data.fundamentals)
    regime = advanced.market_regime or "unknown"
    trend_strength = advanced.trend_strength or 0

    thesis = _build_thesis(
        name=result_partial.get("name", "Instrument"),
        signal=signal,
        confidence=confidence,
        indicators=indicators,
        advanced=advanced,
        fundamentals=fundamentals,
    )
    provider_summary = _provider_summary(market_data)

    return MarketInsight(
        regime=regime,
        trend_strength=trend_strength,
        support_level=advanced.support_level,
        resistance_level=advanced.resistance_level,
        atr_pct=advanced.atr_pct,
        thesis=thesis,
        provider_summary=provider_summary,
        fundamentals=fundamentals,
    )


def insight_to_dict(insight: MarketInsight) -> dict:
    return {
        "regime": insight.regime,
        "trend_strength": insight.trend_strength,
        "support_level": insight.support_level,
        "resistance_level": insight.resistance_level,
        "atr_pct": insight.atr_pct,
        "thesis": insight.thesis,
        "provider_summary": insight.provider_summary,
        "fundamentals": insight.fundamentals,
    }


def _build_thesis(
    name: str,
    signal: Signal,
    confidence: int,
    indicators: IndicatorSnapshot,
    advanced: AdvancedIndicators,
    fundamentals: dict,
) -> str:
    parts: list[str] = []

    regime_text = {
        "trending_up": "in an uptrend",
        "trending_down": "in a downtrend",
        "ranging": "range-bound",
        "volatile": "high-volatility",
    }.get(advanced.market_regime or "", "mixed")

    parts.append(f"{name} is {regime_text} with {advanced.trend_strength or 0}% trend strength.")

    if indicators.rsi_14 is not None:
        if indicators.rsi_14 > 70:
            parts.append(f"Momentum is stretched (RSI {indicators.rsi_14:.1f}).")
        elif indicators.rsi_14 < 30:
            parts.append(f"Momentum is washed out (RSI {indicators.rsi_14:.1f}).")
        else:
            parts.append(f"Momentum is neutral (RSI {indicators.rsi_14:.1f}).")

    if advanced.support_level and advanced.resistance_level:
        parts.append(
            f"Near-term support sits near {advanced.support_level:.2f} "
            f"and resistance near {advanced.resistance_level:.2f}."
        )

    if advanced.atr_pct is not None:
        parts.append(f"Daily volatility is about {advanced.atr_pct:.2f}% (ATR-based).")

    sector = fundamentals.get("sector")
    if sector:
        parts.append(f"Sector context: {sector}.")

    parts.append(f"Our model rates this {signal.value.replace('_', ' ')} at {confidence}% confidence.")
    return " ".join(parts)


def _provider_summary(market_data: MarketData) -> str:
    providers = ", ".join(market_data.providers_used) or market_data.provider
    if market_data.quote_agreement_pct is not None:
        return (
            f"Data sourced from {providers}. Cross-provider price agreement: "
            f"{market_data.quote_agreement_pct:.1f}%."
        )
    return f"Data sourced from {providers}. Add ALPHA_VANTAGE_API_KEY for US cross-validation."
