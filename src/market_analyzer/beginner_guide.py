from __future__ import annotations

from .models import AnalysisResult, Signal

DISCLAIMER = (
    "This guide is for learning only — not financial advice. "
    "Prices can move against any signal. Never invest money you cannot afford to lose. "
    "Talk to a qualified advisor before making investment decisions."
)

GLOSSARY_BASE: dict[str, str] = {
    "RSI": (
        "Relative Strength Index (0–100) measures how fast price has moved recently. "
        "Above 70 often means 'overbought' (may pull back); below 30 means 'oversold' (may bounce)."
    ),
    "MACD": (
        "Moving Average Convergence Divergence tracks momentum. "
        "When MACD crosses above its signal line, momentum is improving; below means weakening."
    ),
    "SMA": (
        "Simple Moving Average — the average closing price over a period (e.g. 20 days). "
        "Price above SMA often means short-term uptrend; below means downtrend."
    ),
    "Stop-loss": (
        "A price level where you exit to limit losses if the trade goes wrong. "
        "Think of it as a safety net — decide it before you buy."
    ),
    "Entry zone": (
        "A price range where buying is considered reasonable based on the analysis. "
        "You don't have to buy at the exact current price — waiting for this zone can help."
    ),
    "Target": (
        "A price level where you might consider taking profit. "
        "Target 1 is nearer; Target 2 is more ambitious."
    ),
    "Risk/Reward": (
        "Compares potential gain vs potential loss. "
        "A 1:2 ratio means you risk ₹1 to potentially make ₹2."
    ),
    "Confidence": (
        "How strongly the technical factors agree with the signal (0–100%). "
        "Low confidence means mixed signals — the app may downgrade to HOLD."
    ),
    "Conviction": (
        "Whether confidence meets the minimum threshold for an actionable BUY or SELL. "
        "If not met, the signal is downgraded to HOLD for safety."
    ),
    "52-week high/low": (
        "The highest and lowest prices in the past year. "
        "Helps you see if the stock is near its peak or has room to run."
    ),
    "Volume": (
        "How many shares traded. Higher-than-normal volume can confirm a move; "
        "low volume may mean the trend is weak."
    ),
    "HOLD": (
        "No clear buy or sell edge right now. "
        "For beginners, this usually means: don't rush in — watch and wait."
    ),
    "BUY": (
        "Technical factors lean bullish with enough conviction. "
        "Still not a guarantee — use the entry zone and stop-loss."
    ),
    "SELL": (
        "Technical factors lean bearish. "
        "If you own it, consider reducing; if you don't, avoid new purchases."
    ),
}


def build_beginner_guide(result: AnalysisResult) -> dict:
    """Return beginner guide in English and Hinglish."""
    name = result.symbol.display_name
    insight = result.market_insight or {}
    why_yes_hi, why_no_hi = _hinglish_pros_cons(result, name)

    return {
        "english": _build_guide_for_language(result, language="english"),
        "hinglish": {
            "disclaimer": _disclaimer("hinglish"),
            "verdict": _build_verdict(result, name, language="hinglish"),
            "why_yes": why_yes_hi,
            "why_no": why_no_hi,
            "checklist": _hinglish_checklist(result, name),
            "signal_explained": _hinglish_signal_explained(result, name),
            "key_levels_explained": _hinglish_key_levels(result),
            "analysis_in_plain_terms": _hinglish_analysis_plain(result, name, insight),
            "risks_plain": _hinglish_risks_plain(result),
            "next_steps": _hinglish_next_steps(result, name),
            "glossary_snippets": _hinglish_glossary(result),
        },
    }


def _build_guide_for_language(result: AnalysisResult, language: str) -> dict:
    name = result.symbol.display_name
    insight = result.market_insight or {}
    why_yes, why_no = _build_pros_cons(result, name, language)

    return {
        "disclaimer": _disclaimer(language),
        "verdict": _build_verdict(result, name, language),
        "why_yes": why_yes,
        "why_no": why_no,
        "checklist": _build_checklist(result, name, language),
        "signal_explained": _build_signal_explained(result, name, language),
        "key_levels_explained": _build_key_levels(result, language),
        "analysis_in_plain_terms": _build_analysis_plain(result, name, insight, language),
        "risks_plain": _build_risks_plain(result, language),
        "next_steps": _build_next_steps(result, name, language),
        "glossary_snippets": _build_glossary_snippets(result, language),
    }


