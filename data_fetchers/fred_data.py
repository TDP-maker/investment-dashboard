"""
FRED (Federal Reserve Economic Data) fetcher.
Retrieves credit spreads, treasury rates, and other economic indicators.
"""

import pandas as pd
from datetime import datetime, timedelta
from config import FRED_API_KEY, FRED_SERIES
from utils.cache import cached_fetch


def _fetch_fred_series(series_id: str, name: str) -> dict:
    """Fetch a single FRED series."""
    if not FRED_API_KEY:
        return {"series_id": series_id, "name": name, "error": "FRED_API_KEY not set"}

    try:
        from fredapi import Fred
        fred = Fred(api_key=FRED_API_KEY)
        data = fred.get_series(series_id, observation_start=datetime.now() - timedelta(days=365))

        if data.empty:
            return {"series_id": series_id, "name": name, "error": "No data available"}

        current = data.iloc[-1]
        prev = data.iloc[-2] if len(data) > 1 else current
        week_ago = data.iloc[-5] if len(data) >= 5 else data.iloc[0]
        month_ago = data.iloc[-22] if len(data) >= 22 else data.iloc[0]

        return {
            "series_id": series_id,
            "name": name,
            "current_value": round(float(current), 4),
            "prev_value": round(float(prev), 4),
            "daily_change": round(float(current - prev), 4),
            "weekly_change": round(float(current - week_ago), 4),
            "monthly_change": round(float(current - month_ago), 4),
            "high_1y": round(float(data.max()), 4),
            "low_1y": round(float(data.min()), 4),
            "last_updated": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"series_id": series_id, "name": name, "error": str(e)}


def fetch_fred_data() -> list[dict]:
    """Fetch all configured FRED series."""
    def _fetch():
        results = []
        for series_id, name in FRED_SERIES.items():
            results.append(_fetch_fred_series(series_id, name))
        return results

    return cached_fetch("fred_data", _fetch)
