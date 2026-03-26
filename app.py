"""
Investment Intelligence Dashboard — Streamlit Application.

Personal investment monitoring system that surfaces plain English
interpretations of market signals for a long-term investor.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
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


# ---------------------------------------------------------------------------
# Plain English explanation generators
# ---------------------------------------------------------------------------

def explain_portfolio(item: dict) -> str:
    """One-liner plain English explanation for a portfolio position."""
    signal = item.get("signal", "AMBER")
    ticker = item.get("ticker", "")
    price = item.get("current_price", 0)
    weekly = item.get("weekly_change_pct", 0)
    pct_from_high = item.get("pct_from_high", 0)

    if "error" in item:
        return "Data isn't loading right now. Nothing to worry about, we'll check again soon."

    if ticker == "VWRA.L":
        if signal == "GREEN":
            return f"Price is holding steady. No action needed right now."
        elif signal == "AMBER":
            return f"Down {abs(weekly):.1f}% this week. Worth keeping an eye on, but not at buy levels yet."
        else:
            return f"Price has dropped to ${price:.2f} — below the $160 support level. This could be an entry opportunity."

    if "SUI" in ticker:
        if signal == "GREEN":
            return "SUI is cruising along nicely. Just let it ride."
        elif signal == "AMBER":
            return f"SUI pulled back {abs(weekly):.1f}% this week. Crypto swings are normal — watch but don't panic."
        else:
            return f"SUI has dropped significantly ({pct_from_high:+.0f}% from its high). Crypto winter vibes. Patience."

    if "XRP" in ticker:
        if signal == "GREEN":
            return "XRP is stable. No news is good news here."
        elif signal == "AMBER":
            return f"XRP is wobbling a bit ({weekly:+.1f}% this week). Typical crypto volatility."
        else:
            return f"XRP took a hit ({pct_from_high:+.0f}% from highs). Sit tight — these cycles take time."

    # Fallback
    if signal == "GREEN":
        return "Looking good. No action needed."
    elif signal == "AMBER":
        return f"Moved {weekly:+.1f}% this week. Keep watching."
    return f"Significant move — down {abs(pct_from_high):.0f}% from highs. Be cautious about adding more right now."


def explain_watchlist(item: dict) -> str:
    """One-liner plain English explanation for a watchlist item."""
    signal = item.get("signal", "AMBER")
    theme = item.get("theme", "")
    weekly = item.get("weekly_change_pct", 0)
    pct_from_high = item.get("pct_from_high", 0)

    if "error" in item:
        return "Can't fetch data right now. We'll try again later."

    explanations = {
        "copper": {
            "GREEN": "Copper miners are doing well. The electrification and infrastructure theme is playing out.",
            "AMBER": f"Copper is cooling off a bit ({weekly:+.1f}% this week). Not unusual — still in a long-term uptrend.",
            "RED": "Copper has sold off hard. Could be a buying window if the long-term thesis hasn't changed.",
        },
        "uranium": {
            "GREEN": "Uranium stocks are strong. Nuclear energy demand keeps growing.",
            "AMBER": f"Uranium names dipped {abs(weekly):.1f}% this week. The sector is volatile but the story is intact.",
            "RED": "Uranium stocks are under pressure. If you believe in nuclear long-term, these prices get interesting.",
        },
        "grid_infrastructure": {
            "GREEN": "Grid infrastructure is trending up. AI data centres and electrification are driving demand.",
            "AMBER": "Grid stocks are taking a breather. The need for grid upgrades isn't going away.",
            "RED": "Grid infrastructure sold off. Rare for this theme — could be worth a closer look.",
        },
        "water": {
            "GREEN": "Water stocks are steady. Quiet and reliable, like the theme itself.",
            "AMBER": "Water sector pulled back a little. One of the most defensive themes on the list.",
            "RED": "Even water stocks are down — that usually means broad market stress, not a water-specific problem.",
        },
        "rare_earths": {
            "GREEN": "Rare earth miners are up. Supply concerns and EV demand are supporting prices.",
            "AMBER": f"Rare earths dipped {abs(weekly):.1f}% this week. This sector swings with China trade news.",
            "RED": "Rare earth stocks are getting hammered. Highly cyclical — could snap back fast when sentiment shifts.",
        },
        "defence": {
            "GREEN": "Defence stocks are strong. Government spending commitments keep flowing.",
            "AMBER": "Defence pulled back slightly. Budget cycles cause temporary dips.",
            "RED": "Defence stocks are down. Unusual given geopolitical backdrop — worth investigating why.",
        },
    }

    theme_expl = explanations.get(theme, {})
    return theme_expl.get(signal, f"Moved {weekly:+.1f}% this week.")


def explain_macro(item: dict) -> str:
    """Plain English explanation for a macro indicator."""
    if "error" in item:
        return "Data unavailable right now."

    ticker = item.get("ticker", "")
    value = item.get("current_price", 0)
    signal = item.get("signal", "AMBER")

    if "VIX" in ticker:
        if value < 15:
            return f"VIX is at {value:.1f} — markets are super calm. Almost too calm. Good for holding, not great for finding bargains."
        elif value < 20:
            return f"VIX at {value:.1f} — normal levels. Markets feel fine. Nothing to do."
        elif value < 25:
            return f"VIX at {value:.1f} — a little elevated. Markets are slightly nervous but nothing serious."
        elif value < 30:
            return f"VIX at {value:.1f} — markets are getting jittery. Not panic level, but pay attention."
        elif value < 35:
            return f"VIX at {value:.1f} — markets are nervous but not panicking yet. Above 30 is when opportunities start appearing."
        else:
            return f"VIX at {value:.1f} — real fear in the market. Historically, buying 2-4 weeks after a VIX spike above 35 has been rewarding."

    if "DX" in ticker:
        if value > 110:
            return f"Dollar index at {value:.1f} — very strong dollar. This squeezes emerging markets and commodities. Headwind for non-USD assets."
        elif value > 105:
            return f"Dollar at {value:.1f} — firming up. A strong dollar makes everything priced in USD more expensive for us."
        else:
            return f"Dollar at {value:.1f} — relatively calm. Not creating problems for our positions."

    if "CL" in ticker:
        if value > 100:
            return f"Oil at ${value:.0f}/barrel — elevated. High energy costs slow the economy and squeeze consumers."
        elif value > 90:
            return f"Oil at ${value:.0f}/barrel — on the higher side. Watch for it dropping below $90 as a positive sign for the economy."
        else:
            return f"Oil at ${value:.0f}/barrel — manageable levels. Not a concern right now."

    return f"Currently at {value}."


def explain_fred(item: dict) -> str:
    """Plain English explanation for FRED economic data."""
    if "error" in item:
        return item.get("error", "Data unavailable.")

    series_id = item.get("series_id", "")
    value = item.get("current_value", 0)

    if "HYM2" in series_id:
        if value > 500:
            return (f"Credit spreads at {value:.0f} basis points — this means companies are paying a lot more to borrow. "
                    "That's a stress signal. When borrowing gets expensive, stocks usually follow lower.")
        elif value > 400:
            return (f"Credit spreads at {value:.0f}bps — creeping up. Companies are paying more to borrow than usual. "
                    "Not crisis level, but the bond market is getting cautious.")
        else:
            return (f"Credit spreads at {value:.0f}bps — normal range. The bond market isn't worried, "
                    "which is usually a good sign for stocks too.")

    if "T10Y2Y" in series_id:
        if value < 0:
            return (f"Yield curve is inverted ({value:+.2f}%). In plain English: short-term interest rates are higher than "
                    "long-term ones. This has predicted almost every recession. Stay cautious.")
        elif value < 0.2:
            return (f"Yield curve is barely positive ({value:.2f}%). It's flat, meaning the bond market is uncertain about "
                    "economic growth ahead. Worth monitoring.")
        else:
            return (f"Yield curve spread is {value:.2f}% — healthy. The bond market expects normal economic conditions. "
                    "No recession warning here.")

    if "DGS10" in series_id:
        if value > 5:
            return (f"10-year Treasury rate at {value:.2f}% — very high. This makes mortgages and business loans expensive. "
                    "Stocks compete with 'risk-free' 5%+ returns from bonds.")
        elif value > 4:
            return (f"10-year rate at {value:.2f}% — elevated but not extreme. Bonds are offering decent returns, "
                    "which creates some competition for stocks.")
        else:
            return f"10-year rate at {value:.2f}% — moderate. Not a major headwind for stocks."

    if "DTWEXBGS" in series_id:
        return f"Trade-weighted dollar index at {value:.1f}. This tracks the dollar against a basket of currencies."

    return f"Currently at {value}."


def explain_cot(key: str, data: dict) -> str:
    """Plain English explanation for COT positioning data."""
    if "error" in data:
        return "COT data unavailable right now."

    signal = data.get("signal", "AMBER")
    commodity = data.get("commodity", key)
    consecutive = data.get("consecutive_net_long", False)
    latest = data.get("latest", {})
    net = latest.get("commercial_net", 0)

    if "COPPER" in commodity.upper():
        if consecutive:
            return ("Big commercial copper buyers (miners, manufacturers) have been accumulating for 3+ weeks straight. "
                    "This is the signal we watch for — they know their market better than anyone.")
        elif net > 0:
            return ("Commercial copper buyers are net long, but not consistently enough yet. "
                    "Getting interesting — keep watching for a confirmed streak.")
        else:
            return ("Commercial copper buyers are net short — they're hedging, not accumulating. "
                    "Not the right time for copper. Be patient.")

    if "OIL" in commodity.upper() or "CRUDE" in commodity.upper():
        if consecutive:
            return ("Oil producers have been net long for 3+ weeks. They're betting on higher prices. "
                    "This usually means supply is tighter than headlines suggest.")
        elif net > 0:
            return "Oil commercials are leaning bullish but the signal isn't confirmed yet. Watch and wait."
        else:
            return ("Oil commercials are net short — they expect lower prices or are locking in current levels. "
                    "No urgency on energy positions.")

    if signal == "GREEN":
        return f"Commercial {commodity.lower()} traders are positioned bullish. Good sign."
    elif signal == "AMBER":
        return f"Mixed positioning in {commodity.lower()}. Not a clear signal yet."
    return f"Commercials are bearish on {commodity.lower()}. Not the time to add."


def explain_scraped(key: str, data: dict) -> str:
    """Plain English explanation for scraped data."""
    if "error" in data:
        return "Couldn't fetch this data right now."

    if key == "uranium_spot":
        value = data.get("value", 0)
        if value < 75:
            return (f"Uranium spot price is ${value:.0f}/lb — below $75, which is below what most contracts are priced at. "
                    "Miners are selling at a discount. This has historically been a good entry for uranium stocks.")
        elif value < 90:
            return f"Uranium at ${value:.0f}/lb — reasonable levels. Not screaming cheap, but the long-term demand story is intact."
        else:
            return f"Uranium at ${value:.0f}/lb — price is running. Good for existing positions, but new entries are pricier."

    if key == "baltic_dry_index":
        value = data.get("value", 0)
        if value < 1000:
            return (f"Baltic Dry Index at {value:.0f} — shipping rates are very low. This means less stuff is being "
                    "moved around the world. Usually a sign the global economy is slowing.")
        elif value < 1500:
            return f"Baltic Dry Index at {value:.0f} — moderate shipping activity. Economy is ticking along, nothing dramatic."
        else:
            return (f"Baltic Dry Index at {value:.0f} — strong shipping demand. Global trade is healthy, "
                    "which is good for commodities and emerging markets.")

    return f"Current value: {data.get('value', 'N/A')}"


def generate_summary_box(signals: dict, alerts: list) -> str:
    """Generate a 2-3 sentence plain English summary of the overall situation."""
    red_count = 0
    amber_count = 0
    green_count = 0

    for section in ["portfolio", "watchlist", "macro", "fred"]:
        for item in signals.get(section, []):
            s = item.get("signal", "AMBER")
            if s == "RED":
                red_count += 1
            elif s == "AMBER":
                amber_count += 1
            else:
                green_count += 1

    for data in signals.get("cot", {}).values():
        s = data.get("signal", "AMBER")
        if s == "RED":
            red_count += 1
        elif s == "AMBER":
            amber_count += 1
        else:
            green_count += 1

    for data in signals.get("scraped", {}).values():
        s = data.get("signal", "AMBER")
        if s == "RED":
            red_count += 1
        elif s == "AMBER":
            amber_count += 1
        else:
            green_count += 1

    total = red_count + amber_count + green_count
    alert_count = len(alerts)

    # Build the summary
    if red_count == 0 and amber_count <= 2:
        mood = "Everything looks calm this week. All signals are steady and there's nothing that needs your attention."
        action = "Stay patient — this is a hold-and-wait kind of week."
    elif red_count == 0 and amber_count > 2:
        mood = f"Mostly fine, but {amber_count} indicators are worth watching. Nothing alarming, just some areas shifting."
        action = "No action needed yet, but check back if things develop."
    elif red_count <= 2:
        mood = (f"A few warning signs this week — {red_count} red signal{'s' if red_count > 1 else ''} "
                f"and {amber_count} amber. Some areas are under pressure.")
        if alert_count > 0:
            action = f"{alert_count} alert{'s' if alert_count > 1 else ''} triggered. Scroll down to see what crossed a threshold — could be an opportunity."
        else:
            action = "Worth a closer look, but don't rush into anything. Watch how next week develops."
    else:
        mood = (f"Markets are stressed — {red_count} red signals across the board. "
                "This is the kind of environment where opportunities eventually appear.")
        if alert_count > 0:
            action = (f"{alert_count} threshold alert{'s' if alert_count > 1 else ''} triggered. "
                      "Historically these moments have been good entry points, but give it a few weeks to settle.")
        else:
            action = "Be patient. Don't try to catch a falling knife — let the dust settle first."

    return f"{mood} {action}"


# ---------------------------------------------------------------------------
# Historical performance — growth of $10,000
# ---------------------------------------------------------------------------

# One representative ticker per theme, chosen for longest available history.
# VT is used as a proxy for VWRA (VT launched 2008, VWRA only 2019).
HISTORICAL_TICKERS = {
    "VWRA (via VT)": "VT",       # Vanguard Total World — proxy for VWRA, 2008+
    "Copper": "COPX",             # Global X Copper Miners, 2010+
    "Uranium": "URA",             # Global X Uranium, 2010+
    "Grid Infra": "GRID",         # First Trust Smart Grid, 2009+
    "Water": "PHO",               # Invesco Water Resources, 2005+
    "Rare Earths": "REMX",        # VanEck Rare Earth, 2010+
    "Defence": "ITA",             # iShares Aerospace & Defense, 2003+
}

THEME_COLORS = {
    "VWRA (via VT)": "#1f77b4",
    "Copper": "#d62728",
    "Uranium": "#2ca02c",
    "Grid Infra": "#ff7f0e",
    "Water": "#17becf",
    "Rare Earths": "#9467bd",
    "Defence": "#8c564b",
}


@st.cache_data(ttl=86400)
def load_historical_data() -> pd.DataFrame:
    """Fetch monthly closing prices for each theme ticker from 2007 to today."""
    start = "2007-01-01"
    all_series = {}

    for label, ticker in HISTORICAL_TICKERS.items():
        try:
            df = yf.download(ticker, start=start, interval="1mo", progress=False)
            if df.empty:
                continue
            # yfinance may return MultiIndex columns for single ticker
            close = df["Close"].squeeze()
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            # Normalise to $10,000
            first_valid = close.first_valid_index()
            if first_valid is None:
                continue
            close = close.loc[first_valid:]
            normalised = (close / close.iloc[0]) * 10_000
            all_series[label] = normalised
        except Exception:
            continue

    if not all_series:
        return pd.DataFrame()

    combined = pd.DataFrame(all_series)
    combined.index = pd.to_datetime(combined.index)
    combined = combined.sort_index()
    return combined


def _cycle_commentary(label: str, current_val: float, peak_val: float, peak_date) -> str:
    """Plain English one-liner about where we are in the cycle."""
    pct_from_peak = ((current_val - peak_val) / peak_val) * 100
    total_return = ((current_val - 10_000) / 10_000) * 100

    peak_str = peak_date.strftime("%b %Y") if hasattr(peak_date, "strftime") else str(peak_date)

    if abs(pct_from_peak) < 5:
        position = f"right near its all-time high (peaked {peak_str})"
    elif pct_from_peak > -15:
        position = f"slightly below its peak from {peak_str} ({pct_from_peak:+.0f}%)"
    elif pct_from_peak > -30:
        position = f"well off its {peak_str} peak ({pct_from_peak:+.0f}%) — mid-cycle pullback territory"
    elif pct_from_peak > -50:
        position = f"deep into a drawdown ({pct_from_peak:+.0f}% from {peak_str} peak) — historically these recoveries take 1-3 years"
    else:
        position = f"in a severe drawdown ({pct_from_peak:+.0f}% from {peak_str} peak) — either the thesis has changed or this is a generational entry"

    if total_return > 0:
        return f"$10K invested at the start would be worth ${current_val:,.0f} today ({total_return:+,.0f}%). Currently {position}."
    else:
        return f"$10K invested at the start would be worth ${current_val:,.0f} today ({total_return:+,.0f}%). Currently {position}."


def render_historical_performance():
    """Render the historical performance section with growth chart and commentary."""
    st.header("Historical Performance")
    st.caption("How would $10,000 have grown in each theme since 2007? This helps you see where we are in each cycle.")

    hist = load_historical_data()
    if hist.empty:
        st.warning("Couldn't load historical data. Try refreshing.")
        return

    # --- Main chart: all themes ---
    fig = go.Figure()
    for label in hist.columns:
        series = hist[label].dropna()
        fig.add_trace(go.Scatter(
            x=series.index,
            y=series.values,
            name=label,
            mode="lines",
            line=dict(color=THEME_COLORS.get(label, "#999"), width=2.5 if "VWRA" in label else 1.5),
            opacity=1.0 if "VWRA" in label else 0.85,
        ))

    fig.update_layout(
        title="Growth of $10,000 — Each Watchlist Theme vs VWRA",
        yaxis_title="Portfolio Value ($)",
        xaxis_title="",
        hovermode="x unified",
        template="plotly_dark",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        yaxis=dict(tickprefix="$", tickformat=","),
    )

    # Add key events as vertical lines
    events = {
        "2008-09-15": "Lehman collapse",
        "2020-03-23": "COVID bottom",
        "2022-01-03": "2022 bear market starts",
    }
    for date_str, event_label in events.items():
        fig.add_vline(x=date_str, line_dash="dot", line_color="rgba(255,255,255,0.3)")
        fig.add_annotation(
            x=date_str, y=1.05, yref="paper", text=event_label,
            showarrow=False, font=dict(size=10, color="rgba(255,255,255,0.5)"),
        )

    st.plotly_chart(fig, use_container_width=True)

    # --- Per-theme commentary ---
    st.subheader("Where are we in each cycle?")

    cols = st.columns(2)
    for i, label in enumerate(hist.columns):
        series = hist[label].dropna()
        if series.empty:
            continue

        current_val = series.iloc[-1]
        peak_val = series.max()
        peak_date = series.idxmax()

        with cols[i % 2]:
            color = THEME_COLORS.get(label, "#999")
            commentary = _cycle_commentary(label, current_val, peak_val, peak_date)
            st.markdown(
                f'<div style="border-left:3px solid {color};padding:8px 12px;margin-bottom:12px;">'
                f'<strong>{label}</strong><br/>'
                f'<span style="font-size:0.92em;">{commentary}</span></div>',
                unsafe_allow_html=True,
            )

    # --- Individual theme charts ---
    with st.expander("Individual theme charts", expanded=False):
        for label in hist.columns:
            series = hist[label].dropna()
            if series.empty:
                continue

            fig_small = go.Figure()
            fig_small.add_trace(go.Scatter(
                x=series.index, y=series.values,
                fill="tozeroy",
                line=dict(color=THEME_COLORS.get(label, "#999"), width=2),
                fillcolor=THEME_COLORS.get(label, "#999").replace(")", ",0.1)").replace("rgb", "rgba")
                    if "rgb" in THEME_COLORS.get(label, "") else f"rgba(100,100,100,0.1)",
            ))
            # Add $10K baseline
            fig_small.add_hline(y=10_000, line_dash="dash", line_color="rgba(255,255,255,0.3)",
                                annotation_text="$10K start", annotation_font_color="rgba(255,255,255,0.4)")

            fig_small.update_layout(
                title=f"{label}",
                yaxis=dict(tickprefix="$", tickformat=","),
                template="plotly_dark",
                height=250,
                showlegend=False,
                margin=dict(l=50, r=20, t=40, b=30),
            )
            st.plotly_chart(fig_small, use_container_width=True)


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

            st.info(explain_portfolio(item))


def render_watchlist(signals: dict):
    """Render watchlist section grouped by theme."""
    st.header("Thematic Watchlist")

    themes = {}
    for item in signals.get("watchlist", []):
        theme = item.get("theme", "other")
        themes.setdefault(theme, []).append(item)

    for theme, items in themes.items():
        with st.expander(f"{theme.replace('_', ' ').title()} ({len(items)} tickers)", expanded=True):
            for item in items:
                signal = item.get("signal", "AMBER")
                name = item.get("name", "Unknown")
                if "error" in item:
                    st.markdown(f"{signal_badge(signal)} **{name}** — Error loading data", unsafe_allow_html=True)
                else:
                    price = item.get("current_price", "N/A")
                    weekly = item.get("weekly_change_pct", 0)
                    st.markdown(
                        f"{signal_badge(signal)} **{name}**: ${price} (week: {weekly:+.1f}%)",
                        unsafe_allow_html=True,
                    )
                st.caption(explain_watchlist(item))


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
                st.markdown(f"{signal_badge(signal)} **{name}**: {value}", unsafe_allow_html=True)
            st.caption(explain_macro(item))

    with col2:
        st.subheader("Economic Data (FRED)")
        for item in signals.get("fred", []):
            signal = item.get("signal", "AMBER")
            name = item.get("name", "Unknown")
            if "error" in item:
                st.markdown(f"{signal_badge(signal)} **{name}**: unavailable", unsafe_allow_html=True)
            else:
                value = item.get("current_value", "N/A")
                st.markdown(f"{signal_badge(signal)} **{name}**: {value}", unsafe_allow_html=True)
            st.caption(explain_fred(item))


def render_cot(signals: dict):
    """Render COT data section."""
    st.header("Commitments of Traders")
    st.caption("What are the big commercial buyers actually doing with their money?")

    cot = signals.get("cot", {})
    if not cot:
        st.info("No COT data available right now. This report comes from the CFTC and updates weekly.")
        return

    for key, data in cot.items():
        signal = data.get("signal", "AMBER")
        commodity = data.get("commodity", key)
        latest = data.get("latest", {})

        col1, col2, col3 = st.columns(3)
        col1.markdown(f"{signal_badge(signal)} **{commodity}**", unsafe_allow_html=True)
        col2.metric("Commercial Net", latest.get("commercial_net", "N/A"))
        col3.metric("Spec Net", latest.get("noncommercial_net", "N/A"))

        st.caption(explain_cot(key, data))


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

    # Summary box at the top
    summary = generate_summary_box(signals, alerts)
    st.markdown(
        f'<div style="background-color:#1a1a2e;border-left:4px solid #1f77b4;padding:16px 20px;'
        f'border-radius:4px;margin-bottom:16px;font-size:1.05em;line-height:1.6;">{summary}</div>',
        unsafe_allow_html=True,
    )

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

    # Scraped data
    scraped_signals = signals.get("scraped", {})
    if scraped_signals:
        st.header("Other Data Sources")
        for key, data in scraped_signals.items():
            signal = data.get("signal", "AMBER")
            name = data.get("name", key.replace("_", " ").title())
            value = data.get("value", "N/A")
            unit = data.get("unit", "")
            st.markdown(f"{signal_badge(signal)} **{name}**: {value} {unit}", unsafe_allow_html=True)
            st.caption(explain_scraped(key, data))
        st.divider()

    # Historical performance
    render_historical_performance()
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
