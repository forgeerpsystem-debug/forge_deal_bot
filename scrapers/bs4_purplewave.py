from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import insert_equipment_listing
from scrapers.utils import parse_title, clean_price

SITE = "Purple Wave"
BASE_URL = "https://www.purplewave.com"


async def scrape_purplewave(keywords: list[str], max_pages: int = 3) -> set[str]:
    print(f"🚜 {SITE}: Hunting {keywords} across up to {max_pages} pages...")
    all_deals: list[dict] = []
    found_urls: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        for keyword in keywords:
            search_term = keyword.replace(" ", "+")

            for page_num in range(1, max_pages + 1):
                url = f"{BASE_URL}/search/{search_term}?page={page_num}"
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_selector("a[href*='/item/']", timeout=8000)
                    html = await page.content()
                except Exception as e:
                    print(f"⚠️ {SITE} p{page_num} '{keyword}': {e}")
                    break

                soup = BeautifulSoup(html, 'html.parser')
                links = soup.find_all("a", href=re.compile(r'/item/'))
                if not links:
                    break

                page_new = 0
                for link in links:
                    href = link.get('href', '')
                    if not href.startswith("http"):
                        href = BASE_URL + href
                    if href in found_urls:
                        continue
                    found_urls.add(href)
                    page_new += 1

                    try:
                        container = link.find_parent("div")
                        for _ in range(4):
                            if container and container.parent:
                                container = container.parent
                        if not container:
                            continue

                        title_elem = container.find(["h2", "h3"])
                        raw_title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)
                        if not raw_title or len(raw_title) < 5:
                            continue

                        year, make, model = parse_title(raw_title)

                        bid_elem = container.find(string=re.compile(r'\$'))
                        current_bid = clean_price(bid_elem) if bid_elem else 0

                        closing_date = "Unknown"
                        date_elem = container.find(string=re.compile(r'(?i)(closes|ends)'))
                        if date_elem:
                            closing_date = date_elem.strip()

                        all_deals.append({
                            "auction_site": SITE,
                            "listing_url": href,
                            "make": make,
                            "model": model,
                            "year": year,
                            "current_bid": current_bid,
                            "closing_date": closing_date,
                            "status": "Active",
                        })
                    except Exception:
                        continue

                if page_new == 0:
                    break

        await browser.close()

    success = sum(1 for d in all_deals if insert_equipment_listing(d))
    print(f"🏁 {SITE} complete. {success} listings upserted.")
    return found_urls
