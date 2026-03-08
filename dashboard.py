"""
dashboard.py - APEX TRADE LAB Trading Cockpit (Final Build)

8 Tabs: Overview | Regime | Trade Tools | Trades | AI Analyst | Subscribe | Services | VIP
All data live. VIP = password-gated extra commentary for friends/donors.
Stripe Payment Links for donations. Beehiiv for newsletter. Formspree for contact.
Math puzzle anti-spam on all forms. Dual AI chat (Claude + GPT-4o).
"""

import json, logging, hashlib
from datetime import datetime
from pathlib import Path
from typing import List
import numpy as np, pandas as pd

logger = logging.getLogger(__name__)

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
    BN = _nb(benchmark_data, D, stats.get("starting_capital",100000))

    bd,bp,bl,sd,sp,sl=[],[],[],[],[],[]
    for t in trade_log:
        lb=f"{t.get('trade_type','')}: {t['ticker']}<br>{t.get('strategy','')}<br>${t['value']:,.0f}"
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

    # Chat data (sanitized - no secrets)
    cd = json.dumps({"latest":la,"stats":{k:v for k,v in stats.items() if k!="regime_stats"},
        "regime_stats":rstat,"transitions":trans[-12:],"recent_trades":trade_log[-25:],
        "equity_tail":equity_history[-20:]},default=str)

    # VIP commentary auto-generated
    vip_commentary = _gen_vip(la, stats, trans, trade_log[-5:])

    return f'''{_css(surl)}
<body>
<div class="hdr"><h1>&#9889; APEX TRADE LAB</h1><div class="tag">TQQQ / SQQQ STRATEGY ENGINE</div>
<div class="upd"><span class="dot"></span>LIVE Paper Trading &bull; {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</div></div>
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

<!-- OVERVIEW -->
<div id="ov" class="pg on">
{_stat_cards(stats)}
<div class="s"><h2 class="y">Current Signal</h2>
<div class="dt"><span class="lb">Date:</span> <b>{la.get('date','')}</b> &nbsp; <span class="lb">Regime:</span> <b class="{rc}">{la.get('regime','')}</b></div>
<div class="dt"><span class="lb">TQQQ:</span> <b class="pos">{la.get('tqqq_alloc',0):.0f}%</b> &nbsp; <span class="lb">SQQQ:</span> <b class="neg">{la.get('sqqq_alloc',0):.0f}%</b> &nbsp; <span class="lb">Cash:</span> {la.get('cash_alloc',100):.0f}%</div>
<div class="dt"><span class="lb">NDX:</span> {la.get('ndx_close',0):,.0f} &nbsp; vs SMA20: {la.get('ext_sma20',0):+.1f}% &nbsp; vs SMA250: {la.get('ext_sma250',0):+.1f}% &nbsp; RSI: {la.get('rsi',50):.0f}</div>
<div class="dt"><span class="lb">Active:</span> {la.get('active_strategies','None')}</div>
<div class="why"><b>Why:</b> {la.get('strategy_details','No active signals')}</div></div>
<div class="s"><h2 class="b">Timing</h2><div class="tg">
<div class="ti"><h3>Decision</h3><p>EOD, 10min before close (3:50 PM ET / 6:20 AM ACST)</p></div>
<div class="ti"><h3>Execution</h3><p>Next-day open (D+1)</p></div>
<div class="ti"><h3>Frequency</h3><p>~2 trades/week, ~10/month</p></div>
<div class="ti"><h3>Your Routine</h3><p>Check 7 AM Darwin. Signal changed? Place order.</p></div></div></div>
<div class="s"><h2>Equity vs QQQ</h2><div id="eq-c"></div></div>
<div class="s"><h2>NDX &mdash; Signals &amp; Regime</h2><p class="m sm">&#9650; BUY &#9660; SELL | Background = regime shading</p><div id="nx-c"></div></div>
<div class="s"><h2>Allocation</h2><div id="al-c"></div></div></div>

<!-- REGIME -->
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
<div class="s"><h2 class="p">Playbook</h2><div class="kg">
<div class="kc"><h3 class="pos">STRONG UPTREND</h3><p><b>Play:</b> Max TQQQ (up to 88%). Buy every dip to SMA20. BB width scales size.</p><p><b>Watch:</b> &gt;8% above SMA20 or RSI &gt;75 = top risk.</p></div>
<div class="kc"><h3 class="pos">UPTREND</h3><p><b>Play:</b> MR Longs active. Standard sizing. Buy pullbacks.</p><p><b>Watch:</b> NDX approaching SMA250 from above = flip risk.</p></div>
<div class="kc"><h3 class="neg">DOWNTREND</h3><p><b>Play:</b> SQQQ via Momentum Shorts. NO dip buying.</p><p><b>Watch:</b> NDX reclaiming SMA250 = flip to bull.</p></div>
<div class="kc"><h3 class="neg">STRONG DOWNTREND</h3><p><b>Play:</b> Max SQQQ. Scale with depth below SMA250.</p><p><b>Watch:</b> RSI &lt;25 = bounce likely. 2022: system -10.9% vs TQQQ -79%.</p></div></div></div></div>

<!-- TRADE TOOLS -->
<div id="tl" class="pg">
<div class="s"><h2 class="y">Position Sizing</h2><div class="cg"><div class="ci">
<div class="ig"><label>Account ($)</label><input type="number" id="psa" value="15000"></div>
<div class="ig"><label>Risk %</label><input type="number" id="psr" value="2.0" step="0.5"></div>
<div class="ig"><label>Entry ($)</label><input type="number" id="pse" value="75" step="0.01"></div>
<div class="ig"><label>Stop ($)</label><input type="number" id="pss" value="71" step="0.01"></div>
<div class="ig"><label>Ticker</label><select id="psi"><option>TQQQ</option><option>SQQQ</option></select></div>
<button class="btn" onclick="cPos()">CALCULATE</button></div>
<div class="cr" id="pso"><div class="rp">Enter values and click Calculate</div></div></div></div>

<div class="s"><h2 class="y">Stop Loss Framework</h2><div class="slg">
<div class="slc"><h3>1. ATR Dynamic</h3><div class="slf">Stop = Entry - (ATR x Mult)</div>
<div class="ig"><label>ATR</label><input type="number" id="sla" value="{atr}" step="0.01"></div>
<div class="ig"><label>Mult</label><select id="slam"><option value="1.5">1.5x</option><option value="2.0" selected>2.0x</option><option value="2.5">2.5x</option><option value="3.0">3.0x</option></select></div>
<button class="btn-sm" onclick="cATR()">Calc</button><div id="slar" class="slr"></div></div>
<div class="slc"><h3>2. Fixed %</h3><div class="slf">Stop = Entry x (1 - %)</div>
<div class="ig"><label>Entry</label><input type="number" id="slfe" value="75" step="0.01"></div>
<div class="ig"><label>%</label><select id="slfp"><option value="3">3%</option><option value="5" selected>5%</option><option value="7">7%</option><option value="10">10%</option></select></div>
<button class="btn-sm" onclick="cFix()">Calc</button><div id="slfr" class="slr"></div></div>
<div class="slc"><h3>3. Regime-Aware</h3><table class="rst"><thead><tr><th>Regime</th><th>Long</th><th>Short</th></tr></thead><tbody>
<tr><td class="pos">Strong Up</td><td>2.5-3x</td><td>1-1.5x</td></tr><tr><td class="pos">Up</td><td>2-2.5x</td><td>1.5x</td></tr>
<tr><td class="neg">Down</td><td>1.5x</td><td>2-2.5x</td></tr><tr><td class="neg">Strong Dn</td><td>1-1.5x</td><td>2.5-3x</td></tr></tbody></table>
<p class="sle"><b>Now: <span class="{rc}">{la.get('regime','')}</span></b></p></div></div></div>

<div class="s"><h2 class="y">Entry &amp; Exit</h2><div class="kg">
<div class="kc"><h3 class="pos">Entry Checklist</h3><ol><li>Regime: above/below SMA250?</li><li>Which strategy triggered?</li><li>Extension from SMA20?</li><li>RSI confirm (&lt;30 long, &gt;70 short)?</li><li>Size via calculator, max 2% risk</li></ol></div>
<div class="kc"><h3 class="neg">Exit (first wins)</h3><ol><li>Stop hit → out immediately</li><li>Strategy EXIT signal</li><li>Regime change → close direction</li></ol><p><b>Trail:</b> 1.5x ATR profit → breakeven. 2.5x → trail 1.5x ATR.</p></div></div></div></div>

<!-- TRADES -->
<div id="tr" class="pg">
<div class="s"><h2>Trade Log</h2><div class="tw"><table><thead><tr><th>Date</th><th>Type</th><th>Tkr</th><th>Side</th><th>Qty</th><th>Price</th><th>Value</th><th>P&L</th><th>Alloc</th><th>Strategy</th><th>Reasoning</th><th>Regime</th></tr></thead>
<tbody>{''.join(_trrow(t) for t in reversed(trade_log[-50:]))}</tbody></table></div></div></div>

<!-- AI ANALYST -->
<div id="ai" class="pg"><div class="s">
<h2 class="b">AI Analyst</h2><p class="m sm">Your data is pre-loaded. Pick a provider, enter YOUR API key.</p>
<div id="ai-s" style="max-width:440px">
<div class="ig"><label>Provider</label><select id="aip" onchange="document.getElementById('h1').style.display=this.value==='anthropic'?'block':'none';document.getElementById('h2').style.display=this.value==='openai'?'block':'none'"><option value="anthropic">Claude Sonnet</option><option value="openai">GPT-4o</option></select></div>
<div class="ig"><label>API Key</label><input type="password" id="aik" placeholder="sk-..."></div>
<button class="btn" onclick="initAI()">CONNECT</button>
<div class="sle" id="h1"><p><a href="https://console.anthropic.com" target="_blank" rel="noopener">console.anthropic.com</a> → API Keys → Create. $5 credit ≈ 500 questions.</p></div>
<div class="sle" id="h2" style="display:none"><p><a href="https://platform.openai.com" target="_blank" rel="noopener">platform.openai.com</a> → API Keys → Create. $5 credit ≈ 500 questions.</p></div>
<p class="m sm" style="margin-top:4px">Key stays in browser memory only. Never stored or shared.</p></div>
<div id="ai-b" style="display:none" class="cc">
<div class="cm" id="msgs"></div>
<div class="cq"><button onclick="aQ('Current regime and outlook?')">Regime</button><button onclick="aQ('Last 5 trades analysis')">Trades</button><button onclick="aQ('Best strategy right now?')">Best Strategy</button><button onclick="aQ('Conviction on current signal?')">Conviction</button><button onclick="aQ('My risk exposure?')">Risk</button><button onclick="aQ('Explain last trade simply')">Explain</button><button onclick="aQ('Position size for $15K?')">Size</button></div>
<div class="cir"><input id="ain" placeholder="Ask anything..." onkeydown="if(event.key==='Enter')sAI()"><button id="aib" onclick="sAI()">SEND</button></div></div></div></div>

<!-- SUBSCRIBE -->
<div id="sub" class="pg">
<div class="s" style="border-color:var(--green)">
<h2 style="color:var(--green);font-size:15px">&#128236; Weekly Signal Reports — Free</h2>
<p class="m sm" style="margin-bottom:12px">Get a weekly email with: P&L summary, trade entries/exits, regime analysis, strategy performance, market outlook, and key learnings.</p>
<div class="sub-cols">
<div class="sub-box"><h3 class="m">Dashboard (what you see now)</h3><ul><li>Live signals + full reasoning</li><li>All charts, tools, trade log</li><li>AI analyst (BYOK)</li><li>Regime playbook</li></ul><div class="sub-price">Free</div></div>
<div class="sub-box" style="border-color:var(--green)"><h3 class="pos">Email Subscriber</h3><ul>
<li class="pos"><b>Weekly P&L report</b></li><li class="pos"><b>Entry/exit recap + reasoning</b></li><li class="pos"><b>Regime change alerts</b></li><li class="pos"><b>Market outlook + macro</b></li><li>Position sizing for current signal</li></ul><div class="sub-price pos">Free</div></div></div></div>

<div class="s"><h2>Subscribe</h2>
<div id="mg1" class="mg"><p><b>Quick verify:</b></p><div id="mq1" class="mq"></div>
<div class="ig" style="max-width:180px"><label>Answer</label><input type="number" id="ma1"></div>
<button class="btn-sm" onclick="cm(1)">Verify</button><div id="me1" class="neg sm"></div></div>
<div id="sf1" style="display:none">
{('<p class="m sm">Opening newsletter signup...</p><a href="'+bh+'" target="_blank" rel="noopener" class="btn" style="display:inline-block;text-decoration:none;margin-top:6px">Subscribe →</a>') if bh else '<p class="m sm">Newsletter coming soon. Leave your details via the Services tab.</p>'}
</div></div>

{'<div class="s"><h2 class="y">Support This Project</h2><p class="m sm">If the signals help you learn, consider a small contribution. 100% goes to keeping this running.</p><div style="text-align:center;padding:10px"><a href="'+stripe+'" target="_blank" rel="noopener" class="btn" style="display:inline-block;text-decoration:none;font-size:14px;padding:12px 28px">&#9889; Support ($5) via Stripe</a></div><p class="m sm" style="text-align:center">Secure payment via Stripe. No account needed.</p></div>' if stripe else ''}
</div>

<!-- SERVICES -->
<div id="svc" class="pg">
<div class="s"><h2 class="b">Services</h2><div class="kg">
<div class="kc" style="border-left:3px solid var(--green)"><h3 class="pos">Custom Strategy Dashboard</h3><p>Your strategy coded, backtested, and deployed as a live autonomous dashboard. From <b>$500</b>.</p></div>
<div class="kc" style="border-left:3px solid var(--yellow)"><h3 class="neu">Backtest Report</h3><p>Send your rules, get a full backtest with metrics, equity curve, regime analysis. From <b>$200</b>.</p></div>
<div class="kc" style="border-left:3px solid var(--purple)"><h3 style="color:var(--purple)">Advertising &amp; Collaboration</h3><p>Feature your product on this dashboard or collaborate on a joint project.</p></div></div></div>

<div class="s"><h2 class="b">Contact</h2>{'<p class="m sm">Email: <a href="mailto:'+cemail+'" style="color:var(--green)">'+cemail+'</a></p>' if cemail else ''}
<div id="mg2" class="mg"><p><b>Verify:</b></p><div id="mq2" class="mq"></div>
<div class="ig" style="max-width:180px"><label>Answer</label><input type="number" id="ma2"></div>
<button class="btn-sm" onclick="cm(2)">Verify</button><div id="me2" class="neg sm"></div></div>
<div id="sf2" style="display:none">
{'<form action="'+fs+'" method="POST" style="max-width:500px"><div class="ig"><label>I am a...</label><select name="user_type"><option>Individual Trader</option><option>Institutional Trader</option><option>Student / Learner</option><option>Business / Fintech</option><option>Content Creator</option></select></div><div class="ig"><label>Reason for contact</label><select name="reason"><option>Subscribe for reports</option><option>Collaborate on backtest &amp; strategy build</option><option>Custom dashboard project</option><option>Advertising enquiry</option><option>Just saying hello</option></select></div><div class="ig"><label>Name</label><input type="text" name="name" required></div><div class="ig"><label>Email</label><input type="email" name="email" required></div><div class="ig"><label>Message</label><textarea name="message" rows="3" style="background:var(--card2);border:1px solid var(--border);color:var(--text);padding:6px;border-radius:3px;width:100%;font-size:12px;resize:vertical"></textarea></div><input type="text" name="_gotcha" style="display:none"><button type="submit" class="btn">Send</button></form>' if fs else '<p class="m sm">Contact form coming soon.'+(' Email: <a href="mailto:'+cemail+'" style="color:var(--green)">'+cemail+'</a>' if cemail else '')+'</p>'}
</div></div>

{_aff_html(affs)}
</div>

<!-- VIP -->
<div id="vip" class="pg">
<div class="s" style="border-color:var(--purple)">
<h2 style="color:var(--purple)">VIP Access</h2>
<p class="m sm">Extra commentary and analysis for friends and supporters.</p>
<div id="vip-gate">
<div class="ig" style="max-width:300px"><label>Password</label><input type="password" id="vip-pw" placeholder="Enter VIP password"></div>
<button class="btn" onclick="checkVIP()" style="background:var(--purple);margin-top:6px">Unlock</button>
<div id="vip-err" class="neg sm" style="margin-top:4px"></div>
</div>
<div id="vip-content" style="display:none">
{vip_commentary}
</div></div></div>

<!-- FOOTER -->
<div class="ftr">
<div class="disc">PAPER TRADING SIMULATION ONLY. Not financial advice. Strategy reverse-engineered from @RealTQQQTrader public posts. Past simulated performance ≠ future results.</div>
{'<div style="margin-top:8px"><a href="'+stripe+'" target="_blank" rel="noopener" class="btn" style="display:inline-block;text-decoration:none;font-size:11px;padding:6px 14px">&#9889; Support This Project</a></div>' if stripe else ''}
<div class="m sm" style="margin-top:6px">&#9889; APEX TRADE LAB &bull; Python + Plotly + GitHub Actions &bull; 100% Free &amp; Open</div>
{'<div class="m sm" style="margin-top:3px;font-size:8px">Some links are affiliate links. We may earn a commission at no extra cost to you.</div>' if affs else ''}
</div>

<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<script>
// NAV
function go(id,b){{document.querySelectorAll('.pg').forEach(p=>p.classList.remove('on'));document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('on'));document.getElementById(id).classList.add('on');b.classList.add('on')}}

// MATH PUZZLES
let mv=[0,0,0,0];
function gm(qid,i){{const a=5+Math.floor(Math.random()*20),b=3+Math.floor(Math.random()*15);document.getElementById(qid).innerHTML='<span class="mono" style="font-size:16px;color:var(--yellow)">'+a+' + '+b+' = ?</span>';mv[i*2]=a;mv[i*2+1]=b}}
window.addEventListener('load',()=>{{gm('mq1',0);gm('mq2',1)}});
function cm(n){{const a=+document.getElementById('ma'+n).value;if(a===mv[(n-1)*2]+mv[(n-1)*2+1]){{document.getElementById('mg'+n).style.display='none';document.getElementById('sf'+n).style.display='block'}}else{{document.getElementById('me'+n).textContent='Wrong. Try again.';gm('mq'+n,n-1)}}}};

// VIP
const VH='{vip_hash}';
async function checkVIP(){{const pw=document.getElementById('vip-pw').value;if(!VH){{document.getElementById('vip-err').textContent='VIP not configured yet.';return}}const enc=new TextEncoder();const hash=await crypto.subtle.digest('SHA-256',enc.encode(pw));const hex=Array.from(new Uint8Array(hash)).map(b=>b.toString(16).padStart(2,'0')).join('');if(hex===VH){{document.getElementById('vip-gate').style.display='none';document.getElementById('vip-content').style.display='block'}}else{{document.getElementById('vip-err').textContent='Incorrect password.'}}}}

// CHARTS
const _D={json.dumps(D)},_EQ={json.dumps(EQ)},_BN={json.dumps(BN)};
const _TA={json.dumps(TA)},_SA={json.dumps(SA)},_CA={json.dumps(CA)};
const _NX={json.dumps(NX)},_S20={json.dumps(S20)},_S250={json.dumps(S250)};
const _BD={json.dumps(bd)},_BP={json.dumps(bp)},_BL={json.dumps(bl)};
const _SD={json.dumps(sd)},_SP={json.dumps(sp)},_SL={json.dumps(sl)};
const L={{paper_bgcolor:'#0d1117',plot_bgcolor:'#0d1117',font:{{color:'#d4dce8',family:'IBM Plex Sans',size:11}},margin:{{t:8,r:25,b:35,l:55}},xaxis:{{gridcolor:'#1c2636'}},yaxis:{{gridcolor:'#1c2636'}},legend:{{bgcolor:'rgba(0,0,0,0)',x:0,y:1}},hovermode:'x unified'}};
window.addEventListener('load',()=>{{
Plotly.newPlot('eq-c',[{{x:_D,y:_EQ,name:'APEX',line:{{color:'#00ffaa',width:2}}}},{{x:_D,y:_BN,name:'QQQ',line:{{color:'#ffcc00',width:1,dash:'dot'}}}}],{{...L,yaxis:{{...L.yaxis,title:'$'}},height:340}},{{responsive:true}});
Plotly.newPlot('nx-c',[{{x:_D,y:_NX,name:'NDX',line:{{color:'#d4dce8',width:1.5}}}},{{x:_D,y:_S20,name:'SMA20',line:{{color:'#ffcc00',width:1,dash:'dash'}}}},{{x:_D,y:_S250,name:'SMA250',line:{{color:'#ff3b5c',width:1.5,dash:'dash'}}}},{{x:_BD,y:_BP,name:'BUY',mode:'markers',text:_BL,marker:{{color:'#00ffaa',size:7,symbol:'triangle-up'}},hoverinfo:'text'}},{{x:_SD,y:_SP,name:'SELL',mode:'markers',text:_SL,marker:{{color:'#ff3b5c',size:7,symbol:'triangle-down'}},hoverinfo:'text'}}],{{...L,yaxis:{{...L.yaxis,title:'NDX'}},shapes:{rs},height:380}},{{responsive:true}});
Plotly.newPlot('al-c',[{{x:_D,y:_TA,name:'TQQQ%',fill:'tozeroy',fillcolor:'rgba(0,255,170,.25)',line:{{color:'#00ffaa'}},stackgroup:'a'}},{{x:_D,y:_SA,name:'SQQQ%',fill:'tonexty',fillcolor:'rgba(255,59,92,.25)',line:{{color:'#ff3b5c'}},stackgroup:'a'}},{{x:_D,y:_CA,name:'Cash%',fill:'tonexty',fillcolor:'rgba(107,125,147,.1)',line:{{color:'#6b7d93'}},stackgroup:'a'}}],{{...L,yaxis:{{...L.yaxis,title:'%',range:[0,105]}},height:240}},{{responsive:true}});
}});

// CALCULATORS
function cPos(){{const a=+document.getElementById('psa').value,r=+document.getElementById('psr').value/100,e=+document.getElementById('pse').value,s=+document.getElementById('pss').value,i=document.getElementById('psi').value;if(!a||!e||!s||s>=e){{document.getElementById('pso').innerHTML='<div class="re">Entry must be above stop</div>';return}};const rd=a*r,rps=Math.abs(e-s),sh=Math.floor(rd/rps),pv=sh*e,pp=pv/a*100;document.getElementById('pso').innerHTML='<div class="rr"><span class="lb">Risk</span><span class="vl neg">$'+rd.toFixed(0)+'</span></div><div class="rr"><span class="lb">Shares</span><span class="vl pos">'+sh+' '+i+'</span></div><div class="rr"><span class="lb">Value</span><span class="vl">$'+pv.toFixed(0)+' ('+pp.toFixed(0)+'%)</span></div><div class="rr"><span class="lb">Max Loss</span><span class="vl neg">$'+(sh*rps).toFixed(0)+'</span></div><hr style="border-color:var(--border);margin:5px 0"><div class="rr"><span class="lb">T1 (1.5R)</span><span class="vl pos">$'+(e+rps*1.5).toFixed(2)+'</span></div><div class="rr"><span class="lb">T2 (2R)</span><span class="vl pos">$'+(e+rps*2).toFixed(2)+'</span></div><div class="rn">Sell 50% at T1, stop to breakeven.</div>'}}
function cATR(){{const a=+document.getElementById('sla').value,m=+document.getElementById('slam').value,e=+document.getElementById('pse')?.value||75,s=e-(a*m);document.getElementById('slar').innerHTML='Stop: <span class="neg">$'+s.toFixed(2)+'</span> ('+((e-s)/e*100).toFixed(1)+'% risk)'}}
function cFix(){{const e=+document.getElementById('slfe').value,p=+document.getElementById('slfp').value/100,s=e*(1-p);document.getElementById('slfr').innerHTML='Stop: <span class="neg">$'+s.toFixed(2)+'</span> ($'+(e-s).toFixed(2)+'/share)'}}

// AI CHAT
const CD={cd};
const SYS='You are APEX TRADE LAB AI. Analyze paper trading data: 7-strategy TQQQ/SQQQ system. SMA20,SMA250,BB,RSI. Regime=NDX vs SMA250. Be concise. $10-25K account, 2% risk. PAPER TRADING only.\\nDATA:\\n'+JSON.stringify(CD);
let ak='',ah=[],ap='anthropic';
function initAI(){{ap=document.getElementById('aip').value;ak=document.getElementById('aik').value.trim();if(!ak||ak.length<10){{alert('Enter valid key');return}};document.getElementById('ai-s').style.display='none';document.getElementById('ai-b').style.display='flex';aM('a','Connected ('+ap+'). Data loaded.')}}
function aM(r,t){{const d=document.getElementById('msgs'),m=document.createElement('div');m.className='msg msg-'+(r==='u'?'u':'a');m.textContent=t;d.appendChild(m);d.scrollTop=d.scrollHeight}}
function aQ(q){{document.getElementById('ain').value=q;sAI()}}
async function sAI(){{const q=document.getElementById('ain').value.trim();if(!q)return;document.getElementById('ain').value='';aM('u',q);ah.push({{role:'user',content:q}});document.getElementById('aib').disabled=true;
try{{let r='';if(ap==='anthropic'){{const f=await fetch('https://api.anthropic.com/v1/messages',{{method:'POST',headers:{{'Content-Type':'application/json','x-api-key':ak,'anthropic-version':'2023-06-01','anthropic-dangerous-direct-browser-access':'true'}},body:JSON.stringify({{model:'claude-sonnet-4-20250514',max_tokens:1000,system:SYS,messages:ah.slice(-8)}})}});const d=await f.json();r=d.content?.map(c=>c.text||'').join('\\n')||d.error?.message||'Error'}}else{{const f=await fetch('https://api.openai.com/v1/chat/completions',{{method:'POST',headers:{{'Content-Type':'application/json','Authorization':'Bearer '+ak}},body:JSON.stringify({{model:'gpt-4o',max_tokens:1000,messages:[{{role:'system',content:SYS}},...ah.slice(-8)]}})}}); const d=await f.json();r=d.choices?.[0]?.message?.content||d.error?.message||'Error'}}
aM('a',r);ah.push({{role:'assistant',content:r}})}}catch(e){{aM('a','Error: '+e.message)}}document.getElementById('aib').disabled=false}}
</script></body></html>'''