def _disclaimer(language: str) -> str:
    if language == "hinglish":
        return (
            "Yeh guide sirf learning ke liye hai — financial advice nahi. "
            "Price kisi bhi signal ke against move kar sakti hai. "
            "Sirf wahi paisa lagao jo lose karne ki capacity ho. "
            "Invest karne se pehle qualified advisor se baat karna better hai."
        )
    return DISCLAIMER


def _build_verdict(result: AnalysisResult, name: str, language: str = "english") -> dict:
    signal = result.signal
    currency = result.currency
    price = result.price
    hi = language == "hinglish"

    if signal in {Signal.STRONG_BUY, Signal.BUY}:
        recommendation = "consider_buying"
        headline = (
            f"{name} mein buy karne ka lean hai — lekin plan ke saath"
            if hi
            else f"Leaning toward buying {name} — but only with a plan"
        )
        simple = (
            f"App ko {name} ke liye {currency} {price:,.2f} par zyada positive signs dikh rahe hain. "
            f"Iska matlab profit guaranteed nahi — bas charts abhi favourable lag rahe hain."
            if hi
            else (
                f"The app sees more positive than negative technical signs for {name} "
                f"at {currency} {price:,.2f}. That does NOT mean guaranteed profit — "
                f"it means conditions look favourable on the charts right now."
            )
        )
    elif signal in {Signal.STRONG_SELL, Signal.SELL}:
        recommendation = "consider_selling_or_avoiding"
        headline = (
            f"Abhi {name} se door rehna better hai"
            if hi
            else f"Leaning away from {name} right now"
        )
        simple = (
            f"{name} ke technical signs {currency} {price:,.2f} par zyada negative hain. "
            f"Agar holding hai toh risk review karo; nayi entry ideal nahi."
            if hi
            else (
                f"Technical signs for {name} are more negative than positive at "
                f"{currency} {price:,.2f}. If you already own it, consider whether "
                f"you still want the risk. If you don't own it, this is not an ideal entry."
            )
        )
    else:
        recommendation = "wait"
        headline = (
            f"Wait karo — abhi {name} buy karne ka strong reason nahi"
            if hi
            else f"Wait — no strong reason to buy {name} right now"
        )
        simple = (
            f"App ne {name} ke liye HOLD bola hai ({currency} {price:,.2f}). "
            f"Beginners ke liye HOLD ka matlab: jaldi invest mat karo, clear opportunity abhi nahi dikh rahi."
            if hi
            else (
                f"The app says HOLD for {name} at {currency} {price:,.2f}. "
                f"For beginners, HOLD means: don't rush to invest. "
                f"The charts don't show a clear, high-confidence opportunity yet."
            )
        )

    return {
        "recommendation": recommendation,
        "headline": headline,
        "simple_summary": simple,
    }


