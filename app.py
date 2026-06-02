import streamlit as st
import pandas as pd
from core.database import supabase
from main import run_deal_bot # Import our new master pipeline

# Configure the page layout
st.set_page_config(page_title="Forge Deal Radar", page_icon="🏗️", layout="wide")

st.title("🏗️ Forge Deal Bot: Command Center")

# Create navigation tabs
tab1, tab2 = st.tabs(["📡 Live Radar", "⚙️ Manual Override"])

# --- TAB 1: THE LIVE RADAR ---
with tab1:
    st.markdown("Monitoring major auction sites for undervalued heavy equipment.")
    st.divider()

    @st.cache_data(ttl=10)
    def load_data():
        listings = supabase.table("equipment_listings").select("*").execute().data
        baselines = supabase.table("market_baselines").select("make, model, fair_market_value").execute().data
        return listings, baselines

    raw_listings, raw_baselines = load_data()

    if raw_listings:
        df = pd.DataFrame(raw_listings)
        
        if raw_baselines:
            baselines_df = pd.DataFrame(raw_baselines)
            df = df.merge(baselines_df, on=['make', 'model'], how='left')
        else:
            df['fair_market_value'] = None
            
        df['potential_margin'] = df['fair_market_value'] - df['current_bid']
        
        # Format for display
        display_cols = ['auction_site', 'make', 'model', 'year', 'current_bid', 'fair_market_value', 'potential_margin', 'status', 'listing_url']
        existing_cols = [col for col in display_cols if col in df.columns]
        df = df[existing_cols]
        
        # Sort by margin so the best deals are at the top!
        df = df.sort_values(by='potential_margin', ascending=False)
        
        st.dataframe(
            df,
            column_config={
                "auction_site": "Auction Site",
                "make": "Make",
                "model": "Model",
                "year": st.column_config.NumberColumn("Year", format="%d"),
                "current_bid": st.column_config.NumberColumn("Current Bid", format="$%d"),
                "fair_market_value": st.column_config.NumberColumn("Retail Value", format="$%d"),
                "potential_margin": st.column_config.NumberColumn("Est. Margin", format="$%d"),
                "status": "Status",
                "listing_url": st.column_config.LinkColumn("Auction Link")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No equipment listings found in the database yet. The radar is quiet.")


# --- TAB 2: MANUAL OVERRIDE ---
with tab2:
    st.header("Manual Data Hunt")
    st.markdown("Force the bot to search the internet for specific equipment right now.")
    
    # Input field for keywords
    target_keywords = st.text_input("Target Keywords (comma separated)", value="skid steer, backhoe, dozer")
    
    if st.button("🚀 Launch Manual Hunt"):
        # Clean up the inputted keywords into a list
        keywords_list = [kw.strip() for kw in target_keywords.split(",") if kw.strip()]
        
        # st.spinner shows a loading wheel on the UI while Python does the heavy lifting
        with st.spinner(f"Hunting for {', '.join(keywords_list)}... (This will take a minute)"):
            run_deal_bot(keywords_list)
            
        st.success("✅ Manual hunt complete! Switch to the Live Radar tab to see the new data.")