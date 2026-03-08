"""
main.py - WhiteLight Paper Trading Simulator Entry Point

This is the main script that orchestrates:
1. Load configuration
2. Fetch market data (NDX, TQQQ, SQQQ, QQQ)
3. Compute technical indicators on NDX
4. Run all 7 WhiteLight strategies
5. Execute paper trades in the simulator
6. Generate HTML dashboard + CSV outputs
7. Save state for next run

Usage:
    python main.py                  # Normal run (backfill or incremental)
    python main.py --reset          # Reset state and run fresh backfill
    python main.py --days 60        # Override lookback days

Designed for GitHub Actions daily cron runs.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import yaml

from data_fetcher import DataFetcher
from indicators import compute_all_indicators
from strategies import WhiteLightStrategies
from simulator import Simulator
from dashboard import generate_dashboard, save_dashboard, save_csvs

# ---- Logging Setup ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("WhiteLight")


def load_config(path: str = "config.yaml") -> dict:
    """Load YAML configuration."""
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    logger.info(f"Config loaded from {path}")
    return config


def main():
    parser = argparse.ArgumentParser(description="WhiteLight Paper Trading Simulator")
    parser.add_argument("--reset", action="store_true", help="Reset state and backfill")
    parser.add_argument("--days", type=int, help="Override lookback days")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("WhiteLight Paper Trading Simulator")
    logger.info(f"Run time: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # 1. Load config
    config = load_config(args.config)
    if args.days:
        config["simulation"]["lookback_days"] = args.days
        logger.info(f"Lookback overridden to {args.days} days")

    # 2. Fetch market data
    logger.info("--- Fetching Market Data ---")
    fetcher = DataFetcher(config)
    try:
        market_data = fetcher.fetch_all()
    except Exception as e:
        logger.error(f"Data fetch failed: {e}")
        sys.exit(1)

    ndx_data = market_data["index"]
    logger.info(f"NDX data: {len(ndx_data)} rows")

    # 3. Compute indicators on NDX
    logger.info("--- Computing Indicators ---")
    indicators = compute_all_indicators(ndx_data, config)

    # Drop rows where SMA250 is NaN (need full lookback)
    valid_start = indicators["SMA250"].first_valid_index()
    if valid_start is not None:
        indicators = indicators.loc[valid_start:]
    logger.info(f"Valid indicator rows: {len(indicators)}")

    # 4. Initialize strategies and simulator
    logger.info("--- Initializing Strategies ---")
    strategies = WhiteLightStrategies(config)
    simulator = Simulator(config)

    # 5. Load or reset state
    state_loaded = False
    if not args.reset:
        state_loaded = simulator.load_state()

    if state_loaded:
        # Incremental mode: only process new days
        logger.info("--- Running Incremental Update ---")
        last_date_str = simulator.portfolio.equity_history[-1]["date"] if simulator.portfolio.equity_history else None

        if last_date_str:
            last_date = pd.Timestamp(last_date_str)
            new_bars = indicators.loc[indicators.index > last_date]
            logger.info(f"New bars since {last_date_str}: {len(new_bars)}")

            for i in range(len(new_bars)):
                bar_idx = indicators.index.get_loc(new_bars.index[i])
                signal = strategies.evaluate(indicators, bar_idx)
                simulator.run_daily(signal, market_data)
                logger.info(
                    f"  {signal.date.date()}: TQQQ={signal.tqqq_weight:.0%} "
                    f"SQQQ={signal.sqqq_weight:.0%} Cash={signal.cash_weight:.0%} "
                    f"Active: {signal.active_strategies}"
                )
        else:
            state_loaded = False  # Force backfill

    if not state_loaded:
        # Backfill mode: run full simulation
        logger.info("--- Running Full Backfill ---")
        signals = []
        for i in range(len(indicators)):
            signal = strategies.evaluate(indicators, i)
            signals.append(signal)

        logger.info(f"Generated {len(signals)} daily signals")
        simulator.run_backfill(signals, market_data)
        logger.info(f"Backfill complete: {len(simulator.portfolio.equity_history)} equity rows")

    # 6. Calculate performance stats
    logger.info("--- Performance Stats ---")
    stats = simulator.get_performance_stats()
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")

    # 7. Save outputs
    logger.info("--- Saving Outputs ---")
    Path(config["outputs"]["csv_dir"]).mkdir(parents=True, exist_ok=True)

    # Save CSVs
    save_csvs(simulator.portfolio, config)

    # Generate and save dashboard
    benchmark = market_data.get("benchmark")
    html = generate_dashboard(
        equity_history=simulator.portfolio.equity_history,
        trade_log=simulator.portfolio.trade_log,
        signal_log=simulator.portfolio.signal_log,
        stats=stats,
        benchmark_data=benchmark,
        config=config,
    )
    dashboard_path = save_dashboard(html, config)

    # Save state for next run
    simulator.save_state()

    logger.info("=" * 60)
    logger.info(f"Dashboard: {dashboard_path}")
    logger.info(f"Equity: ${stats.get('current_equity', 0):,.2f}")
    logger.info(f"Return: {stats.get('total_return_pct', 0):+.1f}%")
    logger.info("=" * 60)
    logger.info("Done!")


# Need pandas for date parsing in incremental mode
import pandas as pd

if __name__ == "__main__":
    main()
