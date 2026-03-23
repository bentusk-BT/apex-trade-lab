"""
dashboard.py - APEX TRADE LAB Dashboard v2.1 (Polished)

Changes from v2.0:
- Dark/light theme toggle with localStorage persistence
- CSS custom properties for all themed colors
- Improved header with branded hero + toggle
- Redesigned signal card (trading terminal style)
- Drawdown chart added below equity curve
- Weekly performance summary card
- P&L page polished with better layout
- Plotly charts adapt to active theme
- All 9 pages preserved
"""

import json, logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
import numpy as np, pandas as pd

logger = logging.getLogger(__name__)

# =====================================================================
# MAIN GENERATOR
# =====================================================================

def generate_dashboard(equity_history, trade_log, signal_log, stats,
                       benchmark_data, config, stress_results=None, social_posts=None):
    D = [r["date"] for r in equity_history]
    EQ = [r["equity"] for r in equity_history]
    TA = [r.get("tqqq_alloc",0) for r in equity_history]
    SA = [r.get("sqqq_alloc",0) for r in equity_history]
    CA = [r.get("cash_alloc",100) for r in equity_history]
    NX = [r.get("ndx_close",0) for r in equity_history]
    S20 = [r.get("sma20") for r in equity_history]
    S250 = [r.get("sma250") for r in equity_history]
    RG = [r.get("regime","") for r in equity_history]
    RSI = [r.get("rsi",50) for r in equity_history]
    E20 = [r.get("ext_sma20",0) for r in equity_history]
    E250 = [r.get("ext_sma250",0) for r in equity_history]
    cap = stats.get("starting_capital",100000)
    BN = _nb(benchmark_data, D, cap)

    # Drawdown series
    DD = _calc_drawdown_series(EQ)

    # Weekly summary
    weekly = _calc_weekly_summary(equity_history, trade_log, stats)

    bd,bp,bl,sd,sp,sl=[],[],[],[],[],[]
    for t in trade_log:
        lb=f"{_human_trade(t)}<br>${t['value']:,.0f}"
        (bd if t["action"]=="BUY" else sd).append(t["date"])
        (bp if t["action"]=="BUY" else sp).append(t["ndx_close"])
        (bl if t["action"]=="BUY" else sl).append(lb)

    la = equity_history[-1] if equity_history else {}
    rstat = stats.get("regime_stats",{})
    trans = _rtrans(equity_history)
    br = config.get("branding",{})
    stress = stress_results or []
    social = social_posts or []
    rc = 'bull' if 'UP' in la.get('regime','') else 'bear'

    regime_map_data = json.dumps([{"d":D[i],"r":RG[i],"rsi":RSI[i],"e250":E250[i]} for i in range(len(D))])

    cd = json.dumps({"latest":la,"stats":{k:v for k,v in stats.items() if k!="regime_stats"},
        "regime_stats":rstat,"transitions":trans[-10:],"recent_trades":trade_log[-20:],
        "equity_tail":equity_history[-15:]},default=str)

    recent50 = trade_log[-50:]
    pnl_data = _calc_pnl(equity_history, trade_log)
    atr_approx = round(la.get("ndx_close",20000)*0.012,2)

    return f'''{_css(br)}
<body>

<!-- HEADER -->
<header>
    <div class="hdr-inner">
        <div class="hdr-brand">
            <div class="logo">&#9889; APEX TRADE LAB</div>
            <div class="tagline">Systematic Trading Research Platform</div>
        </div>
        <div class="hdr-right">
            <div class="live-badge"><span class="dot"></span> Live &bull; {datetime.now().strftime('%b %d, %Y %H:%M UTC')}</div>
            <button class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode" aria-label="Toggle theme">
                <span class="theme-icon" id="theme-icon">&#9789;</span>
            </button>
        </div>
    </div>
</header>

<nav>
    <button class="on" onclick="go('dash',this)">Dashboard</button>
    <button onclick="go('trades',this)">Trades</button>
    <button onclick="go('pnl',this)">P&amp;L</button>
    <button onclick="go('tools',this)">Trade Tools</button>
    <button onclick="go('regime',this)">Market Regime</button>
    <button onclick="go('stress',this)">Stress Test</button>
    <button onclick="go('ai',this)">AI Analyst</button>
    <button onclick="go('learn',this)">Learn</button>
    <div class="dropdown">
        <button onclick="this.parentElement.classList.toggle('open')">Community &#9662;</button>
        <div class="dropdown-menu">
            <a onclick="go('community',document.querySelector('[data-pg=community]'));document.querySelector('.dropdown').classList.remove('open')">Subscribe</a>
            <a onclick="go('vip',document.querySelector('[data-pg=vip]'));document.querySelector('.dropdown').classList.remove('open')">VIP Access</a>
            <a onclick="go('services',document.querySelector('[data-pg=services]'));document.querySelector('.dropdown').classList.remove('open')">Services</a>
        </div>
    </div>
    <button data-pg="community" onclick="go('community',this)" style="display:none"></button>
    <button data-pg="vip" onclick="go('vip',this)" style="display:none"></button>
    <button data-pg="services" onclick="go('services',this)" style="display:none"></button>
</nav>

<!-- ===== DASHBOARD ===== -->
<div id="dash" class="pg on">

<!-- Signal Card -->
<div class="signal-card {rc}">
    <div class="sc-top">
        <div class="sc-badge">CURRENT SIGNAL</div>
        <div class="sc-next">{_next_review()}</div>
    </div>
    <div class="sc-grid">
        <div class="sc-col">
            <div class="sc-label">Regime</div>
            <div class="sc-val {rc}" style="font-size:20px">{la.get('regime','—')}</div>
        </div>
        <div class="sc-col">
            <div class="sc-label">Action</div>
            <div class="sc-val {rc}" style="font-size:20px">{_action_text(la)}</div>
        </div>
        <div class="sc-col sc-alloc-col">
            <div class="sc-label">Allocation</div>
            <div class="sc-alloc-bars">
                <div class="ab"><span class="ab-l">TQQQ</span><div class="ab-track"><div class="ab-fill bull" style="width:{la.get('tqqq_alloc',0)}%"></div></div><span class="ab-v">{la.get('tqqq_alloc',0):.0f}%</span></div>
                <div class="ab"><span class="ab-l">SQQQ</span><div class="ab-track"><div class="ab-fill bear" style="width:{la.get('sqqq_alloc',0)}%"></div></div><span class="ab-v">{la.get('sqqq_alloc',0):.0f}%</span></div>
                <div class="ab"><span class="ab-l">Cash</span><div class="ab-track"><div class="ab-fill cash" style="width:{la.get('cash_alloc',100)}%"></div></div><span class="ab-v">{la.get('cash_alloc',100):.0f}%</span></div>
            </div>
        </div>
        <div class="sc-col">
            <div class="sc-label">Context</div>
            <div class="sc-ctx">
                <span>NDX <strong>{la.get('ndx_close',0):,.0f}</strong></span>
                <span>RSI <strong>{la.get('rsi',50):.0f}</strong></span>
                <span>vs SMA250 <strong class="{rc}">{la.get('ext_sma250',0):+.1f}%</strong></span>
            </div>
            <div class="sc-label" style="margin-top:6px">Active</div>
            <div style="font-size:12px">{la.get('active_strategies','None')}</div>
        </div>
    </div>
    <div class="sc-reason"><strong>Why:</strong> {_human_reason(la)}</div>
</div>

<!-- Stats Row -->
<div class="stats-row">
    <div class="stat"><div class="stat-l">Portfolio {_tip('Total paper portfolio value.')}</div><div class="stat-v bull">${stats.get('current_equity',0):,.0f}</div></div>
    <div class="stat"><div class="stat-l">Return {_tip('Total gain/loss since start.')}</div><div class="stat-v {'bull' if stats.get('total_return_pct',0)>=0 else 'bear'}">{stats.get('total_return_pct',0):+.1f}%</div></div>
    <div class="stat"><div class="stat-l">CAGR {_tip('Annualised compound return.')}</div><div class="stat-v">{stats.get('cagr_pct',0):+.1f}%</div></div>
    <div class="stat"><div class="stat-l">Sharpe {_tip('Risk-adjusted return. Above 1 is good, above 2 is great.')}</div><div class="stat-v">{stats.get('sharpe_ratio',0):.2f}</div></div>
    <div class="stat"><div class="stat-l">Max DD {_tip('Largest peak-to-trough decline.')}</div><div class="stat-v bear">{stats.get('max_drawdown_pct',0):.1f}%</div></div>
    <div class="stat"><div class="stat-l">Win Rate {_tip('% of profitable closed trades.')}</div><div class="stat-v">{stats.get('win_rate_pct',0):.0f}%</div></div>
</div>

<!-- Weekly Summary -->
<div class="card weekly-card">
    <h2>Performance Summary</h2>
    <div class="wk-grid">
        <div class="wk-item"><div class="wk-label">This Week</div><div class="wk-val {'bull' if weekly['week_pct']>=0 else 'bear'}">{weekly['week_pct']:+.1f}%</div></div>
        <div class="wk-item"><div class="wk-label">Month to Date</div><div class="wk-val {'bull' if weekly['mtd_pct']>=0 else 'bear'}">{weekly['mtd_pct']:+.1f}%</div></div>
        <div class="wk-item"><div class="wk-label">Total Return</div><div class="wk-val {'bull' if stats.get('total_return_pct',0)>=0 else 'bear'}">{stats.get('total_return_pct',0):+.1f}%</div></div>
        <div class="wk-item"><div class="wk-label">Regime</div><div class="wk-val {rc}">{la.get('regime','—')}</div></div>
        <div class="wk-item"><div class="wk-label">Trades This Week</div><div class="wk-val">{weekly['week_trades']}</div></div>
        <div class="wk-item"><div class="wk-label">Max Drawdown</div><div class="wk-val bear">{stats.get('max_drawdown_pct',0):.1f}%</div></div>
    </div>
</div>

<!-- Charts -->
<div class="card"><h2>Equity Curve vs QQQ Benchmark</h2><div id="eq-c"></div></div>
<div class="card"><h2>Drawdown</h2><p class="desc">How far the portfolio has fallen from its peak at each point in time. Shallower and shorter drawdowns indicate better risk management.</p><div id="dd-c"></div></div>
<div class="card"><h2>NDX Price — Signals &amp; Regime</h2>
    <p class="desc">Green &#9650; = buy | Red &#9660; = sell | Background shading = market regime</p>
    <div id="nx-c"></div>
    <div class="regime-strip" id="regime-strip"></div>
</div>
<div class="card"><h2>Portfolio Allocation</h2><div id="al-c"></div></div>
</div>

<!-- ===== TRADES ===== -->
<div id="trades" class="pg">
<div class="card"><h2>Trade History</h2>
<p class="desc">Every trade with the strategy that triggered it and a plain-English explanation.</p>
<div class="tbl-wrap"><table><thead><tr><th>Date</th><th>Type</th><th>Ticker</th><th>Side</th><th>Shares</th><th>Price</th><th>Value</th><th>P&amp;L</th><th>Strategy</th><th>What Happened</th><th>Regime</th></tr></thead>
<tbody>{''.join(_trade_row_human(t) for t in reversed(recent50))}</tbody></table></div></div></div>

<!-- ===== P&L ===== -->
<div id="pnl" class="pg">
<div class="card"><h2>Profit &amp; Loss Overview</h2>
<div class="grid-3" style="margin-bottom:16px">
    <div class="card-inner" style="text-align:center"><div class="desc">Total Realised P&amp;L</div><div class="stat-v {'bull' if pnl_data['total_pnl']>=0 else 'bear'}" style="font-size:28px">${pnl_data['total_pnl']:+,.0f}</div></div>
    <div class="card-inner" style="text-align:center"><div class="desc">Winning Trades</div><div class="stat-v bull" style="font-size:28px">{stats.get('winning_trades',0)}</div></div>
    <div class="card-inner" style="text-align:center"><div class="desc">Losing Trades</div><div class="stat-v bear" style="font-size:28px">{stats.get('losing_trades',0)}</div></div>
</div>
<div class="grid-2">
    <div class="card-inner"><div class="desc">Win Rate</div><div class="stat-v" style="font-size:22px">{stats.get('win_rate_pct',0):.0f}%</div></div>
    <div class="card-inner"><div class="desc">Trades per Month</div><div class="stat-v" style="font-size:22px">~{stats.get('trades_per_month',0):.0f}</div></div>
</div>
</div>
{_social_posts_section(social)}
</div>

<!-- ===== TRADE TOOLS ===== -->
<div id="tools" class="pg">
<div class="card"><h2>Position Sizing Calculator</h2>
<div class="calc-grid"><div class="calc-in">
<div class="fg"><label>Account ($)</label><input type="number" id="psa" value="15000"></div>
<div class="fg"><label>Risk %</label><input type="number" id="psr" value="2.0" step="0.5"></div>
<div class="fg"><label>Entry ($)</label><input type="number" id="pse" value="75" step="0.01"></div>
<div class="fg"><label>Stop ($)</label><input type="number" id="pss" value="71" step="0.01"></div>
<div class="fg"><label>Ticker</label><select id="psi"><option>TQQQ</option><option>SQQQ</option></select></div>
<button class="btn" onclick="cPos()">Calculate</button></div>
<div class="calc-out" id="pso"><div class="placeholder">Enter values and click Calculate</div></div></div></div>

<div class="card"><h2>Stop Loss Framework</h2>
<div class="grid-3">
<div class="card-inner"><h3>1. ATR Dynamic</h3><p class="desc">Adapts to volatility.</p>
<div class="formula">Stop = Entry &minus; (ATR &times; Mult)</div>
<div class="fg"><label>ATR</label><input type="number" id="sla" value="{atr_approx}" step="0.01"></div>
<div class="fg"><label>Mult</label><select id="slam"><option value="1.5">1.5&times;</option><option value="2.0" selected>2.0&times;</option><option value="2.5">2.5&times;</option></select></div>
<button class="btn-s" onclick="cATR()">Calculate</button><div id="slar" class="result"></div></div>
<div class="card-inner"><h3>2. Fixed %</h3><p class="desc">Simple and predictable.</p>
<div class="formula">Stop = Entry &times; (1 &minus; %)</div>
<div class="fg"><label>Entry ($)</label><input type="number" id="slfe" value="75" step="0.01"></div>
<div class="fg"><label>Stop %</label><select id="slfp"><option value="3">3%</option><option value="5" selected>5%</option><option value="7">7%</option></select></div>
<button class="btn-s" onclick="cFix()">Calculate</button><div id="slfr" class="result"></div></div>
<div class="card-inner"><h3>3. Regime-Aware</h3><p class="desc">Tighter with trend, wider against it.</p>
<table class="mini-tbl"><thead><tr><th>Regime</th><th>Long</th><th>Short</th></tr></thead><tbody>
<tr><td class="bull">Strong Up</td><td>2.5-3.0&times;</td><td>1.0-1.5&times;</td></tr>
<tr><td class="bull">Up</td><td>2.0-2.5&times;</td><td>1.5&times;</td></tr>
<tr><td class="bear">Down</td><td>1.5&times;</td><td>2.0-2.5&times;</td></tr>
<tr><td class="bear">Strong Dn</td><td>1.0-1.5&times;</td><td>2.5-3.0&times;</td></tr></tbody></table>
<p class="desc" style="margin-top:6px">Now: <strong class="{rc}">{la.get('regime','')}</strong></p></div></div></div>

<div class="card"><h2>Entry &amp; Exit Framework</h2><div class="grid-2">
<div class="card-inner"><h3 class="bull">Entry Checklist</h3><ol><li>Regime: above/below SMA(250)?</li><li>Which strategy triggered?</li><li>Extension from SMA(20)?</li><li>RSI confirm (&lt;30 long, &gt;70 short)?</li><li>Size via calculator &mdash; max 2% risk</li></ol></div>
<div class="card-inner"><h3 class="bear">Exit Triggers (first wins)</h3><ol><li>Stop hit &rarr; out immediately</li><li>Strategy EXIT signal</li><li>Regime change &rarr; close direction</li></ol><p><strong>Trail:</strong> 1.5&times; ATR profit &rarr; breakeven. 2.5&times; &rarr; trail 1.5&times; ATR.</p></div></div></div>
</div>

<!-- ===== MARKET REGIME ===== -->
<div id="regime" class="pg">
<div class="card">
    <h2>Current Market Regime {_tip('Determined by NDX position relative to its 250-day moving average.')}</h2>
    <div class="regime-badge-wrap">
        <div class="regime-badge {rc}">{la.get('regime','')}</div>
        <div class="regime-metas">
            <span>NDX: <strong>{la.get('ndx_close',0):,.0f}</strong></span>
            <span>vs SMA(250): <strong class="{rc}">{la.get('ext_sma250',0):+.1f}%</strong></span>
            <span>RSI: <strong>{la.get('rsi',50):.0f}</strong></span>
        </div>
    </div>
</div>
<div class="card"><h2>Regime Map</h2><p class="desc">Hover for details.</p><div class="regime-strip-full" id="regime-map"></div></div>
<div class="card"><h2>Transitions</h2><div class="tbl-wrap"><table><thead><tr><th>Date</th><th>From</th><th>To</th><th>NDX</th><th>Duration</th><th>Significance</th></tr></thead>
<tbody>{''.join(_trow(t) for t in reversed(trans[-15:]))}</tbody></table></div></div>
<div class="card"><h2>Performance by Regime</h2><div class="grid-4">{_rcards(rstat)}</div></div>
<div class="card"><h2>Playbook</h2><div class="grid-2">
<div class="card-inner" style="border-left:3px solid #22c55e"><h3 class="bull">Strong Uptrend</h3><p>Max TQQQ (up to 88%). Buy every dip to SMA(20). BB width scales position size.</p><p><strong>Watch:</strong> &gt;8% above SMA(20) or RSI &gt;75.</p></div>
<div class="card-inner" style="border-left:3px solid #86efac"><h3 class="bull">Uptrend</h3><p>Mean reversion works best. Buy pullbacks. Standard sizing.</p><p><strong>Watch:</strong> NDX approaching SMA(250).</p></div>
<div class="card-inner" style="border-left:3px solid #f97316"><h3 class="bear">Downtrend</h3><p>SQQQ via Momentum Shorts. All longs OFF. Short failed bounces.</p><p><strong>Critical:</strong> Do not buy dips below SMA(250).</p></div>
<div class="card-inner" style="border-left:3px solid #ef4444"><h3 class="bear">Strong Downtrend</h3><p>Max SQQQ. Scale with depth. 2022: system -10.9% vs TQQQ -79%.</p><p><strong>Watch:</strong> RSI &lt;25 = bounce likely.</p></div>
</div></div></div>

<!-- ===== STRESS TEST ===== -->
<div id="stress" class="pg">
<div class="card"><h2>Stress Test Results</h2>
<p class="desc">Simulated performance during major crashes. TQQQ estimates use synthetic 3x daily returns — actual decay would be worse.</p>
{_stress_table(stress)}
</div></div>

<!-- ===== AI ANALYST ===== -->
<div id="ai" class="pg"><div class="card">
<h2>AI Analyst</h2><p class="desc">Ask questions about signals, performance, or strategy. Your data is pre-loaded.</p>
<div id="ai-s" style="max-width:480px">
<div class="fg"><label>Provider</label><select id="aip" onchange="document.getElementById('h1').style.display=this.value==='anthropic'?'block':'none';document.getElementById('h2').style.display=this.value==='openai'?'block':'none'">
<option value="anthropic">Claude Sonnet</option><option value="openai">GPT-4o</option></select></div>
<div class="fg"><label>API Key</label><input type="password" id="aik" placeholder="sk-..."></div>
<button class="btn" onclick="initAI()">Connect</button>
<div class="hint" id="h1"><a href="https://console.anthropic.com" target="_blank" rel="noopener">console.anthropic.com</a> &rarr; API Keys &rarr; $5 credit &asymp; 500 questions.</div>
<div class="hint" id="h2" style="display:none"><a href="https://platform.openai.com" target="_blank" rel="noopener">platform.openai.com</a> &rarr; API Keys &rarr; $5 credit.</div>
<p class="desc" style="margin-top:6px">&#128274; Your key stays in your browser only.</p>
</div>
<div id="ai-b" style="display:none" class="chat-box">
<div class="chat-msgs" id="msgs"></div>
<div class="chat-suggest">
<button onclick="aQ('Why this signal today?')">Why?</button>
<button onclick="aQ('Explain the last trade')">Last trade</button>
<button onclick="aQ('Current regime outlook?')">Regime</button>
<button onclick="aQ('Risk exposure?')">Risk</button>
<button onclick="aQ('Which strategy is active?')">Active</button>
<button onclick="aQ('Position size for $15K?')">Size</button>
</div>
<div class="chat-input"><input id="ain" placeholder="Ask anything..." onkeydown="if(event.key==='Enter')sAI()"><button onclick="sAI()" id="aib">Send</button></div>
</div></div></div>

<!-- ===== LEARN ===== -->
<div id="learn" class="pg">
<div class="card start-here"><h2>&#128218; Start Here</h2><div class="grid-2"><div>
<h3>What is Apex Trade Lab?</h3><p>A <strong>paper trading simulation</strong> — a virtual portfolio trading TQQQ and SQQQ based on 7 algorithmic strategies. No real money. One decision per day, 10 minutes before market close.</p>
<h3>What is paper trading?</h3><p>Simulated trading with virtual money. A flight simulator for trading.</p></div><div>
<h3>How to read the dashboard</h3><p>The <strong>Signal Card</strong> at the top shows what the system is doing and why. The <strong>equity curve</strong> tracks performance vs QQQ. The <strong>regime indicator</strong> shows bull or bear market status.</p>
<h3>Daily routine (Darwin time)</h3><ol><li>Check signal (7:00 AM)</li><li>Review regime</li><li>Read reasoning</li><li>Place trade if allocation changed</li><li>Return tomorrow</li></ol></div></div></div>
<div class="card"><h2>Inside the System — 7 Strategies</h2><p class="desc">Each strategy has different entry conditions, goals, and risk profiles. They combine for a smoother equity curve.</p>
<div class="strat-grid">{_strategies_explained()}</div></div></div>

<!-- ===== COMMUNITY ===== -->
<div id="community" class="pg">
<div class="card"><h2>&#128236; Subscribe to Weekly Reports</h2><p class="desc">Weekly P&amp;L summary, trade recaps, regime analysis, market outlook. Free. Unsubscribe anytime.</p>
<div id="mg1" class="math-gate"><p><strong>Quick verify:</strong></p><div id="mq1" class="mq"></div>
<div class="fg" style="max-width:180px"><label>Answer</label><input type="number" id="ma1"></div>
<button class="btn-s" onclick="cm(1)">Verify</button><div id="me1" class="bear" style="font-size:12px"></div></div>
<div id="sf1" style="display:none">
{('<a href="'+br.get("beehiiv_subscribe_url","")+'" target="_blank" rel="noopener" class="btn" style="display:inline-block;text-decoration:none;margin-top:8px">Open Newsletter Signup &rarr;</a>') if br.get("beehiiv_subscribe_url") else '<p class="desc">Newsletter launching soon.</p>'}
</div></div>
{_stripe_section(br)}
</div>

<!-- VIP -->
<div id="vip" class="pg"><div class="card"><h2 style="color:var(--purple)">VIP Access</h2>
<p class="desc">Additional commentary and insights for friends, supporters, and collaborators.</p>
<div id="vip-gate"><div class="fg" style="max-width:280px"><label>Password</label><input type="password" id="vip-pw" placeholder="Enter VIP password"></div>
<button class="btn" onclick="checkVIP()" style="background:var(--purple)">Unlock</button><div id="vip-err" class="bear" style="font-size:12px;margin-top:4px"></div></div>
<div id="vip-c" style="display:none">{_vip_content(la, stats, trans, trade_log[-5:])}</div></div></div>

<!-- SERVICES -->
<div id="services" class="pg">
<div class="card"><h2>Services</h2><div class="grid-3">
<div class="card-inner" style="border-top:3px solid var(--green)"><h3>Custom Strategy Dashboard</h3><p>Your strategy coded, backtested, and deployed as a live autonomous dashboard.</p></div>
<div class="card-inner" style="border-top:3px solid var(--yellow)"><h3>Backtest Report</h3><p>Send your rules, receive full backtest with metrics, equity curve, and risk analysis.</p></div>
<div class="card-inner" style="border-top:3px solid var(--purple)"><h3>Advertising &amp; Collaboration</h3><p>Feature your product or collaborate on research.</p></div></div></div>
<div class="card"><h2>Contact</h2>
{('<p class="desc">Email: <a href="mailto:'+br.get("contact_email","")+'">'+br.get("contact_email","")+'</a></p>') if br.get("contact_email") else ''}
<div id="mg2" class="math-gate"><p><strong>Verify:</strong></p><div id="mq2" class="mq"></div>
<div class="fg" style="max-width:180px"><label>Answer</label><input type="number" id="ma2"></div>
<button class="btn-s" onclick="cm(2)">Verify</button><div id="me2" class="bear" style="font-size:12px"></div></div>
<div id="sf2" style="display:none">{_contact_form(br)}</div></div>
{_aff_html([a for a in br.get("affiliates",[]) if a.get("url")])}
</div>

<footer>
<p>APEX TRADE LAB &mdash; Paper trading simulation only. Not financial advice.</p>
<p>Built with Python, Plotly, GitHub Actions. 100% free.</p>
</footer>

<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<script>
// ===== THEME CONTROLLER =====
const THEMES = {{
    light: {{
        bg: '#f8fafc', card: '#fff', cardInner: '#f8fafc', border: '#e2e8f0',
        text: '#1e293b', muted: '#64748b', gridColor: '#f3f4f6',
        plotBg: '#fff', plotPaper: '#fff', plotFont: '#374151',
        chatU: '#f0fdf4', chatUBorder: '#dcfce7', chatA: '#fff', chatABorder: '#e2e8f0',
        inputBg: '#fff', inputBorder: '#d1d5db', thHead: '#f8fafc',
    }},
    dark: {{
        bg: '#0f172a', card: '#1e293b', cardInner: '#1a2332', border: '#334155',
        text: '#e2e8f0', muted: '#94a3b8', gridColor: '#1e293b',
        plotBg: '#1e293b', plotPaper: '#1e293b', plotFont: '#e2e8f0',
        chatU: 'rgba(34,197,94,.1)', chatUBorder: 'rgba(34,197,94,.2)', chatA: '#1a2332', chatABorder: '#334155',
        inputBg: '#1a2332', inputBorder: '#475569', thHead: '#1a2332',
    }}
}};

function applyTheme(t) {{
    const v = THEMES[t];
    const r = document.documentElement.style;
    r.setProperty('--bg', v.bg);
    r.setProperty('--card', v.card);
    r.setProperty('--card-inner', v.cardInner);
    r.setProperty('--border', v.border);
    r.setProperty('--text', v.text);
    r.setProperty('--muted', v.muted);
    r.setProperty('--grid-color', v.gridColor);
    r.setProperty('--input-bg', v.inputBg);
    r.setProperty('--input-border', v.inputBorder);
    r.setProperty('--th-head', v.thHead);
    r.setProperty('--chat-u', v.chatU);
    r.setProperty('--chat-u-border', v.chatUBorder);
    r.setProperty('--chat-a', v.chatA);
    r.setProperty('--chat-a-border', v.chatABorder);
    document.getElementById('theme-icon').innerHTML = t === 'dark' ? '&#9788;' : '&#9789;';
    // Re-render charts with new theme
    if(window._chartsRendered) renderCharts(v);
    try {{ localStorage.setItem('apex-theme', t); }} catch(e) {{}}
}}

function toggleTheme() {{
    const cur = document.documentElement.style.getPropertyValue('--bg') === '#0f172a' ? 'light' : 'dark';
    applyTheme(cur);
}}

// Init theme
(function() {{
    let t = 'light';
    try {{ t = localStorage.getItem('apex-theme') || 'light'; }} catch(e) {{}}
    applyTheme(t);
}})();

// ===== NAV =====
function go(id,b){{document.querySelectorAll('.pg').forEach(p=>p.classList.remove('on'));document.querySelectorAll('nav>button,nav .dropdown>button').forEach(x=>x.classList.remove('on'));document.getElementById(id).classList.add('on');if(b)b.classList.add('on');window.scrollTo(0,0)}}

// ===== MATH PUZZLES =====
let mv=[0,0,0,0];
function gm(q,i){{const a=5+Math.floor(Math.random()*20),b=3+Math.floor(Math.random()*15);document.getElementById(q).innerHTML='<span style="font-size:18px;font-weight:600;color:var(--green)">'+a+' + '+b+' = ?</span>';mv[i*2]=a;mv[i*2+1]=b}}
window.addEventListener('load',()=>{{gm('mq1',0);gm('mq2',1)}});
function cm(n){{const a=+document.getElementById('ma'+n).value;if(a===mv[(n-1)*2]+mv[(n-1)*2+1]){{document.getElementById('mg'+n).style.display='none';document.getElementById('sf'+n).style.display='block'}}else{{document.getElementById('me'+n).textContent='Incorrect.';gm('mq'+n,n-1)}}}}

// VIP
const VH='{br.get("vip_password_hash","")}';
async function checkVIP(){{const pw=document.getElementById('vip-pw').value;if(!VH){{document.getElementById('vip-err').textContent='VIP not configured.';return}};const h=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(pw)))).map(b=>b.toString(16).padStart(2,'0')).join('');if(h===VH){{document.getElementById('vip-gate').style.display='none';document.getElementById('vip-c').style.display='block'}}else{{document.getElementById('vip-err').textContent='Incorrect.'}}}}

// Regime strip
const RM={regime_map_data};
function buildRS(id,full){{const el=document.getElementById(id);if(!RM.length)return;let h='';RM.forEach(r=>{{const c=r.r==='STRONG UPTREND'?'#22c55e':r.r==='UPTREND'?'#86efac':r.r==='DOWNTREND'?'#f97316':r.r==='STRONG DOWNTREND'?'#ef4444':'#d1d5db';h+=`<div title="${{r.d}}\\n${{r.r}}\\nRSI: ${{r.rsi?.toFixed?.(0)||'?'}}\\nvs SMA250: ${{r.e250?.toFixed?.(1)||'?'}}%" style="flex:1;height:${{full?'28px':'10px'}};background:${{c}}"></div>`}});el.innerHTML=h}}
window.addEventListener('load',()=>{{buildRS('regime-strip',false);buildRS('regime-map',true)}});

// ===== CHART DATA =====
const _D={json.dumps(D)},_EQ={json.dumps(EQ)},_BN={json.dumps(BN)},_DD={json.dumps(DD)};
const _TA={json.dumps(TA)},_SA={json.dumps(SA)},_CA={json.dumps(CA)};
const _NX={json.dumps(NX)},_S20={json.dumps(S20)},_S250={json.dumps(S250)};
const _BD={json.dumps(bd)},_BP={json.dumps(bp)},_BL={json.dumps(bl)};
const _SD={json.dumps(sd)},_SP={json.dumps(sp)},_SL={json.dumps(sl)};
const _RS={_rshapes_light(D,RG)};

window._chartsRendered = false;
function renderCharts(v) {{
    const L = {{paper_bgcolor:v.plotPaper,plot_bgcolor:v.plotBg,font:{{color:v.plotFont,family:'Inter,sans-serif',size:12}},margin:{{t:8,r:20,b:35,l:55}},xaxis:{{gridcolor:v.gridColor}},yaxis:{{gridcolor:v.gridColor}},legend:{{bgcolor:'rgba(0,0,0,0)',x:0,y:1}},hovermode:'x unified'}};

    Plotly.newPlot('eq-c',[
        {{x:_D,y:_EQ,name:'APEX',line:{{color:'#22c55e',width:2}}}},
        {{x:_D,y:_BN,name:'QQQ',line:{{color:'#f59e0b',width:1,dash:'dot'}}}}
    ],{{...L,yaxis:{{...L.yaxis,title:'Portfolio Value ($)'}},height:360}},{{responsive:true}});

    Plotly.newPlot('dd-c',[
        {{x:_D,y:_DD,name:'Drawdown',fill:'tozeroy',fillcolor:'rgba(239,68,68,.15)',line:{{color:'#ef4444',width:1.5}}}}
    ],{{...L,yaxis:{{...L.yaxis,title:'Drawdown %'}},height:200}},{{responsive:true}});

    // Regime shapes need to adapt colors for dark mode
    const rsAdapted = v.plotBg === '#fff' ? _RS : _RS.map(s => {{
        const ns = {{...s}};
        if(ns.fillcolor) ns.fillcolor = ns.fillcolor.replace(/\\.0[468]\\)/,'.12)');
        return ns;
    }});

    Plotly.newPlot('nx-c',[
        {{x:_D,y:_NX,name:'NDX',line:{{color:v.plotFont==='#e2e8f0'?'#e2e8f0':'#374151',width:1.5}}}},
        {{x:_D,y:_S20,name:'SMA(20)',line:{{color:'#f59e0b',width:1,dash:'dash'}}}},
        {{x:_D,y:_S250,name:'SMA(250)',line:{{color:'#ef4444',width:1.5,dash:'dash'}}}},
        {{x:_BD,y:_BP,name:'Buy',mode:'markers',text:_BL,marker:{{color:'#22c55e',size:8,symbol:'triangle-up'}},hoverinfo:'text'}},
        {{x:_SD,y:_SP,name:'Sell',mode:'markers',text:_SL,marker:{{color:'#ef4444',size:8,symbol:'triangle-down'}},hoverinfo:'text'}}
    ],{{...L,yaxis:{{...L.yaxis,title:'NDX'}},shapes:_RS,height:400}},{{responsive:true}});

    Plotly.newPlot('al-c',[
        {{x:_D,y:_TA,name:'TQQQ%',fill:'tozeroy',fillcolor:'rgba(34,197,94,.2)',line:{{color:'#22c55e'}},stackgroup:'a'}},
        {{x:_D,y:_SA,name:'SQQQ%',fill:'tonexty',fillcolor:'rgba(239,68,68,.2)',line:{{color:'#ef4444'}},stackgroup:'a'}},
        {{x:_D,y:_CA,name:'Cash%',fill:'tonexty',fillcolor:'rgba(148,163,184,.1)',line:{{color:'#94a3b8'}},stackgroup:'a'}}
    ],{{...L,yaxis:{{...L.yaxis,title:'%',range:[0,105]}},height:260}},{{responsive:true}});

    window._chartsRendered = true;
}}

// Initial chart render
window.addEventListener('load', () => {{
    let t = 'light';
    try {{ t = localStorage.getItem('apex-theme') || 'light'; }} catch(e) {{}}
    renderCharts(THEMES[t]);
}});

// ===== CALCULATORS =====
function cPos(){{const a=+document.getElementById('psa').value,r=+document.getElementById('psr').value/100,e=+document.getElementById('pse').value,s=+document.getElementById('pss').value,i=document.getElementById('psi').value;if(!a||!e||!s||s>=e){{document.getElementById('pso').innerHTML='<span class="bear">Entry must be above stop.</span>';return}};const rd=a*r,rps=Math.abs(e-s),sh=Math.floor(rd/rps),pv=sh*e,pp=pv/a*100;document.getElementById('pso').innerHTML='<div class="rr"><span>Risk Amount</span><span class="bear">$'+rd.toFixed(0)+'</span></div><div class="rr"><span>Shares</span><span class="bull">'+sh+' '+i+'</span></div><div class="rr"><span>Position Value</span><span>$'+pv.toFixed(0)+' ('+pp.toFixed(0)+'%)</span></div><div class="rr"><span>Max Loss</span><span class="bear">$'+(sh*rps).toFixed(0)+'</span></div><hr style="border-color:var(--border)"><div class="rr"><span>Target 1.5R</span><span class="bull">$'+(e+rps*1.5).toFixed(2)+'</span></div><div class="rr"><span>Target 2R</span><span class="bull">$'+(e+rps*2).toFixed(2)+'</span></div><div class="note">Sell 50% at Target 1, stop to breakeven. Trail rest.</div>'}}
function cATR(){{const a=+document.getElementById('sla').value,m=+document.getElementById('slam').value,e=+document.getElementById('pse')?.value||75,s=e-(a*m);document.getElementById('slar').textContent='Stop: $'+s.toFixed(2)+' ('+((e-s)/e*100).toFixed(1)+'% risk)'}}
function cFix(){{const e=+document.getElementById('slfe').value,p=+document.getElementById('slfp').value/100,s=e*(1-p);document.getElementById('slfr').textContent='Stop: $'+s.toFixed(2)+' ($'+(e-s).toFixed(2)+'/share)'}}

// ===== AI CHAT =====
const CD={cd};
const SYS='You are APEX TRADE LAB AI Analyst. Analyze paper trading data from a 7-strategy TQQQ/SQQQ system. Be educational, concise. PAPER TRADING only.\\nDATA:\\n'+JSON.stringify(CD);
let ak='',ah=[],ap='anthropic';
function initAI(){{ap=document.getElementById('aip').value;ak=document.getElementById('aik').value.trim();if(!ak||ak.length<10){{alert('Enter valid key');return}};document.getElementById('ai-s').style.display='none';document.getElementById('ai-b').style.display='flex';aM('a','Connected ('+ap+'). Data loaded.')}}
function aM(r,t){{const d=document.getElementById('msgs'),m=document.createElement('div');m.className='chat-msg chat-'+(r==='u'?'u':'a');m.textContent=t;d.appendChild(m);d.scrollTop=d.scrollHeight}}
function aQ(q){{document.getElementById('ain').value=q;sAI()}}
async function sAI(){{const q=document.getElementById('ain').value.trim();if(!q)return;document.getElementById('ain').value='';aM('u',q);ah.push({{role:'user',content:q}});document.getElementById('aib').disabled=true;
try{{let r='';if(ap==='anthropic'){{const f=await fetch('https://api.anthropic.com/v1/messages',{{method:'POST',headers:{{'Content-Type':'application/json','x-api-key':ak,'anthropic-version':'2023-06-01','anthropic-dangerous-direct-browser-access':'true'}},body:JSON.stringify({{model:'claude-sonnet-4-20250514',max_tokens:1000,system:SYS,messages:ah.slice(-8)}})}});const d=await f.json();r=d.content?.map(c=>c.text||'').join('\\n')||d.error?.message||'Error'}}else{{const f=await fetch('https://api.openai.com/v1/chat/completions',{{method:'POST',headers:{{'Content-Type':'application/json','Authorization':'Bearer '+ak}},body:JSON.stringify({{model:'gpt-4o',max_tokens:1000,messages:[{{role:'system',content:SYS}},...ah.slice(-8)]}})}}); const d=await f.json();r=d.choices?.[0]?.message?.content||d.error?.message||'Error'}}
aM('a',r);ah.push({{role:'assistant',content:r}})}}catch(e){{aM('a','Error: '+e.message)}}document.getElementById('aib').disabled=false}}

// Tooltips
document.addEventListener('DOMContentLoaded',()=>{{document.querySelectorAll('.tip').forEach(el=>{{el.addEventListener('mouseenter',e=>{{const t=el.getAttribute('data-tip');const d=document.createElement('div');d.className='tip-box';d.textContent=t;d.style.left=Math.min(e.pageX,window.innerWidth-260)+'px';d.style.top=(e.pageY-40)+'px';document.body.appendChild(d);el._tip=d}});el.addEventListener('mouseleave',()=>{{if(el._tip)el._tip.remove()}})}});}});
</script></body></html>'''


