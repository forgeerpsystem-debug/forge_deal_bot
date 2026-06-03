import sys
import os

# Ensure Python can find our folders
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.bs4_purplewave import scrape_purplewave
from scrapers.playwright_ritchie import scrape_ritchie_bros
from scrapers.machinery_trader import scrape_machinery_trader
from scrapers.ironbound_auctions import scrape_ironbound

from core.evaluator import auto_generate_baselines, evaluate_deals_and_alert

def run_deal_bot(
    keywords=["skid steer", "trencher", "ditchwitch", "genie", "scissor lift", "mini excavator"], 
    target_sites=["Purple Wave", "Ritchie Bros", "MachineryTrader", "Ironbound Auctions"]
):
    """The master pipeline: Dispatches Scrapers, Evaluates, and Alerts."""
    print(f"\n🤖 Booting Forge Deal Bot...")
    print(f"🎯 Targets: {keywords}")
    print(f"🌐 Sites: {target_sites}")
    
    # 1. Scrape New Deals (The Dispatcher)
    for site in target_sites:
        for kw in keywords:
            if site == "Purple Wave":
                scrape_purplewave(kw)
            elif site == "Ritchie Bros":
                scrape_ritchie_bros(kw)
            elif site == "MachineryTrader":
                scrape_machinery_trader(kw)
            elif site == "Ironbound Auctions":
                scrape_ironbound(kw)

    # 2. Research Missing Baselines via local AI & SerpApi
    auto_generate_baselines()
    
    # 3. Evaluate Margins and Fire Discord Alerts (Alerts if bid <= 70% of retail value)
    evaluate_deals_and_alert(target_ratio=0.70)
    
    print("💤 Bot run complete. Going back to sleep.\n")

if __name__ == "__main__":
    # Runs the bot with all default keywords and sites
    run_deal_bot()
