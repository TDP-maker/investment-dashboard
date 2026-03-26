"""
Briefing generator.
Produces weekly AI briefings via Claude API with template fallback.
"""

import json
from datetime import datetime
from config import ANTHROPIC_API_KEY, BRIEFING_SYSTEM_PROMPT, BRIEFING_USER_PROMPT_TEMPLATE


def _format_data_section(data, indent: int = 2) -> str:
    """Format data for inclusion in the briefing prompt."""
    if isinstance(data, (list, dict)):
        return json.dumps(data, indent=indent, default=str)
    return str(data)


def _generate_template_briefing(signals: dict, alerts: list) -> str:
    """Generate a template-based briefing when Claude API is unavailable."""
    lines = []
    lines.append(f"# Weekly Investment Briefing")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}")
    lines.append(f"**Mode:** Template (Claude API unavailable)")
    lines.append("")

    # Portfolio
    lines.append("## Portfolio Positions")
    for item in signals.get("portfolio", []):
        signal = item.get("signal", "AMBER")
        name = item.get("name", item.get("ticker", "Unknown"))
        price = item.get("current_price", "N/A")
        daily = item.get("daily_change_pct", 0)
        weekly = item.get("weekly_change_pct", 0)
        lines.append(f"- **{signal}** | {name}: ${price} (day: {daily:+.1f}%, week: {weekly:+.1f}%)")

    lines.append("")

    # Watchlist by theme
    lines.append("## Watchlist")
    themes = {}
    for item in signals.get("watchlist", []):
        theme = item.get("theme", "other")
        themes.setdefault(theme, []).append(item)

    for theme, items in themes.items():
        lines.append(f"### {theme.replace('_', ' ').title()}")
        for item in items:
            signal = item.get("signal", "AMBER")
            name = item.get("name", item.get("ticker", "Unknown"))
            price = item.get("current_price", "N/A")
            weekly = item.get("weekly_change_pct", 0)
            lines.append(f"- **{signal}** | {name}: ${price} (week: {weekly:+.1f}%)")

    lines.append("")

    # Macro
    lines.append("## Macro Indicators")
    for item in signals.get("macro", []):
        signal = item.get("signal", "AMBER")
        name = item.get("name", item.get("ticker", "Unknown"))
        value = item.get("current_price", "N/A")
        lines.append(f"- **{signal}** | {name}: {value}")

    # FRED
    for item in signals.get("fred", []):
        signal = item.get("signal", "AMBER")
        name = item.get("name", item.get("series_id", "Unknown"))
        value = item.get("current_value", "N/A")
        lines.append(f"- **{signal}** | {name}: {value}")

    lines.append("")

    # Alerts
    if alerts:
        lines.append("## Active Alerts")
        for alert in alerts:
            lines.append(f"- **{alert.get('severity', 'HIGH')}** | {alert.get('signal', 'Alert triggered')} "
                        f"(current: {alert.get('current_value', 'N/A')}, "
                        f"threshold: {alert.get('condition', 'N/A')})")
    else:
        lines.append("## Active Alerts")
        lines.append("- No alerts triggered this period.")

    lines.append("")
    lines.append("---")
    lines.append("*Template briefing — enable Claude API for AI-powered analysis.*")

    return "\n".join(lines)


def generate_briefing(
    portfolio_data: list,
    watchlist_data: list,
    macro_data: list,
    fred_data: list,
    cot_data: dict,
    scraped_data: dict,
    signals: dict,
    alerts: list,
) -> str:
    """Generate the weekly briefing using Claude API or template fallback."""

    # Try Claude API first
    if ANTHROPIC_API_KEY:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

            user_prompt = BRIEFING_USER_PROMPT_TEMPLATE.format(
                portfolio_data=_format_data_section(portfolio_data),
                watchlist_data=_format_data_section(watchlist_data),
                macro_data=_format_data_section(macro_data),
                fred_data=_format_data_section(fred_data),
                cot_data=_format_data_section(cot_data),
                scraped_data=_format_data_section(scraped_data),
                alerts_data=_format_data_section(alerts),
            )

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=BRIEFING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            return message.content[0].text

        except Exception as e:
            print(f"Claude API error, falling back to template: {e}")

    # Template fallback
    return _generate_template_briefing(signals, alerts)
