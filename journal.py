"""
journal.py - APEX TRADE LAB Trading Journal

Auto-generates insightful journal entries from simulation data.
No API key needed — rule-based analysis from the numbers.

Three types:
  - Daily: What happened, why, what to watch tomorrow, learning nugget
  - Weekly (Fridays): Week review, wins/losses, regime shifts, lesson
  - Monthly (month-end): Deep dive, strategy assessment, outlook

All entries persist in outputs/journal.json and accumulate over time.
"""

import json, logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def generate_journal(equity_history, trade_log, signal_log, stats, config):
    output_dir = Path(config["outputs"]["csv_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    journal_path = output_dir / "journal.json"

    existing = {"daily": [], "weekly": [], "monthly": []}
    if journal_path.exists():
        try:
            with open(journal_path, "r") as f:
                existing = json.load(f)
        except Exception:
            pass

    if not equity_history:
        return existing

    today = equity_history[-1]
    today_date = today.get("date", "")

    # Daily (always)
    daily = _daily_entry(equity_history, trade_log, stats)
    if daily and not any(e.get("date") == today_date for e in existing["daily"]):
        existing["daily"].append(daily)

    # Weekly (Fridays)
    if datetime.now().weekday() == 4:
        weekly = _weekly_entry(equity_history, trade_log, stats)
        if weekly and not any(e.get("date") == today_date for e in existing["weekly"]):
            existing["weekly"].append(weekly)

    # Monthly (end of month)
    if datetime.now().day >= 28 or datetime.now().day <= 1:
        month_key = today_date[:7]
        if not any(e.get("month") == month_key for e in existing["monthly"]):
            monthly = _monthly_entry(equity_history, trade_log, stats)
            if monthly:
                existing["monthly"].append(monthly)

    existing["daily"] = existing["daily"][-90:]
    existing["weekly"] = existing["weekly"][-52:]
    existing["monthly"] = existing["monthly"][-24:]

    with open(journal_path, "w") as f:
        json.dump(existing, f, indent=2, default=str)

    logger.info(f"Journal: {len(existing['daily'])}d / {len(existing['weekly'])}w / {len(existing['monthly'])}m")
    return existing


def _daily_entry(eh, tl, stats):
    if len(eh) < 2:
        return None
    today, yesterday = eh[-1], eh[-2]
    date = today.get("date", "")
    eq_t, eq_y = today.get("equity", 0), yesterday.get("equity", 0)
    day_pnl = eq_t - eq_y
    day_pct = (day_pnl / eq_y * 100) if eq_y > 0 else 0
    regime = today.get("regime", "")
    prev_regime = yesterday.get("regime", "")
    regime_changed = regime != prev_regime
    ext20 = today.get("ext_sma20", 0)
    ext250 = today.get("ext_sma250", 0)
    rsi = today.get("rsi", 50)
    tqqq = today.get("tqqq_alloc", 0)
    sqqq = today.get("sqqq_alloc", 0)
    today_trades = [t for t in tl if t.get("date") == date]

    obs = []
    if regime_changed:
        obs.append(f"Major event: regime shifted from {prev_regime} to {regime}. This is one of the most important signals — the market character has fundamentally changed.")
    else:
        obs.append(f"Market remains in {regime} regime.")

    if abs(ext20) > 4:
        d = "above" if ext20 > 0 else "below"
        obs.append(f"NDX is notably extended at {ext20:+.1f}% {d} its 20-day average. {'Overextension often precedes pullbacks.' if ext20 > 4 else 'Deep pullbacks in uptrends are often buying opportunities.'}")
    elif abs(ext20) < 1:
        obs.append(f"NDX is right at its 20-day average ({ext20:+.1f}%). Decision zone — the next move tends to be directional.")

    if rsi > 70:
        obs.append(f"RSI at {rsi:.0f} — overbought. Can persist in strong trends but often precedes cooling.")
    elif rsi < 30:
        obs.append(f"RSI at {rsi:.0f} — oversold. Often where the best entries occur, but requires discipline.")

    if today_trades:
        for t in today_trades:
            tt = t.get("trade_type", "")
            tk = t.get("ticker", "")
            st = t.get("strategy", "")
            pnl = t.get("realized_pnl", 0)
            if tt == "NEW ENTRY":
                obs.append(f"Opened new {tk} position via {st}. Fresh conviction trade based on current conditions.")
            elif tt == "EXIT":
                obs.append(f"Closed {tk} position ({st}). P&L: ${pnl:+,.0f}. {'Strategy worked as designed.' if pnl > 0 else 'Controlled loss — part of systematic trading.'}")
            elif tt == "ADD":
                obs.append(f"Added to {tk} — continued opportunity detected.")
            elif tt == "REDUCE":
                obs.append(f"Reduced {tk} — taking partial profits or adjusting risk.")
    else:
        obs.append("No trades today. Holding steady. In systematic trading, doing nothing is often the right decision.")

    watch = []
    if abs(ext250) < 3:
        watch.append("NDX near SMA(250) — regime change possible. Most critical level to monitor.")
    if rsi > 65:
        watch.append("Elevated RSI. Watch for momentum fading (bearish divergence).")
    if rsi < 35:
        watch.append("Low RSI. Watch for reversal candle as bounce signal.")
    if tqqq > 60:
        watch.append(f"Heavy TQQQ at {tqqq:.0f}%. Monitor for overextension signals.")
    if sqqq > 30:
        watch.append(f"Active SQQQ at {sqqq:.0f}%. Watch for NDX reclaiming SMA(250).")
    if not watch:
        watch.append("No unusual conditions. Continue daily monitoring.")

    learning = _pick_learning(regime, ext20, rsi, regime_changed, today_trades)

    return {
        "date": date, "type": "daily",
        "title": f"{'REGIME CHANGE!' if regime_changed else regime} — ${day_pnl:+,.0f} ({day_pct:+.1f}%)",
        "regime": regime, "day_pnl": round(day_pnl, 2), "day_pct": round(day_pct, 2),
        "equity": round(eq_t, 2), "ndx": today.get("ndx_close", 0),
        "rsi": round(rsi, 1), "ext_sma20": round(ext20, 2), "ext_sma250": round(ext250, 2),
        "tqqq_alloc": tqqq, "sqqq_alloc": sqqq,
        "trades_today": len(today_trades),
        "observation": " ".join(obs),
        "watch_tomorrow": " ".join(watch),
        "learning": learning,
    }


def _weekly_entry(eh, tl, stats):
    if len(eh) < 5:
        return None
    week = eh[-5:]
    date = week[-1].get("date", "")
    eq_s, eq_e = week[0].get("equity", 0), week[-1].get("equity", 0)
    w_pnl = eq_e - eq_s
    w_pct = (w_pnl / eq_s * 100) if eq_s > 0 else 0
    ws_date = week[0].get("date", "")
    wt = [t for t in tl if t.get("date", "") >= ws_date]
    wins = len([t for t in wt if t.get("realized_pnl", 0) > 0])
    losses = len([t for t in wt if t.get("realized_pnl", 0) < 0])
    regimes_seen = list(set(r.get("regime", "") for r in week))
    rc = len(regimes_seen) > 1

    daily_pnls = [(week[i].get("date",""), week[i].get("equity",0) - week[i-1].get("equity",0)) for i in range(1, len(week))]
    best = max(daily_pnls, key=lambda x: x[1]) if daily_pnls else ("", 0)
    worst = min(daily_pnls, key=lambda x: x[1]) if daily_pnls else ("", 0)

    ref = []
    if w_pct > 2:
        ref.append(f"Strong week at {w_pct:+.1f}%. System positioning was well-aligned.")
    elif w_pct > 0:
        ref.append(f"Positive at {w_pct:+.1f}%. Steady compounding — this is how systematic trading builds wealth.")
    elif w_pct > -2:
        ref.append(f"Small loss of {w_pct:.1f}%. Within normal range. Risk management held.")
    else:
        ref.append(f"Difficult week at {w_pct:.1f}%. Tests discipline. Key question: did the system follow its rules?")
    if rc:
        ref.append(f"Regime changed this week ({', '.join(regimes_seen)}). Transitions create the biggest opportunities and risks.")
    if wins > losses:
        ref.append(f"{wins}W/{losses}L — edge is working.")
    elif losses > wins > 0:
        ref.append(f"{wins}W/{losses}L — more losers, but normal. Win rate matters over months.")

    lesson = _weekly_lesson(w_pct, rc, wins, losses)

    return {
        "date": date, "type": "weekly",
        "title": f"Week ending {date} — ${w_pnl:+,.0f} ({w_pct:+.1f}%)",
        "week_pnl": round(w_pnl, 2), "week_pct": round(w_pct, 2), "equity": round(eq_e, 2),
        "trades": len(wt), "wins": wins, "losses": losses,
        "best_day": {"date": best[0], "pnl": round(best[1], 2)},
        "worst_day": {"date": worst[0], "pnl": round(worst[1], 2)},
        "regimes_seen": regimes_seen,
        "reflection": " ".join(ref), "lesson": lesson,
    }


def _monthly_entry(eh, tl, stats):
    if len(eh) < 20:
        return None
    date = eh[-1].get("date", "")
    mk = date[:7]
    mr = [r for r in eh if r.get("date", "").startswith(mk)]
    if len(mr) < 2:
        return None
    eq_s, eq_e = mr[0].get("equity", 0), mr[-1].get("equity", 0)
    m_pnl = eq_e - eq_s
    m_pct = (m_pnl / eq_s * 100) if eq_s > 0 else 0
    ms_date = mr[0].get("date", "")
    mt = [t for t in tl if t.get("date", "") >= ms_date]
    wins = len([t for t in mt if t.get("realized_pnl", 0) > 0])
    losses = len([t for t in mt if t.get("realized_pnl", 0) < 0])
    total_real = sum(t.get("realized_pnl", 0) for t in mt)

    regimes = [r.get("regime", "") for r in mr]
    rc = {}
    for r in regimes:
        rc[r] = rc.get(r, 0) + 1
    dominant = max(rc, key=rc.get) if rc else "Unknown"

    sp = {}
    for t in mt:
        s = t.get("strategy", "Other")
        sp[s] = sp.get(s, 0) + t.get("realized_pnl", 0)
    best_s = max(sp, key=sp.get) if sp else "None"
    worst_s = min(sp, key=sp.get) if sp else "None"

    eqs = [r.get("equity", 0) for r in mr]
    pk, mdd = eqs[0], 0
    for e in eqs:
        if e > pk: pk = e
        dd = (e - pk) / pk * 100 if pk > 0 else 0
        if dd < mdd: mdd = dd

    analysis = []
    if m_pct > 5:
        analysis.append(f"Excellent month at {m_pct:+.1f}%. Captured a strong trend effectively.")
    elif m_pct > 0:
        analysis.append(f"Positive at {m_pct:+.1f}%. Steady compounding.")
    elif m_pct > -5:
        analysis.append(f"Losing month at {m_pct:.1f}%. Drawdown protection limited the damage.")
    else:
        analysis.append(f"Tough month at {m_pct:.1f}%. Trust is tested most in drawdowns. History shows recovery follows regime shifts.")
    analysis.append(f"Dominant regime: {dominant} ({rc.get(dominant, 0)}/{len(mr)} days).")
    if best_s != "None":
        analysis.append(f"Best strategy: {best_s} (${sp.get(best_s, 0):+,.0f}).")

    learning = _monthly_learning(m_pct, dominant, mdd)

    return {
        "date": date, "month": mk, "type": "monthly",
        "title": f"{mk} — ${m_pnl:+,.0f} ({m_pct:+.1f}%)",
        "month_pnl": round(m_pnl, 2), "month_pct": round(m_pct, 2), "equity": round(eq_e, 2),
        "trades": len(mt), "wins": wins, "losses": losses,
        "realized_pnl": round(total_real, 2), "dominant_regime": dominant,
        "max_drawdown_pct": round(mdd, 1),
        "best_strategy": best_s, "worst_strategy": worst_s,
        "strategy_pnl": {k: round(v, 2) for k, v in sp.items()},
        "analysis": " ".join(analysis), "learning": learning,
        "total_return": stats.get("total_return_pct", 0),
    }


def _pick_learning(regime, ext20, rsi, rc, trades):
    if rc: return "Regime changes are the highest-impact events. When NDX crosses SMA(250), the entire strategy set flips. This is why the SMA(250) is the most important line on the chart."
    if not trades: return "No trades today. In systematic trading, doing nothing is often the right decision. The edge comes from waiting for high-probability setups, not trading frequently."
    if abs(ext20) > 4: return "When price stretches far from its average, mean reversion forces grow. The system uses this extension to size positions — buying more when stretched down (in uptrends), reducing when stretched up."
    if rsi > 70 or rsi < 30: return "RSI extremes aren't automatic signals. In strong trends, RSI stays extreme for weeks. The system uses RSI as confirmation, not primary trigger."
    return "The system runs 7 non-correlated strategies simultaneously. When one underperforms, others compensate. This diversification across strategy types is more valuable than any single strategy's edge."


def _weekly_lesson(w_pct, rc, wins, losses):
    if rc: return "This week included a regime change. Review how the system transitioned: clean exits from old positions, prompt entries into new regime strategies. Transition speed directly impacts returns."
    if w_pct > 3: return "Strong weeks can breed overconfidence. The system's rules don't change based on recent results. Next week's allocation depends purely on current indicators."
    if w_pct < -3: return "Losing weeks are when the system earns its keep — by controlling losses. Check the drawdown chart: is recovery faster than the benchmark? That's the real measure."
    return "A mixed week. Individual weeks are noise in systematic trading. The signal only emerges over months and years. Trust the process."


def _monthly_learning(m_pct, regime, mdd):
    if m_pct > 10: return "Exceptional month — strong trending regime where momentum strategies shine. Don't increase risk expecting repetition. Mean reversion applies to returns too."
    if m_pct < -10: return "Significant drawdown. Most traders abandon systems here. Historical data shows the system's worst drawdowns are followed by recovery — but only if you stick with the rules."
    if "DOWNTREND" in regime: return "Trading downtrend regimes is psychologically hard. Using SQQQ to profit from falling markets feels counterintuitive. Remember: the system follows price vs SMA(250), not opinions."
    if abs(mdd) > 15: return "Notable drawdown this month. Not a failure — it's expected. Key metrics: is drawdown within historical norms? How fast does the system recover?"
    return "Normal month. The best months in systematic trading are unremarkable — steady, controlled, no drama. Excitement usually means risk. Boredom means the system is working."