# ===== VIP COMMENTARY =====

def _gen_vip(la, stats, trans, recent_trades):
    regime = la.get("regime","N/A")
    ret = stats.get("total_return_pct",0)
    dd = stats.get("max_drawdown_pct",0)
    last_trans = trans[-1] if trans else {}
    last_trade = recent_trades[-1] if recent_trades else {}

    return f'''
<div class="kc" style="border:1px solid var(--purple);margin-bottom:10px">
<h3 style="color:var(--purple)">Analyst Notes — {la.get('date','')}</h3>
<p><b>Regime:</b> {regime}. NDX is {la.get('ext_sma250',0):+.1f}% from SMA(250) and {la.get('ext_sma20',0):+.1f}% from SMA(20). RSI at {la.get('rsi',50):.0f}.</p>
<p><b>Performance:</b> Total return {ret:+.1f}% with max drawdown {dd:.1f}%. {'Performing well.' if ret > 0 else 'In drawdown — system is designed to recover from these.'}</p>
<p><b>Last regime shift:</b> {last_trans.get('from','?')} → {last_trans.get('to','?')} on {last_trans.get('date','')}. {last_trans.get('meaning','')}</p>
<p><b>Last trade:</b> {last_trade.get('action','')} {last_trade.get('ticker','')} on {last_trade.get('date','')} — {last_trade.get('strategy','')}. {last_trade.get('reasoning','')[:120]}</p>
<p><b>Current allocation:</b> TQQQ {la.get('tqqq_alloc',0):.0f}% / SQQQ {la.get('sqqq_alloc',0):.0f}% / Cash {la.get('cash_alloc',100):.0f}%</p>
</div>
<p class="m sm">This section updates automatically with each simulation run. Share the password only with people you trust.</p>'''