def _build_pros_cons(result: AnalysisResult, name: str, language: str = "english") -> tuple[list[str], list[str]]:
    why_yes: list[str] = []
    why_no: list[str] = []
    indicators = result.indicators
    signal = result.signal
    price = result.price

    if indicators.sma_20 and price > indicators.sma_20:
        why_yes.append(
            f"Price is above the 20-day average — short-term trend is up for {name}."
        )
    elif indicators.sma_20:
        why_no.append(
            f"Price is below the 20-day average — short-term trend is weak."
        )

    if indicators.sma_50 and indicators.sma_200 and indicators.sma_50 > indicators.sma_200:
        why_yes.append("Longer-term trend (50-day above 200-day) is positive.")
    elif indicators.sma_50 and indicators.sma_200 and indicators.sma_50 < indicators.sma_200:
        why_no.append("Longer-term trend is negative — the stock has been drifting down.")

    if indicators.rsi_14 is not None:
        if 40 <= indicators.rsi_14 <= 60:
            why_yes.append(
                f"RSI is in a neutral zone ({indicators.rsi_14:.1f}) — not overbought or oversold."
            )
        elif indicators.rsi_14 > 70:
            why_no.append(
                f"RSI is overbought ({indicators.rsi_14:.1f}) — price may have run up too fast."
            )
        elif indicators.rsi_14 < 30:
            why_yes.append(
                f"RSI is oversold ({indicators.rsi_14:.1f}) — a bounce is possible, but not guaranteed."
            )

    if indicators.macd is not None and indicators.macd_signal is not None:
        if indicators.macd > indicators.macd_signal:
            why_yes.append("MACD momentum is improving (bullish crossover).")
        else:
            why_no.append("MACD momentum is weakening (bearish crossover).")

    if indicators.volume_ratio and indicators.volume_ratio > 1.2:
        why_yes.append(
            f"Trading volume is above average ({indicators.volume_ratio:.1f}x) — "
            "more people are participating."
        )
    elif indicators.volume_ratio and indicators.volume_ratio < 0.8:
        why_no.append("Volume is below average — the move may lack conviction.")

    if indicators.pct_from_52w_low and indicators.pct_from_52w_low > 40:
        why_no.append(
            f"Price is already {indicators.pct_from_52w_low:.0f}% above its 52-week low — "
            "you may be buying after a big run-up."
        )
    elif indicators.pct_from_52w_low and indicators.pct_from_52w_low < 15:
        why_yes.append("Price is relatively close to its 52-week low — potential value zone.")

    if indicators.pct_from_52w_high and indicators.pct_from_52w_high > -5:
        why_no.append("Price is near its 52-week high — limited upside room near-term.")

    if result.conviction_met and signal in {Signal.BUY, Signal.STRONG_BUY}:
        why_yes.append(
            f"Confidence is {result.confidence}% and meets the conviction threshold — "
            "factors mostly agree."
        )
    elif not result.conviction_met and result.raw_signal != Signal.HOLD:
        why_no.append(
            f"Raw signal was {result.raw_signal.value}, but confidence ({result.confidence}%) "
            "is too low — downgraded to HOLD for safety."
        )

    for detail in result.signal_details:
        if detail.score > 0:
            why_yes.append(f"{detail.factor}: {detail.note}")
        elif detail.score < 0:
            why_no.append(f"{detail.factor}: {detail.note}")

    if not why_yes:
        why_yes.append(f"No strong positive factors stand out for {name} right now.")
    if not why_no:
        why_no.append(f"No major red flags detected, but that doesn't eliminate risk.")

    return _dedupe(why_yes)[:6], _dedupe(why_no)[:6]


def _build_checklist(result: AnalysisResult, name: str, language: str = "english") -> list[dict]:
    items: list[dict] = []
    indicators = result.indicators
    plan = result.trade_plan

    items.append(_check_item(
        "Understand what you're buying",
        "neutral",
        f"{name} ({result.symbol.input_symbol}) on {result.symbol.exchange.value}. "
        "Know what business or asset this represents before investing.",
    ))

    trend_ok = (
        indicators.sma_20 is not None
        and result.price > indicators.sma_20
        and indicators.sma_50 is not None
        and result.price > indicators.sma_50
    )
    items.append(_check_item(
        "Short-term trend supports the idea",
        "pass" if trend_ok else "warn",
        "Price above both 20-day and 50-day averages is a healthier setup."
        if trend_ok
        else "Price is not clearly above key moving averages — trend is mixed or down.",
    ))

    rsi = indicators.rsi_14
    if rsi is not None:
        if rsi > 70:
            items.append(_check_item(
                "RSI not overbought",
                "fail",
                f"RSI is {rsi:.1f} (above 70) — avoid chasing; wait for a pullback.",
            ))
        elif rsi < 30:
            items.append(_check_item(
                "RSI not oversold panic",
                "warn",
                f"RSI is {rsi:.1f} (below 30) — could bounce, but falling knives are risky.",
            ))
        else:
            items.append(_check_item(
                "RSI in a reasonable range",
                "pass",
                f"RSI is {rsi:.1f} — momentum is not extreme.",
            ))

    conviction_status = "pass" if result.conviction_met else "fail"
    items.append(_check_item(
        "Signal has enough conviction",
        conviction_status,
        f"Confidence {result.confidence}% — "
        + ("meets the minimum threshold." if result.conviction_met
           else "below threshold; signal was downgraded to HOLD."),
    ))

    if plan.stop_loss and plan.entry_low:
        items.append(_check_item(
            "You know your stop-loss before buying",
            "neutral",
            f"Suggested stop-loss: {result.currency} {plan.stop_loss:,.2f}. "
            "Never buy without deciding where you'll exit if wrong.",
        ))

    if plan.risk_reward_ratio:
        rr_status = "pass" if plan.risk_reward_ratio >= 1.5 else "warn"
        items.append(_check_item(
            "Risk/reward makes sense",
            rr_status,
            f"Estimated ratio is 1:{plan.risk_reward_ratio:.2f} — "
            + ("reasonable for a planned trade." if plan.risk_reward_ratio >= 1.5
               else "reward may not justify the risk; be cautious."),
        ))

    items.append(_check_item(
        "You can afford to lose this money",
        "neutral",
        "Only invest spare money. Markets can drop 20–50% in bad years.",
    ))

    items.append(_check_item(
        "You've done your own research",
        "neutral",
        "This app uses charts only. Check company fundamentals, news, and your goals too.",
    ))

    return items


