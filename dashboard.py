"""
dashboard.py - APEX TRADE LAB Trading Cockpit
Customized for $10,000 Brisbane Execution.
"""

import json, logging, hashlib
from datetime import datetime
from pathlib import Path
from typing import List
import numpy as np, pandas as pd

logger = logging.getLogger(__name__)

# Helper to make strategy names friendly for beginners
def clean_strat_name(name):
    mapping = {
        "momentum_long_1": "Trend Follower (TQQQ)",
        "mean_reversion_long_1": "SMA20 Pullback (TQQQ)",
        "mean_reversion_long_2": "Deep Dip Buyer (TQQQ)",
        "mean_reversion_long_3": "Long Term Value (TQQQ)",
        "mean_reversion_short_1": "Overbought Hedge (SQQQ)",
        "momentum_short_1": "Bear Market Trend (SQQQ)",
        "momentum_short_2": "Crash Accelerator (SQQQ)"
    }
    return mapping.get(name, name)

# ===== MAIN GENERATOR =====

def generate_dashboard(equity_history, trade_log, signal_log, stats, benchmark_data, config):
    D = [r["date"] for r in equity_history]
    EQ = [r["equity"] for r in equity_history]
    TA = [r.get("tqqq_alloc",0) for r in equity_history]
    SA = [r.get("sqqq_alloc",0) for r in equity_history]
    CA = [r.get("cash_alloc",100) for r in equity_history]
    NX = [r.get("ndx_close",0) for r in equity_history]
    S20 = [r.get("sma20") for r in equity_history]
    S250 = [r.get("sma250") for r in equity_history]
    RG = [r.get("regime","") for r in equity_history]
    BN = _nb(benchmark_data, D, stats.get("starting_capital",10000))

    bd,bp,bl,sd,sp,sl=[],[],[],[],[],[]
    for t in trade_log:
        strat_display = clean_strat_name(t.get('strategy',''))
        lb=f"{t.get('trade_type','')}: {t['ticker']}<br>{strat_display}<br>${t['value']:,.0f}"
        (bd if t["action"]=="BUY" else sd).append(t["date"])
        (bp if t["action"]=="BUY" else sp).append(t["ndx_close"])
        (bl if t["action"]=="BUY" else sl).append(lb)

    rs = _rshapes(D, RG)
    la = equity_history[-1] if equity_history else {}
    rstat = stats.get("regime_stats",{})
    trans = _rtrans(equity_history)
    atr = round(la.get("ndx_close",20000)*0.012,2)
    br = config.get("branding",{})
    stripe = br.get("stripe_payment_url","")
    bh = br.get("beehiiv_subscribe_url","")
    fs = br.get("formspree_endpoint","")
    cemail = br.get("contact_email","")
    affs = [a for a in br.get("affiliates",[]) if a.get("url")]
    vip_hash = br.get("vip_password_hash","")
    surl = br.get("site_url","")
    rc = 'pos' if 'UP' in la.get('regime','') else 'neg'

    cd = json.dumps({"latest":la,"stats":{k:v for k,v in stats.items() if k!="regime_stats"},
        "regime_stats":rstat,"transitions":trans[-12:],"recent_trades":trade_log[-25:],
        "equity_tail":equity_history[-20:]},default=str)

    vip_commentary = _gen_vip(la, stats, trans, trade_log[-5:])

    return f'''{_css(surl)}
<body>
<div class="hdr"><h1>&#9889; APEX TRADE LAB</h1><div class="tag">TQQQ / SQQQ STRATEGY ENGINE</div>
<div class="upd"><span class="dot"></span>LIVE LAB &bull; {datetime.now().strftime('%Y-%m-%d %H:%M')} Brisbane Time</div></div>
<div class="nav">
<button class="on" onclick="go('ov',this)">Overview</button>
<button onclick="go('rg',this)">Regime</button>
<button onclick="go('tl',this)">Trade Tools</button>
<button onclick="go('tr',this)">Trades</button>
<button onclick="go('ai',this)">AI Analyst</button>
<button onclick="go('sub',this)" class="nc">Subscribe</button>
<button onclick="go('svc',this)">Services</button>
<button onclick="go('vip',this)" style="color:var(--purple)">VIP</button>
</div>

<div id="ov" class="pg on">
{_stat_cards(stats)}
<div class="s"><h2 class="y">Current Signal</h2>
<div class="dt"><span class="lb">Date:</span> <b>{la.get('date','')}</b> &nbsp; <span class="lb">Regime:</span> <b class="{rc}">{la.get('regime','')}</b></div>
<div class="dt"><span class="lb">TQQQ:</span> <b class="pos">{la.get('tqqq_alloc',0):.0f}%</b> &nbsp; <span class="lb">SQQQ:</span> <b class="neg">{la.get('sqqq_alloc',0):.0f}%</b> &nbsp; <span class="lb">Cash:</span> {la.get('cash_alloc',100):.0f}%</div>
<div class="dt"><span class="lb">NDX:</span> {la.get('ndx_close',0):,.0f} &nbsp; vs SMA20: {la.get('ext_sma20',0):+.1f}% &nbsp; vs SMA250: {la.get('ext_sma250',0):+.1f}% &nbsp; RSI: {la.get('rsi',50):.0f}</div>
<div class="dt"><span class="lb">Active:</span> {la.get('active_strategies','None')}</div>
<div class="why"><b>Why:</b> {la.get('strategy_details','No active signals')}</div></div>
<div class="s"><h2 class="b">Timing</h2><div class="tg">
<div class="ti"><h3>Decision</h3><p>EOD, 10min before close (3:50 PM ET / 6:50 AM Brisbane)</p></div>
<div class="ti"><h3>Execution</h3><p>Next-day open (7:30 AM Brisbane Time)</p></div>
<div class="ti"><h3>Frequency</h3><p>~2 trades/week. Check daily at breakfast.</p></div>
<div class="ti"><h3>Your Routine</h3><p>Check 7:00 AM. If signal changed, prepare order for 7:30 AM Open.</p></div></div></div>
<div class="s"><h2>Equity vs QQQ</h2><div id="eq-c"></div></div>
<div class="s"><h2>NDX — Signals & Regime</h2><p class="m sm">▲ BUY ▼ SELL | Background = regime shading</p><div id="nx-c"></div></div>
<div class="s"><h2>Allocation</h2><div id="al-c"></div></div></div>

<div id="rg" class="pg">
<div class="s"><h2 class="p">Current Regime</h2><div class="rb">
<div class="badge {'up' if 'UP' in la.get('regime','') else 'dn'}">{la.get('regime','?')}</div>
<div style="display:flex;gap:14px;flex-wrap:wrap">
<div class="rm"><span class="lb">NDX</span><span class="vl">{la.get('ndx_close',0):,.0f}</span></div>
<div class="rm"><span class="lb">vs SMA250</span><span class="vl {rc}">{la.get('ext_sma250',0):+.1f}%</span></div>
<div class="rm"><span class="lb">RSI</span><span class="vl">{la.get('rsi',50):.0f}</span></div></div></div></div>
<div class="s"><h2 class="p">Transitions</h2><div class="tw"><table><thead><tr><th>Date</th><th>From</th><th>To</th><th>NDX</th><th>Days</th><th>Significance</th></tr></thead>
<tbody>{''.join(_trow(t) for t in reversed(trans[-12:]))}</tbody></table></div></div>
<div class="s"><h2 class="p">Performance by Regime</h2><div class="rgg">{_rcards(rstat)}</div></div>
</div>

<div id="tl" class="pg">
<div class="s"><h2 class="y">$10k Position Sizing (Live)</h2>
<p class="m sm" style="margin-bottom:10px">Calculate your shares based on your actual account balance.</p>
<div class="cg"><div class="ci">
<div class="ig"><label>Account ($)</label><input type="number" id="psa" value="10000"></div>
<div class="ig"><label>Risk %</label><input type="number" id="psr" value="1.0" step="0.5"></div>
<div class="ig"><label>Entry Price ($)</label><input type="number" id="pse" value="75" step="0.01"></div>
<div class="ig"><label>Stop Price ($)</label><input type="number" id="pss" value="72" step="0.01"></div>
<div class="ig"><label>Ticker</label><select id="psi"><option>TQQQ</option><option>SQQQ</option></select></div>
<button class="btn" onclick="cPos()">CALCULATE SHARES</button></div>
<div class="cr" id="pso"><div class="rp">Enter entry/stop and click Calculate</div></div></div></div>

<div class="s"><h2 class="y">Stop Loss Framework</h2><div class="slg">
<div class="slc"><h3>1. ATR Dynamic</h3><div class="slf">Stop = Entry - (ATR x Mult)</div>
<div class="ig"><label>ATR</label><input type="number" id="sla" value="{atr}" step="0.01"></div>
<div class="ig"><label>Mult</label><select id="slam"><option value="1.5">1.5x</option><option value="2.0" selected>2.0x</option><option value="2.5">2.5x</option><option value="3.0">3.0x</option></select></div>
<button class="btn-sm" onclick="cATR()">Calc</button><div id="slar" class="slr"></div></div>
<div class="slc"><h3>2. Fixed %</h3><div class="slf">Stop = Entry x (1 - %)</div>
<div class="ig"><label>Entry</label><input type="number" id="slfe" value="75" step="0.01"></div>
<div class="ig"><label>%</label><select id="slfp"><option value="3">3%</option><option value="5" selected>5%</option><option value="7">7%</option><option value="10">10%</option></select></div>
<button class="btn-sm" onclick="cFix()">Calc</button><div id="slfr" class="slr"></div></div>
</div></div>
</div>

<div id="tr" class="pg">
<div class="s"><h2>Trade Log</h2><div class="tw"><table><thead><tr><th>Date</th><th>Type</th><th>Tkr</th><th>Side</th><th>Qty</th><th>Price</th><th>Value</th><th>P&L</th><th>Strategy</th><th>Regime</th></tr></thead>
<tbody>{''.join(_trrow(t) for t in reversed(trade_log[-50:]))}</tbody></table></div></div></div>

<div id="ai" class="pg"><div class="s">
<h2 class="b">AI Analyst</h2><p class="m sm">Your data is pre-loaded. Pick a provider, enter YOUR API key.</p>
<div id="ai-s" style="max-width:440px">
<div class="ig"><label>Provider</label><select id="aip"><option value="anthropic">Claude Sonnet</option><option value="openai">GPT-4o</option></select></div>
<div class="ig"><label>API Key</label><input type="password" id="aik" placeholder="sk-..."></div>
<button class="btn" onclick="initAI()">CONNECT</button>
<p class="m sm" style="margin-top:4px">Key stays in browser memory only.</p></div>
<div id="ai-b" style="display:none" class="cc">
<div class="cm" id="msgs"></div>
<div class="cir"><input id="ain" placeholder="Ask about the current strategy..." onkeydown="if(event.key==='Enter')sAI()"><button id="aib" onclick="sAI()">SEND</button></div></div></div></div>

<div id="sub" class="pg">
<div class="s"><h2>Coming Soon</h2><p class="m">Weekly email reports are being integrated.</p></div>
</div>

<div id="svc" class="pg">
<div class="s"><h2>Contact</h2><p class="m">For consulting or custom builds: <a href="mailto:{cemail}" style="color:var(--green)">{cemail}</a></p></div>
</div>

<div id="vip" class="pg">
<div class="s" style="border-color:var(--purple)">
<h2 style="color:var(--purple)">VIP Access</h2>
<div id="vip-gate">
<div class="ig" style="max-width:300px"><label>Password</label><input type="password" id="vip-pw"></div>
<button class="btn" onclick="checkVIP()" style="background:var(--purple);margin-top:6px">Unlock</button>
</div>
<div id="vip-content" style="display:none">{vip_commentary}</div></div></div>

<div class="ftr">
<div class="disc">PAPER TRADING SIMULATION ONLY. Strategy designed for Brisbane morning execution.</div>
</div>

<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<script>
// NAV
function go(id,b){{document.querySelectorAll('.pg').forEach(p=>p.classList.remove('on'));document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('on'));document.getElementById(id).classList.add('on');b.classList.add('on')}}

// VIP
const VH='{vip_hash}';
async function checkVIP(){{const pw=document.getElementById('vip-pw').value;const enc=new TextEncoder();const hash=await crypto.subtle.digest('SHA-256',enc.encode(pw));const hex=Array.from(new Uint8Array(hash)).map(b=>b.toString(16).padStart(2,'0')).join('');if(hex===VH){{document.getElementById('vip-gate').style.display='none';document.getElementById('vip-content').style.display='block'}}else{{alert('Incorrect')}}}}

// CHARTS
const _D={json.dumps(D)},_EQ={json.dumps(EQ)},_BN={json.dumps(BN)};
const _TA={json.dumps(TA)},_SA={json.dumps(SA)},_CA={json.dumps(CA)};
const _NX={json.dumps(NX)},_S20={json.dumps(S20)},_S250={json.dumps(S250)};
const _BD={json.dumps(bd)},_BP={json.dumps(bp)},_BL={json.dumps(bl)};
const _SD={json.dumps(sd)},_SP={json.dumps(sp)},_SL={json.dumps(sl)};
const L={{paper_bgcolor:'#0d1117',plot_bgcolor:'#0d1117',font:{{color:'#d4dce8',family:'IBM Plex Sans',size:11}},margin:{{t:8,r:25,b:35,l:55}},xaxis:{{gridcolor:'#1c2636'}},yaxis:{{gridcolor:'#1c2636'}},legend:{{bgcolor:'rgba(0,0,0,0)',x:0,y:1}},hovermode:'x unified'}};
window.addEventListener('load',()=>{{
Plotly.newPlot('eq-c',[{{x:_D,y:_EQ,name:'APEX ($10k)',line:{{color:'#00ffaa',width:2}}}},{{x:_D,y:_BN,name:'QQQ',line:{{color:'#ffcc00',width:1,dash:'dot'}}}}],{{...L,height:340}},{{responsive:true}});
Plotly.newPlot('nx-c',[{{x:_D,y:_NX,name:'NDX',line:{{color:'#d4dce8',width:1.5}}}},{{x:_D,y:_S20,name:'SMA20',line:{{color:'#ffcc00',dash:'dash'}}}},{{x:_D,y:_S250,name:'SMA250',line:{{color:'#ff3b5c'}}}}],{{...L,shapes:{rs},height:380}},{{responsive:true}});
Plotly.newPlot('al-c',[{{x:_D,y:_TA,name:'TQQQ%',fill:'tozeroy',line:{{color:'#00ffaa'}},stackgroup:'a'}},{{x:_D,y:_SA,name:'SQQQ%',fill:'tonexty',line:{{color:'#ff3b5c'}},stackgroup:'a'}}],{{...L,height:240}},{{responsive:true}});
}});

// --- THE $10,000 POSITION SIZER LOGIC ---
function cPos() {{
    const acc = parseFloat(document.getElementById('psa').value);
    const riskPct = parseFloat(document.getElementById('psr').value) / 100;
    const entry = parseFloat(document.getElementById('pse').value);
    const stop = parseFloat(document.getElementById('pss').value);
    const ticker = document.getElementById('psi').value;

    if (stop >= entry) {{
        document.getElementById('pso').innerHTML = '<b style="color:var(--red)">Error: Stop must be below Entry</b>';
        return;
    }}

    const riskAmt = acc * riskPct;
    const riskPerShare = entry - stop;
    const shares = Math.floor(riskAmt / riskPerShare);
    const totalCost = (shares * entry).toFixed(2);

    document.getElementById('pso').innerHTML = `
        <div style="background:var(--card2); padding:15px; border-radius:4px; border-left:4px solid var(--green)">
            <h4 style="margin:0 0 10px 0; color:var(--green)">${ticker} Order Plan</h4>
            <p style="font-size:13px">Risking: <b>$${riskAmt.toFixed(2)}</b></p>
            <p style="font-size:18px; margin:10px 0">Buy: <b>${shares} Shares</b></p>
            <p style="font-size:13px">Total Cost: <b>$${totalCost}</b></p>
            <p style="font-size:11px; color:var(--muted); margin-top:10px">Uses ${((totalCost/acc)*100).toFixed(1)}% of your $${acc} account.</p>
        </div>
    `;
}}

function cATR(){{const a=+document.getElementById('sla').value,m=+document.getElementById('slam').value,e=parseFloat(document.getElementById('pse').value),s=e-(a*m);document.getElementById('slar').innerHTML='Stop: <span class="neg">$'+s.toFixed(2)+'</span>'}}
function cFix(){{const e=+document.getElementById('slfe').value,p=+document.getElementById('slfp').value/100,s=e*(1-p);document.getElementById('slfr').innerHTML='Stop: <span class="neg">$'+s.toFixed(2)+'</span>'}}

// AI CHAT
const CD={cd};
const SYS='You are APEX TRADE LAB AI. Help a Brisbane-based novice with TQQQ/SQQQ trading. Be simple.';
let ak='',ah=[];
function initAI(){{ak=document.getElementById('aik').value.trim();document.getElementById('ai-s').style.display='none';document.getElementById('ai-b').style.display='flex';}}
async function sAI(){{const q=document.getElementById('ain').value.trim();if(!q)return;document.getElementById('ain').value='';const d=document.getElementById('msgs');const m=document.createElement('div');m.textContent='User: '+q;d.appendChild(m);}}
</script></body></html>'''


