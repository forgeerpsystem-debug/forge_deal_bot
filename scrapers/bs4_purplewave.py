from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import sys
import os

# Connect to the core database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.database import insert_equipment_listing

def clean_price(price_str):
    """Strips currency symbols and commas to return a clean integer."""
    if not price_str:
        return 0
    clean_str = re.sub(r'[^\d]', '', str(price_str))
    return int(clean_str) if clean_str else 0

def scrape_purplewave(keyword="skid steer"):
    print(f"🚜 Initiating Playwright Data Hunt for: '{keyword}'...")
    search_term = keyword.replace(" ", "+")
    url = f"https://www.purplewave.com/search/{search_term}"

    success_count = 0

    # 1. Fire up the hidden Playwright browser
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Spoof a real Mac computer so we don't look like a bot
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        print("⏳ Waiting for Purple Wave JavaScript to render listings...")
        try:
            # wait_until="networkidle" tells the bot to wait until all the JS loading finishes
            page.goto(url, wait_until="networkidle", timeout=20000)
            html = page.content()
        except Exception as e:
            print(f"⚠️ Page load timed out or failed: {e}")
            browser.close()
            return
            
        browser.close()

    # 2. Parse the fully-rendered HTML
    soup = BeautifulSoup(html, 'html.parser')

    # Aggressive Hunt: Find ALL links on the page that contain '/item/' (Purple Wave's listing structure)
    listing_links = soup.find_all("a", href=re.compile(r'/item/'))
    
    # We use a set to prevent scraping the exact same machine twice if it has multiple links (like an image link + text link)
    processed_urls = set()

    if not listing_links:
        print("⚠️ Still no listings found. Check the URL structure manually in a browser.")
        return

    for link in listing_links:
        try:
            href = link.get('href')
            if not href.startswith("http"):
                href = "https://www.purplewave.com" + href
                
            if href in processed_urls:
                continue
            processed_urls.add(href)

            # Look up the HTML tree to find the "box" containing this listing
            container = link.find_parent("div")
            for _ in range(4): # Move up a few levels to grab the whole card
                if container and container.parent:
                    container = container.parent
            
            if not container:
                continue

            # 3. Extract the Title (Usually the biggest text in the box)
            title_element = container.find(["h2", "h3"]) 
            raw_title = title_element.get_text(strip=True) if title_element else link.get_text(strip=True)
            
            if not raw_title or len(raw_title) < 5:
                continue

            # Parse Make, Model, Year
            parts = raw_title.split(" ", 2)
            year = int(parts[0]) if parts[0].isdigit() else None
            make = parts[1] if len(parts) > 1 else "Unknown"
            model = parts[2] if len(parts) > 2 else "Unknown"

            # 4. Extract the Bid (Hunt for the $ sign in the container text)
            bid_element = container.find(string=re.compile(r'\$'))
            current_bid = clean_price(bid_element) if bid_element else 0

            deal_data = {
                "auction_site": "Purple Wave",
                "listing_url": href,
                "make": make,
                "model": model,
                "year": year,
                "current_bid": current_bid,
                "status": "Active"
            }

            # 5. Inject into Supabase
            if insert_equipment_listing(deal_data):
                success_count += 1

        except Exception as e:
            continue

    print(f"🏁 Scraping complete. {success_count} new listings sent to the Forge Database.")

if __name__ == "__main__":
    scrape_purplewave("skid steer")
    scrape_purplewave("excavator")