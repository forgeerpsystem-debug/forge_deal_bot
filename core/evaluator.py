import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from serpapi import GoogleSearch
from openai import OpenAI

from core.database import supabase  # single shared client — no duplicate init

load_dotenv()

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

llm_client = OpenAI(
    base_url="http://127.0.0.1:18789/v1",
    api_key="local"
)


def check_llm_health() -> bool:
    """Quick ping to confirm the local LLM is reachable before a full run."""
    try:
        llm_client.chat.completions.create(
            model="openclaw",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            timeout=5,
        )
        return True
    except Exception:
        print("⚠️ Local LLM (OpenClaw) is offline — baseline research will be skipped this run.")
        return False


def research_historical_value(make: str, model: str) -> int | None:
    print(f"🔎 Researching market value: {make} {model}...")
    serpapi_key = os.getenv("SERPAPI_KEY")
    if not serpapi_key:
        print("❌ Missing SERPAPI_KEY")
        return None

    try:
        results = GoogleSearch({
            "engine": "google",
            "q": f"{make} {model} used equipment for sale price",
            "hl": "en",
            "gl": "us",
            "api_key": serpapi_key,
        }).get_dict()

        if "error" in results:
            print(f"⚠️ SerpApi: {results['error']}")
            return None

        organic = results.get("organic_results", [])
        raw_text = "\n".join(r.get("snippet", "") + " " + r.get("title", "") for r in organic)
        if not raw_text.strip():
            return None

        response = llm_client.chat.completions.create(
            model="openclaw",
            messages=[{
                "role": "user",
                "content": (
                    f"You are an expert heavy machinery appraiser. "
                    f"Read these search snippets for a used {make} {model} and determine the "
                    f"average fair market retail value. Ignore shipping costs, parts prices, and "
                    f"unrelated numbers. Respond with a single integer USD price only — "
                    f"no symbols, no commas, no text. If you cannot determine it confidently, respond with 0.\n\n"
                    f"Snippets:\n{raw_text}"
                ),
            }],
        )

        val_str = response.choices[0].message.content.strip()
        estimated = int(''.join(filter(str.isdigit, val_str)) or "0")
        return estimated if estimated > 1000 else None

    except Exception as e:
        print(f"⚠️ Research error for {make} {model}: {e}")
        return None


def auto_generate_baselines() -> int:
    if not check_llm_health():
        return 0

    print("🧠 Evaluator Brain: researching missing market baselines...")

    listings = supabase.table("equipment_listings").select("make, model").execute().data
    baselines = supabase.table("market_baselines").select("make, model").execute().data

    known = {f"{b['make']} {b['model']}" for b in baselines}
    # Deduplicate by make+model key, filter out unknowns
    candidates = {
        f"{l['make']} {l['model']}": l
        for l in listings
        if l["make"] != "Unknown" and f"{l['make']} {l['model']}" not in known
    }

    if not candidates:
        print("✅ All models already have baselines.")
        return 0

    new_baselines = 0

    # Research up to 5 models concurrently to respect SerpApi rate limits
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(research_historical_value, item["make"], item["model"]): item
            for item in candidates.values()
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                value = future.result()
            except Exception as e:
                print(f"⚠️ Baseline research failed: {e}")
                continue

            if value:
                try:
                    supabase.table("market_baselines").insert({
                        "make": item["make"],
                        "model": item["model"],
                        "fair_market_value": value,
                        "source": "AI-Researched",
                    }).execute()
                    print(f"✅ Baseline: {item['make']} {item['model']} → ~${value:,}")
                    new_baselines += 1
                except Exception as e:
                    print(f"⚠️ Failed to save baseline for {item['make']} {item['model']}: {e}")
            else:
                print(f"⏭️ No confident data for {item['make']} {item['model']}. Skipping.")

    return new_baselines


def evaluate_deals_and_alert(target_ratio: float = 0.70):
    print(f"🚨 Scanning for deals at or below {int(target_ratio * 100)}% of retail value...")

    listings = supabase.table("equipment_listings").select("*").eq("status", "Active").execute().data
    baselines = supabase.table("market_baselines").select("*").execute().data

    # Pre-fetch all alerted IDs once — eliminates N+1 queries inside the loop
    alerted_ids: set = {
        row["listing_id"]
        for row in supabase.table("alert_logs").select("listing_id").execute().data
    }

    baseline_dict = {f"{b['make']} {b['model']}": b["fair_market_value"] for b in baselines}

    alerts_sent = 0
    new_alert_rows = []

    for item in listings:
        model_key = f"{item['make']} {item['model']}"
        retail_value = baseline_dict.get(model_key)

        if not retail_value or retail_value <= 0 or item["current_bid"] <= 0:
            continue
        if item["id"] in alerted_ids:
            continue

        target_max = retail_value * target_ratio
        if item["current_bid"] > target_max:
            continue

        margin = retail_value - item["current_bid"]
        discount_pct = 100 - (item["current_bid"] / retail_value * 100)

        message = {
            "embeds": [{
                "title": f"🚨 {int(discount_pct)}% OFF RETAIL: {item.get('year') or ''} {item['make']} {item['model']}".strip(),
                "url": item["listing_url"],
                "color": 5763719,
                "fields": [
                    {"name": "Current Bid",       "value": f"${item['current_bid']:,}",  "inline": True},
                    {"name": "Est. Retail Value", "value": f"${retail_value:,}",          "inline": True},
                    {"name": "🔥 Potential Margin","value": f"**${margin:,}**",           "inline": False},
                    {"name": "Auction Site",      "value": item["auction_site"],          "inline": True},
                    {"name": "Closing Date",      "value": item.get("closing_date", "Unknown"), "inline": True},
                ],
                "footer": {"text": "Forge Deal Evaluator Bot (AI Powered)"},
            }]
        }

        try:
            requests.post(DISCORD_WEBHOOK, json=message, timeout=10)
            print(f"🎯 Alert: {item['make']} {item['model']} — {int(discount_pct)}% below retail")
        except Exception as e:
            print(f"⚠️ Discord webhook failed: {e}")

        alerted_ids.add(item["id"])
        new_alert_rows.append({"listing_id": item["id"], "alert_type": "Percentage Discount"})
        alerts_sent += 1

    # Batch-insert all new alert log rows
    if new_alert_rows:
        try:
            supabase.table("alert_logs").insert(new_alert_rows).execute()
        except Exception as e:
            print(f"⚠️ Failed to log alerts: {e}")

    print(f"🏁 Evaluation complete. {alerts_sent} new alerts fired to Discord.")


if __name__ == "__main__":
    auto_generate_baselines()
    evaluate_deals_and_alert(target_ratio=0.70)