# =====================================================================
# HELPERS
# =====================================================================

def _tip(text):
    return f'<span class="tip" data-tip="{text}">&#9432;</span>'

def _action_text(la):
    t,s = la.get('tqqq_alloc',0), la.get('sqqq_alloc',0)
    if t > 50: return f"Buy TQQQ ({t:.0f}%)"
    elif t > 0: return f"Light TQQQ ({t:.0f}%)"
    elif s > 50: return f"Short via SQQQ ({s:.0f}%)"
    elif s > 0: return f"Light SQQQ ({s:.0f}%)"
    return "Cash"

def _human_reason(la):
    d = la.get("strategy_details","")
    if not d: return "No active strategies. The system is in cash, waiting for conditions to align."
    return d.replace(";",". ").replace("MR Long","Mean Reversion Long").replace("Mom Short","Momentum Short")

def _human_trade(t):
    tt = t.get("trade_type","")
    strat = t.get("strategy","")
    if tt == "NEW ENTRY": return f"New position. {strat} detected an opportunity."
    elif tt == "EXIT": return f"Position closed. {strat} exit signal."
    elif tt == "ADD": return f"Added to position. Continued strength."
    elif tt == "REDUCE": return f"Reduced position. Partial profits."
    return f"{tt}: {strat}"

def _next_review():
    now = datetime.utcnow()
    d = now.replace(hour=21, minute=30, second=0)
    if now.hour >= 21: d += timedelta(days=1)
    while d.weekday() >= 5: d += timedelta(days=1)
    return f"Next review: {d.strftime('%A %b %d')} ~7:00 AM Darwin"