# ===== INTERNAL HELPER FUNCTIONS (KEEP THESE) =====

def _stat_cards(stats):
    return f'''<div class="sg">
    <div class="sc"><div class="lb">Total Return</div><div class="vl pos">{stats.get('total_return_pct',0):+.1f}%</div></div>
    <div class="sc"><div class="lb">Max Drawdown</div><div class="vl neg">{stats.get('max_drawdown_pct',0):.1f}%</div></div>
    <div class="sc"><div class="lb">Win Rate</div><div class="vl">{stats.get('win_rate',0):.1f}%</div></div>
    <div class="sc"><div class="lb">Sharpe</div><div class="vl">{stats.get('sharpe_ratio',0):.2f}</div></div>
    </div>'''

def _rcards(rstat):
    h = ''
    for r, s in rstat.items():
        cls = 'su' if 'STRONG UP' in r else 'ut' if 'UP' in r else 'dt_'
        h += f'''<div class="rc {cls}"><h4>{r}</h4><p>Win: {s['win_rate']:.0f}% | Ret: {s['total_return']:+.1f}%</p></div>'''
    return h

def _trow(t):
    return f"<tr><td>{t['date']}</td><td>{t['from']}</td><td>{t['to']}</td><td>{t['ndx']:,.0f}</td><td>{t['days']}</td><td>{t['meaning']}</td></tr>"

