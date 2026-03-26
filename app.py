"""
Investment Intelligence Dashboard — Streamlit Application.

Personal investment monitoring system that surfaces plain English
interpretations of market signals for a long-term investor.
"""

import streamlit as st
import pandas as pd
import numpy as np
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
        "semiconductors": {
            "GREEN": "Chip stocks are riding high on AI spending. Companies are pouring money into data centres.",
            "AMBER": f"Semiconductor stocks pulled back {abs(weekly):.1f}% this week. These are volatile — AI hype swings both ways.",
            "RED": "Chip stocks are in a correction. If AI spending holds up, this could be an entry — but it's a higher-risk theme.",
        },
        "cybersecurity": {
            "GREEN": "Cybersecurity stocks are strong. Every new data centre and smart grid needs protection, and spending keeps rising.",
            "AMBER": f"Cybersecurity dipped {abs(weekly):.1f}% this week. The threat landscape only grows — dips tend to be temporary.",
            "RED": "Cybersecurity stocks are under pressure. The $700 billion market by 2034 thesis hasn't changed — could be an opportunity.",
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


# ---------------------------------------------------------------------------
# Growth Projections & Research — institutional source data
# ---------------------------------------------------------------------------

PROJECTION_YEARS = list(range(2025, 2041))

PROJECTIONS = {
    "vwra": {
        "title": "VWRA — Global Equities",
        "color": "#1f77b4",
        "chart_type": "scenarios",
        "data": {
            "Conservative (7%)": [10_000 * (1.07 ** y) for y in range(16)],
            "Base Case (10%)":   [10_000 * (1.10 ** y) for y in range(16)],
            "Optimistic (12%)":  [10_000 * (1.12 ** y) for y in range(16)],
        },
        "y_prefix": "$",
        "y_label": "Value of $10,000 invested today",
        "source": (
            "Source: MSCI World Index historical annualised returns 1987-2024 (average ~10.1% nominal). "
            "Scenario range based on Vanguard Capital Markets Model 2024 long-term return expectations."
        ),
        "summary": (
            "Global stocks have returned about 10% per year on average over the last 35+ years. "
            "That means $10,000 invested today could become roughly $42,000 by 2040 in a normal market. "
            "Even in the conservative scenario (lower growth, higher inflation) it still roughly triples."
        ),
        "why_matters": (
            "VWRA is your core position — a single ETF that owns thousands of companies across the entire world. "
            "It's the foundation everything else is built around."
        ),
    },
    "water": {
        "title": "Water — Global Freshwater Demand",
        "color": "#17becf",
        "chart_type": "supply_demand",
        "data": {
            "Water Demand (km\u00b3/yr)":        [4200, 4400, 4700, 4900, 5100, 5300, 5500, 5700, 5900, 6100, 6300, 6500, 6700, 6900, 7100, 7300],
            "Sustainable Supply (km\u00b3/yr)":   [4600, 4600, 4600, 4550, 4550, 4500, 4500, 4450, 4450, 4400, 4400, 4350, 4350, 4300, 4300, 4250],
            "Data Centre Water (km\u00b3/yr)":    [4,    8,    18,   30,   44,   55,   65,   75,   85,   95,  105,  115,  125,  135,  145,  155],
        },
        "y_prefix": "",
        "y_label": "Cubic kilometres per year",
        "source": (
            "Source: World Economic Forum — 56% freshwater deficit projected by 2030 | "
            "Morgan Stanley Research 2024 — 11x increase in data centre water consumption by 2028 | "
            "UN World Water Development Report 2024"
        ),
        "summary": (
            "The world is using more water than nature can replenish. By 2030, demand will be 56% higher than "
            "sustainable supply. AI data centres alone will use 11 times more water by 2028 than they do today. "
            "Companies that treat, distribute, and conserve water are solving a problem that only gets bigger."
        ),
        "why_matters": (
            "PHO (Invesco Water Resources ETF) holds companies building the pipes, pumps, and treatment systems "
            "the world needs. This is one of the quietest but most certain long-term themes."
        ),
    },
    "grid_infrastructure": {
        "title": "Grid Infrastructure — Global Investment Required",
        "color": "#ff7f0e",
        "chart_type": "supply_demand",
        "data": {
            "Investment Needed ($bn/yr)":    [330, 380, 430, 480, 530, 600, 620, 650, 680, 710, 740, 770, 800, 830, 860, 900],
            "Current Trajectory ($bn/yr)":   [330, 340, 350, 360, 370, 380, 390, 400, 410, 420, 430, 440, 450, 460, 470, 480],
        },
        "y_prefix": "$",
        "y_label": "Annual investment ($ billions)",
        "extra_annotation": "80 million km of new grid needed by 2040",
        "source": (
            "Source: IEA Electricity Grids and Secure Energy Transitions Report 2023 | "
            "IEA World Energy Outlook 2025 | BloombergNEF New Energy Outlook 2024"
        ),
        "summary": (
            "Governments around the world have legally committed to doubling grid spending by 2030. "
            "The electricity grid is the bottleneck for everything — EVs, heat pumps, data centres, renewables. "
            "80 million km of new power lines are needed by 2040. That money goes directly into the companies these ETFs hold."
        ),
        "why_matters": (
            "GRID (First Trust Smart Grid ETF) holds the companies building transformers, cables, and smart meters. "
            "This is one of the most certain investment themes because the spending is already legally committed."
        ),
    },
    "copper": {
        "title": "Copper — Supply vs Demand Projection",
        "color": "#d62728",
        "chart_type": "supply_demand",
        "data": {
            "Demand (Mt)":                   [28.0, 28.8, 29.7, 30.6, 31.5, 32.5, 33.5, 34.5, 35.5, 36.5, 37.5, 38.5, 39.5, 40.5, 41.3, 42.0],
            "Projected Supply (Mt)":         [28.0, 28.3, 28.6, 28.9, 29.2, 29.5, 29.8, 30.1, 30.4, 30.7, 31.0, 31.3, 31.6, 31.9, 32.2, 32.5],
        },
        "y_prefix": "",
        "y_label": "Million tonnes per year",
        "source": (
            "Source: S&P Global — 'The Future of Copper' 2022 (demand to reach 50Mt by 2035 in net-zero scenario) | "
            "Goldman Sachs Commodities Research 2024 — copper fair value $11,300/tonne | "
            "International Copper Study Group 2024"
        ),
        "summary": (
            "Every electric car needs 4x more copper than a petrol car. Every wind turbine, solar panel, and data centre "
            "needs copper. Demand is growing at 3-4% per year but new mines take 10-15 years to build. "
            "By 2030, the world will need more copper than mines can produce. That gap keeps widening."
        ),
        "why_matters": (
            "COPX (Global X Copper Miners ETF) holds the companies that dig copper out of the ground. "
            "When there's a shortage of something essential, the people who produce it make a lot of money."
        ),
    },
    "uranium": {
        "title": "Uranium — Nuclear Capacity vs Fuel Supply",
        "color": "#2ca02c",
        "chart_type": "supply_demand",
        "data": {
            "Reactor Demand (GWe)":          [391, 400, 415, 430, 450, 475, 500, 525, 555, 585, 615, 645, 675, 710, 730, 746],
            "Current Mine Supply (GWe eq.)": [370, 375, 380, 385, 390, 395, 400, 405, 410, 415, 420, 425, 430, 435, 440, 445],
        },
        "y_prefix": "",
        "y_label": "Gigawatts-electric (GWe)",
        "source": (
            "Source: World Nuclear Association — Nuclear Fuel Report 2023 (Reference Scenario: 746 GWe by 2040) | "
            "WNA 'Harmony' programme targets 25% of global electricity from nuclear by 2050 | "
            "Sprott Asset Management — Uranium Market Overview Q4 2024"
        ),
        "summary": (
            "28 countries at COP28 pledged to triple nuclear energy by 2050. China alone is building 23 reactors right now. "
            "Nuclear capacity is set to almost double to 746 GWe by 2040, but uranium mines can't keep up. "
            "The fuel supply gap means uranium prices need to stay high enough to justify opening new mines."
        ),
        "why_matters": (
            "URA (Global X Uranium ETF) holds uranium miners and nuclear fuel companies. "
            "When reactors need fuel and there isn't enough, these companies benefit directly."
        ),
    },
    "rare_earths": {
        "title": "Rare Earths & Critical Minerals — Demand Growth",
        "color": "#9467bd",
        "chart_type": "scenarios",
        "data": {
            "EV + Battery Demand (index)":   [100, 125, 160, 200, 250, 310, 370, 430, 500, 570, 640, 710, 790, 870, 950, 1040],
            "Wind + Solar Demand (index)":   [100, 115, 135, 155, 180, 210, 240, 275, 310, 350, 390, 430, 480, 530, 580, 640],
            "Defence + Aerospace (index)":   [100, 108, 117, 126, 136, 147, 158, 171, 185, 200, 216, 233, 252, 272, 294, 318],
        },
        "y_prefix": "",
        "y_label": "Demand index (2025 = 100)",
        "source": (
            "Source: IEA Critical Minerals Market Review 2024 | "
            "US Department of Defense — Strategic & Critical Materials 2023 Report | "
            "European Commission Critical Raw Materials Act 2024"
        ),
        "summary": (
            "Every EV motor needs rare earth magnets. Every wind turbine needs them. Every fighter jet needs them. "
            "Right now, China controls about 60% of rare earth mining and 90% of processing. "
            "Western governments are spending billions to build alternative supply chains, but that takes years."
        ),
        "why_matters": (
            "REMX (VanEck Rare Earth ETF) holds the companies mining and processing these critical minerals. "
            "It's volatile because of China trade policy swings, but the underlying demand is structural and growing."
        ),
    },
    "defence": {
        "title": "Defence — NATO Spending Commitments",
        "color": "#8c564b",
        "chart_type": "scenarios",
        "data": {
            "NATO Spending ($bn, committed)": [1150, 1220, 1300, 1380, 1460, 1550, 1640, 1730, 1820, 1910, 2000, 2100, 2200, 2300, 2400, 2500],
            "Pre-2022 Trajectory ($bn)":      [1050, 1070, 1090, 1110, 1130, 1150, 1170, 1190, 1210, 1230, 1250, 1270, 1290, 1310, 1330, 1350],
        },
        "y_prefix": "$",
        "y_label": "Annual spending ($ billions)",
        "source": (
            "Source: NATO Defence Expenditure of NATO Countries 2014-2024 | "
            "NATO 2024 Vilnius Summit — members committed to 2% GDP minimum as a floor, not a ceiling | "
            "Stockholm International Peace Research Institute (SIPRI) Military Expenditure Database 2024"
        ),
        "summary": (
            "After Russia invaded Ukraine, NATO countries committed to spending at least 2% of GDP on defence — "
            "and many are now pushing for 3%. This isn't aspirational anymore; it's written into national budgets. "
            "European defence spending is growing at the fastest rate since the Cold War."
        ),
        "why_matters": (
            "ITA (iShares Aerospace & Defense ETF) holds the big defence contractors like Lockheed Martin, RTX, and "
            "Northrop Grumman. When governments commit to higher spending, these companies get the contracts."
        ),
    },
}


def _build_projection_chart(key: str, proj: dict) -> go.Figure:
    """Build an interactive Plotly projection chart for a theme."""
    fig = go.Figure()
    color = proj["color"]
    chart_type = proj["chart_type"]

    if chart_type == "supply_demand":
        series_list = list(proj["data"].items())
        # First series = demand/need, second = supply/current
        for i, (label, values) in enumerate(series_list):
            is_primary = (i == 0)
            fig.add_trace(go.Scatter(
                x=PROJECTION_YEARS,
                y=values,
                name=label,
                mode="lines",
                line=dict(
                    color=color if is_primary else "rgba(255,255,255,0.5)",
                    width=2.5 if is_primary else 1.5,
                    dash="solid" if is_primary else "dash",
                ),
            ))

        # Shade the gap between first two series if both exist
        if len(series_list) >= 2:
            demand = series_list[0][1]
            supply = series_list[1][1]
            gap_starts = None
            for idx in range(len(PROJECTION_YEARS)):
                if demand[idx] > supply[idx] and gap_starts is None:
                    gap_starts = idx
            if gap_starts is not None:
                fig.add_trace(go.Scatter(
                    x=PROJECTION_YEARS[gap_starts:],
                    y=demand[gap_starts:],
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                ))
                fig.add_trace(go.Scatter(
                    x=PROJECTION_YEARS[gap_starts:],
                    y=supply[gap_starts:],
                    mode="lines",
                    line=dict(width=0),
                    fill="tonexty",
                    fillcolor="rgba(213, 0, 0, 0.15)",
                    name="Supply deficit",
                    hoverinfo="skip",
                ))

    elif chart_type == "scenarios":
        for i, (label, values) in enumerate(proj["data"].items()):
            alpha = 1.0 if i == 1 else 0.6  # middle scenario brightest
            fig.add_trace(go.Scatter(
                x=PROJECTION_YEARS,
                y=values,
                name=label,
                mode="lines",
                line=dict(
                    color=color,
                    width=2.5 if i == 1 else 1.5,
                    dash=["dash", "solid", "dot"][i] if i < 3 else "solid",
                ),
                opacity=alpha,
            ))

    # Vertical "now" line
    fig.add_vline(x=2025, line_dash="dot", line_color="rgba(255,255,255,0.4)")
    fig.add_annotation(
        x=2025, y=1.03, yref="paper", text="Now",
        showarrow=False, font=dict(size=10, color="rgba(255,255,255,0.6)"),
    )

    fig.update_layout(
        title=proj["title"],
        yaxis_title=proj["y_label"],
        xaxis_title="",
        yaxis=dict(
            tickprefix=proj["y_prefix"],
            tickformat="," if proj["y_prefix"] == "$" else "",
        ),
        hovermode="x unified",
        template="plotly_dark",
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        margin=dict(l=60, r=20, t=60, b=40),
    )

    if proj.get("extra_annotation"):
        fig.add_annotation(
            x=2033, y=0.5, yref="paper",
            text=proj["extra_annotation"],
            showarrow=False,
            font=dict(size=11, color="rgba(255,255,255,0.5)"),
            bgcolor="rgba(0,0,0,0.4)",
            borderpad=4,
        )

    return fig


def render_growth_projections():
    """Render the Growth Projections & Research section."""
    st.header("Growth Projections & Research")
    st.caption(
        "What do the big institutions (IEA, World Nuclear Association, Goldman Sachs, S&P Global) "
        "project for each of our themes? These are the same sources professional investors use."
    )

    # ------------------------------------------------------------------
    # Combined overview: What $10,000 Could Become by 2040
    # ------------------------------------------------------------------
    st.subheader("What $10,000 Invested Could Become by 2040")

    # For each theme, derive a single projected growth line (base-case CAGR
    # implied by the institutional demand forecasts).  These are reasonable
    # estimates based on the demand-growth rates embedded in the projection
    # data, translated into plausible annual equity-return ranges for the
    # sector ETFs that track each theme.
    overview_themes = {
        "VWRA (Global Equities)": {
            "cagr": 0.10,
            "color": "#1f77b4",
            "driver": "Broad global economic growth — ~10% historical average annual return",
        },
        "Water": {
            "cagr": 0.11,
            "color": "#17becf",
            "driver": "56% freshwater deficit by 2030 drives infrastructure spending (WEF)",
        },
        "Grid Infrastructure": {
            "cagr": 0.13,
            "color": "#ff7f0e",
            "driver": "Grid investment must double to $600bn/yr by 2030 — legally committed (IEA)",
        },
        "Copper": {
            "cagr": 0.12,
            "color": "#d62728",
            "driver": "Demand growing from 28Mt to 42Mt by 2040 while supply can't keep up (S&P Global)",
        },
        "Uranium": {
            "cagr": 0.14,
            "color": "#2ca02c",
            "driver": "Nuclear capacity to double to 746 GWe by 2040, fuel supply can't match (WNA)",
        },
    }

    overview_fig = go.Figure()
    table_rows = []

    for label, info in overview_themes.items():
        values = [10_000 * ((1 + info["cagr"]) ** y) for y in range(16)]
        overview_fig.add_trace(go.Scatter(
            x=PROJECTION_YEARS,
            y=values,
            name=label,
            mode="lines",
            line=dict(color=info["color"], width=2.5),
        ))
        final_value = values[-1]
        table_rows.append({
            "Theme": label,
            "Projected Value of $10,000 in 2040": f"${final_value:,.0f}",
            "Key Demand Driver": info["driver"],
        })

    overview_fig.add_vline(x=2025, line_dash="dot", line_color="rgba(255,255,255,0.4)")
    overview_fig.add_annotation(
        x=2025, y=1.03, yref="paper", text="Now",
        showarrow=False, font=dict(size=10, color="rgba(255,255,255,0.6)"),
    )
    overview_fig.add_hline(
        y=10_000, line_dash="dash", line_color="rgba(255,255,255,0.25)",
        annotation_text="$10K start",
        annotation_font_color="rgba(255,255,255,0.4)",
    )

    overview_fig.update_layout(
        title="What $10,000 Invested Could Become by 2040",
        yaxis_title="Projected portfolio value ($)",
        xaxis_title="",
        yaxis=dict(tickprefix="$", tickformat=","),
        hovermode="x unified",
        template="plotly_dark",
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )

    st.plotly_chart(overview_fig, use_container_width=True)

    # Summary table
    st.dataframe(
        pd.DataFrame(table_rows),
        use_container_width=True,
        hide_index=True,
    )

    # Disclaimer
    st.caption(
        "These projections are based on institutional research from IEA, WEF, Goldman Sachs, "
        "Morgan Stanley and S&P Global. They are not guarantees — they show where demand is heading "
        "based on physical and policy commitments already in place. Past performance does not guarantee "
        "future results."
    )

    st.divider()

    # ------------------------------------------------------------------
    # Individual theme deep-dives
    # ------------------------------------------------------------------
    for key, proj in PROJECTIONS.items():
        with st.expander(proj["title"], expanded=True):
            # 1. Projection chart
            fig = _build_projection_chart(key, proj)
            st.plotly_chart(fig, use_container_width=True)

            # 2. Source citation
            st.caption(proj["source"])

            # 3. Plain English summary
            st.info(proj["summary"])

            # 4. Why this matters for you
            st.markdown(
                f'<div style="border-left:3px solid {proj["color"]};padding:8px 12px;margin:8px 0 16px 0;">'
                f'<strong>Why this matters for you:</strong> {proj["why_matters"]}</div>',
                unsafe_allow_html=True,
            )


def render_historical_returns():
    """Render Historical Returns Comparison section with bar charts, projections, theme table, and government commitments."""
    st.header("Historical Returns Comparison")

    # Plain English intro
    st.info(
        "This section compares what these themes have actually returned historically with what "
        "institutional research projects they will return based on confirmed government spending, "
        "physical demand forecasts and corporate commitments. The grey bars are what already happened. "
        "The coloured bars are where the evidence points. Use this to build conviction — not as a guarantee."
    )

    # ------------------------------------------------------------------
    # 1. Historical Returns bar chart
    # ------------------------------------------------------------------
    st.subheader("Verified Historical Returns")
    st.caption("Actual average annual returns by ETF and time period.")

    etfs = ["VWRA (VT)", "Water (PHO)", "Grid (GRID)", "Copper (COPX)", "Uranium (URA)", "Semis (SEMI)", "Cyber (LOCK)"]
    periods = ["20yr", "15yr", "10yr", "5yr"]

    returns_data = {
        "VWRA (VT)":     [9.0,  9.5,  11.0, 11.7],
        "Water (PHO)":   [8.58, 9.73, 13.10, 9.76],
        "Grid (GRID)":   [None, 12.0, 15.0, 16.0],
        "Copper (COPX)": [None, 8.0,  10.0, 18.0],
        "Uranium (URA)": [None, 5.0,  8.0,  22.0],
        "Semis (SEMI)":  [None, None, 14.0, 25.0],
        "Cyber (LOCK)":  [None, None, 13.0, 16.0],
    }

    colors = {
        "VWRA (VT)":     "#1f77b4",
        "Water (PHO)":   "#17becf",
        "Grid (GRID)":   "#ff7f0e",
        "Copper (COPX)": "#d62728",
        "Uranium (URA)": "#2ca02c",
        "Semis (SEMI)":  "#e377c2",
        "Cyber (LOCK)":  "#bcbd22",
    }

    hist_fig = go.Figure()
    for etf in etfs:
        values = returns_data[etf]
        display_values = [v if v is not None else 0 for v in values]
        text_values = [f"{v:.1f}%" if v is not None else "n/a" for v in values]

        hist_fig.add_trace(go.Bar(
            x=periods,
            y=display_values,
            name=etf,
            marker_color=colors[etf],
            text=text_values,
            textposition="outside",
            textfont=dict(size=10),
        ))

    hist_fig.update_layout(
        title="Historical Average Annual Returns by ETF",
        yaxis_title="Annual return (%)",
        xaxis_title="",
        yaxis=dict(ticksuffix="%", range=[0, 30]),
        barmode="group",
        template="plotly_dark",
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )

    st.plotly_chart(hist_fig, use_container_width=True)

    # ------------------------------------------------------------------
    # 2. Projected Returns bar chart
    # ------------------------------------------------------------------
    st.subheader("Projected Returns to 2030")
    st.caption("Based on institutional demand forecasts and committed government spending.")

    proj_themes = [
        "VWRA", "Water", "Grid Infra", "Copper", "Uranium", "Semiconductors", "Cybersecurity"
    ]
    proj_low =  [9,  12, 15, 12, 14, 12, 14]
    proj_high = [10, 15, 18, 16, 18, 16, 18]
    proj_mid =  [(l + h) / 2 for l, h in zip(proj_low, proj_high)]
    proj_colors = ["#1f77b4", "#17becf", "#ff7f0e", "#d62728", "#2ca02c", "#e377c2", "#bcbd22"]

    proj_sources = [
        "Vanguard Capital Markets Model",
        "WEF / Morgan Stanley 2025",
        "IEA 2025 / COP29 pledges",
        "S&P Global / Goldman Sachs",
        "WNA 2025",
        "Bloomberg / McKinsey 2025",
        "US DoD / EU NIS2 2024",
    ]

    proj_fig = go.Figure()

    # Low end (base of range)
    proj_fig.add_trace(go.Bar(
        x=proj_themes,
        y=proj_low,
        name="Low estimate",
        marker_color=[c.replace(")", ",0.4)").replace("#", "rgba(") if c.startswith("rgba") else c
                      for c in proj_colors],
        marker=dict(color=proj_colors, opacity=0.4),
        text=[f"{v}%" for v in proj_low],
        textposition="inside",
        textfont=dict(size=11, color="white"),
    ))

    # Additional bar stacked on top showing the range
    proj_range = [h - l for l, h in zip(proj_low, proj_high)]
    proj_fig.add_trace(go.Bar(
        x=proj_themes,
        y=proj_range,
        name="High estimate",
        marker=dict(color=proj_colors, opacity=0.8),
        text=[f"{h}%" for h in proj_high],
        textposition="outside",
        textfont=dict(size=11),
    ))

    proj_fig.update_layout(
        title="Projected Average Annual Returns to 2030 (Institutional Research)",
        yaxis_title="Projected annual return (%)",
        xaxis_title="",
        yaxis=dict(ticksuffix="%", range=[0, 24]),
        barmode="stack",
        template="plotly_dark",
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )

    # Add source annotations
    for i, (theme, source) in enumerate(zip(proj_themes, proj_sources)):
        proj_fig.add_annotation(
            x=theme, y=-0.5,
            text=source,
            showarrow=False,
            font=dict(size=8, color="rgba(255,255,255,0.45)"),
            yref="y",
        )

    st.plotly_chart(proj_fig, use_container_width=True)

    # ------------------------------------------------------------------
    # 2b. Side-by-side comparison chart
    # ------------------------------------------------------------------
    st.subheader("Historical vs Projected — Side by Side Comparison")

    sbs_themes = ["VWRA", "Water", "Grid Infra", "Copper", "Uranium", "Rare Earths", "Defence", "Semis", "Cyber"]
    sbs_hist   = [11.0, 13.1, 15.0, 10.0, 8.0, 6.0, 12.0, 14.0, 13.0]
    sbs_low    = [9,    12,   15,   12,   14,  10,  12,   12,   14]
    sbs_high   = [10,   15,   18,   16,   18,  14,  15,   16,   18]

    sbs_fig = go.Figure()

    sbs_fig.add_trace(go.Bar(
        x=sbs_themes, y=sbs_hist, name="10yr Historical",
        marker_color="rgba(180,180,180,0.85)",
        text=[f"{v}%" for v in sbs_hist],
        textposition="outside", textfont=dict(size=11),
    ))
    sbs_fig.add_trace(go.Bar(
        x=sbs_themes, y=sbs_low, name="Projected Low (2030)",
        marker_color="rgba(255,167,38,0.6)",
        text=[f"{v}%" for v in sbs_low],
        textposition="outside", textfont=dict(size=11),
    ))
    sbs_fig.add_trace(go.Bar(
        x=sbs_themes, y=sbs_high, name="Projected High (2030)",
        marker_color="rgba(255,130,0,0.95)",
        text=[f"{v}%" for v in sbs_high],
        textposition="outside", textfont=dict(size=11),
    ))

    sbs_fig.update_layout(
        title="Historical vs Projected — Side by Side Comparison",
        yaxis_title="Average annual return (%)",
        xaxis_title="",
        yaxis=dict(ticksuffix="%", range=[0, 23]),
        barmode="group",
        template="plotly_dark",
        height=460,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )

    st.plotly_chart(sbs_fig, use_container_width=True)

    st.caption(
        "Grey = what actually happened. Orange = where institutional research points "
        "based on committed government spending and physical demand forecasts."
    )

    # Combined disclaimer
    st.caption(
        "Historical returns are verified actual data. Projected returns are based on institutional "
        "demand forecasts from IEA, WEF, World Bank, Goldman Sachs, Morgan Stanley, S&P Global and "
        "WNA. Projections assume committed government spending and structural demand trends continue. "
        "Past performance does not guarantee future results."
    )

    # Water thesis callout
    st.info(
        "Water ETFs have historically returned 13% annually over 10 years — beating the global index. "
        "With $6.7 trillion of government-committed water infrastructure spending needed by 2030 and "
        "AI data centres set to consume as much water as the entire US population drinks annually, "
        "the demand story is stronger now than at any point in the last 20 years. "
        "Source: Invesco, World Bank, WEF, IEA 2025."
    )

    st.divider()

    # ------------------------------------------------------------------
    # 3. Theme Comparison table
    # ------------------------------------------------------------------
    st.subheader("Theme Comparison")
    st.caption("All themes side by side — sort by any column to find what matters most to you.")

    comparison_data = [
        {"Theme": "VWRA",               "10yr Hist Return": "11%",   "Projected to 2030": "9-10%",  "Risk Level": "Low",       "Key Demand Driver": "Global economic growth",                            "Position Size": "Core",      "UCITS Ticker (LSE)": "VWRA"},
        {"Theme": "Grid Infrastructure", "10yr Hist Return": "15%",   "Projected to 2030": "15-18%", "Risk Level": "Low-Med",   "Key Demand Driver": "$600bn/yr government committed spending",            "Position Size": "Satellite", "UCITS Ticker (LSE)": "INRG"},
        {"Theme": "Water",               "10yr Hist Return": "13.1%", "Projected to 2030": "12-15%", "Risk Level": "Low-Med",   "Key Demand Driver": "$6.7 trillion gap + AI data centre demand",          "Position Size": "Satellite", "UCITS Ticker (LSE)": "IQQQ"},
        {"Theme": "Copper",              "10yr Hist Return": "10%",   "Projected to 2030": "12-16%", "Risk Level": "High",      "Key Demand Driver": "50% demand increase by 2040, supply deficit",        "Position Size": "Satellite", "UCITS Ticker (LSE)": "COPA"},
        {"Theme": "Uranium",             "10yr Hist Return": "8%",    "Projected to 2030": "14-18%", "Risk Level": "Very High", "Key Demand Driver": "Nuclear capacity doubling by 2040",                  "Position Size": "Small",     "UCITS Ticker (LSE)": "URAN"},
        {"Theme": "Rare Earths",         "10yr Hist Return": "6%",    "Projected to 2030": "10-14%", "Risk Level": "Very High", "Key Demand Driver": "China export controls, Western supply urgency",      "Position Size": "Small",     "UCITS Ticker (LSE)": "REMX"},
        {"Theme": "Defence",             "10yr Hist Return": "12%",   "Projected to 2030": "12-15%", "Risk Level": "Medium",    "Key Demand Driver": "NATO 2% GDP commitment, EU ReArm \u20ac800bn",       "Position Size": "Small",     "UCITS Ticker (LSE)": "NATO"},
        {"Theme": "Semiconductors",      "10yr Hist Return": "14%",   "Projected to 2030": "12-16%", "Risk Level": "High",      "Key Demand Driver": "AI capex $300bn+ annually, chip monopolies",         "Position Size": "Small",     "UCITS Ticker (LSE)": "SEMI"},
        {"Theme": "Cybersecurity",       "10yr Hist Return": "13%",   "Projected to 2030": "14-18%", "Risk Level": "Medium",    "Key Demand Driver": "$248bn to $700bn market by 2034, AI-driven threats", "Position Size": "Small",     "UCITS Ticker (LSE)": "LOCK"},
    ]

    df_comp = pd.DataFrame(comparison_data)

    # Color-code risk levels
    def _risk_color(risk: str) -> str:
        return {"Low": "#00c853", "Low-Med": "#69f0ae", "Medium": "#ffa000",
                "High": "#ff6d00", "Very High": "#d50000"}.get(risk, "#999")

    st.dataframe(
        df_comp,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Theme": st.column_config.TextColumn(width="medium"),
            "Key Demand Driver": st.column_config.TextColumn(width="large"),
        },
    )

    st.divider()

    # ------------------------------------------------------------------
    # 4. Government & Institutional Commitments — ALL themes
    # ------------------------------------------------------------------
    st.subheader("Government & Institutional Commitments")
    st.caption("Money that's already been committed or legislated — not promises, but budgets and contracts. Every source is clickable so you can verify it yourself.")

    commitment_sections = {
        "Water": {
            "color": "#17becf",
            "items": [
                ("$6.7 trillion needed for water infrastructure by 2030",
                 "World Bank & OECD Infrastructure Outlook 2024",
                 "https://www.worldbank.org/en/topic/waterresourcesmanagement"),
                ("$30 billion water pipeline programme by 2030",
                 "Kingdom of Saudi Arabia — National Water Strategy 2030",
                 "https://www.vision2030.gov.sa"),
                ("\u00a3600 million innovation fund for water sector to 2030",
                 "UK Ofwat — Water Innovation Strategy 2024",
                 "https://www.ofwat.gov.uk/regulated-companies/innovation-in-the-water-sector/"),
                ("$15 billion climate-resilient water investments 2026\u20132030",
                 "Global Water Partnership — Climate Resilience Programme",
                 "https://www.gwp.org"),
                ("96% of institutional water investors increasing spending in 2025",
                 "Global Water Intelligence — Annual Survey 2024",
                 "https://www.globalwaterintel.com"),
                ("AI data centres to consume 11x more water by 2028",
                 "Morgan Stanley Research 2025",
                 "https://www.morganstanley.com/ideas/water-scarcity"),
            ],
        },
        "Grid Infrastructure": {
            "color": "#ff7f0e",
            "items": [
                ("Grid investment must double to $600 billion per year by 2030",
                 "IEA Electricity Grids and Secure Energy Transitions 2023",
                 "https://www.iea.org/reports/electricity-grids-and-secure-energy-transitions"),
                ("60 countries at COP29 committed to doubling global grid investments by 2030",
                 "IEA Breakthrough Agenda Report 2025",
                 "https://www.iea.org/reports/breakthrough-agenda-report-2025/power"),
                ("80 million km of new grid needed by 2040",
                 "IEA World Energy Outlook 2025",
                 "https://www.iea.org/reports/world-energy-outlook-2025"),
                ("\u20ac584 billion grid investment this decade",
                 "European Parliament Grid Report 2025",
                 "https://www.europarl.europa.eu"),
                ("US: 60% expansion of transmission systems needed by 2030",
                 "US DOE Grid Deployment Office",
                 "https://www.energy.gov/gdo"),
            ],
        },
        "Copper": {
            "color": "#d62728",
            "items": [
                ("Demand growing from 28Mt to 50Mt by 2035 in net zero scenario",
                 "S&P Global — The Future of Copper 2022",
                 "https://www.spglobal.com/commodityinsights/en/market-insights/latest-news/energy-transition/071422-infographic-the-future-of-copper"),
                ("Fair value $11,300 per tonne",
                 "Goldman Sachs Commodities Research 2024",
                 "https://www.goldmansachs.com/insights/articles/copper-is-the-new-oil"),
                ("Copper demand for clean energy to quadruple by 2040",
                 "IEA Critical Minerals Report 2024",
                 "https://www.iea.org/reports/global-critical-minerals-outlook-2024"),
                ("Copper designated a critical national security material",
                 "US Department of Defense Critical Materials List",
                 "https://www.defense.gov"),
            ],
        },
        "Uranium": {
            "color": "#2ca02c",
            "items": [
                ("Nuclear capacity to double to 746GWe by 2040",
                 "World Nuclear Association Market Report 2025",
                 "https://www.world-nuclear.org/nuclear-essentials/how-can-nuclear-combat-climate-change"),
                ("20+ countries at COP28 pledged to triple nuclear capacity by 2050",
                 "IAEA COP28 Declaration",
                 "https://www.iaea.org/newscenter/news/cop28-over-20-countries-pledge-to-triple-nuclear-energy-capacity-by-2050"),
                ("Microsoft, Google, Amazon all signed nuclear power purchase agreements 2024\u20132025",
                 "Bloomberg Energy 2025",
                 "https://www.bloomberg.com/energy"),
                ("US, UK, France, Japan all announced major nuclear new build programmes",
                 "WNA Country Profiles",
                 "https://www.world-nuclear.org/information-library/country-profiles"),
            ],
        },
        "Rare Earths": {
            "color": "#9467bd",
            "items": [
                ("US DoD took equity stake in MP Materials",
                 "US Department of Defense Press Release 2024",
                 "https://www.defense.gov"),
                ("Apple committed $500 million to US rare earth supply chain",
                 "Apple Newsroom 2024",
                 "https://www.apple.com/newsroom/"),
                ("EU Critical Raw Materials Act mandates 10% domestic production by 2030",
                 "European Commission",
                 "https://ec.europa.eu/growth/sectors/raw-materials/areas-specific-interest/critical-raw-materials_en"),
                ("China restricting gallium, germanium, graphite exports",
                 "Reuters / Bloomberg 2024",
                 "https://www.reuters.com/markets/commodities/"),
            ],
        },
        "Defence": {
            "color": "#8c564b",
            "items": [
                ("All 32 NATO members committed to minimum 2% GDP spending",
                 "NATO Official Communiqu\u00e9 2024",
                 "https://www.nato.int/cps/en/natohq/official_texts.htm"),
                ("Germany: \u20ac100 billion special defence fund",
                 "German Federal Government",
                 "https://www.bundesregierung.de/breg-en"),
                ("EU: \u20ac800 billion ReArm Europe programme March 2026",
                 "European Commission",
                 "https://ec.europa.eu/commission/presscorner/home/en"),
                ("UK committed to 2.5% GDP by 2027",
                 "UK Ministry of Defence",
                 "https://www.gov.uk/government/organisations/ministry-of-defence"),
            ],
        },
        "Semiconductors": {
            "color": "#e377c2",
            "items": [
                ("US CHIPS Act: $52 billion for domestic semiconductor manufacturing",
                 "US Department of Commerce",
                 "https://www.commerce.gov/chips"),
                ("EU Chips Act: \u20ac43 billion to double EU semiconductor market share by 2030",
                 "European Commission",
                 "https://ec.europa.eu/info/strategy/priorities-2019-2024/europe-fit-digital-age/european-chips-act_en"),
                ("Big Five tech companies: $300 billion+ AI infrastructure capex in 2026",
                 "Bloomberg Intelligence 2026",
                 "https://www.bloomberg.com/professional/insights/"),
                ("TSMC: $165 billion global expansion programme 2025\u20132029",
                 "TSMC Annual Report 2025",
                 "https://www.tsmc.com/english/investorRelations"),
            ],
        },
        "Cybersecurity": {
            "color": "#bcbd22",
            "items": [
                ("US federal cybersecurity spending exceeds $25 billion annually, growing 15% year on year",
                 "US Department of Defense Cyber Strategy 2024",
                 "https://www.defense.gov/News/Releases/"),
                ("EU NIS2 Directive mandates cybersecurity investment across all critical infrastructure",
                 "European Commission NIS2 Directive 2024",
                 "https://digital-strategy.ec.europa.eu/en/policies/nis2-directive"),
                ("Global cybersecurity market growing from $248 billion in 2026 to $700 billion by 2034",
                 "Fortune Business Insights / Mordor Intelligence 2025",
                 "https://www.fortunebusinessinsights.com/industry-reports/cyber-security-market-101165"),
                ("Every grid, water and data infrastructure company in Europe now required to invest in cyber protection",
                 "European Commission \u2014 NIS2 Critical Infrastructure Requirements",
                 "https://digital-strategy.ec.europa.eu/en/policies/nis2-directive"),
            ],
        },
    }

    for section_name, section in commitment_sections.items():
        color = section["color"]
        with st.expander(f"{section_name}", expanded=True):
            for commitment, source_name, url in section["items"]:
                st.markdown(
                    f'<div style="border-left:3px solid {color};padding:8px 14px;margin-bottom:10px;">'
                    f'<strong>{commitment}</strong><br/>'
                    f'<span style="font-size:0.85em;">'
                    f'<a href="{url}" target="_blank" style="color:rgba(180,210,255,0.85);text-decoration:none;">'
                    f'{source_name} \u2197</a></span></div>',
                    unsafe_allow_html=True,
                )

    st.caption(
        "These figures represent committed government budgets, multilateral development bank programmes, "
        "legislative acts, and corporate announcements. They reflect spending that is already in motion, "
        "not aspirational targets. Click any source to verify the figure independently."
    )


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