# ===== HTML PARTS =====

def _css(surl):
    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>APEX TRADE LAB — TQQQ/SQQQ Strategy Engine</title>
<meta name="description" content="Free autonomous paper trading: 7-strategy TQQQ/SQQQ system with AI analyst, regime analysis, position sizing tools.">
<meta property="og:title" content="&#9889; APEX TRADE LAB — TQQQ/SQQQ Strategy Engine"><meta property="og:description" content="Live paper trading dashboard with AI chat, regime analysis, trade tools. 100% free.">
<meta property="og:type" content="website"><meta name="twitter:card" content="summary_large_image"><meta name="theme-color" content="#00ffaa">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#9889;</text></svg>">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#060a10;--card:#0d1117;--card2:#151b25;--border:#1c2636;--text:#d4dce8;--muted:#6b7d93;--dim:#3d4f63;--green:#00ffaa;--red:#ff3b5c;--yellow:#ffcc00;--blue:#3b9eff;--purple:#9d7aff}}
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'IBM Plex Sans',sans-serif;background:var(--bg);color:var(--text);line-height:1.5}}::selection{{background:var(--green);color:var(--bg)}}::-webkit-scrollbar{{width:5px}}::-webkit-scrollbar-thumb{{background:var(--dim);border-radius:3px}}
.hdr{{text-align:center;padding:18px 16px 0}}.hdr h1{{font-family:'Space Mono',monospace;font-size:24px;color:var(--green);letter-spacing:2px;text-shadow:0 0 25px rgba(0,255,170,.1)}}.hdr .tag{{color:var(--muted);font-size:10px;letter-spacing:3px;text-transform:uppercase}}.hdr .upd{{color:var(--dim);font-size:9px;margin-top:3px}}.dot{{display:inline-block;width:6px;height:6px;background:var(--green);border-radius:50%;margin-right:3px;animation:p 2s infinite}}@keyframes p{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.nav{{display:flex;gap:3px;justify-content:center;padding:10px 12px;flex-wrap:wrap;border-bottom:1px solid var(--border)}}.nav button{{font-family:'Space Mono',monospace;background:0;border:1px solid transparent;color:var(--muted);padding:6px 12px;border-radius:3px;cursor:pointer;font-size:10px;letter-spacing:.3px;text-transform:uppercase;transition:.15s}}.nav button:hover{{color:var(--text);border-color:var(--border)}}.nav button.on{{color:var(--green);border-color:var(--green);background:rgba(0,255,170,.04)}}.nc{{color:var(--yellow)!important}}
.pg{{display:none;padding:14px;max-width:1400px;margin:0 auto}}.pg.on{{display:block}}.s{{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:14px;margin-bottom:12px}}.s h2{{font-family:'Space Mono',monospace;color:var(--green);font-size:11px;margin-bottom:8px;letter-spacing:.6px;text-transform:uppercase}}.s h2.y{{color:var(--yellow)}}.s h2.b{{color:var(--blue)}}.s h2.p{{color:var(--purple)}}
.pos{{color:var(--green)}}.neg{{color:var(--red)}}.neu{{color:var(--yellow)}}.m{{color:var(--muted)}}.sm{{font-size:10px}}.mono{{font-family:'Space Mono',monospace}}
.sg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:6px;margin-bottom:12px}}.sc{{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:9px;text-align:center}}.sc .lb{{color:var(--muted);font-size:8px;text-transform:uppercase;letter-spacing:.4px}}.sc .vl{{font-family:'Space Mono',monospace;font-size:17px;font-weight:700;margin-top:1px}}
.dt{{margin:2px 0;font-size:11px}}.dt .lb{{color:var(--muted);min-width:70px;display:inline-block}}.why{{margin-top:5px;padding:6px;background:var(--card2);border-radius:3px;font-size:10px;color:var(--muted)}}
.tg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:6px}}.ti{{background:var(--card2);border-radius:3px;padding:8px;border-left:2px solid var(--yellow)}}.ti h3{{color:var(--yellow);font-size:10px;margin-bottom:2px;font-family:'Space Mono',monospace}}.ti p{{color:var(--muted);font-size:10px}}
.rb{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}.badge{{font-family:'Space Mono',monospace;font-size:15px;font-weight:700;padding:7px 16px;border-radius:3px;border:1px solid}}.badge.up{{color:var(--green);border-color:var(--green);background:rgba(0,255,170,.05)}}.badge.dn{{color:var(--red);border-color:var(--red);background:rgba(255,59,92,.05)}}.rm{{text-align:center}}.rm .lb{{display:block;color:var(--muted);font-size:8px;text-transform:uppercase}}.rm .vl{{font-family:'Space Mono',monospace;font-size:13px;font-weight:600}}
.rgg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}}.rc{{background:var(--card2);border-radius:3px;padding:10px;border-left:3px solid var(--dim)}}.rc.su{{border-left-color:#00ff88}}.rc.ut{{border-left-color:var(--green)}}.rc.dt_{{border-left-color:var(--red)}}.rc.sd{{border-left-color:#ff0033}}.rc h3{{font-size:10px;margin-bottom:4px;font-family:'Space Mono',monospace}}.rc .sr{{display:flex;justify-content:space-between;font-size:9px;margin:1px 0}}.rc .sr .k{{color:var(--muted)}}
.kg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px}}.kc{{background:var(--card2);border-radius:4px;padding:12px;font-size:10px;border:1px solid var(--border)}}.kc h3{{font-size:11px;margin-bottom:3px}}.kc p{{margin:3px 0;color:var(--muted)}}.kc b{{color:var(--text)}}.kc ol,.kc ul{{margin:3px 0 3px 14px;color:var(--muted)}}.kc li{{margin:2px 0}}
.cg{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.ci{{display:flex;flex-direction:column;gap:5px}}.cr{{background:var(--card2);border-radius:4px;padding:12px;font-size:11px}}.ig{{margin-bottom:4px}}.ig label{{color:var(--muted);font-size:8px;text-transform:uppercase;display:block;margin-bottom:1px}}.ig input,.ig select{{background:var(--card2);border:1px solid var(--border);color:var(--text);padding:5px 7px;border-radius:3px;font-size:11px;font-family:'Space Mono',monospace;width:100%}}.btn{{background:var(--green);color:var(--bg);border:none;padding:7px 12px;border-radius:3px;cursor:pointer;font-weight:700;font-size:11px;font-family:'Space Mono',monospace}}.btn-sm{{background:var(--yellow);color:var(--bg);border:none;padding:3px 8px;border-radius:3px;cursor:pointer;font-weight:600;font-size:9px;margin-top:3px}}
.rr{{display:flex;justify-content:space-between;margin:2px 0;font-size:10px}}.rr .lb{{color:var(--muted)}}.rr .vl{{font-family:'Space Mono',monospace;font-weight:600}}.rn{{color:var(--yellow);font-size:9px;margin-top:4px;font-style:italic}}.re{{color:var(--red);font-size:10px}}.rp{{color:var(--dim);font-size:10px;text-align:center;padding:16px 0}}
.slg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px}}.slc{{background:var(--card2);border-radius:4px;padding:10px;border:1px solid var(--border)}}.slc h3{{font-size:11px;margin-bottom:3px}}.slf{{background:var(--bg);padding:4px 7px;border-radius:3px;font-family:'Space Mono',monospace;font-size:9px;margin:4px 0;color:var(--yellow)}}.slr{{margin-top:4px;font-family:'Space Mono',monospace;font-size:10px}}.sle{{margin-top:5px;font-size:9px;color:var(--muted);border-top:1px solid var(--border);padding-top:4px}}.sle a{{color:var(--blue)}}
.rst{{width:100%;font-size:9px;margin:5px 0}}.rst th{{background:var(--bg);padding:3px 4px;color:var(--muted);text-align:left;font-size:7px;text-transform:uppercase}}.rst td{{padding:3px 4px;border-bottom:1px solid var(--border)}}
table{{width:100%;border-collapse:collapse;font-size:9px}}th{{background:var(--card2);color:var(--muted);padding:5px 3px;text-align:left;font-size:7px;text-transform:uppercase;letter-spacing:.2px;position:sticky;top:0;font-family:'Space Mono',monospace}}td{{padding:3px;border-bottom:1px solid var(--border)}}tr:hover td{{background:rgba(0,255,170,.02)}}.te{{color:var(--green);font-weight:600}}.tx{{color:var(--red);font-weight:600}}.ta{{color:var(--blue)}}.tr_{{color:var(--yellow)}}.tc{{font-size:8px;max-width:130px}}.trc{{font-size:8px;color:var(--muted);max-width:180px}}.tw{{overflow-x:auto}}
.cc{{display:flex;flex-direction:column;height:440px}}.cm{{flex:1;overflow-y:auto;padding:6px;display:flex;flex-direction:column;gap:4px}}.msg{{padding:7px 9px;border-radius:6px;font-size:10px;line-height:1.5;max-width:85%;white-space:pre-wrap}}.msg-u{{background:rgba(0,255,170,.06);align-self:flex-end;border:1px solid rgba(0,255,170,.1)}}.msg-a{{background:var(--card2);align-self:flex-start;border:1px solid var(--border)}}.cq{{display:flex;flex-wrap:wrap;gap:3px;padding:4px;border-top:1px solid var(--border)}}.cq button{{background:var(--card2);border:1px solid var(--border);color:var(--text);padding:3px 6px;border-radius:10px;cursor:pointer;font-size:8px;white-space:nowrap}}.cq button:hover{{border-color:var(--green);color:var(--green)}}.cir{{display:flex;gap:4px;padding:5px;border-top:1px solid var(--border)}}.cir input{{flex:1;background:var(--card2);border:1px solid var(--border);color:var(--text);padding:7px 9px;border-radius:3px;font-size:10px;outline:none}}.cir button{{background:var(--green);color:var(--bg);border:none;padding:7px 12px;border-radius:3px;cursor:pointer;font-weight:700;font-size:10px;font-family:'Space Mono',monospace}}
.sub-cols{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px}}.sub-box{{background:var(--card2);border-radius:4px;padding:12px;border:1px solid var(--border)}}.sub-box h3{{font-size:12px;margin-bottom:6px}}.sub-box ul{{margin:5px 0 5px 14px;font-size:10px;color:var(--muted)}}.sub-box .pos{{color:var(--green)}}.sub-price{{font-family:'Space Mono',monospace;font-size:18px;margin-top:8px;font-weight:700}}
.mg{{background:var(--card2);border-radius:4px;padding:10px;border:1px solid var(--border);max-width:350px}}.mq{{margin:4px 0}}
.aff-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin-top:8px}}.aff-card{{background:var(--card2);border-radius:4px;padding:12px;border:1px solid var(--border)}}.aff-card:hover{{border-color:var(--green)}}.aff-card h3{{font-size:12px;margin-bottom:3px}}.aff-card p{{color:var(--muted);font-size:10px;margin-bottom:6px}}.aff-btn{{display:inline-block;background:var(--green);color:var(--bg);padding:5px 12px;border-radius:3px;text-decoration:none;font-size:10px;font-weight:700;font-family:'Space Mono',monospace}}
.ftr{{text-align:center;padding:16px;border-top:1px solid var(--border);margin-top:14px}}.ftr .disc{{color:var(--dim);font-size:8px}}
@media(max-width:768px){{.sg{{grid-template-columns:repeat(2,1fr)}}.cg,.slg,.kg,.tg,.rgg,.sub-cols,.aff-grid{{grid-template-columns:1fr}}}}
</style></head>'''


def _stat_cards(s):
    r,c,p=s.get('total_return_pct',0),s.get('cagr_pct',0),s.get('total_realized_pnl',0)
    return f'<div class="sg"><div class="sc"><div class="lb">Portfolio</div><div class="vl pos">${s.get("current_equity",0):,.0f}</div></div><div class="sc"><div class="lb">Return</div><div class="vl {"pos" if r>=0 else "neg"}">{r:+.1f}%</div></div><div class="sc"><div class="lb">CAGR</div><div class="vl {"pos" if c>=0 else "neg"}">{c:+.1f}%</div></div><div class="sc"><div class="lb">Max DD</div><div class="vl neg">{s.get("max_drawdown_pct",0):.1f}%</div></div><div class="sc"><div class="lb">Sharpe</div><div class="vl neu">{s.get("sharpe_ratio",0):.2f}</div></div><div class="sc"><div class="lb">Win</div><div class="vl neu">{s.get("win_rate_pct",0):.0f}%</div></div><div class="sc"><div class="lb">Trades/Mo</div><div class="vl neu">~{s.get("trades_per_month",0):.0f}</div></div><div class="sc"><div class="lb">P&L</div><div class="vl {"pos" if p>=0 else "neg"}">${p:+,.0f}</div></div></div>'

def _aff_html(affs):
    if not affs: return ''
    cards=''.join(f'<div class="aff-card"><h3>{a["name"]}</h3><p>{a.get("tagline","")}</p><a href="{a["url"]}" target="_blank" rel="noopener noreferrer" class="aff-btn">Open Account &rarr;</a></div>' for a in affs)
    return f'<div class="s"><h2 class="b">Recommended Brokers</h2><p class="m sm">Affiliate links &mdash; we may earn a commission at no extra cost to you.</p><div class="aff-grid">{cards}</div></div>'

def _nb(bd,dates,cap):
    if bd is None or bd.empty: return [None]*len(dates)
    bs=bd["Close"].iloc[0]; return [round(bd.loc[bd.index<=pd.Timestamp(d)].iloc[-1]["Close"]/bs*cap,2) if not bd.loc[bd.index<=pd.Timestamp(d)].empty else None for d in dates]

def _rshapes(D,R):
    if not D: return "[]"
    sh,i=[],0
    while i<len(D):
        rg,s=R[i],D[i]
        while i<len(D) and R[i]==rg: i+=1
        c={"STRONG UPTREND":"rgba(0,255,136,.05)","UPTREND":"rgba(0,255,170,.03)","DOWNTREND":"rgba(255,59,92,.04)","STRONG DOWNTREND":"rgba(255,0,51,.06)"}.get(rg,"rgba(107,125,147,.02)")
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
            m={"STRONG UPTREND,UPTREND":"Momentum fading.","UPTREND,STRONG UPTREND":"Acceleration! Scale up.","UPTREND,DOWNTREND":"CRITICAL: Below SMA250. Switch to SQQQ.","DOWNTREND,UPTREND":"CRITICAL: Reclaimed SMA250. Switch to TQQQ.","DOWNTREND,STRONG DOWNTREND":"Deepening sell-off.","STRONG DOWNTREND,DOWNTREND":"Easing. Reduce shorts.","STRONG UPTREND,DOWNTREND":"Sharp reversal!","STRONG DOWNTREND,UPTREND":"V-recovery!"}.get(f"{prev},{rg}",f"{prev} to {rg}")
            tr.append({"date":r["date"],"from":prev,"to":rg,"ndx":r.get("ndx_close",0),"dur":dur,"m":m})
        if rg!=prev: pd_=r["date"]
        prev=rg
    return tr

def _trow(t):
    return f'<tr><td>{t["date"]}</td><td class="{"pos" if "UP" in t["from"] else "neg"}">{t["from"]}</td><td class="{"pos" if "UP" in t["to"] else "neg"}">{t["to"]}</td><td>{t["ndx"]:,.0f}</td><td>{t["dur"]}d</td><td class="trc">{t["m"]}</td></tr>'

def _rcards(rs):
    if not rs: return '<p class="m">Insufficient data.</p>'
    cards=[]
    for r in ["STRONG UPTREND","UPTREND","DOWNTREND","STRONG DOWNTREND"]:
        if r not in rs: continue
        s=rs[r]; css={"STRONG UPTREND":"su","UPTREND":"ut","DOWNTREND":"dt_","STRONG DOWNTREND":"sd"}[r]; rc="var(--green)" if s["total_return_pct"]>0 else "var(--red)"
        cards.append(f'<div class="rc {css}"><h3>{r}</h3><div class="sr"><span class="k">Time</span><span>{s["pct_of_time"]}%</span></div><div class="sr"><span class="k">Days</span><span>{s["days"]}</span></div><div class="sr"><span class="k">Return</span><span style="color:{rc}">{s["total_return_pct"]:+.1f}%</span></div><div class="sr"><span class="k">Vol</span><span>{s["volatility_ann_pct"]:.1f}%</span></div><div class="sr"><span class="k">Trades</span><span>{s["trades"]}</span></div></div>')
    return "".join(cards)

def _trrow(t):
    tt=t.get("trade_type",""); tc={"NEW ENTRY":"te","EXIT":"tx","ADD":"ta","REDUCE":"tr_"}.get(tt,"")
    pnl=t.get("realized_pnl",0); ps=f"${pnl:+,.0f}" if pnl else "-"
    return f'<tr><td>{t["date"]}</td><td class="{tc}">{tt}</td><td>{t["ticker"]}</td><td class="{"pos" if t["action"]=="BUY" else "neg"}">{t["action"]}</td><td>{t["shares"]:.1f}</td><td>${t["price"]:,.2f}</td><td>${t["value"]:,.0f}</td><td class="{"pos" if pnl>0 else "neg" if pnl<0 else ""}">{ps}</td><td>{t.get("allocation_after_pct",0):.0f}%</td><td class="tc">{t.get("strategy","")}</td><td class="trc">{t.get("reasoning","")[:70]}</td><td>{t.get("regime","")}</td></tr>'

# ===== OUTPUT =====

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