def _build_signal_explained(result: AnalysisResult, name: str, language: str = "english") -> dict:
    signal = result.signal
    raw = result.raw_signal

    signal_meanings = {
        Signal.STRONG_BUY: (
            "STRONG BUY means multiple technical factors strongly agree the price could rise. "
            "This is the most bullish rating — but still not a guarantee."
        ),
        Signal.BUY: (
            "BUY means technical factors lean positive. "
            "Consider buying in the entry zone with a stop-loss — don't chase blindly."
        ),
        Signal.HOLD: (
            "HOLD means the app does not see a clear buy or sell opportunity. "
            "For beginners: sit on your hands. Watching is a valid strategy."
        ),
        Signal.SELL: (
            "SELL means technical factors lean negative. "
            "Avoid new purchases; consider reducing if you already hold."
        ),
        Signal.STRONG_SELL: (
            "STRONG SELL means bearish signals are strong. "
            "High risk of further decline — protect your capital."
        ),
    }

    buy_sell_hold = (
        "BUY = charts look favourable (use entry zone + stop-loss). "
        "SELL = charts look unfavourable (avoid or reduce). "
        "HOLD = no clear edge — wait for a better setup."
    )

    raw_vs_final = ""
    if raw != signal:
        raw_vs_final = (
            f"The raw technical reading was {raw.value.replace('_', ' ')}, "
            f"but it was downgraded to {signal.value.replace('_', ' ')} because "
            f"confidence ({result.confidence}%) did not meet the conviction threshold. "
            "This protects you from acting on weak signals."
        )
    else:
        raw_vs_final = (
            f"Both the raw reading and final signal agree: {signal.value.replace('_', ' ')} "
            f"at {result.confidence}% confidence."
        )

    return {
        "signal": signal.value,
        "raw_signal": raw.value,
        "what_it_means": signal_meanings.get(signal, signal_meanings[Signal.HOLD]),
        "buy_sell_hold_plain": buy_sell_hold,
        "confidence_explained": (
            f"Confidence {result.confidence}% measures how much the factors agree. "
            f"{'Conviction threshold met — signal is actionable.' if result.conviction_met else 'Below threshold — treated as HOLD for safety.'}"
        ),
        "raw_vs_final": raw_vs_final,
        "for_this_symbol": (
            f"For {name}, the app currently says {signal.value.replace('_', ' ')}. "
            f"Action advice: {result.action_advice}"
        ),
    }


def _build_key_levels(result: AnalysisResult, language: str = "english") -> dict:
    plan = result.trade_plan
    currency = result.currency
    insight = result.market_insight or {}

    entry_text = "Not available"
    if plan.entry_low and plan.entry_high:
        entry_text = (
            f"If you decide to buy, consider waiting for price between "
            f"{currency} {plan.entry_low:,.2f} and {currency} {plan.entry_high:,.2f}. "
            f"Current price is {currency} {result.price:,.2f}."
        )

    stop_text = "Not available"
    if plan.stop_loss:
        stop_text = (
            f"Set a stop-loss near {currency} {plan.stop_loss:,.2f}. "
            "If price falls to this level, exit to limit your loss. "
            "This is typically 3–5% below your entry."
        )

    target_text = "Not available"
    if plan.target_1:
        parts = [f"First profit target: {currency} {plan.target_1:,.2f}"]
        if plan.target_2:
            parts.append(f"Stretch target: {currency} {plan.target_2:,.2f}")
        target_text = ". ".join(parts) + "."

    support = insight.get("support_level")
    resistance = insight.get("resistance_level")
    support_resistance = ""
    if support and resistance:
        support_resistance = (
            f"Near-term support (floor): {currency} {support:,.2f}. "
            f"Resistance (ceiling): {currency} {resistance:,.2f}."
        )

    return {
        "entry_zone": entry_text,
        "stop_loss": stop_text,
        "targets": target_text,
        "support_resistance": support_resistance or "Support/resistance levels not available.",
        "risk_reward": (
            f"Risk/reward ratio: 1:{plan.risk_reward_ratio:.2f} — "
            "you risk ₹1 to potentially gain this many rupees."
            if plan.risk_reward_ratio
            else "Risk/reward ratio not calculated."
        ),
    }