def _calc_drawdown_series(eq_values):
    """Calculate drawdown % series from equity values."""
    if not eq_values: return []
    peak = eq_values[0]
    dd = []
    for v in eq_values:
        if v > peak: peak = v
        dd.append(round((v - peak) / peak * 100, 2) if peak > 0 else 0)
    return dd

def _calc_weekly_summary(eh, tl, stats):
    """Calculate week and MTD performance."""
    if len(eh) < 2:
        return {"week_pct":0, "mtd_pct":0, "week_trades":0}
    # Last 5 days
    recent5 = eh[-5:] if len(eh)>=5 else eh
    w_start = recent5[0].get("equity",1)
    w_end = recent5[-1].get("equity",1)
    week_pct = ((w_end - w_start) / w_start * 100) if w_start > 0 else 0

    # MTD
    today = eh[-1].get("date","")[:7]  # YYYY-MM
    month_rows = [r for r in eh if r.get("date","").startswith(today)]
    if month_rows:
        m_start = month_rows[0].get("equity",1)
        m_end = month_rows[-1].get("equity",1)
        mtd_pct = ((m_end - m_start) / m_start * 100) if m_start > 0 else 0
    else:
        mtd_pct = 0

    # Trades this week
    if recent5:
        week_start_date = recent5[0].get("date","")
        week_trades = len([t for t in tl if t.get("date","") >= week_start_date])
    else:
        week_trades = 0

    return {"week_pct": round(week_pct,1), "mtd_pct": round(mtd_pct,1), "week_trades": week_trades}

