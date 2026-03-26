"""
Signal classification engine.
Assigns GREEN / AMBER / RED status to portfolio positions, watchlist items, and macro indicators.
"""

from config import THRESHOLDS


def _classify_price_signal(data: dict) -> str:
    """Classify a ticker based on price action."""
    if "error" in data:
        return "AMBER"

    daily = data.get("daily_change_pct", 0)
    weekly = data.get("weekly_change_pct", 0)
    pct_from_high = data.get("pct_from_high", 0)

    # RED: significant decline
    if weekly < -10 or pct_from_high < -30:
        return "RED"

    # AMBER: moderate decline or elevated volatility
    if weekly < -5 or pct_from_high < -20 or abs(daily) > 5:
        return "AMBER"

    return "GREEN"


def _classify_macro_signal(data: dict) -> str:
    """Classify macro indicators."""
    if "error" in data:
        return "AMBER"

    ticker = data.get("ticker", "")
    current = data.get("current_price", 0)

    # VIX classification
    if "VIX" in ticker:
        if current > 35:
            return "RED"
        elif current > 25:
            return "AMBER"
        return "GREEN"

    # DXY classification
    if "DX" in ticker:
        if current > 110:
            return "RED"
        elif current > 105:
            return "AMBER"
        return "GREEN"

    # Oil
    if "CL" in ticker:
        if current > 100:
            return "RED"
        elif current > 90:
            return "AMBER"
        return "GREEN"

    return "GREEN"


def _classify_fred_signal(data: dict) -> str:
    """Classify FRED economic data."""
    if "error" in data:
        return "AMBER"

    series_id = data.get("series_id", "")
    current = data.get("current_value", 0)

    # Credit spreads (HY OAS)
    if "HYM2" in series_id:
        if current > 500:
            return "RED"
        elif current > 400:
            return "AMBER"
        return "GREEN"

    # 10Y-2Y spread (yield curve)
    if "T10Y2Y" in series_id:
        if current < 0:
            return "RED"
        elif current < 0.2:
            return "AMBER"
        return "GREEN"

    return "GREEN"


def _classify_cot_signal(data: dict) -> str:
    """Classify COT positioning data."""
    if "error" in data:
        return "AMBER"

    if data.get("consecutive_net_long"):
        return "GREEN"  # Commercials net long = bullish signal

    latest = data.get("latest", {})
    net = latest.get("commercial_net", 0)

    if net > 0:
        return "AMBER"  # Net long but not consecutive enough

    return "RED"  # Commercials net short


def classify_signals(
    portfolio_data: list,
    watchlist_data: list,
    macro_data: list,
    fred_data: list,
    cot_data: dict,
    scraped_data: dict,
) -> dict:
    """Classify all data into GREEN/AMBER/RED signals."""
    signals = {
        "portfolio": [],
        "watchlist": [],
        "macro": [],
        "fred": [],
        "cot": {},
        "scraped": {},
    }

    # Portfolio signals
    for item in portfolio_data:
        signal = _classify_price_signal(item)
        # Check specific thresholds
        if item.get("ticker") == "VWRA.L" and item.get("current_price", 999) < THRESHOLDS["vwra_support"]["value"]:
            signal = "RED"
        signals["portfolio"].append({**item, "signal": signal})

    # Watchlist signals
    for item in watchlist_data:
        signal = _classify_price_signal(item)
        signals["watchlist"].append({**item, "signal": signal})

    # Macro signals
    for item in macro_data:
        signal = _classify_macro_signal(item)
        signals["macro"].append({**item, "signal": signal})

    # FRED signals
    for item in fred_data:
        signal = _classify_fred_signal(item)
        signals["fred"].append({**item, "signal": signal})

    # COT signals
    if isinstance(cot_data, dict) and "error" not in cot_data:
        for key, data in cot_data.items():
            signal = _classify_cot_signal(data)
            signals["cot"][key] = {**data, "signal": signal}

    # Scraped data signals
    uranium = scraped_data.get("uranium_spot", {})
    if isinstance(uranium, dict) and "value" in uranium:
        uranium_signal = "RED" if uranium["value"] < 75 else "GREEN"
        signals["scraped"]["uranium_spot"] = {**uranium, "signal": uranium_signal}

    bdi = scraped_data.get("baltic_dry_index", {})
    if isinstance(bdi, dict) and "value" in bdi:
        bdi_signal = "RED" if bdi["value"] < 1000 else ("AMBER" if bdi["value"] < 1500 else "GREEN")
        signals["scraped"]["baltic_dry_index"] = {**bdi, "signal": bdi_signal}

    return signals