def _build_analysis_plain(result: AnalysisResult, name: str, insight: dict, language: str = "english") -> str:
    parts: list[str] = []

    parts.append(
        f"{name} is trading at {result.currency} {result.price:,.2f}"
        + (f" ({'+' if (result.day_change_pct or 0) >= 0 else ''}{result.day_change_pct:.2f}% today)"
           if result.day_change_pct is not None else "")
        + "."
    )

    thesis = insight.get("thesis")
    if thesis:
        parts.append(thesis)
    else:
        parts.append(result.summary)

    parts.append(f"In plain terms: {result.action_advice}")

    if result.fifty_two_week_high and result.fifty_two_week_low:
        parts.append(
            f"Over the past year, {name} traded between "
            f"{result.currency} {result.fifty_two_week_low:,.2f} and "
            f"{result.currency} {result.fifty_two_week_high:,.2f}."
        )

    return " ".join(parts)


def _build_risks_plain(result: AnalysisResult, language: str = "english") -> list[str]:
    risks: list[str] = []
    for risk in result.risks:
        risks.append(_simplify_risk(risk))

    risks.extend([
        "Past chart patterns do not predict the future — surprises happen (earnings, news, global events).",
        "This tool does not check company financials, debt, management, or valuation.",
        "You can lose part or all of your investment. Only use money you can afford to lose.",
    ])

    return _dedupe(risks)


def _build_next_steps(result: AnalysisResult, name: str, language: str = "english") -> list[dict]:
    signal = result.signal
    plan = result.trade_plan
    currency = result.currency
    steps: list[dict] = []

    if signal in {Signal.STRONG_BUY, Signal.BUY}:
        steps.append({
            "step": 1,
            "action": "Do not buy at market price blindly",
            "detail": f"Wait for price to reach the entry zone ({currency} {plan.entry_low:,.2f}–{plan.entry_high:,.2f}).",
        })
        steps.append({
            "step": 2,
            "action": "Set your stop-loss before you buy",
            "detail": f"Place a mental or broker stop at {currency} {plan.stop_loss:,.2f}.",
        })
        steps.append({
            "step": 3,
            "action": "Decide your position size",
            "detail": "Risk only 1–2% of your portfolio on this trade. Smaller is safer for beginners.",
        })
        steps.append({
            "step": 4,
            "action": "Know your exit targets",
            "detail": f"Plan to take profit near {currency} {plan.target_1:,.2f} (Target 1).",
        })
        steps.append({
            "step": 5,
            "action": "Re-check before acting",
            "detail": "Run analysis again on the day you plan to buy — signals change daily.",
        })
    elif signal in {Signal.STRONG_SELL, Signal.SELL}:
        steps.append({
            "step": 1,
            "action": "Do not open a new position in " + name,
            "detail": "Technical setup is unfavourable. Look for better opportunities elsewhere.",
        })
        steps.append({
            "step": 2,
            "action": "Review if you already hold this",
            "detail": "Consider whether you still want the risk. Selling is also a valid choice.",
        })
        steps.append({
            "step": 3,
            "action": "Watch for a trend change",
            "detail": "Re-run analysis weekly. A SELL signal can flip to HOLD or BUY later.",
        })
    else:
        steps.append({
            "step": 1,
            "action": "Do nothing for now — and that's okay",
            "detail": f"HOLD means {name} doesn't offer a clear entry. Patience is a strategy.",
        })
        steps.append({
            "step": 2,
            "action": "Add to your watchlist",
            "detail": f"Track {name} and re-analyze in a few days or after a price move.",
        })
        if plan.entry_low and plan.entry_high:
            steps.append({
                "step": 3,
                "action": "Note the ideal entry zone for later",
                "detail": (
                    f"If price dips to {currency} {plan.entry_low:,.2f}–{plan.entry_high:,.2f}, "
                    "re-run analysis — a better setup may appear."
                ),
            })
        if result.indicators.rsi_14 and result.indicators.rsi_14 > 70:
            steps.append({
                "step": 4,
                "action": "Wait for RSI to cool down",
                "detail": (
                    f"RSI is {result.indicators.rsi_14:.1f} (overbought). "
                    "Buying after a pullback is usually safer than chasing."
                ),
            })
        else:
            steps.append({
                "step": 4,
                "action": "Learn while you wait",
                "detail": "Read about the company/ETF, check recent news, and understand why you might want it.",
            })
        steps.append({
            "step": 5,
            "action": "Set a reminder to re-check",
            "detail": "Markets change. Re-analyze in 3–7 days or after a 3%+ price move.",
        })

    return steps