def _trrow(t):
    pnl_cls = 'pos' if t.get('pnl_pct',0) > 0 else 'neg'
    strat = clean_strat_name(t.get('strategy',''))
    return f"<tr><td>{t['date']}</td><td>{t['action']}</td><td>{t['ticker']}</td><td>{t['side']}</td><td>{t['qty']}</td><td>{t['price']:.2f}</td><td>${t['value']:,.0f}</td><td class='{pnl_cls}'>{t.get('pnl_pct',0):+.1f}%</td><td>{strat}</td><td>{t.get('regime','')}</td></tr>"

def _nb(bench, dates, start_cap):
    if not bench or 'Close' not in bench: return [start_cap]*len(dates)
    b_data = bench.reindex(pd.to_datetime(dates)).ffill()
    first_price = b_data['Close'].iloc[0]
    return (b_data['Close'] / first_price * start_cap).tolist()

def _rshapes(D, RG):
    shapes = []
    if not D or not RG: return shapes
    start_i = 0
    for i in range(1, len(RG)):
        if RG[i] != RG[start_i]:
            shapes.append(_mkshape(D[start_i], D[i], RG[start_i]))
            start_i = i
    shapes.append(_mkshape(D[start_i], D[-1], RG[start_i]))
    return shapes

def _mkshape(x0, x1, r):
    c = 'rgba(0,255,170,0.05)' if 'STRONG UP' in r else 'rgba(0,255,170,0.02)' if 'UP' in r else 'rgba(255,59,92,0.05)' if 'STRONG DOWN' in r else 'rgba(255,59,92,0.02)' if 'DOWN' in r else 'rgba(0,0,0,0)'
    return {"type":"rect","xref":"x","yref":"paper","x0":x0,"x1":x1,"y0":0,"y1":1,"fillcolor":c,"line":{"width":0},"layer":"below"}

