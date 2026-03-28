"""
Threshold-based alert triggers.
Checks current data against configured thresholds and fires alerts.
"""

from datetime import datetime
from config import THRESHOLDS, COT_CONFIG


def check_alerts(
    portfolio_data: list,
    macro_data: list,
    fred_data: list,
    cot_data: dict,
    scraped_data: dict,
) -> list:
    """Check all thresholds and return triggered alerts."""
    alerts = []

    # Build lookup dicts
    ticker_prices = {}
    for item in portfolio_data + macro_data:
        if "current_price" in item:
            ticker_prices[item["ticker"]] = item["current_price"]

    fred_values = {}
    for item in fred_data:
        if "current_value" in item:
            fred_values[item["series_id"]] = item["current_value"]

    # Check ticker-based thresholds
    for alert_key, config in THRESHOLDS.items():
        if "ticker" in config:
            price = ticker_prices.get(config["ticker"])
            if price is None:
                continue

            triggered = False
            if config["condition"] == "below" and price < config["value"]:
                triggered = True
            elif config["condition"] == "above" and price > config["value"]:
                triggered = True

            if triggered:
                alerts.append({
                    "alert_key": alert_key,
                    "type": "threshold",
                    "ticker": config["ticker"],
                    "condition": f"{config['condition']} {config['value']}",
                    "current_value": price,
                    "signal": config["signal"],
                    "severity": "HIGH",
                    "triggered_at": datetime.now().isoformat(),
                })

        # Check FRED-based thresholds
        elif "series" in config:
            value = fred_values.get(config["series"])
            if value is None:
                continue

            triggered = False
            if config["condition"] == "above" and value > config["value"]:
                triggered = True
            elif config["condition"] == "below" and value < config["value"]:
                triggered = True

            if triggered:
                alerts.append({
                    "alert_key": alert_key,
                    "type": "fred_threshold",
                    "series": config["series"],
                    "condition": f"{config['condition']} {config['value']}",
                    "current_value": value,
                    "signal": config["signal"],
                    "severity": "HIGH",
                    "triggered_at": datetime.now().isoformat(),
                })

        # Check scraper-based thresholds
        elif config.get("source") == "scraper":
            uranium = scraped_data.get("uranium_spot", {})
            if isinstance(uranium, dict) and "value" in uranium:
                value = uranium["value"]
                triggered = False
                if config["condition"] == "below" and value < config["value"]:
                    triggered = True

                if triggered:
                    alerts.append({
                        "alert_key": alert_key,
                        "type": "scraped_threshold",
                        "source": "uranium_spot",
                        "condition": f"{config['condition']} {config['value']}",
                        "current_value": value,
                        "signal": config["signal"],
                        "severity": "HIGH",
                        "triggered_at": datetime.now().isoformat(),
                    })

    # Check COT signals
    if isinstance(cot_data, dict):
        for key, config in COT_CONFIG.items():
            cot_entry = cot_data.get(key, {})
            if cot_entry.get("consecutive_net_long"):
                alerts.append({
                    "alert_key": f"cot_{key}",
                    "type": "cot_signal",
                    "commodity": config["commodity"],
                    "condition": f"{config['consecutive_weeks_threshold']}+ weeks commercial net long",
                    "signal": config["signal"],
                    "severity": "MEDIUM",
                    "triggered_at": datetime.now().isoformat(),
                })

    return alerts
