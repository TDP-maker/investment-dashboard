"""
Automated scheduler for the Investment Intelligence Dashboard.
Runs weekly briefings and daily alert checks.

Usage:
    python scheduler.py          # Start scheduled runner (Fridays at 4pm EST)
    python scheduler.py --once   # Run a single briefing now
    python scheduler.py --alerts # Run alert check only
"""

import argparse
import schedule
import time
from datetime import datetime

from config import BRIEFING_SCHEDULE
from data_fetchers import fetch_portfolio_data, fetch_watchlist_data, fetch_macro_data
from data_fetchers import fetch_fred_data, fetch_cot_data, fetch_scraped_data
from analysis.signals import classify_signals
from analysis.alerts import check_alerts
from briefing.generator import generate_briefing
from utils.cache import clear_cache
from utils.notifications import send_email_alert, format_alerts_email


def run_briefing():
    """Run a full briefing cycle: fetch data, analyse, generate briefing, send alerts."""
    print(f"\n{'='*60}")
    print(f"Running briefing at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # Clear cache for fresh data
    clear_cache()

    # Fetch all data
    print("Fetching portfolio data...")
    portfolio = fetch_portfolio_data()

    print("Fetching watchlist data...")
    watchlist = fetch_watchlist_data()

    print("Fetching macro data...")
    macro = fetch_macro_data()

    print("Fetching FRED data...")
    fred = fetch_fred_data()

    print("Fetching COT data...")
    cot = fetch_cot_data()

    print("Fetching scraped data...")
    scraped = fetch_scraped_data()

    # Classify signals
    print("\nClassifying signals...")
    signals = classify_signals(portfolio, watchlist, macro, fred, cot, scraped)

    # Check alerts
    print("Checking alert thresholds...")
    alerts = check_alerts(portfolio, macro, fred, cot, scraped)

    if alerts:
        print(f"\n*** {len(alerts)} ALERT(S) TRIGGERED ***")
        for alert in alerts:
            print(f"  [{alert['severity']}] {alert['signal']}")

        # Send email alerts
        subject, body = format_alerts_email(alerts)
        send_email_alert(subject, body)

    # Generate briefing
    print("\nGenerating briefing...")
    briefing = generate_briefing(portfolio, watchlist, macro, fred, cot, scraped, signals, alerts)

    # Print briefing
    print(f"\n{'='*60}")
    print("WEEKLY BRIEFING")
    print(f"{'='*60}\n")
    print(briefing)

    # Save briefing to file
    filename = f"briefing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(filename, "w") as f:
        f.write(briefing)
    print(f"\nBriefing saved to {filename}")

    return briefing


def run_alert_check():
    """Run alert check only (no briefing generation)."""
    print(f"Running alert check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    portfolio = fetch_portfolio_data()
    macro = fetch_macro_data()
    fred = fetch_fred_data()
    cot = fetch_cot_data()
    scraped = fetch_scraped_data()

    alerts = check_alerts(portfolio, macro, fred, cot, scraped)

    if alerts:
        print(f"{len(alerts)} alert(s) triggered:")
        for alert in alerts:
            print(f"  [{alert['severity']}] {alert['signal']} "
                  f"(current: {alert.get('current_value', 'N/A')})")

        subject, body = format_alerts_email(alerts)
        send_email_alert(subject, body)
    else:
        print("No alerts triggered.")

    return alerts


def start_scheduler():
    """Start the automated scheduler."""
    day = BRIEFING_SCHEDULE["day"]
    hour = BRIEFING_SCHEDULE["hour"]
    minute = BRIEFING_SCHEDULE["minute"]

    time_str = f"{hour:02d}:{minute:02d}"

    print(f"Investment Intelligence Dashboard — Scheduler")
    print(f"Briefing scheduled: {day.title()}s at {time_str} EST")
    print(f"Alert checks: Daily at 09:00 and 16:00 EST")
    print(f"Press Ctrl+C to stop.\n")

    # Weekly briefing
    getattr(schedule.every(), day).at(time_str).do(run_briefing)

    # Daily alert checks
    schedule.every().day.at("09:00").do(run_alert_check)
    schedule.every().day.at("16:00").do(run_alert_check)

    while True:
        schedule.run_pending()
        time.sleep(60)


def main():
    parser = argparse.ArgumentParser(description="Investment Intelligence Dashboard Scheduler")
    parser.add_argument("--once", action="store_true", help="Run a single briefing now")
    parser.add_argument("--alerts", action="store_true", help="Run alert check only")
    args = parser.parse_args()

    if args.once:
        run_briefing()
    elif args.alerts:
        run_alert_check()
    else:
        start_scheduler()


if __name__ == "__main__":
    main()