def _calc_pnl(eh, tl):
    return {"total_pnl": sum(t.get("realized_pnl",0) for t in tl)}

def _trade_row_human(t):
    tt=t.get("trade_type","")
    tc={"NEW ENTRY":"te","EXIT":"tx","ADD":"ta","REDUCE":"tr"}.get(tt,"")
    pnl=t.get("realized_pnl",0)
    ps=f"${pnl:+,.0f}" if pnl else "—"
    pc="bull" if pnl>0 else "bear" if pnl<0 else ""
    return f'<tr><td>{t["date"]}</td><td class="{tc}">{tt}</td><td>{t["ticker"]}</td><td class="{"bull" if t["action"]=="BUY" else "bear"}">{t["action"]}</td><td>{t["shares"]:.1f}</td><td>${t["price"]:,.2f}</td><td>${t["value"]:,.0f}</td><td class="{pc}">{ps}</td><td style="font-size:11px">{t.get("strategy","")}</td><td style="font-size:11px;color:var(--muted)">{_human_trade(t)}</td><td>{t.get("regime","")}</td></tr>'

def _strategies_explained():
    strats = [
        ("Momentum Long","TQQQ","Uptrend","NDX breaks above upper Bollinger Band + above SMA(20).","Ride strong upward momentum.","Stops if NDX closes below SMA(20).","In a strong bull, NDX pushes above the upper BB. System goes heavily long."),
        ("MR Long 1 (SMA20 Pullback)","TQQQ","Uptrend","NDX pulls back to within 1% of SMA(20).","Buy dips in uptrends.","Exits if NDX extends 3%+ above SMA(20).","After a 2-3% pullback in a bull market, the system buys expecting a bounce."),
        ("MR Long 2 (Deep Pullback)","TQQQ","Uptrend","NDX drops below lower Bollinger Band but above SMA(250).","Buy deep dips aggressively.","Exits above middle BB.","A sharp 5%+ pullback in uptrend — the system sees a sale."),
        ("MR Long 3 (SMA250 Bounce)","TQQQ","Near SMA(250)","NDX within 3% of SMA(250) + bullish candle.","Catch bounces at the critical SMA(250) support.","Exits if extended 5%+ above SMA(20).","NDX tests its 250-day average and bounces."),
        ("MR Short (Overextension)","SQQQ","Uptrend (extended)","NDX 4%+ above SMA(20) AND above upper BB.","Fade extreme overextension.","Exits when NDX reverts to SMA(20).","After a massive rally, the system takes a small contrarian short."),
        ("Momentum Short 1 (Breakdown)","SQQQ","Downtrend","NDX closes below SMA(250) + below lower BB.","Ride the downtrend. Size scales with depth.","Exits when NDX reclaims SMA(250).","NDX breaks its 250-day average — major bearish signal."),
        ("Momentum Short 2 (Failed Bounce)","SQQQ","Downtrend","NDX bounced to SMA(20) then closed below it.","Short bull traps in bear markets.","Exits if above SMA(20) for 3 days.","In a downtrend, a rally that fails is a classic short entry."),
    ]
    html = ""
    for name,inst,regime,entry,goal,risk,example in strats:
        e = "&#128994;" if inst=="TQQQ" else "&#128308;"
        html += f'<div class="strat-card"><div class="strat-head"><span>{e} {name}</span><span class="strat-inst">{inst}</span></div><div class="strat-row"><strong>When:</strong> {regime}</div><div class="strat-row"><strong>Entry:</strong> {entry}</div><div class="strat-row"><strong>Goal:</strong> {goal}</div><div class="strat-row"><strong>Risk:</strong> {risk}</div><div class="strat-row"><strong>Example:</strong> <em>{example}</em></div></div>'
    return html

