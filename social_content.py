"""
social_content.py - Social Media Content Generator

Generates ready-to-post social media copy from simulation outputs.
Manual-first workflow: review posts, copy-paste to platforms.

Generates:
  - Daily signal posts
  - Weekly Friday P&L summaries
  - Monthly performance reports
  - Post history saved to social_posts.json

Designed for: Twitter/X, Facebook, LinkedIn, Telegram, Discord
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


def generate_social_content(
    equity_history: list,
    trade_log: list,
    stats: dict,
    daily_signal: dict,
    config: dict,
) -> List[dict]:
    """
    Generate social media posts from latest simulation data.
    Returns list of post objects. Saves to social_posts.json.
    """
    posts = []
    social_cfg = config.get("social", {})
    name = social_cfg.get("platform_name", "APEX TRADE LAB")
    tags = social_cfg.get("hashtags", "")
    handle = social_cfg.get("handle", "")

    # 1. Daily signal post (always generated)
    posts.append(_daily_post(daily_signal, name, tags, handle))

    # 2. Weekly post (Fridays only)
    today = datetime.now()
    if today.weekday() == 4:  # Friday
        posts.append(_weekly_post(equity_history, trade_log, stats, name, tags))

    # 3. Monthly post (last day of month or 1st of new month)
    if today.day <= 1 or today.day >= 28:
        posts.append(_monthly_post(equity_history, stats, name, tags))

    # Load existing history and append
    output_dir = Path(config["outputs"]["csv_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    history_path = output_dir / config["outputs"]["social_posts_json"]

    existing = []
    if history_path.exists():
        try:
            with open(history_path, "r") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    # Deduplicate by date+type
    existing_keys = {(p.get("date"), p.get("type")) for p in existing}
    for p in posts:
        key = (p.get("date"), p.get("type"))
        if key not in existing_keys:
            existing.append(p)

    # Keep last 90 posts max
    existing = existing[-90:]

    with open(history_path, "w") as f:
        json.dump(existing, f, indent=2, default=str)

    logger.info(f"Social content: {len(posts)} new posts, {len(existing)} total history")
    return posts


def _daily_post(signal: dict, name: str, tags: str, handle: str) -> dict:
    """Generate daily signal post."""
    date = signal.get("date", datetime.now().strftime("%Y-%m-%d"))
    regime = signal.get("regime", "Unknown")
    action = signal.get("action", "Checking")
    tqqq = signal.get("tqqq_pct", 0)
    sqqq = signal.get("sqqq_pct", 0)
    cash = signal.get("cash_pct", 100)
    ndx = signal.get("ndx_close", 0)
    rsi = signal.get("rsi", 50)

    # Emoji based on regime
    emoji = "🟢" if "UP" in regime else "🔴" if "DOWN" in regime else "⚪"

    # Build post variants
    twitter = (
        f"{emoji} {name} Daily Signal — {date}\n\n"
        f"Regime: {regime}\n"
        f"Action: {action}\n\n"
        f"TQQQ: {tqqq:.0f}% | SQQQ: {sqqq:.0f}% | Cash: {cash:.0f}%\n"
        f"NDX: {ndx:,.0f} | RSI: {rsi:.0f}\n\n"
        f"Paper trading simulation — not financial advice.\n"
        f"{tags}"
    )

    facebook = (
        f"⚡ {name} — Daily Signal Update\n"
        f"📅 {date}\n\n"
        f"{emoji} Market Regime: {regime}\n"
        f"📊 Action: {action}\n\n"
        f"Portfolio Allocation:\n"
        f"  • TQQQ (3x Long): {tqqq:.0f}%\n"
        f"  • SQQQ (3x Short): {sqqq:.0f}%\n"
        f"  • Cash: {cash:.0f}%\n\n"
        f"NDX closed at {ndx:,.0f} | RSI: {rsi:.0f}\n\n"
        f"This is a paper trading simulation for educational purposes.\n"
        f"Full dashboard: [link in bio]\n\n"
        f"{tags}"
    )

    telegram = (
        f"⚡ <b>{name}</b> — {date}\n\n"
        f"{emoji} <b>{regime}</b>\n"
        f"Action: {action}\n\n"
        f"TQQQ: {tqqq:.0f}% | SQQQ: {sqqq:.0f}% | Cash: {cash:.0f}%\n"
        f"NDX: {ndx:,.0f} | RSI: {rsi:.0f}\n\n"
        f"<i>Paper trading only — not advice.</i>"
    )

    return {
        "date": date,
        "type": "daily",
        "generated": datetime.utcnow().isoformat(),
        "twitter": twitter,
        "facebook": facebook,
        "telegram": telegram,
        "discord": twitter,  # Same format works
    }


def _weekly_post(equity_history: list, trade_log: list, stats: dict,
                 name: str, tags: str) -> dict:
    """Generate weekly P&L summary (Fridays)."""
    date = datetime.now().strftime("%Y-%m-%d")

    # Last 5 trading days
    recent = equity_history[-5:] if len(equity_history) >= 5 else equity_history
    if len(recent) >= 2:
        week_start_eq = recent[0].get("equity", 0)
        week_end_eq = recent[-1].get("equity", 0)
        week_pnl = week_end_eq - week_start_eq
        week_pct = (week_pnl / week_start_eq * 100) if week_start_eq > 0 else 0
    else:
        week_pnl, week_pct = 0, 0

    # Trades this week
    week_trades = [t for t in trade_log[-20:] if t.get("date", "") >= recent[0].get("date", "")] if recent else []
    total_ret = stats.get("total_return_pct", 0)
    equity = stats.get("current_equity", 0)

    emoji = "📈" if week_pnl >= 0 else "📉"

    twitter = (
        f"{emoji} {name} — Weekly P&L\n"
        f"Week ending {date}\n\n"
        f"Weekly: ${week_pnl:+,.0f} ({week_pct:+.1f}%)\n"
        f"Total Return: {total_ret:+.1f}%\n"
        f"Portfolio: ${equity:,.0f}\n"
        f"Trades this week: {len(week_trades)}\n\n"
        f"Paper trading sim — not advice.\n"
        f"{tags}"
    )

    facebook = (
        f"📊 {name} — Weekly Performance Report\n"
        f"Week ending {date}\n\n"
        f"{emoji} This Week: ${week_pnl:+,.0f} ({week_pct:+.1f}%)\n"
        f"💰 Portfolio Value: ${equity:,.0f}\n"
        f"📈 Total Return: {total_ret:+.1f}%\n"
        f"🔄 Trades Executed: {len(week_trades)}\n\n"
        f"The system traded {'actively' if len(week_trades) > 3 else 'conservatively'} this week.\n\n"
        f"Full analysis: [link in bio]\n\n"
        f"Paper trading simulation — educational purposes only.\n"
        f"{tags}"
    )

    return {
        "date": date, "type": "weekly",
        "generated": datetime.utcnow().isoformat(),
        "twitter": twitter, "facebook": facebook,
        "telegram": twitter, "discord": twitter,
    }


def _monthly_post(equity_history: list, stats: dict, name: str, tags: str) -> dict:
    """Generate monthly performance report."""
    date = datetime.now().strftime("%Y-%m-%d")
    total_ret = stats.get("total_return_pct", 0)
    cagr = stats.get("cagr_pct", 0)
    sharpe = stats.get("sharpe_ratio", 0)
    max_dd = stats.get("max_drawdown_pct", 0)
    equity = stats.get("current_equity", 0)
    win_rate = stats.get("win_rate_pct", 0)
    trades = stats.get("total_trades", 0)

    twitter = (
        f"📊 {name} — Monthly Report\n"
        f"{date}\n\n"
        f"Total Return: {total_ret:+.1f}%\n"
        f"CAGR: {cagr:+.1f}%\n"
        f"Sharpe: {sharpe:.2f}\n"
        f"Max DD: {max_dd:.1f}%\n"
        f"Win Rate: {win_rate:.0f}%\n"
        f"Portfolio: ${equity:,.0f}\n\n"
        f"Full report + live dashboard: [link]\n"
        f"{tags}"
    )

    facebook = (
        f"📈 {name} — Monthly Performance Report\n\n"
        f"Here is how the 7-strategy TQQQ/SQQQ system performed:\n\n"
        f"💰 Portfolio: ${equity:,.0f}\n"
        f"📊 Total Return: {total_ret:+.1f}%\n"
        f"📈 CAGR: {cagr:+.1f}%\n"
        f"⚖️ Sharpe Ratio: {sharpe:.2f}\n"
        f"📉 Max Drawdown: {max_dd:.1f}%\n"
        f"🎯 Win Rate: {win_rate:.0f}%\n"
        f"🔄 Total Trades: {trades}\n\n"
        f"The system runs autonomously — making one decision at market close each day.\n\n"
        f"This is a paper trading simulation for learning systematic trading.\n"
        f"Full dashboard: [link in bio]\n\n"
        f"{tags}"
    )

    return {
        "date": date, "type": "monthly",
        "generated": datetime.utcnow().isoformat(),
        "twitter": twitter, "facebook": facebook,
        "telegram": twitter, "discord": twitter,
    }
