"""
main.py - APEX TRADE LAB Entry Point
Auto-runs stress tests on first backfill. Generates daily journal.
"""

import argparse, logging, sys
from datetime import datetime
from pathlib import Path
import yaml, pandas as pd

from data_fetcher import DataFetcher
from indicators import compute_all_indicators
from strategies import WhiteLightStrategies
from simulator import Simulator
from dashboard import generate_dashboard, save_dashboard, save_csvs
from signal_exporter import export_daily_signal
from social_content import generate_social_content
from journal import generate_journal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("APEX")

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="APEX TRADE LAB")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--days", type=int)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--stress-test", action="store_true")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("APEX TRADE LAB")
    logger.info(f"Run: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    config = load_config(args.config)
    if args.days:
        config["simulation"]["lookback_days"] = args.days

    # 1. Fetch
    logger.info("--- Fetching Data ---")
    fetcher = DataFetcher(config)
    try:
        market_data = fetcher.fetch_all()
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        sys.exit(1)

    # 2. Indicators
    logger.info("--- Indicators ---")
    indicators = compute_all_indicators(market_data["index"], config)
    vs = indicators["SMA250"].first_valid_index()
    if vs is not None:
        indicators = indicators.loc[vs:]

    # 3. Simulate
    logger.info("--- Simulation ---")
    strategies = WhiteLightStrategies(config)
    simulator = Simulator(config)

    state_loaded = False
    if not args.reset:
        state_loaded = simulator.load_state()

    if state_loaded:
        last = simulator.portfolio.equity_history[-1]["date"] if simulator.portfolio.equity_history else None
        if last:
            new_bars = indicators.loc[indicators.index > pd.Timestamp(last)]
            logger.info(f"New bars: {len(new_bars)}")
            for i in range(len(new_bars)):
                idx = indicators.index.get_loc(new_bars.index[i])
                sig = strategies.evaluate(indicators, idx)
                simulator.run_daily(sig, market_data)
        else:
            state_loaded = False

    if not state_loaded:
        logger.info("--- Full Backfill ---")
        sigs = [strategies.evaluate(indicators, i) for i in range(len(indicators))]
        logger.info(f"{len(sigs)} signals")
        simulator.run_backfill(sigs, market_data)

    # 4. Stats
    stats = simulator.get_performance_stats()
    logger.info(f"Equity: ${stats.get('current_equity',0):,.2f} | Return: {stats.get('total_return_pct',0):+.1f}%")

    # 5. Save CSVs
    Path(config["outputs"]["csv_dir"]).mkdir(parents=True, exist_ok=True)
    save_csvs(simulator.portfolio, config)

    # 6. Signal export
    daily_signal = export_daily_signal(simulator.portfolio.equity_history, simulator.portfolio.signal_log, config)

    # 7. Social content
    try:
        social_posts = generate_social_content(simulator.portfolio.equity_history, simulator.portfolio.trade_log, stats, daily_signal, config)
    except Exception as e:
        logger.warning(f"Social: {e}")
        social_posts = []

    # 8. Journal
    try:
        journal_data = generate_journal(simulator.portfolio.equity_history, simulator.portfolio.trade_log, simulator.portfolio.signal_log, stats, config)
    except Exception as e:
        logger.warning(f"Journal: {e}")
        journal_data = {"daily": [], "weekly": [], "monthly": []}

    # 9. Stress tests — auto-run on first backfill OR if flag set
    stress_results = []
    stress_csv = Path(config["outputs"]["csv_dir"]) / config["outputs"].get("stress_test_csv", "stress_test.csv")

    if args.stress_test or (not state_loaded and not stress_csv.exists()):
        logger.info("--- Stress Tests ---")
        try:
            from stress_test import run_stress_tests
            stress_results = run_stress_tests(config)
        except Exception as e:
            logger.warning(f"Stress test: {e}")

    if stress_csv.exists() and not stress_results:
        try:
            stress_results = pd.read_csv(stress_csv).to_dict("records")
        except Exception:
            pass

    # 10. Dashboard
    logger.info("--- Dashboard ---")
    html = generate_dashboard(
        equity_history=simulator.portfolio.equity_history,
        trade_log=simulator.portfolio.trade_log,
        signal_log=simulator.portfolio.signal_log,
        stats=stats,
        benchmark_data=market_data.get("benchmark"),
        config=config,
        stress_results=stress_results,
        social_posts=social_posts,
        journal_data=journal_data,
    )
    save_dashboard(html, config)
    simulator.save_state()

    logger.info("=" * 60)
    logger.info("Done!")

if __name__ == "__main__":
    main()
