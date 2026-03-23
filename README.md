# ⚡ APEX TRADE LAB

**Systematic Trading Research Platform — TQQQ/SQQQ Strategy Engine**

Free autonomous paper trading dashboard simulating 7 strategies on leveraged Nasdaq ETFs.

> Paper trading simulation only. Not financial advice.

## Pages

| Page | Description |
|------|-------------|
| **Dashboard** | Live signal, equity curve, NDX chart with trade markers |
| **Trades** | Full log with human-readable explanations |
| **P&L** | Profit/loss summary + social posts ready to copy |
| **Trade Tools** | Position sizer, stop-loss calculators, entry/exit checklists |
| **Market Regime** | Regime map, transitions, performance by regime, playbook |
| **Stress Test** | Historical crash simulations (2000, 2008, 2020, 2022) |
| **AI Analyst** | Chat with your data via Claude or GPT-4o |
| **Learn** | Start Here guide + all 7 strategies explained |
| **Community** | Subscribe, VIP access, services, contact |

## Setup (15 minutes)

1. Create repo `apex-trade-lab` on GitHub (public)
2. Upload all files from this ZIP
3. Create `.github/workflows/daily-simulation.yml`
4. Settings → Actions → General → **Read and write permissions**
5. Settings → Pages → Branch: **main** / Folder: **/(root)**
6. Actions → Run workflow manually
7. Bookmark: `https://YOUR-USERNAME.github.io/apex-trade-lab/outputs/`

## Structure

```
apex-trade-lab/
├── engine/
│   ├── data_fetcher.py      # Yahoo Finance data
│   ├── indicators.py        # SMA, BB, RSI, ATR
│   ├── strategies.py        # 7 WhiteLight strategies
│   └── simulator.py         # Paper trading engine
├── dashboard/
│   ├── dashboard.py         # HTML generator (light theme)
│   └── stress_test.py       # Crash simulations
├── automation/
│   ├── signal_exporter.py   # daily_signal.json
│   └── social_content.py    # Social media posts
├── outputs/                 # Auto-generated
├── config.yaml
├── main.py
└── requirements.txt
```

## Commands

```bash
python main.py                  # Normal run
python main.py --reset          # Fresh backfill
python main.py --stress-test    # Run stress tests
```

## Custom Domain

Buy a domain (~$12/year), then:
```
A Record: @ → 185.199.108.153 (and .109, .110, .111)
```
Settings → Pages → Custom domain → Enter domain → Enforce HTTPS.
