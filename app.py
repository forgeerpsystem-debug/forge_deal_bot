import os
import streamlit as st
import pandas as pd
from core.database import supabase
from main import run_deal_bot 

@st.cache_resource
def install_playwright():
    os.system("python -m playwright install chromium")

install_playwright()

st.set_page_config(page_title="Forge Deal Radar", page_icon="🏗️", layout="wide")
st.title("🏗️ Forge Deal Bot: Command Center (AI Enhanced)")

tab1, tab2 = st.tabs(["📡 Live Radar", "⚙️ Manual Override"])

with tab1:
    st.markdown("Monitoring major auction sites for undervalued heavy equipment. Market values generated via local OpenClaw LLM analysis.")
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
        
        # Calculate discount percentage for sorting/filtering
        df['discount_percent'] = 0.0
        mask = (df['fair_market_value'].notnull()) & (df['fair_market_value'] > 0)
        df.loc[mask, 'discount_percent'] = 100 - ((df.loc[mask, 'current_bid'] / df.loc[mask, 'fair_market_value']) * 100)
        
        if 'closing_date' not in df.columns:
            df['closing_date'] = "Unknown"
            
        display_cols = ['auction_site', 'make', 'model', 'year', 'closing_date', 'current_bid', 'fair_market_value', 'discount_percent', 'potential_margin', 'status', 'listing_url']
        existing_cols = [col for col in display_cols if col in df.columns]
        df = df[existing_cols]
        
        # Sort by best discount percentage
        df = df.sort_values(by='discount_percent', ascending=False)
        
        st.dataframe(
            df,
            column_config={
                "auction_site": "Auction Site",
                "make": "Make",
                "model": "Model",
                "year": st.column_config.NumberColumn("Year", format="%d"),
                "closing_date": "Closing Date",
                "current_bid": st.column_config.NumberColumn("Current Bid", format="$%d"),
                "fair_market_value": st.column_config.NumberColumn("Est. Retail (AI)", format="$%d"),
                "discount_percent": st.column_config.NumberColumn("Discount %", format="%d%%"),
                "potential_margin": st.column_config.NumberColumn("Est. Margin", format="$%d"),
                "status": "Status",
                "listing_url": st.column_config.LinkColumn("Auction Link")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No equipment listings found in the database yet. The radar is quiet.")


with tab2:
    st.header("Manual Data Hunt")
    st.markdown("Force the bot to search specific sites and keywords right now.")
    
    available_sites = ["Purple Wave", "Ritchie Bros", "MachineryTrader", "Ironbound Auctions"]
    target_sites = st.multiselect("Select Target Auction Sites", available_sites, default=available_sites)
    
    target_keywords = st.text_input("Target Keywords (comma separated)", value="skid steer, trencher, ditchwitch, genie, scissor lift, mini excavator")
    
    if st.button("🚀 Launch Manual Hunt"):
        if not target_sites:
            st.error("⚠️ Please select at least one auction site!")
        else:
            keywords_list = [kw.strip() for kw in target_keywords.split(",") if kw.strip()]
            with st.spinner(f"Hunting {', '.join(target_sites)} for {', '.join(keywords_list)}..."):
                run_deal_bot(keywords_list, target_sites)
                
            st.success("✅ Manual hunt complete! Switch to the Live Radar tab to see the new data.")
