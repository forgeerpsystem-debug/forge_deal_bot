import sys
import os

# Ensure Python can find our folders
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.bs4_purplewave import scrape_purplewave
# IMPORT FUTURE SCRAPERS HERE:
# from scrapers.ritchie_bros import scrape_ritchie_bros
# from scrapers.machinery_trader import scrape_machinery_trader

from core.evaluator import auto_generate_baselines, evaluate_deals_and_alert

def run_deal_bot(keywords=["skid steer", "excavator"], target_sites=["Purple Wave"]):
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
                print(f"⚠️ [Placeholder] Ritchie Bros scraper not yet built. Skipping {kw}.")
                # scrape_ritchie_bros(kw)
                
            elif site == "MachineryTrader":
                print(f"⚠️ [Placeholder] MachineryTrader scraper not yet built. Skipping {kw}.")
                # scrape_machinery_trader(kw)

    # 2. Research Missing Baselines via SerpApi
    auto_generate_baselines()
    
    # 3. Evaluate Margins and Fire Discord Alerts
    evaluate_deals_and_alert(target_margin=15000)
    
    print("💤 Bot run complete. Going back to sleep.\n")

if __name__ == "__main__":
    # If run on autopilot (Cron Job), it will default to these settings
    run_deal_bot(keywords=["skid steer", "excavator"], target_sites=["Purple Wave"])