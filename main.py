"""
main.py - APEX TRADE LAB Entry Point (Flat Structure)
All files in root directory - no subfolders needed.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import yaml
import pandas as pd

from data_fetcher import DataFetcher
from indicators import compute_all_indicators
from strategies import WhiteLightStrategies
from simulator import Simulator
from dashboard import generate_dashboard, save_dashboard, save_csvs
from signal_exporter import export_daily_signal
from social_content import generate_social_content

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("APEX")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="APEX TRADE LAB")
    parser.add_argument("--reset", action="store_true", help="Reset state and backfill")
    parser.add_argument("--days", type=int, help="Override lookback days")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--stress-test", action="store_true", help="Run stress tests")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("APEX TRADE LAB — Systematic Trading Research Platform")
    logger.info(f"Run: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    config = load_config(args.config)
    if args.days:
        config["simulation"]["lookback_days"] = args.days

    # 1. Fetch data
    logger.info("--- Fetching Market Data ---")
    fetcher = DataFetcher(config)
    try:
        market_data = fetcher.fetch_all()
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        sys.exit(1)

    ndx_data = market_data["index"]
    logger.info(f"NDX: {len(ndx_data)} rows")

    # 2. Indicators
    logger.info("--- Computing Indicators ---")
    indicators = compute_all_indicators(ndx_data, config)
    valid_start = indicators["SMA250"].first_valid_index()
    if valid_start is not None:
        indicators = indicators.loc[valid_start:]
    logger.info(f"Valid rows: {len(indicators)}")

    # 3. Strategies + Simulation
    logger.info("--- Running Simulation ---")
    strategies = WhiteLightStrategies(config)
    simulator = Simulator(config)

    state_loaded = False
    if not args.reset:
        state_loaded = simulator.load_state()

    if state_loaded:
        last_date_str = simulator.portfolio.equity_history[-1]["date"] if simulator.portfolio.equity_history else None
        if last_date_str:
            last_date = pd.Timestamp(last_date_str)
            new_bars = indicators.loc[indicators.index > last_date]
            logger.info(f"New bars since {last_date_str}: {len(new_bars)}")
            for i in range(len(new_bars)):
                bar_idx = indicators.index.get_loc(new_bars.index[i])
                signal = strategies.evaluate(indicators, bar_idx)
                simulator.run_daily(signal, market_data)
        else:
            state_loaded = False

    if not state_loaded:
        logger.info("--- Full Backfill ---")
        signals = []
        for i in range(len(indicators)):
            signal = strategies.evaluate(indicators, i)
            signals.append(signal)
        logger.info(f"{len(signals)} daily signals generated")
        simulator.run_backfill(signals, market_data)

    # 4. Stats
    stats = simulator.get_performance_stats()
    logger.info(f"Equity: ${stats.get('current_equity', 0):,.2f} | Return: {stats.get('total_return_pct', 0):+.1f}%")

    # 5. Save CSVs
    logger.info("--- Saving Outputs ---")
    Path(config["outputs"]["csv_dir"]).mkdir(parents=True, exist_ok=True)
    save_csvs(simulator.portfolio, config)

    # 6. Export daily signal JSON
    daily_signal = export_daily_signal(
        simulator.portfolio.equity_history,
        simulator.portfolio.signal_log,
        config,
    )

    # 7. Generate social content
    try:
        social_posts = generate_social_content(
            simulator.portfolio.equity_history,
            simulator.portfolio.trade_log,
            stats, daily_signal, config,
        )
    except Exception as e:
        logger.warning(f"Social content generation failed: {e}")
        social_posts = []

    # 8. Stress tests (optional, slow)
    stress_results = []
    if args.stress_test:
        logger.info("--- Running Stress Tests ---")
        from stress_test import run_stress_tests
        stress_results = run_stress_tests(config)

    # Load existing stress test data if available
    stress_csv = Path(config["outputs"]["csv_dir"]) / config["outputs"]["stress_test_csv"]
    if stress_csv.exists() and not stress_results:
        stress_results = pd.read_csv(stress_csv).to_dict("records")

    # 9. Generate dashboard
    logger.info("--- Generating Dashboard ---")
    html = generate_dashboard(
        equity_history=simulator.portfolio.equity_history,
        trade_log=simulator.portfolio.trade_log,
        signal_log=simulator.portfolio.signal_log,
        stats=stats,
        benchmark_data=market_data.get("benchmark"),
        config=config,
        stress_results=stress_results,
        social_posts=social_posts,
    )
    save_dashboard(html, config)

    # 10. Save state
    simulator.save_state()

    logger.info("=" * 60)
    logger.info("Done!")


if __name__ == "__main__":
    main()
