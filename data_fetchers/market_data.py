"""
Market data fetcher using yfinance.
Retrieves prices for portfolio, watchlist, and macro tickers.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from config import PORTFOLIO, WATCHLIST, MACRO_TICKERS
from utils.cache import cached_fetch


def _fetch_ticker_data(ticker: str, period: str = "6mo") -> dict:
    """Fetch price data for a single ticker."""
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period=period)
        if hist.empty:
            return {"ticker": ticker, "error": "No data available"}

        current = hist["Close"].iloc[-1]
        prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else current
        week_ago = hist["Close"].iloc[-5] if len(hist) >= 5 else hist["Close"].iloc[0]
        month_ago = hist["Close"].iloc[-22] if len(hist) >= 22 else hist["Close"].iloc[0]

        high_52w = hist["Close"].max()
        low_52w = hist["Close"].min()

        return {
            "ticker": ticker,
            "current_price": round(current, 4),
            "prev_close": round(prev_close, 4),
            "daily_change_pct": round((current - prev_close) / prev_close * 100, 2),
            "weekly_change_pct": round((current - week_ago) / week_ago * 100, 2),
            "monthly_change_pct": round((current - month_ago) / month_ago * 100, 2),
            "high_52w": round(high_52w, 4),
            "low_52w": round(low_52w, 4),
            "pct_from_high": round((current - high_52w) / high_52w * 100, 2),
            "last_updated": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def fetch_portfolio_data() -> list[dict]:
    """Fetch current data for all portfolio positions."""
    def _fetch():
        results = []
        for ticker, info in PORTFOLIO.items():
            data = _fetch_ticker_data(ticker)
            data["name"] = info["name"]
            data["category"] = info["category"]
            data["notes"] = info.get("notes", "")
            results.append(data)
        return results

    return cached_fetch("portfolio_data", _fetch)


def fetch_watchlist_data() -> list[dict]:
    """Fetch current data for all watchlist tickers."""
    def _fetch():
        results = []
        for ticker, info in WATCHLIST.items():
            data = _fetch_ticker_data(ticker)
            data["name"] = info["name"]
            data["theme"] = info["theme"]
            results.append(data)
        return results

    return cached_fetch("watchlist_data", _fetch)


def fetch_macro_data() -> list[dict]:
    """Fetch macro indicator data."""
    def _fetch():
        results = []
        for ticker, name in MACRO_TICKERS.items():
            data = _fetch_ticker_data(ticker, period="3mo")
            data["name"] = name
            results.append(data)
        return results

    return cached_fetch("macro_data", _fetch)


def fetch_put_call_ratio() -> dict:
    """Fetch CBOE put/call ratio (approximation via VIX options volume)."""
    try:
        vix = yf.Ticker("^VIX")
        info = vix.info
        return {
            "name": "Put/Call Ratio (VIX proxy)",
            "value": info.get("impliedVolatility", "N/A"),
            "last_updated": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"name": "Put/Call Ratio", "error": str(e)}
