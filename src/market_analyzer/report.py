from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import AnalysisResult, Signal


SIGNAL_COLORS = {
    Signal.STRONG_BUY: "bold green",
    Signal.BUY: "green",
    Signal.HOLD: "yellow",
    Signal.SELL: "red",
    Signal.STRONG_SELL: "bold red",
}


def render_analysis(result: AnalysisResult, console: Console | None = None) -> None:
    console = console or Console()
    symbol = result.symbol

    header = (
        f"{symbol.display_name} ({symbol.input_symbol}) | "
        f"{symbol.exchange.value} | Yahoo: {symbol.yahoo_symbol}"
    )
    console.print(Panel(header, title="Market Analysis", border_style="cyan"))

    price_line = f"Price: {result.currency} {result.price:,.2f}"
    if result.day_change_pct is not None:
        sign = "+" if result.day_change_pct >= 0 else ""
        price_line += f" ({sign}{result.day_change_pct:.2f}% today)"
    if result.volume is not None:
        price_line += f" | Volume: {result.volume:,.0f}"

    console.print(price_line)

    signal_style = SIGNAL_COLORS.get(result.signal, "white")
    signal_line = (
        f"{result.signal.value}  |  Confidence: {result.confidence}%  |  Score: {result.score}"
    )
    if result.raw_signal != result.signal:
        signal_line += f"  |  Raw: {result.raw_signal.value}"
    console.print(
        Panel(
            Text(signal_line, style=signal_style),
            title="Signal",
        )
    )

    console.print(Panel(result.action_advice, title="Action", border_style="bold cyan"))
    console.print(result.summary)

    if result.market_insight:
        insight = result.market_insight
        insight_table = Table(title="Market Insight", show_header=True, header_style="bold")
        insight_table.add_column("Field")
        insight_table.add_column("Value")
        insight_table.add_row("Regime", str(insight.get("regime", "N/A")))
        insight_table.add_row("Trend Strength", f"{insight.get('trend_strength', 'N/A')}%")
        insight_table.add_row("Support", _fmt(insight.get("support_level")))
        insight_table.add_row("Resistance", _fmt(insight.get("resistance_level")))
        insight_table.add_row("ATR %", _fmt(insight.get("atr_pct"), suffix="%"))
        insight_table.add_row("Providers", ", ".join(result.data_providers or []) or "N/A")
        if result.quote_agreement_pct is not None:
            insight_table.add_row("Price Agreement", f"{result.quote_agreement_pct:.1f}%")
        console.print(insight_table)
        console.print(Panel(insight.get("thesis", ""), title="Thesis", border_style="dim"))
        if insight.get("provider_summary"):
            console.print(f"[dim]{insight['provider_summary']}[/dim]")

    plan = result.trade_plan
    trade = Table(title="Trade Plan", show_header=True, header_style="bold")
    trade.add_column("Level")
    trade.add_column("Price", justify="right")
    trade.add_row("Entry Zone", _range(plan.entry_low, plan.entry_high, result.currency))
    trade.add_row("Stop Loss", _money(plan.stop_loss, result.currency))
    trade.add_row("Target 1", _money(plan.target_1, result.currency))
    trade.add_row("Target 2", _money(plan.target_2, result.currency))
    trade.add_row(
        "Risk/Reward",
        "N/A" if plan.risk_reward_ratio is None else f"1:{plan.risk_reward_ratio:.2f}",
    )
    console.print(trade)

    if result.beginner_guide:
        _render_beginner_guide(console, result.beginner_guide)

    metrics = Table(title="Key Metrics", show_header=True, header_style="bold")
    metrics.add_column("Metric")
    metrics.add_column("Value", justify="right")
    metrics.add_row("52W High", _fmt(result.fifty_two_week_high))
    metrics.add_row("52W Low", _fmt(result.fifty_two_week_low))
    metrics.add_row("SMA 20", _fmt(result.indicators.sma_20))
    metrics.add_row("SMA 50", _fmt(result.indicators.sma_50))
    metrics.add_row("SMA 200", _fmt(result.indicators.sma_200))
    metrics.add_row("RSI (14)", _fmt(result.indicators.rsi_14))
    metrics.add_row("MACD", _fmt(result.indicators.macd))
    metrics.add_row("MACD Signal", _fmt(result.indicators.macd_signal))
    metrics.add_row("Volume Ratio", _fmt(result.indicators.volume_ratio, suffix="x"))
    metrics.add_row("1M Return", _fmt(result.indicators.return_1m_pct, suffix="%"))
    metrics.add_row("3M Return", _fmt(result.indicators.return_3m_pct, suffix="%"))
    metrics.add_row("From 52W High", _fmt(result.indicators.pct_from_52w_high, suffix="%"))
    metrics.add_row("From 52W Low", _fmt(result.indicators.pct_from_52w_low, suffix="%"))
    console.print(metrics)

    factors = Table(title="Signal Breakdown", show_header=True, header_style="bold")
    factors.add_column("Factor")
    factors.add_column("Score", justify="right")
    factors.add_column("Weight", justify="right")
    factors.add_column("Note")
    for detail in result.signal_details:
        factors.add_row(detail.factor, str(detail.score), str(detail.weight), detail.note)
    console.print(factors)

    recent = Table(title="Recent Sessions", show_header=True, header_style="bold")
    recent.add_column("Date")
    recent.add_column("Close", justify="right")
    recent.add_column("Volume", justify="right")
    for bar in result.recent_bars:
        recent.add_row(bar.date, f"{bar.close:,.2f}", f"{bar.volume:,.0f}")
    console.print(recent)

    risks = Table(title="Risk Flags", show_header=False)
    for risk in result.risks:
        risks.add_row(f"• {risk}")
    console.print(risks)

    console.print(
        Panel(
            "Educational analysis only. Not investment advice. Validate with your own research and risk plan.",
            border_style="dim",
        )
    )


