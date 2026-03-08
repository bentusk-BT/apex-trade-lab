# ⚡ APEX TRADE LAB

**TQQQ/SQQQ Strategy Engine — Free Autonomous Paper Trading Dashboard**

Live simulation of a 7-strategy leveraged ETF system. Everything free. No paid services.

> **DISCLAIMER:** Paper trading simulation only. Not financial advice.

---

## Features

| Tab | What It Does |
|-----|-------------|
| **Overview** | Stats, live signal + reasoning, equity curve, NDX chart with trade markers |
| **Regime** | Current regime, transition history, performance per regime, strategy playbook |
| **Trade Tools** | Position sizer, 3 stop-loss calculators, entry/exit checklists |
| **Trades** | Full log with strategy, reasoning, P&L, regime context |
| **AI Analyst** | Chat with your data via Claude or GPT-4o (BYOK, ~$0.01/msg) |
| **Subscribe** | Email signup via Beehiiv (free newsletter) |
| **Services** | Consulting, backtesting, contact form with user-type segmentation |
| **VIP** | Password-gated extra commentary for friends/donors |

---

## Quick Setup (15 minutes, no coding)

### Step 1: GitHub Account
[github.com](https://github.com) → Sign up → Verify email.

### Step 2: Create Repository
**+** → **New repository** → Name: `apex-trade-lab` → **Public** → Create.

### Step 3: Upload Files
Click **"uploading an existing file"** → Drag all files from this ZIP → Commit.

### Step 4: Create Workflow
**Add file** → **Create new file** → Name: `.github/workflows/daily-simulation.yml` → Paste YAML → Commit.

### Step 5: Fix Permissions
**Settings** → **Actions** → **General** → Workflow permissions → **Read and write** → Save.

### Step 6: Enable Pages
**Settings** → **Pages** → Branch: **main** / Folder: **/(root)** → Save.

### Step 7: First Run
**Actions** tab → **APEX TRADE LAB Daily Run** → **Run workflow** → Wait 2 min.

### Step 8: View Dashboard
```
https://YOUR-USERNAME.github.io/apex-trade-lab/outputs/
```

---

## Adding a Custom Domain (Optional — ~$12/year)

### Step 1: Buy a Domain
Recommended registrars (cheapest): Cloudflare Registrar, Namecheap, or Porkbun.
Example: `apextradelab.com` or `apex-trade.lab` (if available).

### Step 2: Configure DNS
At your registrar, add these DNS records:

**Option A: Apex domain (apextradelab.com)**
```
Type: A     Name: @    Value: 185.199.108.153
Type: A     Name: @    Value: 185.199.109.153
Type: A     Name: @    Value: 185.199.110.153
Type: A     Name: @    Value: 185.199.111.153
```

**Option B: Subdomain (www.apextradelab.com)**
```
Type: CNAME    Name: www    Value: YOUR-USERNAME.github.io
```

### Step 3: Tell GitHub
In your repo: **Settings** → **Pages** → **Custom domain** → Enter `apextradelab.com` → Save.
Check **"Enforce HTTPS"** (wait a few minutes for SSL certificate).

### Step 4: Create CNAME File
In your repo root, create a file called `CNAME` containing just:
```
apextradelab.com
```

DNS propagation takes 15-60 minutes. After that, your domain works with free SSL.

---

## Monetisation Setup (All Free Services)

### Stripe Payment Links ($5 donations → direct to your bank)
1. Go to [dashboard.stripe.com](https://dashboard.stripe.com) → Sign up (free)
2. **Payment Links** → **New** → Set price $5 → Create
3. Copy the link → Paste in `config.yaml` under `stripe_payment_url`

### Beehiiv Newsletter (free up to 2,500 subscribers)
1. Go to [beehiiv.com](https://beehiiv.com) → Create publication (free)
2. **Settings** → **Subscribe Forms** → Copy the subscribe URL
3. Paste in `config.yaml` under `beehiiv_subscribe_url`

### Formspree Contact Form (free, 50 submissions/month)
1. Go to [formspree.io](https://formspree.io) → Create form (free)
2. Copy endpoint URL → Paste in `config.yaml` under `formspree_endpoint`

### Affiliate Broker Links
1. Sign up for referral programs: [Stake](https://stake.com.au), [IBKR](https://www.interactivebrokers.com), [Webull](https://www.webull.com)
2. Get your referral URLs → Paste in `config.yaml` under `affiliates`

### VIP Password
1. Choose a password (e.g., `apex2024`)
2. Generate the hash:
   ```
   python3 -c "import hashlib; print(hashlib.sha256(b'apex2024').hexdigest())"
   ```
3. Paste the hash in `config.yaml` under `vip_password_hash`
4. Share the password (not the hash) with friends/donors manually

---

## Security Notes

- **API keys** (AI chat): Entered by each user in their browser. Stored in JS memory only. Never saved to disk, cookies, or localStorage. Sent only to Anthropic/OpenAI APIs directly.
- **VIP password**: Compared via SHA-256 hash in the browser. Casual security — stops 99% of visitors. A determined developer could find the hash in page source but can't reverse it.
- **Contact form**: Protected by math puzzle + Formspree honeypot. No personal data stored on GitHub.
- **Public repo**: Your code is visible. The value isn't the code — it's the running signals, your curation, and your audience. Anyone can fork it but few will maintain it.
- **No cookies, no tracking, no analytics** by default. Add your own if you want.

---

## Time Zones

| Event | UTC | ACST (Darwin) | US Eastern |
|-------|-----|---------------|------------|
| Market Close | 21:00 | 06:30 next day | 4:00 PM |
| Sim Runs | 21:30 | 07:00 next day | 4:30 PM |

---

## Files

```
├── main.py              # Entry point
├── data_fetcher.py      # Yahoo Finance data + caching
├── indicators.py        # SMA, BB, RSI, ATR
├── strategies.py        # 7 WhiteLight strategies
├── simulator.py         # Paper trading engine
├── dashboard.py         # HTML dashboard generator
├── config.yaml          # All settings + monetisation
├── requirements.txt     # Python deps
├── .github/workflows/   # Daily automation
└── outputs/             # Dashboard + CSVs (auto-generated)
```
