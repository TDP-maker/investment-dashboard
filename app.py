"""
Investment Intelligence Dashboard — Streamlit Application.

Personal investment monitoring system that surfaces plain English
interpretations of market signals for a long-term investor.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from config import PORTFOLIO, WATCHLIST, THRESHOLDS, DASHBOARD_PASSWORD
from data_fetchers import fetch_portfolio_data, fetch_watchlist_data, fetch_macro_data
from data_fetchers import fetch_fred_data, fetch_cot_data, fetch_scraped_data
from analysis.signals import classify_signals
from analysis.alerts import check_alerts
from briefing.generator import generate_briefing
from utils.cache import clear_cache

# Page config
st.set_page_config(
    page_title="Investment Intelligence Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Signal color mapping
SIGNAL_COLORS = {
    "GREEN": "#00c853",
    "AMBER": "#ffa000",
    "RED": "#d50000",
}


def signal_badge(signal: str) -> str:
    """Return a colored HTML badge for a signal."""
    color = SIGNAL_COLORS.get(signal, "#666")
    return f'<span style="background-color:{color};color:white;padding:2px 8px;border-radius:4px;font-weight:bold;font-size:0.85em;">{signal}</span>'


@st.cache_data(ttl=3600)
def load_all_data():
    """Load all data sources with caching."""
    portfolio = fetch_portfolio_data()
    watchlist = fetch_watchlist_data()
    macro = fetch_macro_data()
    fred = fetch_fred_data()
    cot = fetch_cot_data()
    scraped = fetch_scraped_data()
    return portfolio, watchlist, macro, fred, cot, scraped


def render_sidebar():
    """Render the sidebar with controls."""
    with st.sidebar:
        st.title("Controls")

        if st.button("Refresh Data", use_container_width=True):
            clear_cache()
            st.cache_data.clear()
            st.rerun()

        st.divider()

        st.subheader("Alert Thresholds")
        for key, config in THRESHOLDS.items():
            label = key.replace("_", " ").title()
            ticker = config.get("ticker", config.get("series", config.get("source", "")))
            st.text(f"{label}: {config['condition']} {config['value']}")

        st.divider()
        st.caption(f"Last refresh: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        st.caption("Personal use only. Not financial advice.")


def render_portfolio(signals: dict):
    """Render portfolio positions section."""
    st.header("Portfolio Positions")

    cols = st.columns(len(signals.get("portfolio", [])) or 1)
    for i, item in enumerate(signals.get("portfolio", [])):
        with cols[i % len(cols)]:
            signal = item.get("signal", "AMBER")
            color = SIGNAL_COLORS.get(signal, "#666")

            st.markdown(f"### {item.get('name', 'Unknown')}")
            st.markdown(f"**Signal:** {signal_badge(signal)}", unsafe_allow_html=True)

            if "error" not in item:
                price = item.get("current_price", "N/A")
                daily = item.get("daily_change_pct", 0)
                weekly = item.get("weekly_change_pct", 0)
                monthly = item.get("monthly_change_pct", 0)

                st.metric("Price", f"${price}", f"{daily:+.2f}%")

                col1, col2 = st.columns(2)
                col1.metric("Week", f"{weekly:+.2f}%")
                col2.metric("Month", f"{monthly:+.2f}%")

                st.caption(f"52W High: ${item.get('high_52w', 'N/A')} | "
                          f"Low: ${item.get('low_52w', 'N/A')} | "
                          f"From High: {item.get('pct_from_high', 0):+.1f}%")
            else:
                st.error(f"Error: {item['error']}")


def render_watchlist(signals: dict):
    """Render watchlist section grouped by theme."""
    st.header("Thematic Watchlist")

    themes = {}
    for item in signals.get("watchlist", []):
        theme = item.get("theme", "other")
        themes.setdefault(theme, []).append(item)

    for theme, items in themes.items():
        with st.expander(f"{theme.replace('_', ' ').title()} ({len(items)} tickers)", expanded=True):
            rows = []
            for item in items:
                if "error" in item:
                    rows.append({
                        "Signal": item.get("signal", "AMBER"),
                        "Name": item.get("name", "Unknown"),
                        "Price": "Error",
                        "Day %": "N/A",
                        "Week %": "N/A",
                    })
                else:
                    rows.append({
                        "Signal": item.get("signal", "AMBER"),
                        "Name": item.get("name", "Unknown"),
                        "Price": f"${item.get('current_price', 'N/A')}",
                        "Day %": f"{item.get('daily_change_pct', 0):+.2f}%",
                        "Week %": f"{item.get('weekly_change_pct', 0):+.2f}%",
                    })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_macro(signals: dict):
    """Render macro indicators section."""
    st.header("Macro Indicators")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Market Indicators")
        for item in signals.get("macro", []):
            signal = item.get("signal", "AMBER")
            name = item.get("name", "Unknown")
            if "error" in item:
                st.markdown(f"{signal_badge(signal)} **{name}**: Error", unsafe_allow_html=True)
            else:
                value = item.get("current_price", "N/A")
                daily = item.get("daily_change_pct", 0)
                st.markdown(f"{signal_badge(signal)} **{name}**: {value} ({daily:+.2f}%)", unsafe_allow_html=True)

    with col2:
        st.subheader("Economic Data (FRED)")
        for item in signals.get("fred", []):
            signal = item.get("signal", "AMBER")
            name = item.get("name", "Unknown")
            if "error" in item:
                st.markdown(f"{signal_badge(signal)} **{name}**: {item.get('error', 'N/A')}", unsafe_allow_html=True)
            else:
                value = item.get("current_value", "N/A")
                change = item.get("daily_change", 0)
                st.markdown(f"{signal_badge(signal)} **{name}**: {value} ({change:+.4f})", unsafe_allow_html=True)


def render_cot(signals: dict):
    """Render COT data section."""
    st.header("Commitments of Traders (COT)")

    cot = signals.get("cot", {})
    if not cot:
        st.info("No COT data available.")
        return

    for key, data in cot.items():
        signal = data.get("signal", "AMBER")
        commodity = data.get("commodity", key)
        latest = data.get("latest", {})

        col1, col2, col3 = st.columns(3)
        col1.markdown(f"{signal_badge(signal)} **{commodity}**", unsafe_allow_html=True)
        col2.metric("Commercial Net", latest.get("commercial_net", "N/A"))
        col3.metric("Spec Net", latest.get("noncommercial_net", "N/A"))

        if data.get("consecutive_net_long"):
            st.success(f"Signal: {data.get('signal_text', data.get('signal', ''))}")


def render_alerts(alerts: list):
    """Render active alerts section."""
    st.header("Active Alerts")

    if not alerts:
        st.success("No threshold alerts triggered.")
        return

    for alert in alerts:
        severity = alert.get("severity", "MEDIUM")
        if severity == "HIGH":
            st.error(f"**{alert.get('signal', 'Alert')}** — "
                    f"Current: {alert.get('current_value', 'N/A')} "
                    f"(threshold: {alert.get('condition', 'N/A')})")
        else:
            st.warning(f"**{alert.get('signal', 'Alert')}** — "
                      f"{alert.get('condition', 'N/A')}")


def render_briefing(briefing_text: str):
    """Render the AI briefing section."""
    st.header("Weekly Briefing")

    if briefing_text:
        st.markdown(briefing_text)
    else:
        st.info("No briefing generated yet. Click 'Generate Briefing' to create one.")


def check_password() -> bool:
    """Prompt for password if DASHBOARD_PASSWORD is set. Returns True if access is granted."""
    if not DASHBOARD_PASSWORD:
        return True

    if st.session_state.get("authenticated"):
        return True

    st.title("Investment Intelligence Dashboard")
    st.markdown("---")
    password = st.text_input("Enter password to access the dashboard:", type="password")

    if password:
        if password == DASHBOARD_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()


def main():
    if not check_password():
        return

    st.title("Investment Intelligence Dashboard")
    st.caption("Long-term positioning signals — not a trading tool")

    render_sidebar()

    # Load data
    with st.spinner("Loading market data..."):
        portfolio, watchlist, macro, fred, cot, scraped = load_all_data()

    # Classify signals
    signals = classify_signals(portfolio, watchlist, macro, fred, cot, scraped)

    # Check alerts
    alerts = check_alerts(portfolio, macro, fred, cot, scraped)

    # Render sections
    render_alerts(alerts)
    st.divider()

    render_portfolio(signals)
    st.divider()

    render_watchlist(signals)
    st.divider()

    render_macro(signals)
    st.divider()

    render_cot(signals)
    st.divider()

    # Briefing section
    st.header("Weekly Briefing")
    if st.button("Generate Briefing", use_container_width=True):
        with st.spinner("Generating briefing..."):
            briefing = generate_briefing(
                portfolio, watchlist, macro, fred, cot, scraped, signals, alerts
            )
            st.session_state["briefing"] = briefing

    if "briefing" in st.session_state:
        render_briefing(st.session_state["briefing"])


if __name__ == "__main__":
    main()