def _render_beginner_guide(console: Console, guide: dict) -> None:
    for lang_key, title in (("english", "Beginner Guide (English)"), ("hinglish", "Beginner Guide (Hinglish)")):
        section = guide.get(lang_key)
        if not section and lang_key == "english":
            section = guide
        if not section:
            continue
        verdict = section.get("verdict", {})
        lines = [
            f"[bold]{verdict.get('headline', '')}[/bold]",
            verdict.get("simple_summary", ""),
            "",
            "[bold]Why this could work:[/bold]",
            *[f"  • {item}" for item in section.get("why_yes", [])[:4]],
            "",
            "[bold]Why to be careful:[/bold]",
            *[f"  • {item}" for item in section.get("why_no", [])[:4]],
            "",
            f"[bold]Signal:[/bold] {section.get('signal_explained', {}).get('what_it_means', '')}",
            "",
            f"[dim]{section.get('disclaimer', '')}[/dim]",
        ]
        console.print(Panel("\n".join(lines), title=title, border_style="blue"))


def analysis_to_dict(result: AnalysisResult) -> dict:
    return {
        "symbol": {
            "input": result.symbol.input_symbol,
            "yahoo": result.symbol.yahoo_symbol,
            "exchange": result.symbol.exchange.value,
            "name": result.symbol.display_name,
        },
        "price": result.price,
        "previous_close": result.previous_close,
        "day_change_pct": result.day_change_pct,
        "volume": result.volume,
        "fifty_two_week_high": result.fifty_two_week_high,
        "fifty_two_week_low": result.fifty_two_week_low,
        "currency": result.currency,
        "signal": result.signal.value,
        "raw_signal": result.raw_signal.value,
        "confidence": result.confidence,
        "score": result.score,
        "conviction_met": result.conviction_met,
        "action_advice": result.action_advice,
        "trade_plan": {
            "entry_low": result.trade_plan.entry_low,
            "entry_high": result.trade_plan.entry_high,
            "stop_loss": result.trade_plan.stop_loss,
            "target_1": result.trade_plan.target_1,
            "target_2": result.trade_plan.target_2,
            "risk_reward_ratio": result.trade_plan.risk_reward_ratio,
        },
        "summary": result.summary,
        "resolved_from": result.resolved_from,
        "data_providers": result.data_providers or [],
        "quote_agreement_pct": result.quote_agreement_pct,
        "market_insight": result.market_insight,
        "indicators": {
            "sma_20": result.indicators.sma_20,
            "sma_50": result.indicators.sma_50,
            "sma_200": result.indicators.sma_200,
            "rsi_14": result.indicators.rsi_14,
            "macd": result.indicators.macd,
            "macd_signal": result.indicators.macd_signal,
            "macd_histogram": result.indicators.macd_histogram,
            "avg_volume_20": result.indicators.avg_volume_20,
            "volume_ratio": result.indicators.volume_ratio,
            "pct_from_52w_high": result.indicators.pct_from_52w_high,
            "pct_from_52w_low": result.indicators.pct_from_52w_low,
            "return_1m_pct": result.indicators.return_1m_pct,
            "return_3m_pct": result.indicators.return_3m_pct,
        },
        "signal_details": [
            {
                "factor": detail.factor,
                "score": detail.score,
                "weight": detail.weight,
                "note": detail.note,
            }
            for detail in result.signal_details
        ],
        "recent_bars": [
            {
                "date": bar.date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in result.recent_bars
        ],
        "risks": result.risks,
        "beginner_guide": result.beginner_guide,
        "chart_data": result.chart_data,
    }


def write_json_report(result: AnalysisResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(analysis_to_dict(result), indent=2), encoding="utf-8")


def _fmt(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{value:,.2f}{suffix}"


def _money(value: float | None, currency: str) -> str:
    if value is None:
        return "N/A"
    return f"{currency} {value:,.2f}"


def _range(low: float | None, high: float | None, currency: str) -> str:
    if low is None or high is None:
        return "N/A"
    return f"{currency} {low:,.2f} - {high:,.2f}"