def _stress_table(results):
    if not results: return '<p class="desc">No stress test data. Run <code>python main.py --stress-test</code>.</p>'
    rows = ""
    for r in results:
        sc = "bull" if r.get("system_estimated_pct",0)>0 else "bear"
        rows += f'<tr><td><strong>{r["name"]}</strong></td><td>{r["start"]} to {r["end"]}</td><td class="bear">{r.get("ndx_return_pct",0):+.1f}%</td><td class="bear">{r.get("tqqq_estimated_pct",0):+.1f}%</td><td class="{sc}">{r.get("system_estimated_pct",0):+.1f}%</td><td class="bear">{r.get("max_drawdown_pct",0):.1f}%</td><td>{r.get("recovery_days","?")}d</td></tr>'
    return f'<div class="tbl-wrap"><table><thead><tr><th>Scenario</th><th>Period</th><th>NDX</th><th>TQQQ (est)</th><th>System (est)</th><th>Max DD</th><th>Recovery</th></tr></thead><tbody>{rows}</tbody></table></div>'

def _social_posts_section(posts):
    if not posts: return ""
    html = '<div class="card"><h2>Social Posts (Ready to Copy)</h2><p class="desc">Review and copy-paste to your platforms.</p>'
    for p in posts:
        html += f'<div class="card-inner" style="margin-bottom:8px"><h3>{p.get("type","").title()} — {p.get("date","")}</h3>'
        html += f'<div style="margin-top:6px"><strong>Twitter/X:</strong><pre class="social-pre">{p.get("twitter","")}</pre></div>'
        html += f'<div style="margin-top:4px"><strong>Facebook:</strong><pre class="social-pre">{p.get("facebook","")}</pre></div></div>'
    return html + '</div>'