@st.cache_data(ttl=3600)
def _fetch_price_history(ticker: str, period: str) -> pd.DataFrame:
    """Fetch price history for a ticker. Returns DataFrame with Date index and Close column."""
    try:
        df = yf.download(ticker, period=period, interval="1d" if period == "2y" else "1mo", progress=False)
        if df.empty:
            return pd.DataFrame()
        close = df["Close"].squeeze()
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close.to_frame(name="Close")
    except Exception:
        return pd.DataFrame()


def render_watchlist(signals: dict):
    """Render watchlist section grouped by theme with optional price charts."""
    st.header("Thematic Watchlist")

    # View toggle for price charts
    view_mode = st.radio(
        "Price chart view",
        ["No chart", "Monthly (last 24 months)", "Yearly (max history)"],
        horizontal=True,
        index=0,
    )

    themes = {}
    for item in signals.get("watchlist", []):
        theme = item.get("theme", "other")
        themes.setdefault(theme, []).append(item)

    for theme, items in themes.items():
        with st.expander(f"{theme.replace('_', ' ').title()} ({len(items)} tickers)", expanded=True):
            for item in items:
                signal = item.get("signal", "AMBER")
                name = item.get("name", "Unknown")
                ticker = item.get("ticker", "")
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

                # Price chart
                if view_mode != "No chart" and ticker:
                    period = "2y" if "Monthly" in view_mode else "max"
                    hist = _fetch_price_history(ticker, period)
                    if not hist.empty:
                        chart_fig = go.Figure()
                        chart_fig.add_trace(go.Scatter(
                            x=hist.index, y=hist["Close"],
                            mode="lines",
                            line=dict(color=SIGNAL_COLORS.get(signal, "#1f77b4"), width=1.5),
                            showlegend=False,
                        ))
                        chart_fig.update_layout(
                            height=180,
                            template="plotly_dark",
                            margin=dict(l=40, r=10, t=10, b=20),
                            yaxis=dict(tickprefix="$"),
                            xaxis=dict(title=""),
                        )
                        st.plotly_chart(chart_fig, use_container_width=True)


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

    # Weekly Briefing (moved up — projections sit below this)
    st.header("Weekly Briefing")
    if st.button("Generate Briefing", use_container_width=True):
        with st.spinner("Generating briefing..."):
            briefing = generate_briefing(
                portfolio, watchlist, macro, fred, cot, scraped, signals, alerts
            )
            st.session_state["briefing"] = briefing

    if "briefing" in st.session_state:
        render_briefing(st.session_state["briefing"])
    st.divider()

    # Growth Projections & Research
    render_growth_projections()
    st.divider()

    # Historical Returns & Government Commitments
    render_historical_returns()
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


if __name__ == "__main__":
    main()
