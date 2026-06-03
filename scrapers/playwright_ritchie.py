from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import insert_equipment_listing

def clean_price(price_str):
    if not price_str:
        return 0
    clean_str = re.sub(r'[^\d]', '', str(price_str))
    return int(clean_str) if clean_str else 0

def scrape_ritchie_bros(keyword="skid steer"):
    print(f"🚜 Initiating Ritchie Bros Hunt for: '{keyword}'...")
    search_term = keyword.replace(" ", "+")
    url = f"https://www.rbauction.com/search?keywords={search_term}"

    success_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        print("⏳ Waiting for Ritchie Bros to load...")
        try:
            page.goto(url, wait_until="networkidle", timeout=25000)
            html = page.content()
        except Exception as e:
            print(f"⚠️ Page load timed out or failed: {e}")
            browser.close()
            return
            
        browser.close()

    soup = BeautifulSoup(html, 'html.parser')
    
    # Broadly match Ritchie Bros equipment links
    listing_links = soup.find_all("a", href=re.compile(r'/(equipment|heavy-equipment|construction)/'))
    processed_urls = set()

    if not listing_links:
        print("⚠️ No Ritchie Bros listings found. The site layout may require deeper inspection.")
        return

    for link in listing_links:
        try:
            href = link.get('href')
            if not href.startswith("http"):
                href = "https://www.rbauction.com" + href
                
            if href in processed_urls:
                continue
            processed_urls.add(href)

            container = link.find_parent("div")
            for _ in range(4):
                if container and container.parent:
                    container = container.parent
            if not container:
                continue

            raw_title = link.get_text(strip=True)
            if not raw_title or len(raw_title) < 5:
                title_elem = container.find(["h3", "h4", "a"])
                raw_title = title_elem.get_text(strip=True) if title_elem else ""
                
            if not raw_title:
                continue

            parts = raw_title.split(" ", 2)
            year = int(parts[0]) if parts[0].isdigit() else None
            make = parts[1] if len(parts) > 1 else "Unknown"
            model = parts[2] if len(parts) > 2 else "Unknown"

            bid_element = container.find(string=re.compile(r'\$'))
            current_bid = clean_price(bid_element) if bid_element else 0
            
            closing_date = "Unknown"
            date_element = container.find(string=re.compile(r'(?i)(closes|ends|auction date|bidding opens)'))
            if date_element:
                closing_date = date_element.strip()

            deal_data = {
                "auction_site": "Ritchie Bros",
                "listing_url": href,
                "make": make,
                "model": model,
                "year": year,
                "current_bid": current_bid,
                "closing_date": closing_date,
                "status": "Active"
            }

            if insert_equipment_listing(deal_data):
                success_count += 1

        except Exception as e:
            continue

    print(f"🏁 Ritchie Bros scraping complete. {success_count} new listings sent to the Forge Database.")

if __name__ == "__main__":
    scrape_ritchie_bros("skid steer")
