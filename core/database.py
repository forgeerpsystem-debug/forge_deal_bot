import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from the .env file
load_dotenv()

# Securely fetch credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in .env file")

# Initialize the database client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def insert_equipment_listing(listing_data: dict):
    """
    Upserts a scraped piece of equipment into the database.
    If the listing_url is new, it inserts a new row.
    If the listing_url already exists, it updates the current_bid automatically.
    """
    try:
        # The 'upsert' command looks for a conflict on the listing_url column.
        # If it finds one, it overwrites the old data (like current_bid) with the new data.
        response = supabase.table("equipment_listings").upsert(
            listing_data, 
            on_conflict="listing_url"
        ).execute()
        
        return response
    except Exception as e:
        print(f"⚠️ Database Error: {e}")
        return None