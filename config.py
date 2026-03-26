"""
Configuration for the Investment Intelligence Dashboard.
Portfolio positions, watchlist, thresholds, and Claude prompts.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
FRED_API_KEY = os.getenv("FRED_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Dashboard password (optional — if unset, no login required)
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD")

# SMTP config
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")

# Cache config
CACHE_DIR = os.getenv("CACHE_DIR", "data_cache")
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "4"))

# --- Portfolio Positions ---
PORTFOLIO = {
    "VWRA.L": {
        "name": "Vanguard FTSE All-World UCITS ETF (USD Acc)",
        "category": "core",
        "notes": "Core global equity position",
    },
    "SUI-USD": {
        "name": "Sui",
        "category": "crypto",
        "notes": "Layer 1 blockchain",
    },
    "XRP-USD": {
        "name": "XRP",
        "category": "crypto",
        "notes": "Cross-border payments",
    },
}

# --- Thematic Watchlist ---
WATCHLIST = {
    "COPX": {
        "name": "Global X Copper Miners ETF",
        "theme": "copper",
    },
    "HG=F": {
        "name": "Copper Futures",
        "theme": "copper",
    },
    "URA": {
        "name": "Global X Uranium ETF",
        "theme": "uranium",
    },
    "URNM": {
        "name": "Sprott Uranium Miners ETF",
        "theme": "uranium",
    },
    "U-UN.TO": {
        "name": "Sprott Physical Uranium Trust (SPUT)",
        "theme": "uranium",
    },
    "GRID": {
        "name": "First Trust NASDAQ Clean Edge Smart Grid Infra",
        "theme": "grid_infrastructure",
    },
    "PHO": {
        "name": "Invesco Water Resources ETF",
        "theme": "water",
    },
    "REMX": {
        "name": "VanEck Rare Earth/Strategic Metals ETF",
        "theme": "rare_earths",
    },
    "ITA": {
        "name": "iShares U.S. Aerospace & Defense ETF",
        "theme": "defence",
    },
    "PPA": {
        "name": "Invesco Aerospace & Defense ETF",
        "theme": "defence",
    },
    "SEMI.L": {
        "name": "iShares Semiconductor UCITS ETF",
        "theme": "semiconductors",
        "notes": "AI chip infrastructure play. Covers semiconductor equipment and materials companies "
                 "including ASML, TSMC, and the supply chain that makes AI chips possible. Higher risk "
                 "and valuation than infrastructure themes — smaller position appropriate. Ireland domiciled UCITS ETF.",
    },
}

# --- Macro Indicators ---
MACRO_TICKERS = {
    "^VIX": "VIX (Volatility Index)",
    "DX-Y.NYB": "US Dollar Index (DXY)",
    "CL=F": "Crude Oil Futures (WTI)",
}

# FRED series IDs for macro data
FRED_SERIES = {
    "BAMLH0A0HYM2": "ICE BofA US High Yield OAS (Credit Spreads)",
    "T10Y2Y": "10Y-2Y Treasury Spread",
    "DGS10": "10-Year Treasury Rate",
    "DTWEXBGS": "Trade Weighted US Dollar Index",
}

# --- Alert Thresholds ---
THRESHOLDS = {
    "vwra_support": {
        "ticker": "VWRA.L",
        "condition": "below",
        "value": 160,
        "signal": "Historical support — entry signal",
    },
    "vix_spike": {
        "ticker": "^VIX",
        "condition": "above",
        "value": 35,
        "signal": "Within 2-4 weeks of market bottom",
    },
    "oil_low": {
        "ticker": "CL=F",
        "condition": "below",
        "value": 90,
        "signal": "De-escalation signal",
    },
    "credit_stress": {
        "series": "BAMLH0A0HYM2",
        "condition": "above",
        "value": 500,
        "signal": "Credit stress — equities follow lower",
    },
    "uranium_discount": {
        "source": "scraper",
        "condition": "below",
        "value": 75,
        "signal": "Discount to contract prices",
    },
    "semi_drawdown": {
        "ticker": "SEMI.L",
        "condition": "below",
        "value": None,  # Set dynamically as 85% of current price (15% drawdown)
        "pct_drop": 15,
        "signal": "Semiconductor ETF 15% drawdown — potential entry signal",
    },
}

# COT thresholds
COT_CONFIG = {
    "copper": {
        "commodity": "COPPER",
        "consecutive_weeks_threshold": 3,
        "signal": "Entry window for copper",
    },
    "oil": {
        "commodity": "CRUDE OIL",
        "consecutive_weeks_threshold": 3,
        "signal": "Positioning shift in oil",
    },
}

# --- Briefing Prompt ---
BRIEFING_SYSTEM_PROMPT = """You are an investment analyst assistant for a long-term investor.
The investor is non-US (UAE-incorporated), uses UCITS ETFs, and makes 4-6 meaningful
positioning decisions per year. This is NOT a trading tool — it's an informed positioning tool.

Your role is to produce a concise weekly briefing that:
1. Summarises the current state of each portfolio position and watchlist item
2. Assigns a GREEN / AMBER / RED status to each based on the data provided
3. Highlights any threshold alerts that have triggered
4. Provides plain English interpretation of macro signals
5. Ends with 1-3 actionable observations (not recommendations)

GREEN = conditions favourable or neutral, no action needed
AMBER = worth monitoring, conditions shifting
RED = threshold breached or significant adverse signal

Be concise. Use bullet points. No disclaimers needed — the investor understands this is
informational only."""

BRIEFING_USER_PROMPT_TEMPLATE = """Here is this week's market data. Please produce the weekly briefing.

## Portfolio Positions
{portfolio_data}

## Watchlist
{watchlist_data}

## Macro Indicators
{macro_data}

## FRED Economic Data
{fred_data}

## COT Data (Commitments of Traders)
{cot_data}

## Scraped Data
{scraped_data}

## Active Alerts
{alerts_data}

Please produce the weekly briefing with GREEN/AMBER/RED status for each position and watchlist item."""

# --- Schedule ---
BRIEFING_SCHEDULE = {
    "day": "friday",
    "hour": 16,
    "minute": 0,
    "timezone": "US/Eastern",
}