def _vip_content(la, stats, trans, recent):
    lt = trans[-1] if trans else {}; lt2 = recent[-1] if recent else {}
    return f'<div class="card-inner" style="border-left:3px solid var(--purple)"><h3 style="color:var(--purple)">Analyst Notes — {la.get("date","")}</h3><p><strong>Regime:</strong> {la.get("regime","")}. NDX {la.get("ext_sma250",0):+.1f}% from SMA(250). RSI {la.get("rsi",50):.0f}.</p><p><strong>Performance:</strong> {stats.get("total_return_pct",0):+.1f}% total, {stats.get("max_drawdown_pct",0):.1f}% max DD.</p><p><strong>Last shift:</strong> {lt.get("from","?")} &rarr; {lt.get("to","?")} on {lt.get("date","")}.</p><p><strong>Last trade:</strong> {lt2.get("action","")} {lt2.get("ticker","")} on {lt2.get("date","")} — {lt2.get("strategy","")}</p></div>'

def _stripe_section(br):
    url = br.get("stripe_payment_url","")
    if not url: return ""
    return f'<div class="card"><h2>Support This Project</h2><p class="desc">100% goes toward keeping the platform running.</p><div style="text-align:center;padding:12px"><a href="{url}" target="_blank" rel="noopener" class="btn" style="display:inline-block;text-decoration:none">&#9889; Support ($5) via Stripe</a></div></div>'

def _contact_form(br):
    fs = br.get("formspree_endpoint","")
    if not fs: return f'<p class="desc">Contact form coming soon.{" Email: "+br.get("contact_email","") if br.get("contact_email") else ""}</p>'
    return f'<form action="{fs}" method="POST" style="max-width:500px"><div class="fg"><label>I am a...</label><select name="user_type"><option>Individual Investor</option><option>Institutional Investor</option><option>Trading Beginner</option><option>Quant / Developer</option><option>Content Creator</option></select></div><div class="fg"><label>Interest</label><select name="interest"><option>Daily Signals</option><option>Strategy Research</option><option>Learning Systematic Trading</option><option>Backtesting Tools</option><option>Collaboration</option></select></div><div class="fg"><label>Inquiry</label><select name="service"><option>Custom Dashboard</option><option>Backtest Report</option><option>Advertising</option><option>General</option></select></div><div class="fg"><label>Name</label><input type="text" name="name" required></div><div class="fg"><label>Email</label><input type="email" name="email" required></div><div class="fg"><label>Message</label><textarea name="message" rows="3" style="width:100%;padding:6px;border:1px solid var(--input-border);border-radius:6px;font-size:13px;resize:vertical;background:var(--input-bg);color:var(--text)"></textarea></div><input type="text" name="_gotcha" style="display:none"><button type="submit" class="btn">Send</button></form>'

def _aff_html(affs):
    if not affs: return ''
    cards=''.join(f'<div class="card-inner"><h3>{a["name"]}</h3><p class="desc">{a.get("tagline","")}</p><a href="{a["url"]}" target="_blank" rel="noopener noreferrer" class="btn-s" style="display:inline-block;text-decoration:none">Open Account &rarr;</a></div>' for a in affs)
    return f'<div class="card"><h2>Recommended Brokers</h2><p class="desc" style="font-size:11px">Affiliate links — commission at no cost to you.</p><div class="grid-3">{cards}</div></div>'

def _nb(bd,D,cap):
    if bd is None or bd.empty: return [None]*len(D)
    bs=bd["Close"].iloc[0]
    return [round(bd.loc[bd.index<=pd.Timestamp(d)].iloc[-1]["Close"]/bs*cap,2) if not bd.loc[bd.index<=pd.Timestamp(d)].empty else None for d in D]

