"""
Web scraper for data not available via APIs.
- Uranium spot prices
- Sprott SPUT NAV/premium data
- Baltic Dry Index
- Congressional stock trades
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from utils.cache import cached_fetch


def _scrape_uranium_spot() -> dict:
    """Scrape uranium spot price from public sources."""
    try:
        url = "https://www.cameco.com/invest/markets/uranium-price"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; InvestmentDashboard/1.0)"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        price_text = soup.find(string=lambda t: t and "$" in t and "/lb" in t if t else False)

        if price_text:
            price_str = price_text.strip().replace("$", "").replace("/lb", "").replace(",", "").split()[0]
            price = float(price_str)
            return {
                "name": "Uranium Spot Price",
                "value": price,
                "unit": "$/lb U3O8",
                "source": "cameco.com",
                "last_updated": datetime.now().isoformat(),
            }
        return {"name": "Uranium Spot Price", "error": "Could not parse price"}
    except Exception as e:
        return {"name": "Uranium Spot Price", "error": str(e)}


def _scrape_baltic_dry_index() -> dict:
    """Scrape Baltic Dry Index."""
    try:
        url = "https://tradingeconomics.com/commodity/baltic"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; InvestmentDashboard/1.0)"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        price_elem = soup.find("div", {"id": "p"}) or soup.find("span", {"id": "p"})

        if price_elem:
            value = float(price_elem.text.strip().replace(",", ""))
            return {
                "name": "Baltic Dry Index",
                "value": value,
                "source": "tradingeconomics.com",
                "last_updated": datetime.now().isoformat(),
            }
        return {"name": "Baltic Dry Index", "error": "Could not parse value"}
    except Exception as e:
        return {"name": "Baltic Dry Index", "error": str(e)}


def _scrape_congressional_trades() -> list[dict]:
    """Scrape recent congressional stock trades from public sources."""
    try:
        url = "https://www.capitoltrades.com/trades?pageSize=20"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; InvestmentDashboard/1.0)"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        trades = []

        rows = soup.find_all("tr")
        for row in rows[:20]:
            cells = row.find_all("td")
            if len(cells) >= 4:
                trades.append({
                    "politician": cells[0].get_text(strip=True),
                    "ticker": cells[1].get_text(strip=True),
                    "type": cells[2].get_text(strip=True),
                    "amount": cells[3].get_text(strip=True),
                })

        return trades if trades else [{"note": "No recent trades parsed"}]
    except Exception as e:
        return [{"error": str(e)}]


def fetch_scraped_data() -> dict:
    """Fetch all scraped data sources."""
    def _fetch():
        return {
            "uranium_spot": _scrape_uranium_spot(),
            "baltic_dry_index": _scrape_baltic_dry_index(),
            "congressional_trades": _scrape_congressional_trades(),
            "last_updated": datetime.now().isoformat(),
        }

    return cached_fetch("scraped_data", _fetch)
