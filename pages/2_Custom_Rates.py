# Page 2: Custom Rates - Individual Item Pricing
import streamlit as st
import pandas as pd
import os

# Import shared utilities
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    initialize_session_state, ensure_dataframe_loaded,
    is_poa_value, get_numeric_price, format_price_display,
    get_discounted_price, calculate_discount_percent
)

# Initialize session state
initialize_session_state()

# Check authentication
if not st.session_state.get("authenticated", False):
    st.warning("🔐 Please log in from the main page first.")
    st.stop()

# Ensure data is loaded
if not ensure_dataframe_loaded():
    st.error("❌ Failed to load equipment data. Please check the Excel file.")
    st.stop()

df = st.session_state['df']
global_discount = st.session_state.get('global_discount', 0.0)
customer_name = st.session_state.get('customer_name', '')

st.title("🎯 Custom Rates")
st.markdown("Set individual prices for specific equipment items.")

# Show current settings
col1, col2, col3 = st.columns(3)
with col1:
    st.info(f"**Customer:** {customer_name or 'Not set'}")
with col2:
    st.info(f"**Global Discount:** {global_discount}%")
with col3:
    custom_count = sum(1 for idx, _ in df.iterrows() if st.session_state.get(f"price_{idx}", "").strip())
    st.info(f"**Custom Prices:** {custom_count}")

st.markdown("---")

# Initialize pending prices
if 'pending_prices' not in st.session_state:
    st.session_state.pending_prices = {}

# Initialize price keys
for idx, row in df.iterrows():
    price_key = f"price_{idx}"
    if price_key not in st.session_state:
        st.session_state[price_key] = ""

# Controls
col_expand, col_collapse, col_legend = st.columns([2, 2, 6])

with col_expand:
    if st.button("🔓 Expand All", use_container_width=True):
        st.session_state.keep_expanded = True
        st.rerun()

with col_collapse:
    if st.button("🔒 Collapse All", use_container_width=True):
        st.session_state.keep_expanded = False
        st.rerun()

with col_legend:
    st.markdown("**Legend:** 🎯 = Custom Price | 📊 = Calculated | ✏️ = Pending | ⚠️ = Over Max")

keep_expanded = st.session_state.get('keep_expanded', False)

