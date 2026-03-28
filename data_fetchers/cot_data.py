"""
CFTC Commitments of Traders (COT) report parser.
Tracks commercial and speculative positioning in copper and oil.
"""

import requests
import pandas as pd
import io
import zipfile
from datetime import datetime
from config import COT_CONFIG
from utils.cache import cached_fetch

# CFTC COT report URLs
COT_FUTURES_URL = "https://www.cftc.gov/dea/newcot/deafut.txt"
COT_COMBINED_URL = "https://www.cftc.gov/dea/newcot/f_disagg.txt"
COT_HISTORICAL_URL = "https://www.cftc.gov/files/dea/history/deacot{year}.zip"


def _parse_cot_report(text: str, commodity_filter: str) -> list:
    """Parse COT report text for a specific commodity."""
    results = []
    lines = text.strip().split("\n")

    if not lines:
        return results

    for i, line in enumerate(lines):
        if commodity_filter.upper() in line.upper():
            fields = line.split(",")
            if len(fields) < 20:
                continue
            try:
                results.append({
                    "commodity": fields[0].strip(),
                    "date": fields[2].strip() if len(fields) > 2 else "Unknown",
                    "commercial_long": int(fields[8].strip()) if len(fields) > 8 and fields[8].strip().lstrip("-").isdigit() else 0,
                    "commercial_short": int(fields[9].strip()) if len(fields) > 9 and fields[9].strip().lstrip("-").isdigit() else 0,
                    "noncommercial_long": int(fields[6].strip()) if len(fields) > 6 and fields[6].strip().lstrip("-").isdigit() else 0,
                    "noncommercial_short": int(fields[7].strip()) if len(fields) > 7 and fields[7].strip().lstrip("-").isdigit() else 0,
                })
            except (ValueError, IndexError):
                continue

    return results


def _calculate_net_positions(records: list) -> list:
    """Calculate net commercial and speculative positions."""
    for record in records:
        record["commercial_net"] = record["commercial_long"] - record["commercial_short"]
        record["noncommercial_net"] = record["noncommercial_long"] - record["noncommercial_short"]
    return records


def _check_consecutive_net_long(records: list, weeks: int) -> bool:
    """Check if commercials have been net long for N consecutive weeks."""
    if len(records) < weeks:
        return False
    recent = records[-weeks:]
    return all(r["commercial_net"] > 0 for r in recent)


def fetch_cot_data() -> dict:
    """Fetch and analyse COT data for configured commodities."""
    def _fetch():
        results = {}
        try:
            response = requests.get(COT_FUTURES_URL, timeout=30)
            response.raise_for_status()
            report_text = response.text
        except Exception as e:
            return {"error": f"Failed to fetch COT report: {str(e)}"}

        for key, config in COT_CONFIG.items():
            records = _parse_cot_report(report_text, config["commodity"])
            records = _calculate_net_positions(records)

            consecutive_threshold = config["consecutive_weeks_threshold"]
            is_signal = _check_consecutive_net_long(records, consecutive_threshold)

            latest = records[-1] if records else {}
            results[key] = {
                "commodity": config["commodity"],
                "latest": latest,
                "records_count": len(records),
                "consecutive_net_long": is_signal,
                "consecutive_weeks_threshold": consecutive_threshold,
                "signal": config["signal"] if is_signal else None,
                "last_updated": datetime.now().isoformat(),
            }

        return results

    return cached_fetch("cot_data", _fetch)
