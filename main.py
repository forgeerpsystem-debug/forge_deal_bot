import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.bs4_purplewave import scrape_purplewave
from scrapers.playwright_ritchie import scrape_ritchie_bros
from scrapers.machinery_trader import scrape_machinery_trader
from scrapers.ironbound_auctions import scrape_ironbound
from core.evaluator import auto_generate_baselines, evaluate_deals_and_alert
from core.database import cleanup_stale_listings

SCRAPER_MAP = {
    "Purple Wave":       scrape_purplewave,
    "Ritchie Bros":      scrape_ritchie_bros,
    "MachineryTrader":   scrape_machinery_trader,
    "Ironbound Auctions": scrape_ironbound,
}


async def _scrape_all(keywords: list[str], target_sites: list[str]):
    """Run all requested scrapers concurrently — one browser per site."""
    tasks = {
        site: asyncio.create_task(SCRAPER_MAP[site](keywords))
        for site in target_sites
        if site in SCRAPER_MAP
    }

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    for site, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            print(f"⚠️ {site} scraper failed: {result}")
        elif isinstance(result, set):
            cleanup_stale_listings(site, result)


def run_deal_bot(
    keywords: list[str] | None = None,
    target_sites: list[str] | None = None,
):
    """Master pipeline: scrape concurrently → baseline AI research → evaluate & alert."""
    if keywords is None:
        keywords = ["skid steer", "trencher", "ditchwitch", "genie", "scissor lift", "mini excavator"]
    if target_sites is None:
        target_sites = list(SCRAPER_MAP.keys())

    print(f"\n🤖 Booting Forge Deal Bot...")
    print(f"🎯 Keywords : {keywords}")
    print(f"🌐 Sites    : {target_sites}")

    # 1. Scrape all sites in parallel
    asyncio.run(_scrape_all(keywords, target_sites))

    # 2. Fill missing market baselines via SerpApi + local LLM (parallel threads)
    auto_generate_baselines()

    # 3. Evaluate margins and fire Discord alerts
    evaluate_deals_and_alert(target_ratio=0.70)

    print("💤 Bot run complete.\n")


if __name__ == "__main__":
    run_deal_bot()