def _build_glossary_snippets(result: AnalysisResult, language: str = "english") -> list[dict]:
    terms_needed = ["HOLD", "BUY", "SELL", "RSI", "MACD", "Stop-loss", "Entry zone", "Confidence", "Conviction"]
    if result.trade_plan.risk_reward_ratio:
        terms_needed.append("Risk/Reward")
    if result.fifty_two_week_high:
        terms_needed.append("52-week high/low")
    if result.indicators.volume_ratio:
        terms_needed.append("Volume")
    if result.indicators.sma_20:
        terms_needed.append("SMA")

    signal_term = result.signal.value.replace("_", " ")
    if signal_term in ("STRONG BUY", "BUY"):
        terms_needed.insert(0, "BUY")
    elif signal_term in ("STRONG SELL", "SELL"):
        terms_needed.insert(0, "SELL")
    else:
        terms_needed.insert(0, "HOLD")

    seen: set[str] = set()
    snippets: list[dict] = []
    for term in terms_needed:
        key = term.upper().replace("-", "_").replace("/", "_")
        lookup = term
        if lookup not in GLOSSARY_BASE:
            lookup = term.replace("_", "-")
        if lookup in GLOSSARY_BASE and lookup not in seen:
            seen.add(lookup)
            snippets.append({"term": term, "explanation": GLOSSARY_BASE[lookup]})

    return snippets


def _check_item(item: str, status: str, detail: str) -> dict:
    return {"item": item, "status": status, "detail": detail}


def _simplify_risk(risk: str) -> str:
    replacements = {
        "RSI is overbought": "The stock may have risen too fast (overbought) — a pullback is possible",
        "RSI is oversold": "The stock has fallen hard (oversold) — it could keep falling before bouncing",
        "conviction is below": "The signal wasn't strong enough to trust — that's why it says HOLD",
        "Volatility regime": "Prices are swinging wildly — use smaller positions and wider stops",
        "52-week high": "Price is near its yearly peak — less room to grow in the short term",
        "52-week low": "Price has already risen a lot from its yearly bottom",
        "1-month rally": "It already went up a lot this month — buying now means chasing",
    }
    for key, plain in replacements.items():
        if key.lower() in risk.lower():
            return f"{plain}. ({risk})"
    return risk


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()[:60]
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _hinglish_pros_cons(result: AnalysisResult, name: str) -> tuple[list[str], list[str]]:
    indicators = result.indicators
    why_yes: list[str] = []
    why_no: list[str] = []
    price = result.price

    if indicators.sma_20 and price > indicators.sma_20:
        why_yes.append(f"Price 20-day average ke upar hai — short-term trend up hai.")
    else:
        why_no.append("Price 20-day average ke neeche hai — short-term trend weak hai.")

    if indicators.rsi_14 and indicators.rsi_14 > 70:
        why_no.append(f"RSI {indicators.rsi_14:.1f} hai (overbought) — yahan chase karna risky hai.")
    elif indicators.rsi_14 and indicators.rsi_14 < 30:
        why_yes.append(f"RSI {indicators.rsi_14:.1f} oversold hai — bounce ho sakta hai, par sure nahi.")

    if result.conviction_met and result.signal in {Signal.BUY, Signal.STRONG_BUY}:
        why_yes.append(f"Confidence {result.confidence}% hai — conviction threshold meet ho raha hai.")
    if not result.conviction_met and result.raw_signal != Signal.HOLD:
        why_no.append(
            f"Raw signal {result.raw_signal.value} tha, par confidence kam hai — safety ke liye HOLD."
        )

    if not why_yes:
        why_yes.append(f"Abhi {name} ke liye koi strong positive factor nahi dikh raha.")
    if not why_no:
        why_no.append("Koi major red flag nahi, par risk hamesha rehta hai.")
    return why_yes[:6], why_no[:6]