# Define the pricing fragment - only this section reruns on input changes
@st.fragment
def pricing_fragment():
    def count_pending_changes():
        count = 0
        for key, pending_val in st.session_state.pending_prices.items():
            saved_val = st.session_state.get(key, "")
            if pending_val != saved_val:
                count += 1
        return count
    
    grouped_df = df.groupby(["GroupName", "Sub Section"])
    
    for (group, subsection), group_df in grouped_df:
        # Check for custom prices in group
        has_custom_in_group = any(
            st.session_state.pending_prices.get(f"price_{idx}", st.session_state.get(f"price_{idx}", "")).strip() 
            for idx in group_df.index
        )
        
        has_pending_in_group = any(
            st.session_state.pending_prices.get(f"price_{idx}", "") != st.session_state.get(f"price_{idx}", "")
            for idx in group_df.index
            if f"price_{idx}" in st.session_state.pending_prices
        )
        
        header_text = f"{group} - {subsection}"
        if has_pending_in_group:
            header_text += " ✏️"
        elif has_custom_in_group:
            header_text += " 🎯"
        
        should_expand = keep_expanded or has_custom_in_group
        
        with st.expander(header_text, expanded=should_expand):
            for idx, row in group_df.iterrows():
                price_key = f"price_{idx}"
                saved_value = st.session_state.get(price_key, "")
                
                # Get discounted price
                discount_key = f"{row['GroupName']}_{row['Sub Section']}_discount"
                group_discount = st.session_state.get(discount_key, global_discount)
                discounted_price = get_discounted_price(row, global_discount)
                
                col1, col2, col3, col4, col5 = st.columns([2, 3, 1.5, 1.5, 1.5])
                
                with col1:
                    st.markdown(f"**{row['ItemCategory']}**")
                
                with col2:
                    st.markdown(row["EquipmentName"])
                
                with col3:
                    if is_poa_value(row["HireRateWeekly"]):
                        st.markdown("**POA**")
                    else:
                        st.markdown(f"**{format_price_display(row['HireRateWeekly'])}**")
                
                with col4:
                    current_value = st.session_state.pending_prices.get(price_key, saved_value)
                    
                    if is_poa_value(row["HireRateWeekly"]):
                        placeholder_text = "POA - Enter custom or leave"
                        help_text = "Item is POA - enter specific price"
                    else:
                        placeholder_text = "Enter Special Rate or POA"
                        help_text = "Leave empty for calculated price"
                    
                    new_value = st.text_input(
                        "", 
                        value=current_value,
                        key=f"input_{idx}", 
                        label_visibility="collapsed", 
                        placeholder=placeholder_text, 
                        help=help_text
                    )
                    
                    if new_value != saved_value:
                        st.session_state.pending_prices[price_key] = new_value
                    elif price_key in st.session_state.pending_prices:
                        del st.session_state.pending_prices[price_key]
                
                with col5:
                    preview_value = st.session_state.pending_prices.get(price_key, saved_value)
                    user_input = preview_value.strip() if preview_value else ""
                    
                    is_pending = price_key in st.session_state.pending_prices and st.session_state.pending_prices[price_key] != saved_value
                    pending_indicator = " ✏️" if is_pending else ""
                    
                    if user_input:
                        if is_poa_value(user_input):
                            st.markdown(f"**POA** 🎯{pending_indicator}")
                        else:
                            try:
                                custom_price = float(user_input)
                                discount_percent = calculate_discount_percent(row["HireRateWeekly"], custom_price)
                                
                                if discount_percent == "POA":
                                    st.markdown(f"**POA** 🎯{pending_indicator}")
                                else:
                                    orig_numeric = get_numeric_price(row["HireRateWeekly"])
                                    if orig_numeric and discount_percent > row["Max Discount"]:
                                        st.markdown(f"**{discount_percent:.2f}%** 🎯⚠️{pending_indicator}")
                                    else:
                                        st.markdown(f"**{discount_percent:.2f}%** 🎯{pending_indicator}")
                            except ValueError:
                                st.markdown(f"**POA** 🎯⚠️{pending_indicator}")
                    else:
                        custom_price = discounted_price
                        discount_percent = calculate_discount_percent(row["HireRateWeekly"], custom_price)
                        
                        if discount_percent == "POA":
                            st.markdown("**POA** 📊")
                        else:
                            st.markdown(f"**{discount_percent:.2f}%** 📊")
                    
                    # Store final values for export (use SAVED values)
                    saved_input = saved_value.strip() if saved_value else ""
                    if saved_input:
                        if is_poa_value(saved_input):
                            df.at[idx, "CustomPrice"] = "POA"
                            df.at[idx, "DiscountPercent"] = "POA"
                        else:
                            try:
                                df.at[idx, "CustomPrice"] = float(saved_input)
                                df.at[idx, "DiscountPercent"] = calculate_discount_percent(row["HireRateWeekly"], float(saved_input))
                            except ValueError:
                                df.at[idx, "CustomPrice"] = "POA"
                                df.at[idx, "DiscountPercent"] = "POA"
                    else:
                        df.at[idx, "CustomPrice"] = discounted_price
                        df.at[idx, "DiscountPercent"] = calculate_discount_percent(row["HireRateWeekly"], discounted_price)
    
    # Apply/Discard buttons
    st.markdown("---")
    pending_count = count_pending_changes()
    apply_disabled = pending_count == 0
    
    col_apply, col_discard, col_spacer = st.columns([2, 2, 6])
    
    with col_apply:
        if st.button(f"✅ Apply Changes ({pending_count})", type="primary", disabled=apply_disabled, use_container_width=True):
            applied = 0
            for key, value in st.session_state.pending_prices.items():
                if st.session_state.get(key, "") != value:
                    st.session_state[key] = value
                    applied += 1
            st.session_state.pending_prices = {}
            st.success(f"✅ Applied {applied} price change(s)")
            st.rerun()
    
    with col_discard:
        if st.button("🗑️ Discard", disabled=apply_disabled, use_container_width=True):
            st.session_state.pending_prices = {}
            st.info("Changes discarded")
            st.rerun()

# Run the pricing fragment
pricing_fragment()

# Update session state DataFrame
st.session_state['df'] = df

st.markdown("---")

# -------------------------------
# Summary Tables
# -------------------------------
st.markdown("### 📋 Manually Entered Custom Prices")

manual_entries = []
for idx, row in df.iterrows():
    price_key = f"price_{idx}"
    user_input = st.session_state.get(price_key, "").strip()
    
    if user_input:
        if is_poa_value(user_input):
            manual_entries.append({
                "Category": row["ItemCategory"],
                "Equipment": row["EquipmentName"],
                "Original": format_price_display(row["HireRateWeekly"]),
                "Custom Price": "POA",
                "Discount %": "POA"
            })
        else:
            try:
                entered_price = float(user_input)
                discount_pct = calculate_discount_percent(row['HireRateWeekly'], entered_price)
                manual_entries.append({
                    "Category": row["ItemCategory"],
                    "Equipment": row["EquipmentName"],
                    "Original": format_price_display(row["HireRateWeekly"]),
                    "Custom Price": f"£{entered_price:.2f}",
                    "Discount %": f"{discount_pct:.2f}%" if discount_pct != "POA" else "POA"
                })
            except ValueError:
                manual_entries.append({
                    "Category": row["ItemCategory"],
                    "Equipment": row["EquipmentName"],
                    "Original": format_price_display(row["HireRateWeekly"]),
                    "Custom Price": "POA (Invalid)",
                    "Discount %": "POA"
                })

if manual_entries:
    st.dataframe(pd.DataFrame(manual_entries), use_container_width=True)
else:
    st.info("No custom prices have been entered yet.")

# Navigation hint
st.markdown("---")
st.info("👉 **Next:** Go to **Export** page to download Excel, PDF, or email the price list.")
