"""
signal_exporter.py - Daily Signal JSON Export

Exports the latest signal to outputs/daily_signal.json
for automation, sharing, and social media posting.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def export_daily_signal(equity_history: list, signal_log: list, config: dict) -> dict:
    """Export latest signal to JSON file."""
    if not equity_history:
        return {}

    latest = equity_history[-1]
    latest_sig = signal_log[-1] if signal_log else {}

    signal = {
        "date": latest.get("date", ""),
        "generated_utc": datetime.utcnow().isoformat(),
        "regime": latest.get("regime", ""),
        "tqqq_pct": latest.get("tqqq_alloc", 0),
        "sqqq_pct": latest.get("sqqq_alloc", 0),
        "cash_pct": latest.get("cash_alloc", 100),
        "active_strategies": latest.get("active_strategies", "").split(", ") if latest.get("active_strategies") else [],
        "reason": latest.get("strategy_details", ""),
        "ndx_close": latest.get("ndx_close", 0),
        "ndx_vs_sma20_pct": latest.get("ext_sma20", 0),
        "ndx_vs_sma250_pct": latest.get("ext_sma250", 0),
        "rsi": latest.get("rsi", 50),
        "equity": latest.get("equity", 0),
        "action": _determine_action(latest),
    }

    # Save
    output_dir = Path(config["outputs"]["csv_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / config["outputs"]["daily_signal_json"]
    with open(path, "w") as f:
        json.dump(signal, f, indent=2)
    logger.info(f"Daily signal exported: {path}")

    return signal


def _determine_action(latest: dict) -> str:
    """Determine human-readable action from allocations."""
    tqqq = latest.get("tqqq_alloc", 0)
    sqqq = latest.get("sqqq_alloc", 0)
    if tqqq > 50:
        return f"LONG TQQQ ({tqqq:.0f}%)"
    elif tqqq > 0:
        return f"Light long TQQQ ({tqqq:.0f}%)"
    elif sqqq > 50:
        return f"SHORT via SQQQ ({sqqq:.0f}%)"
    elif sqqq > 0:
        return f"Light short via SQQQ ({sqqq:.0f}%)"
    else:
        return "CASH — no position"
