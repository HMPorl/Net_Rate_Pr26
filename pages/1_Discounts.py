# Page 1: Discounts - Customer Setup & Discount Configuration
import streamlit as st
import pandas as pd
import os
import io
import json

# Import shared utilities (Streamlit runs from project root)
from utils import (
    initialize_session_state, ensure_dataframe_loaded, get_available_pdf_files,
    TRANSPORT_TYPES, DEFAULT_TRANSPORT_CHARGES, SCRIPT_DIR, get_uk_time,
    create_save_data, apply_loaded_data
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

st.title("⚙️ Discounts & Setup")
st.markdown("Configure customer details, global discount, and group-level discounts.")

# -------------------------------
# Customer Information Section
# -------------------------------
st.markdown("### 👤 Customer Information")

col1, col2 = st.columns([2, 1])

with col1:
    customer_name = st.text_input(
        "⭐ Customer Name", 
        key="customer_name",
        help="Required for all exports"
    )
    
    bespoke_email = st.text_input(
        "Bespoke Email Address (optional)", 
        key="bespoke_email"
    )

with col2:
    # PDF Header Selection
    available_pdfs = get_available_pdf_files()
    header_pdf_choice = st.selectbox(
        "⭐ PDF Header (Sales Person)",
        ["(Select Sales Person)"] + available_pdfs,
        key="header_pdf_choice",
        help=f"Found {len(available_pdfs)} PDF files"
    )
    
    # Load PDF file into session state
    if header_pdf_choice and header_pdf_choice != "(Select Sales Person)":
        pdf_full_path = os.path.join(SCRIPT_DIR, header_pdf_choice)
        if os.path.exists(pdf_full_path):
            with open(pdf_full_path, "rb") as f:
                st.session_state['header_pdf_file'] = io.BytesIO(f.read())

# Logo upload
logo_file = st.file_uploader("Company Logo (optional)", type=["png", "jpg", "jpeg"])
if logo_file is not None:
    st.session_state['logo_file'] = logo_file

st.markdown("---")

# -------------------------------
# Global Discount Section
# -------------------------------
st.markdown("### 💰 Global Discount")

global_discount = st.number_input(
    "Global Discount (%)", 
    min_value=0.0, 
    max_value=100.0, 
    step=0.01, 
    key="global_discount"
)

# Pre-calculate group info for bulk operations
grouped_df = df.groupby(["GroupName", "Sub Section"])
group_keys = list(grouped_df.groups.keys())

# Build excluded groups set
excluded_groups = set()
for (group, subsection), group_df in grouped_df:
    if group_df["ExcludeFromGlobalDiscount"].any():
        excluded_groups.add((group, subsection))

# Quick action buttons
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🔄 Apply to All Groups", type="primary", use_container_width=True):
        applied = 0
        skipped = 0
        for group, subsection in group_keys:
            discount_key = f"{group}_{subsection}_discount"
            if (group, subsection) in excluded_groups:
                st.session_state[discount_key] = 0.0
                skipped += 1
            else:
                st.session_state[discount_key] = global_discount
                applied += 1
        
        msg = f"✅ {applied} groups set to {global_discount}%"
        if skipped > 0:
            msg += f" ({skipped} excluded)"
        st.success(msg)
        st.rerun()

with col2:
    custom_count = sum(1 for idx, _ in df.iterrows() if st.session_state.get(f"price_{idx}", "").strip())
    if st.button(f"🗑️ Clear Custom Prices ({custom_count})", use_container_width=True):
        cleared = 0
        for idx, _ in df.iterrows():
            price_key = f"price_{idx}"
            input_key = f"input_{idx}"
            if st.session_state.get(price_key, "").strip():
                st.session_state[price_key] = ""
                cleared += 1
            if input_key in st.session_state:
                st.session_state[input_key] = ""
        st.session_state['pending_prices'] = {}
        st.success(f"✅ Cleared {cleared} custom prices")
        st.rerun()

with col3:
    if st.button("🔄 Reset All", use_container_width=True):
        # Reset group discounts
        for group, subsection in group_keys:
            discount_key = f"{group}_{subsection}_discount"
            st.session_state[discount_key] = 0.0
        # Clear custom prices
        for idx, _ in df.iterrows():
            st.session_state[f"price_{idx}"] = ""
            if f"input_{idx}" in st.session_state:
                st.session_state[f"input_{idx}"] = ""
        st.session_state['pending_prices'] = {}
        st.success("✅ All discounts reset")
        st.rerun()

st.markdown("---")

# -------------------------------
# Group-Level Discounts
# -------------------------------
st.markdown("### 🎛️ Group-Level Discounts")

if excluded_groups:
    st.info(f"🔒 {len(excluded_groups)} group(s) excluded from global discount")

# Initialize group discounts
for group, subsection in group_keys:
    discount_key = f"{group}_{subsection}_discount"
    if discount_key not in st.session_state:
        is_excluded = (group, subsection) in excluded_groups
        st.session_state[discount_key] = 0.0 if is_excluded else global_discount

# Display in 3 columns
cols = st.columns(3)
for i, (group, subsection) in enumerate(group_keys):
    col = cols[i % 3]
    discount_key = f"{group}_{subsection}_discount"
    is_excluded = (group, subsection) in excluded_groups
    
    with col:
        label = f"🔒 {group} - {subsection}" if is_excluded else f"{group} - {subsection}"
        st.number_input(
            label,
            min_value=0.0,
            max_value=100.0,
            step=0.01,
            key=discount_key,
            help="Excluded from global discount" if is_excluded else None
        )

st.markdown("---")

# -------------------------------
# Transport Charges Section
# -------------------------------
st.markdown("### 🚚 Transport Charges")

for i, (transport_type, default_value) in enumerate(zip(TRANSPORT_TYPES, DEFAULT_TRANSPORT_CHARGES)):
    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown(f"**{transport_type}**")
    with col2:
        st.text_input(
            f"Charge for {transport_type}",
            value=st.session_state.get(f"transport_{i}", default_value),
            key=f"transport_{i}",
            label_visibility="collapsed"
        )

st.markdown("---")

# -------------------------------
# Save/Load Progress
# -------------------------------
st.markdown("### 💾 Save/Load Progress")

col1, col2 = st.columns(2)

with col1:
    if customer_name:
        safe_name = customer_name.strip().replace(" ", "_").replace("/", "_")
        timestamp = get_uk_time().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{safe_name}_progress_{timestamp}.json"
        
        save_data = create_save_data(customer_name, df)
        json_data = json.dumps(save_data, indent=2)
        
        st.download_button(
            label="💾 Save Progress",
            data=json_data,
            file_name=filename,
            mime="application/json",
            use_container_width=True
        )
    else:
        st.button("💾 Save Progress", disabled=True, use_container_width=True, help="Enter customer name first")

with col2:
    uploaded_file = st.file_uploader("📁 Load Progress", type=['json'], key="load_progress")
    if uploaded_file:
        if st.button("📁 Apply Loaded Data", use_container_width=True):
            try:
                uploaded_file.seek(0)
                loaded_data = json.load(uploaded_file)
                apply_loaded_data(loaded_data, df)
                st.success("✅ Progress loaded!")
                st.rerun()
            except Exception as e:
                st.error(f"Error loading: {e}")

# -------------------------------
# Summary Stats
# -------------------------------
st.markdown("---")
st.markdown("### 📊 Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Items", len(df))

with col2:
    st.metric("Global Discount", f"{global_discount}%")

with col3:
    custom_count = sum(1 for idx, _ in df.iterrows() if st.session_state.get(f"price_{idx}", "").strip())
    st.metric("Custom Prices", custom_count)

with col4:
    groups_count = len(group_keys)
    st.metric("Groups", groups_count)

# Navigation hint
st.markdown("---")
st.info("👉 **Next:** Go to **Custom Rates** page to set individual item prices, or **Export** to generate files.")
