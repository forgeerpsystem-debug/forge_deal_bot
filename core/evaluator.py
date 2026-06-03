import os
import requests
import json
from dotenv import load_dotenv
from supabase import create_client, Client
from serpapi import GoogleSearch
from openai import OpenAI

# Load environment variables
load_dotenv()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

llm_client = OpenAI(
    base_url="http://127.0.0.1:18789/v1",
    api_key=***
)

def research_historical_value(make, model):
    print(f"🔎 Researching Market Value for: {make} {model}...")
    SERPAPI_KEY = ***"SERPAPI_KEY")
    if not SERPAPI_KEY:
        print("❌ MISSING SERPAPI KEY!")
        return None

    query = f"{make} {model} used equipment for sale price"
    params = {
      "engine": "google",
      "q": query,
      "hl": "en",
      "gl": "us",
      "api_key": SERPAPI_KEY
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if "error" in results:
            print(f"⚠️ SerpApi Error: {results['error']}")
            return None
            
        organic_results = results.get("organic_results", [])
        snippets = [res.get("snippet", "") + " " + res.get("title", "") for res in organic_results]
        raw_text = "\n".join(snippets)
        
        if not raw_text.strip():
            return None

        prompt = f"""
        You are an expert heavy machinery appraiser. 
        I am going to give you raw search snippets for a used: {make} {model}.
        
        Your job is to read the snippets, ignore random numbers (like $150 shipping, or parts), 
        and determine the AVERAGE fair market retail value for this specific machine.
        
        Snippets:
        {raw_text}
        
        Respond ONLY with a single integer representing the average price in USD. No symbols, no commas, no text. Just the number. If you cannot determine it confidently, respond with 0.
        """
        
        response = llm_client.chat.completions.create(
            model="openclaw",
            messages=[{"role": "user", "content": prompt}]
        )
        
        val_str = response.choices[0].message.content.strip()
        estimated_value = int(''.join(filter(str.isdigit, val_str)))
        
        if estimated_value > 1000:
            return estimated_value
        return None
                
    except Exception as e:
        print(f"⚠️ Evaluator LLM Error for {make} {model}: {e}")
        return None

def auto_generate_baselines():
    print("🧠 Booting Evaluator Brain: AI analyzing market baselines...")
    listings = supabase.table("equipment_listings").select("make, model").execute().data
    baselines = supabase.table("market_baselines").select("make, model").execute().data
    
    known_models = {f"{b['make']} {b['model']}" for b in baselines}
    unique_active_models = {f"{l['make']} {l['model']}": l for l in listings}
    
    new_baselines_added = 0

    for model_key, item in unique_active_models.items():
        if model_key not in known_models and item['make'] != "Unknown":
            estimated_value = research_historical_value(item['make'], item['model'])
            
            if estimated_value:
                supabase.table("market_baselines").insert({
                    "make": item['make'],
                    "model": item['model'],
                    "fair_market_value": estimated_value,
                    "source": "AI-Researched"
                }).execute()
                print(f"✅ AI determined baseline: {item['make']} {item['model']} is worth ~${estimated_value:,}")
                new_baselines_added += 1
            else:
                print(f"⏭️ AI lacked confident data for {item['make']} {item['model']}. Skipping.")

    return new_baselines_added

def evaluate_deals_and_alert(target_ratio=0.70):
    """Checks for deals where the current bid is <= target_ratio of the retail value."""
    print(f"🚨 Scanning radar for deals at or below {int(target_ratio*100)}% of retail value...")
    
    listings = supabase.table("equipment_listings").select("*").eq("status", "Active").execute().data
    baselines = supabase.table("market_baselines").select("*").execute().data
    
    baseline_dict = {f"{b['make']} {b['model']}": b['fair_market_value'] for b in baselines}
    
    alerts_sent = 0

    for item in listings:
        model_key = f"{item['make']} {item['model']}"
        retail_value = baseline_dict.get(model_key)
        
        # Only evaluate if we have a baseline and the current bid is more than $0
        # (A $0 bid technically triggers the 70% rule, but is usually an un-opened auction)
        if retail_value and retail_value > 0 and item['current_bid'] > 0:
            target_max_bid = retail_value * target_ratio
            
            if item['current_bid'] <= target_max_bid:
                margin = retail_value - item['current_bid']
                discount_percent = 100 - ((item['current_bid'] / retail_value) * 100)
                
                existing_alert = supabase.table("alert_logs").select("id").eq("listing_id", item['id']).execute().data
                if not existing_alert:
                    message = {
                        "embeds": [{
                            "title": f"🚨 {int(discount_percent)}% OFF RETAIL: {item['year'] or ''} {item['make']} {item['model']}",
                            "url": item['listing_url'],
                            "color": 5763719,
                            "fields": [
                                {"name": "Current Bid", "value": f"${item['current_bid']:,}", "inline": True},
                                {"name": "Est. Retail Value", "value": f"${retail_value:,}", "inline": True},
                                {"name": "🔥 Potential Margin", "value": f"**${margin:,}**", "inline": False},
                                {"name": "Auction Site", "value": item['auction_site'], "inline": True},
                                {"name": "Closing Date", "value": item.get('closing_date', 'Unknown'), "inline": True}
                            ],
                            "footer": {"text": "Forge Deal Evaluator Bot (AI Powered)"}
                        }]
                    }
                    
                    requests.post(DISCORD_WEBHOOK, json=message)
                    print(f"🎯 Alert Fired: {item['make']} {item['model']} ({int(discount_percent)}% below retail)")
                    
                    supabase.table("alert_logs").insert({"listing_id": item['id'], "alert_type": "Percentage Discount"}).execute()
                    alerts_sent += 1

    print(f"🏁 Evaluation complete. {alerts_sent} new alerts fired to Discord.")

if __name__ == "__main__":
    auto_generate_baselines()
    evaluate_deals_and_alert(target_ratio=0.70)
