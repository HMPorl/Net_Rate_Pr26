# Page 2: Custom Rates - Individual Item Pricing (Optimized with data_editor)
import streamlit as st
import pandas as pd

# Import shared utilities
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
st.markdown("Set individual prices for specific equipment items. **Edit the 'Special Rate' column directly.**")

# Show current settings
col1, col2, col3 = st.columns(3)
with col1:
    st.info(f"**Customer:** {customer_name or 'Not set'}")
with col2:
    st.info(f"**Global Discount:** {global_discount}%")
with col3:
    # Count custom prices from session state
    custom_count = sum(1 for idx in df.index if st.session_state.get(f"price_{idx}", "").strip())
    st.info(f"**Custom Prices:** {custom_count}")

st.markdown("---")

# Initialize custom_prices in session state if not exists
if 'custom_prices_df' not in st.session_state:
    st.session_state.custom_prices_df = None

# Build editable dataframe
def build_editable_df():
    """Build the editable dataframe with current prices"""
    rows = []
    for idx, row in df.iterrows():
        # Get saved custom price from session state
        saved_price = st.session_state.get(f"price_{idx}", "")
        
        # Calculate discounted price based on group discount
        discount_key = f"{row['GroupName']}_{row['Sub Section']}_discount"
        group_discount = st.session_state.get(discount_key, global_discount)
        
        if is_poa_value(row["HireRateWeekly"]):
            original_display = "POA"
            calculated_price = "POA"
        else:
            try:
                original = float(row["HireRateWeekly"])
                original_display = f"£{original:.2f}"
                calculated_price = f"£{original * (1 - group_discount/100):.2f}"
            except:
                original_display = "POA"
                calculated_price = "POA"
        
        # Calculate discount % for saved special rates
        special_discount = ""
        if saved_price and str(saved_price).strip():
            price_str = str(saved_price).strip()
            if is_poa_value(price_str):
                special_discount = "POA"
            else:
                try:
                    special_val = float(price_str)
                    discount_pct = calculate_discount_percent(row["HireRateWeekly"], special_val)
                    if discount_pct != "POA":
                        special_discount = f"{discount_pct:.1f}%"
                    else:
                        special_discount = "POA"
                except:
                    special_discount = "-"
        
        rows.append({
            "_idx": idx,  # Hidden index for tracking
            "Group": row["GroupName"],
            "Category": row["ItemCategory"],
            "Sub Category": row["Sub Section"],
            "Equipment": row["EquipmentName"],
            "List Rate": original_display,
            "Calculated": calculated_price,
            "Special Rate": saved_price,  # Editable column
            "Discount %": special_discount,  # Shows discount for saved special rates
        })
    
    return pd.DataFrame(rows)

# Filters
st.markdown("### 🔍 Filter Items")
col_filter1, col_filter2, col_filter3 = st.columns(3)

with col_filter1:
    groups = ["All Groups"] + sorted(df["GroupName"].unique().tolist())
    selected_group = st.selectbox("Group", groups, key="filter_group")

with col_filter2:
    if selected_group != "All Groups":
        categories = ["All Categories"] + sorted(df[df["GroupName"] == selected_group]["ItemCategory"].unique().tolist())
    else:
        categories = ["All Categories"] + sorted(df["ItemCategory"].unique().tolist())
    selected_category = st.selectbox("Category", categories, key="filter_category")

with col_filter3:
    search_term = st.text_input("🔎 Search Equipment", key="search_equipment", placeholder="Type to search...")

# Build and filter the dataframe
edit_df = build_editable_df()

# Apply filters
if selected_group != "All Groups":
    edit_df = edit_df[edit_df["Group"] == selected_group]
if selected_category != "All Categories":
    edit_df = edit_df[edit_df["Category"] == selected_category]
if search_term:
    edit_df = edit_df[edit_df["Equipment"].str.contains(search_term, case=False, na=False)]

st.markdown(f"**Showing {len(edit_df)} of {len(df)} items**")

st.markdown("---")

# Data editor - fast, efficient editing
st.markdown("### ✏️ Edit Special Rates")
st.caption("Click on any cell in the 'Special Rate' column to enter a custom price. Leave blank to use the calculated price.")

# Configure column settings
column_config = {
    "_idx": None,  # Hide the index column
    "Group": st.column_config.TextColumn("Group", disabled=True, width="small"),
    "Category": st.column_config.TextColumn("Category", disabled=True, width="small"),
    "Sub Category": st.column_config.TextColumn("Sub Category", disabled=True, width="small"),
    "Equipment": st.column_config.TextColumn("Equipment", disabled=True, width="medium"),
    "List Rate": st.column_config.TextColumn("List Rate £", disabled=True, width="small"),
    "Calculated": st.column_config.TextColumn("With Global Discount", disabled=True, width="small"),
    "Special Rate": st.column_config.TextColumn(
        "Special Rate",
        width="small",
        help="Enter custom price (e.g., 45.00) or POA. Leave blank for calculated price."
    ),
    "Discount %": st.column_config.TextColumn("Discount %", disabled=True, width="small"),
}