def _hinglish_checklist(result: AnalysisResult, name: str) -> list[dict]:
    plan = result.trade_plan
    indicators = result.indicators
    items: list[dict] = [
        _check_item(
            "Samjho kya buy kar rahe ho",
            "neutral",
            f"{name} ({result.symbol.input_symbol}) {result.symbol.exchange.value} par — "
            "pehle business ya ETF samjho.",
        ),
    ]

    trend_ok = (
        indicators.sma_20 is not None
        and result.price > indicators.sma_20
        and indicators.sma_50 is not None
        and result.price > indicators.sma_50
    )
    items.append(_check_item(
        "Short-term trend support karta hai?",
        "pass" if trend_ok else "warn",
        "Price 20-day aur 50-day average ke upar hai — healthier setup."
        if trend_ok
        else "Price key moving averages ke upar clearly nahi — trend mixed ya down.",
    ))

    rsi = indicators.rsi_14
    if rsi is not None:
        if rsi > 70:
            items.append(_check_item(
                "RSI overbought nahi hona chahiye",
                "fail",
                f"RSI {rsi:.1f} hai (70 se upar) — chase mat karo, pullback ka wait karo.",
            ))
        elif rsi < 30:
            items.append(_check_item(
                "RSI oversold panic",
                "warn",
                f"RSI {rsi:.1f} oversold hai — bounce ho sakta hai, par falling knife risky hai.",
            ))
        else:
            items.append(_check_item(
                "RSI reasonable range mein hai",
                "pass",
                f"RSI {rsi:.1f} — momentum extreme nahi hai.",
            ))

    conviction_status = "pass" if result.conviction_met else "fail"
    items.append(_check_item(
        "Signal mein enough conviction hai?",
        conviction_status,
        f"Confidence {result.confidence}% — "
        + ("threshold meet ho raha hai." if result.conviction_met
           else "threshold se neeche; signal HOLD mein downgrade hua."),
    ))

    if plan.stop_loss:
        items.append(_check_item(
            "Stop-loss pehle se decide kiya?",
            "neutral",
            f"Suggested stop-loss: {result.currency} {plan.stop_loss:,.2f}. "
            "Bina exit plan ke buy mat karo.",
        ))

    if plan.risk_reward_ratio:
        rr_status = "pass" if plan.risk_reward_ratio >= 1.5 else "warn"
        items.append(_check_item(
            "Risk/reward sense banata hai?",
            rr_status,
            f"Ratio 1:{plan.risk_reward_ratio:.2f} — "
            + ("planned trade ke liye reasonable." if plan.risk_reward_ratio >= 1.5
               else "reward risk justify nahi kar raha; careful raho."),
        ))

    items.extend([
        _check_item(
            "Sirf spare money use karo",
            "neutral",
            "Sirf wahi paisa lagao jo lose kar sakte ho. Markets 20–50% gir sakte hain.",
        ),
        _check_item(
            "Khud ki research ki?",
            "neutral",
            "Yeh app sirf charts dekhta hai — news, fundamentals, goals bhi check karo.",
        ),
    ])
    return items


def _hinglish_signal_explained(result: AnalysisResult, name: str) -> dict:
    signal = result.signal
    meanings = {
        Signal.HOLD: "HOLD ka matlab abhi clear buy/sell edge nahi — wait karo.",
        Signal.BUY: "BUY ka matlab positive bias hai, par entry zone + stop-loss zaroori hai.",
        Signal.STRONG_BUY: "STRONG BUY matlab factors zyada bullish align hain — phir bhi guarantee nahi.",
        Signal.SELL: "SELL matlab weakness hai — nayi buying avoid karo.",
        Signal.STRONG_SELL: "STRONG SELL matlab bearish pressure strong hai.",
    }
    return {
        "signal": signal.value,
        "raw_signal": result.raw_signal.value,
        "what_it_means": meanings.get(signal, meanings[Signal.HOLD]),
        "buy_sell_hold_plain": "BUY = favourable, SELL = unfavourable, HOLD = wait karo.",
        "confidence_explained": f"Confidence {result.confidence}% — kitne factors agree kar rahe hain.",
        "raw_vs_final": result.action_advice,
        "for_this_symbol": f"{name} ke liye abhi signal {signal.value} hai.",
    }


