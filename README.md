# Investment Intelligence Dashboard

Personal investment monitoring system that surfaces plain English interpretations of market signals for a long-term investor. Built with Python, Streamlit, and Claude API.

## What It Does

- **Monitors** portfolio positions (VWRA, SUI, XRP) and a thematic watchlist (copper, uranium, grid infrastructure, water, rare earths, defence)
- **Analyses** macro signals (VIX, credit spreads, put/call ratio, DXY, Baltic Dry Index)
- **Parses** CFTC Commitments of Traders reports for copper and oil positioning
- **Scrapes** uranium spot prices, Sprott SPUT data, congressional trades
- **Generates** weekly AI briefings via Claude API with GREEN/AMBER/RED status for every position
- **Alerts** immediately when thresholds are hit (VIX spike, VWRA price drop, COT confirmation, etc.)

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env

# Launch dashboard
streamlit run app.py

# Or run a one-off briefing
python scheduler.py --once

# Or start the automated scheduler (Fridays at 4pm EST)
python scheduler.py
```

## Required API Keys

| Key | Source | Cost |
|-----|--------|------|
| `FRED_API_KEY` | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) | Free |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) | Pay per use |

Both are optional — the dashboard works without them (FRED data will be missing, briefing uses a template fallback instead of AI).

## Architecture

```
├── app.py                  # Streamlit dashboard
├── scheduler.py            # Automated weekly/daily runner
├── config.py               # Portfolio, watchlist, thresholds, Claude prompts
├── data_fetchers/
│   ├── market_data.py      # yfinance — prices for all tickers
│   ├── fred_data.py        # FRED API — credit spreads
│   ├── cot_data.py         # CFTC COT reports — copper & oil positioning
│   └── scraper.py          # Uranium, BDI, congressional trades
├── analysis/
│   ├── signals.py          # GREEN/AMBER/RED classification engine
│   └── alerts.py           # Threshold-based alert triggers
├── briefing/
│   └── generator.py        # Claude API briefing + template fallback
└── utils/
    ├── cache.py            # File-based data caching
    └── notifications.py    # Email alerts via SMTP
```

## Alert Thresholds

| Trigger | Threshold | Signal |
|---------|-----------|--------|
| VWRA price | Below $160 | Historical support — entry signal |
| VIX | Above 35 | Within 2-4 weeks of market bottom |
| Copper COT | 3+ consecutive weeks commercial net long | Entry window for copper |
| Uranium spot | Below $75/lb | Discount to contract prices |
| Oil | Below $90/bbl | De-escalation signal |
| Credit spreads | Above 500bps | Credit stress — equities follow lower |

## Investor Profile

Designed for a non-US (UAE-incorporated), long-term investor using UCITS ETFs. Not a trading tool — an informed positioning tool for someone making 4-6 meaningful decisions per year.

---

*Personal use only. Not financial advice.*
