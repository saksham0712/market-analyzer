from __future__ import annotations

from .chart_data import build_chart_data
from .beginner_guide import build_beginner_guide
from .data_provider import DataProvider
from .indicators import compute_indicators
from .market_insights import build_market_insight, insight_to_dict
from .models import AnalysisResult, Signal
from .signals import SignalConfig, SignalEngine
from .symbol_resolver import resolve_user_symbol
from .trade_plan import apply_conviction_filter, build_action_advice, build_trade_plan


class MarketAnalyzer:
    def __init__(
        self,
        history_range: str = "6mo",
        interval: str = "1d",
        signal_config: SignalConfig | None = None,
    ) -> None:
        self.data_provider = DataProvider(history_range=history_range, interval=interval)
        self.signal_engine = SignalEngine(config=signal_config)
        self.signal_config = signal_config or SignalConfig()

    def analyze(
        self,
        symbol: str,
        exchange: str | None = None,
        market_type: str | None = None,
    ) -> AnalysisResult:
        symbol_info, resolved_from = resolve_user_symbol(symbol, exchange=exchange, market_type=market_type)
        market_data = self.data_provider.fetch(symbol_info)
        indicators, enriched_frame, advanced = compute_indicators(market_data)

        latest = market_data.frame.iloc[-1]
        price = float(latest["Close"])
        previous_close = float(market_data.frame.iloc[-2]["Close"]) if len(market_data.frame) > 1 else None
        day_change_pct = None
        if previous_close:
            day_change_pct = ((price - previous_close) / previous_close) * 100

        volume = float(latest.get("Volume", 0) or 0)
        raw_signal, confidence, score, details = self.signal_engine.generate(price, indicators)
        signal, conviction_met = apply_conviction_filter(
            raw_signal,
            confidence,
            self.signal_config.min_confidence,
        )
        recent_bars = self.data_provider.recent_bars(market_data, count=10)
        trade_plan = build_trade_plan(
            price=price,
            indicators=indicators,
            signal=signal,
            raw_signal=raw_signal,
            fifty_two_week_high=market_data.fifty_two_week_high,
            fifty_two_week_low=market_data.fifty_two_week_low,
            recent_bars=recent_bars,
        )
        chart_data = build_chart_data(enriched_frame, trade_plan, chart_range="6m")
        action_advice = build_action_advice(
            signal=signal,
            raw_signal=raw_signal,
            confidence=confidence,
            conviction_met=conviction_met,
            indicators=indicators,
        )
        insight = build_market_insight(
            result_partial={"name": symbol_info.display_name},
            market_data=market_data,
            advanced=advanced,
            indicators=indicators,
            signal=signal,
            confidence=confidence,
        )
        risks = self._build_risks(indicators, signal, raw_signal, conviction_met, advanced)
        summary = self._build_summary(
            symbol_info.display_name,
            signal,
            raw_signal,
            confidence,
            conviction_met,
            action_advice,
            indicators,
            resolved_from,
        )

        result = AnalysisResult(
            symbol=symbol_info,
            price=price,
            previous_close=previous_close,
            day_change_pct=day_change_pct,
            volume=volume,
            fifty_two_week_high=market_data.fifty_two_week_high,
            fifty_two_week_low=market_data.fifty_two_week_low,
            currency=market_data.currency,
            indicators=indicators,
            signal=signal,
            raw_signal=raw_signal,
            confidence=confidence,
            score=score,
            conviction_met=conviction_met,
            action_advice=action_advice,
            trade_plan=trade_plan,
            signal_details=details,
            recent_bars=recent_bars,
            summary=summary,
            risks=risks,
            resolved_from=resolved_from,
            data_providers=market_data.providers_used,
            quote_agreement_pct=market_data.quote_agreement_pct,
            market_insight=insight_to_dict(insight),
            chart_data=chart_data,
        )
        result.beginner_guide = build_beginner_guide(result)
        return result

    def _build_risks(self, indicators, signal, raw_signal, conviction_met, advanced) -> list[str]:
        risks: list[str] = []
        if not conviction_met and raw_signal != Signal.HOLD:
            risks.append(
                f"Raw signal was {raw_signal.value}, but confidence is below "
                f"{self.signal_config.min_confidence}% — downgraded to HOLD."
            )
        if advanced.market_regime == "volatile":
            risks.append("Volatility regime detected; wider stops and smaller size are prudent.")
        if indicators.rsi_14 and indicators.rsi_14 > 70:
            risks.append("RSI is overbought; short-term pullback risk is elevated.")
        if indicators.rsi_14 and indicators.rsi_14 < 30:
            risks.append("RSI is oversold; downside may continue before reversal.")
        if indicators.pct_from_52w_low and indicators.pct_from_52w_low > 50:
            risks.append("Price is far above its 52-week low; gains may be stretched.")
        if indicators.pct_from_52w_high and indicators.pct_from_52w_high > -5:
            risks.append("Price is near 52-week high; upside may be limited near-term.")
        if signal in {Signal.BUY, Signal.STRONG_BUY} and indicators.return_1m_pct and indicators.return_1m_pct > 10:
            risks.append("Strong 1-month rally already in place; avoid chasing without a plan.")
        if not risks:
            risks.append("No major technical risk flags detected, but markets can move against any signal.")
        return risks

    def _build_summary(
        self,
        name: str,
        signal: Signal,
        raw_signal: Signal,
        confidence: int,
        conviction_met: bool,
        action_advice: str,
        indicators,
        resolved_from: str | None,
    ) -> str:
        rsi_text = f"RSI {indicators.rsi_14:.1f}" if indicators.rsi_14 is not None else "RSI unavailable"
        raw_text = ""
        if not conviction_met and raw_signal != signal:
            raw_text = f" Raw technical bias: {raw_signal.value}."
        resolved_text = ""
        if resolved_from and resolved_from.upper() != name.upper():
            resolved_text = f" Resolved from search: '{resolved_from}'."
        return (
            f"{name}: {action_advice} Final signal {signal.value} at {confidence}% confidence. "
            f"{rsi_text}.{raw_text}{resolved_text}"
        )