def _rshapes_light(D,RG):
    if not D: return "[]"
    sh,i=[],0
    while i<len(D):
        rg,s=RG[i],D[i]
        while i<len(D) and RG[i]==rg: i+=1
        c={"STRONG UPTREND":"rgba(34,197,94,.08)","UPTREND":"rgba(134,239,172,.06)","DOWNTREND":"rgba(249,115,22,.06)","STRONG DOWNTREND":"rgba(239,68,68,.08)"}.get(rg,"rgba(209,213,219,.04)")
        sh.append(f'{{"type":"rect","xref":"x","yref":"paper","x0":"{s}","x1":"{D[i-1]}","y0":0,"y1":1,"fillcolor":"{c}","line":{{"width":0}}}}')
    return "["+",".join(sh)+"]"

def _rtrans(eh):
    tr,prev,pd_=[],None,None
    for r in eh:
        rg=r.get("regime","")
        if rg!=prev and prev:
            dur=0
            if pd_:
                try: dur=(pd.Timestamp(r["date"])-pd.Timestamp(pd_)).days
                except: pass
            m={"STRONG UPTREND,UPTREND":"Momentum fading. Still bullish.","UPTREND,STRONG UPTREND":"Acceleration! Scaling up.","UPTREND,DOWNTREND":"Critical: below SMA(250). Switching to SQQQ.","DOWNTREND,UPTREND":"Recovery: reclaimed SMA(250). Switching to TQQQ.","DOWNTREND,STRONG DOWNTREND":"Deepening. Increasing SQQQ.","STRONG DOWNTREND,DOWNTREND":"Easing. Reducing shorts.","STRONG UPTREND,DOWNTREND":"Sharp reversal! Closing longs.","STRONG DOWNTREND,UPTREND":"V-recovery! Going long."}.get(f"{prev},{rg}",f"{prev} to {rg}")
            tr.append({"date":r["date"],"from":prev,"to":rg,"ndx":r.get("ndx_close",0),"dur":dur,"m":m})
        if rg!=prev: pd_=r["date"]
        prev=rg
    return tr

def _trow(t):
    return f'<tr><td>{t["date"]}</td><td class="{"bull" if "UP" in t["from"] else "bear"}">{t["from"]}</td><td class="{"bull" if "UP" in t["to"] else "bear"}">{t["to"]}</td><td>{t["ndx"]:,.0f}</td><td>{t["dur"]} days</td><td style="font-size:12px;color:var(--muted)">{t["m"]}</td></tr>'

def _rcards(rs):
    if not rs: return '<p class="desc">Not enough data.</p>'
    cards=[]
    for r in ["STRONG UPTREND","UPTREND","DOWNTREND","STRONG DOWNTREND"]:
        if r not in rs: continue
        s=rs[r]; bc={"STRONG UPTREND":"#22c55e","UPTREND":"#86efac","DOWNTREND":"#f97316","STRONG DOWNTREND":"#ef4444"}[r]
        rc="bull" if s["total_return_pct"]>0 else "bear"
        cards.append(f'<div class="card-inner" style="border-top:3px solid {bc}"><h3>{r}</h3><div class="mini-stats"><div><span class="desc">Time</span><br><strong>{s["pct_of_time"]}%</strong></div><div><span class="desc">Days</span><br><strong>{s["days"]}</strong></div><div><span class="desc">Return</span><br><strong class="{rc}">{s["total_return_pct"]:+.1f}%</strong></div><div><span class="desc">Trades</span><br><strong>{s["trades"]}</strong></div></div></div>')
    return "".join(cards)


# =====================================================================
# CSS — Theme-aware with CSS custom properties
# =====================================================================

def _css(br):
    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>APEX TRADE LAB — Systematic Trading Research</title>
<meta name="description" content="Free autonomous paper trading. 7-strategy TQQQ/SQQQ system with AI analyst, regime analysis, stress testing.">
<meta property="og:title" content="APEX TRADE LAB"><meta name="theme-color" content="#22c55e">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#9889;</text></svg>">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Code+Pro:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {{
    --bg: #f8fafc; --card: #fff; --card-inner: #f8fafc; --border: #e2e8f0;
    --text: #1e293b; --muted: #64748b; --grid-color: #f3f4f6;
    --green: #22c55e; --red: #ef4444; --yellow: #f59e0b; --blue: #3b82f6; --purple: #7c3aed;
    --input-bg: #fff; --input-border: #d1d5db; --th-head: #f8fafc;
    --chat-u: #f0fdf4; --chat-u-border: #dcfce7; --chat-a: #fff; --chat-a-border: #e2e8f0;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);line-height:1.6;font-size:14px;transition:background .2s,color .2s}}
::selection{{background:var(--green);color:#fff}}

/* Header */
header{{background:var(--card);border-bottom:1px solid var(--border);padding:16px 24px;transition:background .2s}}
.hdr-inner{{max-width:1200px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}}
.hdr-brand{{}}
.logo{{font-family:'Source Code Pro',monospace;font-size:22px;font-weight:700;color:var(--text);letter-spacing:1px}}
.tagline{{color:var(--muted);font-size:11px;letter-spacing:2px;text-transform:uppercase}}
.hdr-right{{display:flex;align-items:center;gap:12px}}
.live-badge{{font-size:11px;color:var(--muted)}}
.dot{{display:inline-block;width:7px;height:7px;background:var(--green);border-radius:50%;margin-right:3px;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.theme-toggle{{background:var(--card-inner);border:1px solid var(--border);width:36px;height:36px;border-radius:8px;cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;transition:.2s;color:var(--text)}}
.theme-toggle:hover{{border-color:var(--green)}}

/* Nav */
nav{{display:flex;gap:2px;justify-content:center;padding:8px 12px;background:var(--card);border-bottom:1px solid var(--border);flex-wrap:wrap;position:sticky;top:0;z-index:100;transition:background .2s}}
nav button{{background:none;border:none;color:var(--muted);padding:8px 14px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500;transition:.15s}}
nav button:hover{{color:var(--text);background:var(--card-inner)}}
nav button.on{{color:var(--green);background:rgba(34,197,94,.08);font-weight:600}}
.dropdown{{position:relative}}.dropdown-menu{{display:none;position:absolute;top:100%;left:0;background:var(--card);border:1px solid var(--border);border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.1);min-width:160px;z-index:200;padding:4px}}
.dropdown.open .dropdown-menu{{display:block}}.dropdown-menu a{{display:block;padding:8px 14px;color:var(--text);font-size:13px;cursor:pointer;border-radius:4px}}.dropdown-menu a:hover{{background:rgba(34,197,94,.08);color:var(--green)}}

.pg{{display:none;padding:16px;max-width:1200px;margin:0 auto}}.pg.on{{display:block}}

/* Cards */
.card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.04);transition:background .2s,border-color .2s}}
.card h2{{font-size:16px;font-weight:600;margin-bottom:10px}}.card h3{{font-size:14px;font-weight:600;margin-bottom:6px}}
.card-inner{{background:var(--card-inner);border:1px solid var(--border);border-radius:8px;padding:14px;transition:background .2s}}
.desc{{color:var(--muted);font-size:13px;margin-bottom:8px}}
.bull{{color:#16a34a}}.bear{{color:#dc2626}}.te{{color:#16a34a;font-weight:600}}.tx{{color:#dc2626;font-weight:600}}.ta{{color:#2563eb}}.tr{{color:#d97706}}

/* Signal Card */
.signal-card{{background:var(--card);border:2px solid var(--border);border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 2px 12px rgba(0,0,0,.06);transition:all .2s}}
.signal-card.bull{{border-color:var(--green)}}.signal-card.bear{{border-color:var(--red)}}
.sc-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}}
.sc-badge{{font-family:'Source Code Pro',monospace;font-size:11px;letter-spacing:2px;color:var(--muted);text-transform:uppercase;background:var(--card-inner);padding:4px 12px;border-radius:4px;border:1px solid var(--border)}}
.sc-next{{font-size:11px;color:var(--muted)}}
.sc-grid{{display:grid;grid-template-columns:1fr 1fr 2fr 2fr;gap:20px;align-items:start}}
.sc-label{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}}
.sc-val{{font-family:'Source Code Pro',monospace;font-weight:700}}.sc-val.bull{{color:#16a34a}}.sc-val.bear{{color:#dc2626}}
.sc-alloc-bars{{display:flex;flex-direction:column;gap:8px}}
.ab{{display:flex;align-items:center;gap:8px}}.ab-l{{width:38px;font-size:11px;color:var(--muted)}}.ab-track{{flex:1;height:10px;background:var(--card-inner);border-radius:5px;overflow:hidden;border:1px solid var(--border)}}
.ab-fill{{height:100%;border-radius:5px;transition:width .3s}}.ab-fill.bull{{background:var(--green)}}.ab-fill.bear{{background:var(--red)}}.ab-fill.cash{{background:#94a3b8}}.ab-v{{width:36px;font-size:12px;font-weight:600;text-align:right;font-family:'Source Code Pro',monospace}}
.sc-ctx{{display:flex;flex-direction:column;gap:2px;font-size:12px;color:var(--muted)}}
.sc-reason{{margin-top:16px;padding:12px;background:var(--card-inner);border-radius:6px;font-size:13px;color:var(--muted);border-left:3px solid var(--green)}}
.signal-card.bear .sc-reason{{border-left-color:var(--red)}}

/* Stats */
.stats-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin-bottom:16px}}
.stat{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center;transition:background .2s}}
.stat-l{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.3px}}.stat-v{{font-family:'Source Code Pro',monospace;font-size:20px;font-weight:700;margin-top:2px}}

