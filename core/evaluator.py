import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client
import re

# Load environment variables
load_dotenv()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

def clean_price(price_str):
    """Converts price strings to clean integers."""
    if not price_str: return 0
    clean_str = re.sub(r'[^\d]', '', str(price_str))
    return int(clean_str) if clean_str else 0

import os
import re
from serpapi import GoogleSearch

def research_historical_value(make, model):
    """
    Uses SerpApi to legally bypass Google firewalls, CAPTCHAs, and regional blocks.
    Returns clean, US-based pricing data in JSON format.
    """
    print(f"🔎 Asking SerpApi to find market value for: {make} {model}...")
    
    SERPAPI_KEY = os.getenv("SERPAPI_KEY")
    if not SERPAPI_KEY:
        print("❌ MISSING SERPAPI KEY: Please add SERPAPI_KEY to your .env file!")
        return None

    query = f"{make} {model} used equipment for sale price"
    
    # We tell SerpApi exactly what we want: Google US, English language
    params = {
      "engine": "google",
      "q": query,
      "hl": "en",
      "gl": "us",
      "api_key": SERPAPI_KEY
    }

    historical_prices = []

    try:
        # Fire the request to SerpApi's enterprise servers
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if "error" in results:
            print(f"⚠️ SerpApi Error: {results['error']}")
            return None
            
        # Extract the text snippets from the top Google results
        organic_results = results.get("organic_results", [])
        raw_text = ""
        for result in organic_results:
            raw_text += result.get("snippet", "") + " "
            raw_text += result.get("title", "") + " "
            
        # Hunt for dollar amounts in the clean text
        prices = re.findall(r'\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?', raw_text)
        
        for p_str in prices:
            price = clean_price(p_str)
            # Filter out junk (like $100 replacement manuals)
            if 5000 < price < 500000:
                historical_prices.append(price)
                
    except Exception as e:
        print(f"⚠️ SerpApi connection error for {make} {model}: {e}")
        return None

    # Calculate the Estimate Retail Value
    if len(historical_prices) > 0:
        historical_prices.sort()
        
        # Drop the outliers (highest and lowest) so a single crazy price doesn't ruin the average
        if len(historical_prices) > 4:
            historical_prices = historical_prices[2:-2] 
        elif len(historical_prices) > 2:
            historical_prices = historical_prices[1:-1]
            
        avg_value = sum(historical_prices) / len(historical_prices)
        return int(avg_value)
    else:
        print(f"❌ SerpApi bypassed the firewall, but the snippets didn't contain enough price tags.")
        return None

def auto_generate_baselines():
    """Finds machines without a retail value, researches them, and updates the database."""
    print("🧠 Booting Evaluator Brain: Checking for missing market baselines...")
    
    # Get all active listings
    listings = supabase.table("equipment_listings").select("make, model").execute().data
    # Get all known baselines
    baselines = supabase.table("market_baselines").select("make, model").execute().data
    
    known_models = {f"{b['make']} {b['model']}" for b in baselines}
    unique_active_models = {f"{l['make']} {l['model']}": l for l in listings}
    
    new_baselines_added = 0

    for model_key, item in unique_active_models.items():
        if model_key not in known_models and item['make'] != "Unknown":
            # 1. We found a machine we don't know the value of. Let's research it.
            estimated_value = research_historical_value(item['make'], item['model'])
            
            if estimated_value:
                # 2. Save it to the database
                supabase.table("market_baselines").insert({
                    "make": item['make'],
                    "model": item['model'],
                    "fair_market_value": estimated_value,
                    "source": "Auto-Researched"
                }).execute()
                print(f"✅ Learned new baseline: {item['make']} {item['model']} is worth ~${estimated_value:,}")
                new_baselines_added += 1
            else:
                print(f"⏭️ Could not confidently determine value for {item['make']} {item['model']}. Skipping.")

    return new_baselines_added

def evaluate_deals_and_alert(target_margin=15000):
    """Checks for massive margins and fires Discord Webhooks."""
    print("🚨 Scanning radar for high-margin deals...")
    
    listings = supabase.table("equipment_listings").select("*").eq("status", "Active").execute().data
    baselines = supabase.table("market_baselines").select("*").execute().data
    
    # Create a quick dictionary lookup for retail values
    baseline_dict = {f"{b['make']} {b['model']}": b['fair_market_value'] for b in baselines}
    
    alerts_sent = 0

    for item in listings:
        model_key = f"{item['make']} {item['model']}"
        retail_value = baseline_dict.get(model_key)
        
        if retail_value:
            margin = retail_value - item['current_bid']
            
            # If the margin is higher than our target (e.g., $15k profit), FIRE THE ALARM!
            if margin >= target_margin:
                
                # Check if we already alerted about this specific listing to prevent spam
                existing_alert = supabase.table("alert_logs").select("id").eq("listing_id", item['id']).execute().data
                if not existing_alert:
                    
                    # 1. Format a beautiful Discord card
                    message = {
                        "embeds": [{
                            "title": f"🚨 HIGH MARGIN DEAL: {item['year'] or ''} {item['make']} {item['model']}",
                            "url": item['listing_url'],
                            "color": 5763719, # Green color
                            "fields": [
                                {"name": "Current Bid", "value": f"${item['current_bid']:,}", "inline": True},
                                {"name": "Est. Retail Value", "value": f"${retail_value:,}", "inline": True},
                                {"name": "🔥 Potential Margin", "value": f"**${margin:,}**", "inline": False},
                                {"name": "Auction Site", "value": item['auction_site'], "inline": True}
                            ],
                            "footer": {"text": "Forge Deal Evaluator Bot"}
                        }]
                    }
                    
                    # 2. Send to Discord
                    requests.post(DISCORD_WEBHOOK, json=message)
                    print(f"🎯 Alert Fired: {item['make']} {item['model']} (${margin:,} margin)")
                    
                    # 3. Log it so we don't spam it again
                    supabase.table("alert_logs").insert({"listing_id": item['id'], "alert_type": "High Margin"}).execute()
                    alerts_sent += 1

    print(f"🏁 Evaluation complete. {alerts_sent} new alerts fired to Discord.")

if __name__ == "__main__":
    auto_generate_baselines()
    evaluate_deals_and_alert(target_margin=15000)