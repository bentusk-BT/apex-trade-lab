"""
stress_test.py - Stress Test Module for APEX TRADE LAB

Simulates how the WhiteLight system would have performed during
major market crashes using synthetic TQQQ/SQQQ data derived from NDX.

Crashes tested:
  - 2000 Dot-com crash
  - 2008 Global Financial Crisis
  - 2020 COVID crash
  - 2022 Bear market

Outputs stress_test.csv with results per scenario.
"""

import logging
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def run_stress_tests(config: dict) -> List[dict]:
    """
    Run stress tests using historical NDX data.
    Returns list of scenario results for dashboard display.
    """
    scenarios = config.get("stress_tests", [])
    if not scenarios:
        return []

    results = []
    for scenario in scenarios:
        name = scenario["name"]
        start = scenario["start"]
        end = scenario["end"]
        logger.info(f"Stress test: {name} ({start} to {end})")

        try:
            result = _simulate_scenario(name, start, end, config)
            results.append(result)
        except Exception as e:
            logger.warning(f"Stress test '{name}' failed: {e}")
            results.append({
                "name": name,
                "start": start,
                "end": end,
                "error": str(e),
                "ndx_return_pct": 0,
                "tqqq_estimated_pct": 0,
                "system_estimated_pct": 0,
                "max_drawdown_pct": 0,
                "recovery_days": 0,
            })

    # Save to CSV
    output_dir = Path(config["outputs"]["csv_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / config["outputs"]["stress_test_csv"]
    pd.DataFrame(results).to_csv(csv_path, index=False)
    logger.info(f"Stress test results saved: {csv_path}")

    return results


def _simulate_scenario(name: str, start: str, end: str, config: dict) -> dict:
    """
    Simulate a single crash scenario.

    Since TQQQ didn't exist before 2010, we estimate synthetic 3x daily returns
    from NDX data. The WhiteLight system's performance is estimated based on
    regime-aware allocation (the system goes to SQQQ in downtrends).
    """
    import yfinance as yf

    # Fetch NDX data for the period
    ndx = yf.download("^NDX", start=start, end=end, auto_adjust=True, progress=False)
    if ndx is None or ndx.empty or len(ndx) < 10:
        raise ValueError(f"Insufficient data for {name}")

    if isinstance(ndx.columns, pd.MultiIndex):
        ndx.columns = ndx.columns.get_level_values(0)

    ndx["Return"] = ndx["Close"].pct_change()

    # Synthetic TQQQ = 3x daily NDX return (simplified, ignores decay/expenses)
    ndx["TQQQ_Return"] = ndx["Return"] * 3
    ndx["SQQQ_Return"] = ndx["Return"] * -3

    # NDX cumulative
    ndx["NDX_Cum"] = (1 + ndx["Return"]).cumprod()
    ndx["TQQQ_Cum"] = (1 + ndx["TQQQ_Return"]).cumprod()

    # Simple system simulation: use SMA(250) for regime
    # Above SMA250 = hold TQQQ, below = hold SQQQ
    sma250 = ndx["Close"].rolling(250).mean()
    ndx["Above_SMA250"] = ndx["Close"] > sma250

    # System return: TQQQ when above SMA250, SQQQ when below
    ndx["Sys_Return"] = np.where(
        ndx["Above_SMA250"],
        ndx["TQQQ_Return"],
        ndx["SQQQ_Return"]
    )
    ndx["Sys_Cum"] = (1 + ndx["Sys_Return"]).cumprod()

    # Calculate metrics
    ndx_return = (ndx["NDX_Cum"].iloc[-1] - 1) * 100
    tqqq_return = (ndx["TQQQ_Cum"].iloc[-1] - 1) * 100
    sys_return = (ndx["Sys_Cum"].iloc[-1] - 1) * 100

    # Max drawdown
    sys_cummax = ndx["Sys_Cum"].cummax()
    sys_dd = ((ndx["Sys_Cum"] - sys_cummax) / sys_cummax * 100).min()

    tqqq_cummax = ndx["TQQQ_Cum"].cummax()
    tqqq_dd = ((ndx["TQQQ_Cum"] - tqqq_cummax) / tqqq_cummax * 100).min()

    # Recovery days (from max drawdown to new high)
    dd_series = (ndx["Sys_Cum"] - sys_cummax) / sys_cummax
    at_bottom = dd_series.idxmin()
    recovered = ndx.loc[at_bottom:][dd_series.loc[at_bottom:] >= 0]
    recovery_days = (recovered.index[0] - at_bottom).days if not recovered.empty else 999

    trading_days = len(ndx.dropna())

    return {
        "name": name,
        "start": start,
        "end": end,
        "trading_days": trading_days,
        "ndx_return_pct": round(ndx_return, 1),
        "tqqq_estimated_pct": round(tqqq_return, 1),
        "tqqq_max_dd_pct": round(tqqq_dd, 1),
        "system_estimated_pct": round(sys_return, 1),
        "max_drawdown_pct": round(sys_dd, 1),
        "recovery_days": recovery_days,
        "note": "Synthetic 3x returns. Actual TQQQ decay would be worse.",
    }