def _rtrans(hist):
    ts = []
    for i in range(1, len(hist)):
        if hist[i]['regime'] != hist[i-1]['regime']:
            ts.append({"date":hist[i]['date'], "from":hist[i-1]['regime'], "to":hist[i]['regime'], "ndx":hist[i]['ndx_close'], "days":0, "meaning":"Regime Shift"})
    return ts

def _css(surl):
    return f'''<style>
    :root{{--bg:#060a10;--card:#0d1117;--card2:#151b25;--border:#1c2636;--text:#d4dce8;--muted:#6b7d93;--dim:#3d4f63;--green:#00ffaa;--red:#ff3b5c;--yellow:#ffcc00;--blue:#3b9eff;--purple:#9d7aff}}
    body{{font-family:'IBM Plex Sans', sans-serif; background-color:var(--bg); color:var(--text); margin:0; padding:0;}}
    .hdr{{padding:30px; text-align:center; border-bottom:1px solid var(--border); background:linear-gradient(to bottom, #09121d, var(--bg));}}
    .hdr h1{{font-family:'Space Mono', monospace; color:var(--green); letter-spacing:3px; margin:0;}}
    .nav{{display:flex; justify-content:center; gap:8px; padding:15px; background:var(--card); border-bottom:1px solid var(--border); position:sticky; top:0; z-index:100;}}
    .nav button{{background:none; border:1px solid var(--border); color:var(--muted); padding:10px 18px; cursor:pointer; border-radius:4px; font-family:'Space Mono', monospace; font-size:11px; text-transform:uppercase; transition: 0.2s;}}
    .nav button.on{{border-color:var(--green); color:var(--green); background:rgba(0,255,170,0.05);}}
    .nav button:hover{{color:var(--text); border-color:var(--dim);}}
    .pg{{display:none; padding:25px; max-width:1200px; margin:auto; animation: fadeIn 0.3s ease-in;}}
    @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    .pg.on{{display:block}}
    .s{{background:var(--card); border:1px solid var(--border); padding:25px; border-radius:12px; margin-bottom:20px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);}}
    .sc{{background:var(--card2); padding:20px; border-radius:10px; text-align:center; border:1px solid var(--border);}}
    .vl{{font-family:'Space Mono', monospace; font-size:26px; font-weight:bold; margin-top:5px;}}
    </style>'''

def _aff_html(affs): return "" # Simplified for now
