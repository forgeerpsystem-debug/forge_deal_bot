import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in .env file")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def insert_equipment_listing(listing_data: dict):
    """Upserts a listing. If listing_url already exists, updates current_bid and other fields."""
    try:
        return supabase.table("equipment_listings").upsert(
            listing_data,
            on_conflict="listing_url"
        ).execute()
    except Exception as e:
        print(f"⚠️ DB insert error: {e}")
        return None


def cleanup_stale_listings(site: str, active_urls: set[str]):
    """Mark Active listings for a site that weren't seen in the latest scrape as Closed."""
    if not active_urls:
        return
    try:
        current = (
            supabase.table("equipment_listings")
            .select("id, listing_url")
            .eq("auction_site", site)
            .eq("status", "Active")
            .execute()
            .data
        )
        stale_ids = [row["id"] for row in current if row["listing_url"] not in active_urls]
        if stale_ids:
            supabase.table("equipment_listings").update({"status": "Closed"}).in_("id", stale_ids).execute()
            print(f"🧹 Marked {len(stale_ids)} stale {site} listings as Closed.")
    except Exception as e:
        print(f"⚠️ Cleanup error for {site}: {e}")