def _hinglish_key_levels(result: AnalysisResult) -> dict:
    plan = result.trade_plan
    c = result.currency
    insight = result.market_insight or {}

    entry_zone = "Abhi available nahi"
    if plan.entry_low and plan.entry_high:
        entry_zone = (
            f"Agar buy karna ho, price {c} {plan.entry_low:,.2f} se {c} {plan.entry_high:,.2f} "
            f"ke beech ka wait karo. Abhi price {c} {result.price:,.2f} hai."
        )

    stop_loss = "Abhi available nahi"
    if plan.stop_loss:
        stop_loss = (
            f"Stop-loss ~{c} {plan.stop_loss:,.2f} rakho. "
            "Yahan neeche jaaye toh loss limit karke exit karo."
        )

    targets = "Abhi available nahi"
    if plan.target_1:
        parts = [f"Pehla target: {c} {plan.target_1:,.2f}"]
        if plan.target_2:
            parts.append(f"Stretch target: {c} {plan.target_2:,.2f}")
        targets = ". ".join(parts) + "."

    support = insight.get("support_level")
    resistance = insight.get("resistance_level")
    support_resistance = "Support/resistance abhi available nahi."
    if support and resistance:
        support_resistance = (
            f"Support (floor): {c} {support:,.2f}. Resistance (ceiling): {c} {resistance:,.2f}."
        )

    return {
        "entry_zone": entry_zone,
        "stop_loss": stop_loss,
        "targets": targets,
        "support_resistance": support_resistance,
        "risk_reward": (
            f"Risk/Reward 1:{plan.risk_reward_ratio:.2f} — ₹1 risk par itna potential gain."
            if plan.risk_reward_ratio
            else "Risk/reward calculate nahi hua."
        ),
    }


def _hinglish_analysis_plain(result: AnalysisResult, name: str, insight: dict) -> str:
    thesis = insight.get("thesis") or result.summary
    return (
        f"{name} abhi {result.currency} {result.price:,.2f} par trade ho raha hai. "
        f"{result.action_advice} "
        f"Simple words mein: {thesis}"
    )


def _hinglish_risks_plain(result: AnalysisResult) -> list[str]:
    risks = [_simplify_risk_hinglish(r) for r in result.risks[:4]]
    risks.extend([
        "Past performance future guarantee nahi karti — news/events se surprise aa sakta hai.",
        "Yeh tool company fundamentals check nahi karta.",
        "Pura paisa lose bhi ho sakta hai — sirf risk capital use karo.",
    ])
    return _dedupe(risks)


def _hinglish_next_steps(result: AnalysisResult, name: str) -> list[dict]:
    plan = result.trade_plan
    c = result.currency
    if result.signal in {Signal.BUY, Signal.STRONG_BUY}:
        return [
            {"step": 1, "action": "Blind buy mat karo", "detail": f"Entry zone {c} {plan.entry_low:,.2f}-{plan.entry_high:,.2f} ka wait karo."},
            {"step": 2, "action": "Stop-loss set karo", "detail": f"~{c} {plan.stop_loss:,.2f} par exit plan rakho."},
            {"step": 3, "action": "Chhota size rakho", "detail": "Beginner ho toh kam quantity se start karo."},
        ]
    if result.signal in {Signal.SELL, Signal.STRONG_SELL}:
        return [
            {"step": 1, "action": "Nayi entry avoid", "detail": f"{name} abhi weak setup dikha raha hai."},
            {"step": 2, "action": "Holding review", "detail": "Agar already hold karte ho, risk dubara socho."},
        ]
    return [
        {"step": 1, "action": "Abhi kuch mat karo", "detail": "HOLD = patience. Clear entry nahi hai."},
        {"step": 2, "action": "Watchlist mein daalo", "detail": f"{name} ko track karo, 3-7 din baad dubara analyze karo."},
        {"step": 3, "action": "Dip ka wait", "detail": f"Agar price {c} {plan.entry_low:,.2f} zone aaye, phir check karo."},
    ]


def _hinglish_glossary(result: AnalysisResult) -> list[dict]:
    return [
        {"term": "RSI", "explanation": "Momentum meter. 70+ overbought, 30- oversold."},
        {"term": "HOLD", "explanation": "Abhi action mat lo — wait/observe karo."},
        {"term": "Stop-loss", "explanation": "Max loss limit jahan aap exit karne ka plan rakhte ho."},
        {"term": "Entry zone", "explanation": "Woh price range jahan buy karna comparatively better ho."},
        {"term": "Confidence", "explanation": "Kitne technical factors signal se agree kar rahe hain (0-100%)."},
    ]


def _simplify_risk_hinglish(risk: str) -> str:
    if "overbought" in risk.lower():
        return "Stock zyada tezi se up gaya ho sakta hai — pullback aa sakta hai."
    if "52-week low" in risk.lower():
        return "Price 52-week low se bahut upar hai — move stretched ho sakta hai."
    return risk
