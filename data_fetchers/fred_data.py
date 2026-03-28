"""
FRED (Federal Reserve Economic Data) fetcher.
Calls the FRED API directly via requests. Reads API key from st.secrets.
Every call is wrapped so a failure never crashes the app.
"""

import requests
from datetime import datetime, timedelta

# Series we care about
FRED_SERIES = {
    "BAMLH0A0HYM2": "Credit Spreads (High Yield OAS)",
    "DGS10": "10-Year Treasury Rate",
    "T10Y2Y": "Yield Curve (10Y minus 2Y)",
    "DTWEXBGS": "Trade Weighted Dollar Index",
}

FRED_API_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _get_fred_key():
    """Read FRED API key from Streamlit secrets. Returns None if unavailable."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "FRED_API_KEY" in st.secrets:
            return st.secrets["FRED_API_KEY"]
    except Exception:
        pass
    return None


def _fetch_one_series(series_id: str, name: str, api_key: str) -> dict:
    """Fetch a single FRED series via the REST API. Never raises."""
    try:
        start = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        resp = requests.get(
            FRED_API_BASE,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start,
                "sort_order": "desc",
                "limit": 60,
            },
            timeout=10,
        )
        resp.raise_for_status()
        observations = resp.json().get("observations", [])

        # Filter to valid numeric values
        values = []
        for obs in observations:
            try:
                values.append(float(obs["value"]))
            except (ValueError, KeyError):
                continue

        if not values:
            return {"series_id": series_id, "name": name, "error": "No data returned"}

        # values are newest-first (sort_order=desc)
        current = values[0]
        prev = values[1] if len(values) > 1 else current
        week_ago = values[4] if len(values) >= 5 else values[-1]
        month_ago = values[21] if len(values) >= 22 else values[-1]

        return {
            "series_id": series_id,
            "name": name,
            "current_value": round(current, 4),
            "prev_value": round(prev, 4),
            "daily_change": round(current - prev, 4),
            "weekly_change": round(current - week_ago, 4),
            "monthly_change": round(current - month_ago, 4),
            "high_1y": round(max(values), 4),
            "low_1y": round(min(values), 4),
            "last_updated": datetime.now().isoformat(),
        }
    except requests.exceptions.Timeout:
        return {"series_id": series_id, "name": name, "error": "FRED API timed out"}
    except requests.exceptions.HTTPError as e:
        if "400" in str(e) or "403" in str(e):
            return {"series_id": series_id, "name": name, "error": "Invalid FRED API key"}
        return {"series_id": series_id, "name": name, "error": f"FRED API error: {e}"}
    except Exception as e:
        return {"series_id": series_id, "name": name, "error": f"Could not load: {e}"}


def fetch_fred_data() -> list:
    """Fetch all FRED series. Always returns a list, never crashes."""
    try:
        api_key = _get_fred_key()
        if not api_key:
            return [{"series_id": sid, "name": name, "error": "FRED_API_KEY not configured"}
                    for sid, name in FRED_SERIES.items()]

        results = []
        for series_id, name in FRED_SERIES.items():
            results.append(_fetch_one_series(series_id, name, api_key))
        return results
    except Exception:
        return [{"series_id": sid, "name": name, "error": "FRED data temporarily unavailable"}
                for sid, name in FRED_SERIES.items()]
