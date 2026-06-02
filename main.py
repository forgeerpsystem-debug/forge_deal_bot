import sys
import os

# Ensure Python can find our folders
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.bs4_purplewave import scrape_purplewave
from core.evaluator import auto_generate_baselines, evaluate_deals_and_alert

def run_deal_bot(keywords=["skid steer", "excavator"]):
    """The master pipeline: Scrapes, Evaluates, and Alerts."""
    print(f"\n🤖 Booting Forge Deal Bot for targets: {keywords}...")
    
    # 1. Scrape New Deals
    for kw in keywords:
        scrape_purplewave(kw)
        
    # 2. Research Missing Baselines via SerpApi
    auto_generate_baselines()
    
    # 3. Evaluate Margins and Fire Discord Alerts (targeting $15k+ margin)
    evaluate_deals_and_alert(target_margin=15000)
    
    print("💤 Bot run complete. Going back to sleep.\n")

if __name__ == "__main__":
    # This runs if the cloud Cron Job triggers the script automatically
    run_deal_bot()