# Show the editable data (height for ~30 visible rows)
edited_df = st.data_editor(
    edit_df,
    column_config=column_config,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    height=735,  # ~20 rows visible (35px per row + header)
    key="price_editor"
)

# Show live preview of unsaved edits with calculated discounts
unsaved_changes = []
for i in range(len(edit_df)):
    orig_special = str(edit_df.iloc[i]["Special Rate"]) if pd.notna(edit_df.iloc[i]["Special Rate"]) else ""
    edit_special = str(edited_df.iloc[i]["Special Rate"]) if pd.notna(edited_df.iloc[i]["Special Rate"]) else ""
    
    if edit_special.strip() and edit_special != orig_special:
        # Calculate discount for this unsaved edit
        idx = edited_df.iloc[i]["_idx"]
        original_row = df.loc[idx]
        
        if is_poa_value(edit_special):
            calc_discount = "POA"
        else:
            try:
                special_val = float(edit_special)
                discount_pct = calculate_discount_percent(original_row["HireRateWeekly"], special_val)
                calc_discount = f"{discount_pct:.1f}%" if discount_pct != "POA" else "POA"
            except:
                calc_discount = "Invalid"
        
        unsaved_changes.append({
            "Equipment": edited_df.iloc[i]["Equipment"],
            "New Special Rate": f"£{edit_special}" if not is_poa_value(edit_special) else "POA",
            "Discount %": calc_discount
        })

if unsaved_changes:
    st.markdown("#### ⏳ Unsaved Changes Preview")
    st.dataframe(pd.DataFrame(unsaved_changes), use_container_width=True, hide_index=True)

# Save changes button
st.markdown("---")

col_save, col_clear, col_spacer = st.columns([2, 2, 6])

with col_save:
    if st.button("💾 Save All Changes", type="primary", use_container_width=True):
        # Save edited values back to session state
        saved_count = 0
        for _, row in edited_df.iterrows():
            idx = row["_idx"]
            new_price = str(row["Special Rate"]).strip() if pd.notna(row["Special Rate"]) else ""
            old_price = st.session_state.get(f"price_{idx}", "")
            
            if new_price != old_price:
                st.session_state[f"price_{idx}"] = new_price
                saved_count += 1
        
        if saved_count > 0:
            st.success(f"✅ Saved {saved_count} price change(s)")
            st.rerun()
        else:
            st.info("No changes to save")

with col_clear:
    if st.button("🗑️ Clear All Custom Prices", use_container_width=True):
        cleared = 0
        for idx in df.index:
            if st.session_state.get(f"price_{idx}", ""):
                st.session_state[f"price_{idx}"] = ""
                cleared += 1
        if cleared > 0:
            st.success(f"✅ Cleared {cleared} custom price(s)")
            st.rerun()
        else:
            st.info("No custom prices to clear")

# Summary of custom prices
st.markdown("---")
st.markdown("### 📋 Custom Prices Summary")

# Build summary of non-empty custom prices
summary_rows = []
for idx, row in df.iterrows():
    custom_price = st.session_state.get(f"price_{idx}", "").strip()
    if custom_price:
        if is_poa_value(custom_price):
            discount_display = "POA"
            price_display = "POA"
        else:
            try:
                price_val = float(custom_price)
                price_display = f"£{price_val:.2f}"
                discount_pct = calculate_discount_percent(row["HireRateWeekly"], price_val)
                discount_display = f"{discount_pct:.2f}%" if discount_pct != "POA" else "POA"
            except:
                price_display = custom_price
                discount_display = "Invalid"
        
        summary_rows.append({
            "Group": row["GroupName"],
            "Category": row["ItemCategory"],
            "Equipment": row["EquipmentName"],
            "Original": format_price_display(row["HireRateWeekly"]),
            "Special Rate": price_display,
            "Discount %": discount_display
        })

if summary_rows:
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
else:
    st.info("No custom prices set. Edit the 'Special Rate' column above to add custom prices.")

# Update the main dataframe with custom prices for export
for idx, row in df.iterrows():
    custom_price = st.session_state.get(f"price_{idx}", "").strip()
    
    if custom_price:
        if is_poa_value(custom_price):
            df.at[idx, "CustomPrice"] = "POA"
            df.at[idx, "DiscountPercent"] = "POA"
        else:
            try:
                price_val = float(custom_price)
                df.at[idx, "CustomPrice"] = price_val
                df.at[idx, "DiscountPercent"] = calculate_discount_percent(row["HireRateWeekly"], price_val)
            except:
                df.at[idx, "CustomPrice"] = "POA"
                df.at[idx, "DiscountPercent"] = "POA"
    else:
        # Use calculated price
        discount_key = f"{row['GroupName']}_{row['Sub Section']}_discount"
        group_discount = st.session_state.get(discount_key, global_discount)
        discounted = get_discounted_price(row, group_discount)
        df.at[idx, "CustomPrice"] = discounted
        df.at[idx, "DiscountPercent"] = calculate_discount_percent(row["HireRateWeekly"], discounted)

# Save updated df back to session state
st.session_state['df'] = df

# Navigation hint
st.markdown("---")
st.info("👉 **Next:** Go to **Export** page to download Excel, PDF, or email the price list.")
