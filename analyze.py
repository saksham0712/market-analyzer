#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from rich.console import Console

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from market_analyzer.analyzer import MarketAnalyzer
from market_analyzer.report import analysis_to_dict, render_analysis, write_json_report
from market_analyzer.signals import SignalConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze NSE/BSE stocks, ETFs, and indices with buy/sell signals."
    )
    parser.add_argument("symbol", nargs="?", help="Symbol to analyze, e.g. TATAGOLD, NIFTY, RELIANCE")
    parser.add_argument("--exchange", choices=["NSE", "BSE", "INDEX", "US"], help="Exchange hint")
    parser.add_argument(
        "--market-type",
        choices=list(
            {
                "index",
                "nse_stock",
                "bse_stock",
                "etf",
                "us_stock",
                "us_etf",
                "us_index",
                "global_index",
            }
        ),
        help="Market type for name/symbol resolution",
    )
    parser.add_argument("--range", default="6mo", help="History range for Yahoo Finance, e.g. 1mo, 6mo, 1y")
    parser.add_argument("--config", type=Path, help="Optional YAML config with watchlist and signal settings")
    parser.add_argument("--watchlist", action="store_true", help="Analyze all symbols from config watchlist")
    parser.add_argument("--json", type=Path, help="Write JSON report to this file")
    parser.add_argument("--json-stdout", action="store_true", help="Print JSON to stdout")
    return parser.parse_args()


def load_config(path: Path | None) -> dict:
    if not path:
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def collect_watchlist_symbols(config: dict) -> list[tuple[str, str | None]]:
    watchlist = config.get("watchlist", {})
    symbols: list[tuple[str, str | None]] = []

    for item in watchlist.get("indices", []):
        symbols.append((item.get("yahoo") or item.get("symbol"), "INDEX"))

    for bucket in ("stocks", "etfs"):
        for item in watchlist.get(bucket, []):
            symbols.append((item["symbol"], item.get("exchange", "NSE")))

    return symbols


def main() -> int:
    args = parse_args()
    console = Console()
    config = load_config(args.config)

    defaults = config.get("defaults", {})
    history_range = args.range or defaults.get("history_range", "6mo")
    signal_settings = config.get("signals", {})
    signal_config = SignalConfig(
        rsi_oversold=signal_settings.get("rsi_oversold", 30),
        rsi_overbought=signal_settings.get("rsi_overbought", 70),
        volume_spike_multiplier=signal_settings.get("volume_spike_multiplier", 1.5),
        min_confidence=signal_settings.get("min_confidence", 50),
    )
    analyzer = MarketAnalyzer(history_range=history_range, signal_config=signal_config)

    targets: list[tuple[str, str | None, str | None]] = []
    if args.watchlist:
        watchlist = collect_watchlist_symbols(config)
        if not watchlist:
            console.print("[red]No watchlist found in config.[/red]")
            return 1
        targets = [(symbol, exchange, None) for symbol, exchange in watchlist]
    elif args.symbol:
        targets = [(args.symbol, args.exchange, args.market_type)]
    else:
        console.print("[red]Provide a symbol or use --watchlist with --config.[/red]")
        return 1

    exit_code = 0
    for index, (symbol, exchange, market_type) in enumerate(targets):
        try:
            result = analyzer.analyze(symbol, exchange=exchange, market_type=market_type)
            if index > 0:
                console.print()
            render_analysis(result, console=console)

            if args.json:
                write_json_report(result, args.json)
                console.print(f"[dim]JSON report written to {args.json}[/dim]")
            if args.json_stdout:
                import json

                print(json.dumps(analysis_to_dict(result), indent=2))
        except Exception as exc:
            exit_code = 1
            console.print(f"[red]Failed to analyze {symbol}: {exc}[/red]")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