/* Weekly Summary */
.weekly-card{{border-color:var(--green);border-width:1px}}
.wk-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}}
.wk-item{{text-align:center;padding:10px;background:var(--card-inner);border-radius:8px;border:1px solid var(--border)}}
.wk-label{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.3px}}.wk-val{{font-family:'Source Code Pro',monospace;font-size:18px;font-weight:700;margin-top:4px}}

/* Regime */
.regime-strip,.regime-strip-full{{display:flex;border-radius:4px;overflow:hidden;margin-top:8px}}
.regime-badge-wrap{{display:flex;align-items:center;gap:16px;flex-wrap:wrap}}
.regime-badge{{font-family:'Source Code Pro',monospace;font-size:18px;font-weight:700;padding:10px 24px;border-radius:8px;border:2px solid}}
.regime-badge.bull{{color:#16a34a;border-color:var(--green);background:rgba(34,197,94,.08)}}.regime-badge.bear{{color:#dc2626;border-color:var(--red);background:rgba(239,68,68,.08)}}
.regime-metas{{display:flex;gap:16px;font-size:13px;color:var(--muted)}}

/* Grids */
.grid-2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}
.grid-3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}
.grid-4{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}}
.mini-stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:8px;text-align:center;font-size:13px}}

/* Tables */
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:var(--th-head);color:var(--muted);padding:8px 6px;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.3px;font-weight:600;border-bottom:2px solid var(--border)}}
td{{padding:6px;border-bottom:1px solid var(--border)}}.tbl-wrap{{overflow-x:auto}}.mini-tbl{{font-size:12px}}.mini-tbl th{{font-size:9px}}

/* Calculators */
.calc-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.calc-in{{display:flex;flex-direction:column;gap:6px}}.calc-out{{background:var(--card-inner);border:1px solid var(--border);border-radius:8px;padding:16px}}
.fg{{margin-bottom:6px}}.fg label{{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.3px;margin-bottom:2px}}
.fg input,.fg select{{width:100%;padding:8px 10px;border:1px solid var(--input-border);border-radius:6px;font-size:13px;font-family:'Source Code Pro',monospace;background:var(--input-bg);color:var(--text);transition:background .2s,border-color .2s}}
.btn{{background:var(--green);color:#fff;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px}}.btn:hover{{filter:brightness(.9)}}
.btn-s{{background:var(--yellow);color:#fff;border:none;padding:6px 12px;border-radius:4px;cursor:pointer;font-weight:600;font-size:11px}}
.rr{{display:flex;justify-content:space-between;margin:3px 0;font-size:13px}}.rr span:first-child{{color:var(--muted)}}.rr span:last-child{{font-family:'Source Code Pro',monospace;font-weight:600}}
.note{{color:var(--yellow);font-size:11px;margin-top:6px}}.formula{{background:rgba(34,197,94,.06);padding:6px 10px;border-radius:4px;font-family:'Source Code Pro',monospace;font-size:12px;margin:6px 0;color:#16a34a;border:1px solid rgba(34,197,94,.15)}}
.result{{margin-top:6px;font-family:'Source Code Pro',monospace;font-size:13px}}.placeholder{{color:var(--muted);text-align:center;padding:20px}}
.hint{{font-size:12px;color:var(--muted);margin-top:6px}}.hint a{{color:var(--blue)}}

/* Strategy cards */
.strat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}}
.strat-card{{background:var(--card-inner);border:1px solid var(--border);border-radius:8px;padding:14px}}
.strat-head{{display:flex;justify-content:space-between;font-weight:600;margin-bottom:8px;font-size:14px}}
.strat-inst{{font-size:12px;padding:2px 8px;border-radius:4px;background:rgba(34,197,94,.08);color:#16a34a}}
.strat-row{{font-size:12px;margin:4px 0;color:var(--muted)}}.strat-row strong{{color:var(--text)}}

/* Chat */
.chat-box{{display:flex;flex-direction:column;height:460px;background:var(--card-inner);border:1px solid var(--border);border-radius:8px;overflow:hidden}}
.chat-msgs{{flex:1;overflow-y:auto;padding:10px;display:flex;flex-direction:column;gap:6px}}
.chat-msg{{padding:8px 12px;border-radius:8px;font-size:12px;max-width:85%;white-space:pre-wrap;line-height:1.5}}
.chat-u{{background:var(--chat-u);align-self:flex-end;border:1px solid var(--chat-u-border)}}.chat-a{{background:var(--chat-a);align-self:flex-start;border:1px solid var(--chat-a-border)}}
.chat-suggest{{display:flex;flex-wrap:wrap;gap:4px;padding:6px;border-top:1px solid var(--border)}}
.chat-suggest button{{background:var(--card);border:1px solid var(--border);color:var(--text);padding:4px 10px;border-radius:14px;cursor:pointer;font-size:10px}}.chat-suggest button:hover{{border-color:var(--green);color:#16a34a}}
.chat-input{{display:flex;gap:4px;padding:6px;border-top:1px solid var(--border)}}
.chat-input input{{flex:1;padding:8px 12px;border:1px solid var(--input-border);border-radius:6px;font-size:12px;outline:none;background:var(--input-bg);color:var(--text)}}
.chat-input button{{background:var(--green);color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:600}}

/* Social posts */
.social-pre{{background:var(--card-inner);padding:10px;border-radius:6px;font-size:11px;white-space:pre-wrap;border:1px solid var(--border);color:var(--text);font-family:'Source Code Pro',monospace}}

/* Subscribe */
.math-gate{{background:var(--card-inner);border:1px solid var(--border);border-radius:8px;padding:14px;max-width:340px}}.mq{{margin:6px 0}}

/* Start Here */
.start-here{{border:2px solid var(--green);background:rgba(34,197,94,.03)}}.start-here h2{{color:#16a34a}}
.start-here ol{{margin:8px 0 8px 20px;color:var(--muted)}}.start-here ol li{{margin:4px 0}}

/* Tooltips */
.tip{{color:var(--muted);cursor:help;font-size:14px;margin-left:4px}}
.tip-box{{position:absolute;background:#1e293b;color:#f1f5f9;padding:6px 10px;border-radius:6px;font-size:11px;max-width:240px;z-index:300;pointer-events:none;box-shadow:0 2px 8px rgba(0,0,0,.2)}}

footer{{text-align:center;padding:20px;color:var(--muted);font-size:11px;border-top:1px solid var(--border);margin-top:20px}}footer p{{margin:3px 0}}

@media(max-width:768px){{
.sc-grid{{grid-template-columns:1fr 1fr}}.stats-row,.wk-grid{{grid-template-columns:repeat(2,1fr)}}
.calc-grid,.grid-2,.grid-3,.grid-4,.strat-grid{{grid-template-columns:1fr}}
.hdr-inner{{flex-direction:column;text-align:center}}
nav{{gap:1px}}nav button{{padding:6px 8px;font-size:11px}}
}}
</style></head>'''


# =====================================================================
# OUTPUT
# =====================================================================

def save_dashboard(html, config):
    d=Path(config["outputs"]["html_dir"]); d.mkdir(parents=True,exist_ok=True)
    p=d/config["outputs"]["dashboard_html"]
    with open(p,"w") as f: f.write(html)
    logger.info(f"Dashboard: {p}"); return p

def save_csvs(portfolio, config):
    d=Path(config["outputs"]["csv_dir"]); d.mkdir(parents=True,exist_ok=True)
    if portfolio.equity_history: pd.DataFrame(portfolio.equity_history).to_csv(d/config["outputs"]["equity_csv"],index=False)
    if portfolio.trade_log: pd.DataFrame(portfolio.trade_log).to_csv(d/config["outputs"]["trades_csv"],index=False)
    if portfolio.signal_log: pd.DataFrame(portfolio.signal_log).to_csv(d/config["outputs"]["signals_csv"],index=False)
