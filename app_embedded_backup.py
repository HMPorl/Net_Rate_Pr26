# Net Rates Calculator - Multi-Page Version with Explicit Navigation
# Uses sidebar radio buttons for reliable page navigation

import streamlit as st

# -------------------------------
# Page Configuration (MUST be first Streamlit command)
# -------------------------------
st.set_page_config(
    page_title="Net Rates Calculator V2",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------
# Import shared utilities
# -------------------------------
from utils import (
    initialize_session_state, load_config, save_config, ensure_dataframe_loaded,
    get_available_pdf_files, TRANSPORT_TYPES, DEFAULT_TRANSPORT_CHARGES, 
    SCRIPT_DIR, get_uk_time, create_save_data, apply_loaded_data,
    is_poa_value, get_numeric_price, format_price_display,
    get_discounted_price, calculate_discount_percent,
    format_price_for_export, format_custom_price_for_export,
    format_discount_for_export, format_custom_price_for_display,
    create_admin_dataframe, create_transport_dataframe,
    SENDGRID_API_KEY, SENDGRID_FROM_EMAIL
)
import pandas as pd
import os
import io
import json

# Initialize session state
initialize_session_state()

# -------------------------------
# Authentication Page
# -------------------------------
def login_page():
    """Handle user authentication"""
    correct_username = "HM"
    correct_pin = "1985"
    
    st.title("🔐 Net Rates Calculator - Access Required")
    st.markdown("### Please enter your credentials to access the calculator")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        username_input = st.text_input("Username:", max_chars=10, placeholder="Enter username")
        pin_input = st.text_input("Enter PIN:", type="password", max_chars=4, placeholder="****")
        
        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_b:
            if st.button("🔓 Login", use_container_width=True, type="primary"):
                if username_input == correct_username and pin_input == correct_pin:
                    st.session_state.authenticated = True
                    st.success("✅ Authentication successful!")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials. Please try again.")
    
    st.markdown("---")
    with st.expander("❓ Need Help?"):
        st.markdown("""
        **Access Issues:**
        - Contact your administrator for login credentials
        - Ensure you're using the correct username and 4-digit PIN
        
        **Support:** netrates@thehireman.co.uk
        """)

# -------------------------------
# Home/Dashboard Page
# -------------------------------
def home_page():
    st.title("🚀 Net Rates Calculator")
    st.markdown("### Welcome! Choose a section from the sidebar to get started.")
    
    if not ensure_dataframe_loaded():
        st.error("❌ Failed to load equipment data. Please check the Excel file exists.")
        return
    
    df = st.session_state.get('df')
    
    st.markdown("---")
    st.markdown("## 📊 Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        customer_name = st.session_state.get('customer_name', '')
        if customer_name:
            st.metric("👤 Customer", customer_name[:15] + "..." if len(customer_name) > 15 else customer_name)
        else:
            st.metric("👤 Customer", "Not Set")
    
    with col2:
        global_discount = st.session_state.get('global_discount', 0.0)
        st.metric("💰 Global Discount", f"{global_discount}%")
    
    with col3:
        if df is not None:
            custom_count = sum(1 for idx, _ in df.iterrows() if st.session_state.get(f"price_{idx}", "").strip())
            st.metric("🎯 Custom Prices", custom_count)
        else:
            st.metric("🎯 Custom Prices", 0)
    
    with col4:
        if df is not None:
            st.metric("📦 Total Items", len(df))
        else:
            st.metric("📦 Total Items", 0)
    
    st.markdown("---")
    st.info("👈 **Use the sidebar** to navigate between Discounts, Custom Rates, and Export pages.")
    
    # Debug: Show current session state values
    with st.expander("🔍 Debug: Session State", expanded=False):
        st.write(f"**Customer Name:** {st.session_state.get('customer_name', 'NOT SET')}")
        st.write(f"**Global Discount:** {st.session_state.get('global_discount', 'NOT SET')}")
        custom_prices_set = sum(1 for k, v in st.session_state.items() if k.startswith('price_') and v)
        st.write(f"**Custom Prices Count:** {custom_prices_set}")

# -------------------------------
# Discounts Page
# -------------------------------
def discounts_page():
    st.title("⚙️ Discounts & Setup")
    st.markdown("Configure customer details, global discount, and group-level discounts.")
    
    if not ensure_dataframe_loaded():
        st.error("❌ Failed to load equipment data.")
        return
    
    df = st.session_state['df']
    
    # Initialize values if not present (before widgets)
    if "customer_name" not in st.session_state:
        st.session_state["customer_name"] = ""
    if "bespoke_email" not in st.session_state:
        st.session_state["bespoke_email"] = ""
    if "global_discount" not in st.session_state:
        st.session_state["global_discount"] = 0.0
    
    # Customer Information
    st.markdown("### 👤 Customer Information")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Use callbacks to ensure values persist
        def save_customer_name():
            pass  # Key handles persistence, callback ensures update
        
        st.text_input(
            "⭐ Customer Name", 
            key="customer_name", 
            help="Required for all exports",
            on_change=save_customer_name
        )
        st.text_input("Bespoke Email Address (optional)", key="bespoke_email")
    
    with col2:
        available_pdfs = get_available_pdf_files()
        
        # Initialize PDF choice if not present
        if "header_pdf_choice" not in st.session_state:
            st.session_state["header_pdf_choice"] = "(Select Sales Person)"
        
        header_pdf_choice = st.selectbox(
            "⭐ PDF Header (Sales Person)",
            ["(Select Sales Person)"] + available_pdfs,
            key="header_pdf_choice"
        )
        
        if header_pdf_choice and header_pdf_choice != "(Select Sales Person)":
            pdf_full_path = os.path.join(SCRIPT_DIR, header_pdf_choice)
            if os.path.exists(pdf_full_path):
                with open(pdf_full_path, "rb") as f:
                    st.session_state['header_pdf_file'] = io.BytesIO(f.read())
    
    st.markdown("---")
    
    # Global Discount
    st.markdown("### 💰 Global Discount")
    
    # Use callback to ensure value persists
    def on_discount_change():
        pass  # Key handles persistence
    
    global_discount = st.number_input(
        "Global Discount (%)", 
        min_value=0.0, max_value=100.0, step=0.01, 
        key="global_discount",
        on_change=on_discount_change
    )
    
    # Group operations
    grouped_df = df.groupby(["GroupName", "Sub Section"])
    group_keys = list(grouped_df.groups.keys())
    
    excluded_groups = set()
    for (group, subsection), group_df in grouped_df:
        if group_df["ExcludeFromGlobalDiscount"].any():
            excluded_groups.add((group, subsection))
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Apply to All Groups", type="primary", use_container_width=True):
            for group, subsection in group_keys:
                discount_key = f"{group}_{subsection}_discount"
                if (group, subsection) in excluded_groups:
                    st.session_state[discount_key] = 0.0
                else:
                    st.session_state[discount_key] = global_discount
            st.success(f"✅ Groups set to {global_discount}%")
            st.rerun()
    
    with col2:
        custom_count = sum(1 for idx, _ in df.iterrows() if st.session_state.get(f"price_{idx}", "").strip())
        if st.button(f"🗑️ Clear Custom Prices ({custom_count})", use_container_width=True):
            for idx, _ in df.iterrows():
                st.session_state[f"price_{idx}"] = ""
            st.session_state['pending_prices'] = {}
            st.success("✅ Custom prices cleared")
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset All", use_container_width=True):
            for group, subsection in group_keys:
                st.session_state[f"{group}_{subsection}_discount"] = 0.0
            for idx, _ in df.iterrows():
                st.session_state[f"price_{idx}"] = ""
            st.success("✅ All reset")
            st.rerun()
    
    st.markdown("---")
    
    # Group-Level Discounts
    with st.expander("🎛️ Group-Level Discounts", expanded=False):
        if excluded_groups:
            st.info(f"🔒 {len(excluded_groups)} group(s) excluded from global discount")
        
        for group, subsection in group_keys:
            discount_key = f"{group}_{subsection}_discount"
            if discount_key not in st.session_state:
                is_excluded = (group, subsection) in excluded_groups
                st.session_state[discount_key] = 0.0 if is_excluded else global_discount
        
        cols = st.columns(3)
        for i, (group, subsection) in enumerate(group_keys):
            with cols[i % 3]:
                discount_key = f"{group}_{subsection}_discount"
                is_excluded = (group, subsection) in excluded_groups
                label = f"🔒 {group} - {subsection}" if is_excluded else f"{group} - {subsection}"
                st.number_input(label, min_value=0.0, max_value=100.0, step=0.01, key=discount_key)
    
    st.markdown("---")
    
    # Transport Charges
    st.markdown("### 🚚 Transport Charges")
    
    for i, (transport_type, default_value) in enumerate(zip(TRANSPORT_TYPES, DEFAULT_TRANSPORT_CHARGES)):
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**{transport_type}**")
        with col2:
            if f"transport_{i}" not in st.session_state:
                st.session_state[f"transport_{i}"] = default_value
            st.text_input(f"Charge for {transport_type}", key=f"transport_{i}", label_visibility="collapsed")
    
    st.markdown("---")
    
    # Save/Load Progress
    st.markdown("### 💾 Save/Load Progress")
    
    col1, col2 = st.columns(2)
    
    customer_name = st.session_state.get('customer_name', '')
    
    with col1:
        if customer_name:
            safe_name = customer_name.strip().replace(" ", "_").replace("/", "_")
            timestamp = get_uk_time().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{safe_name}_progress_{timestamp}.json"
            
            save_data = create_save_data(customer_name, df)
            json_data = json.dumps(save_data, indent=2)
            
            st.download_button("💾 Save Progress", json_data, filename, "application/json", use_container_width=True)
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
                    st.error(f"Error: {e}")

# -------------------------------
# Custom Rates Page
# -------------------------------
def custom_rates_page():
    st.title("🎯 Custom Rates")
    st.markdown("Set individual prices for specific equipment items.")
    
    if not ensure_dataframe_loaded():
        st.error("❌ Failed to load equipment data.")
        return
    
    df = st.session_state['df']
    global_discount = st.session_state.get('global_discount', 0.0)
    
    # Show current settings
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"**Customer:** {st.session_state.get('customer_name', 'Not set')}")
    with col2:
        st.info(f"**Global Discount:** {global_discount}%")
    with col3:
        custom_count = sum(1 for idx, _ in df.iterrows() if st.session_state.get(f"price_{idx}", "").strip())
        st.info(f"**Custom Prices:** {custom_count}")
    
    st.markdown("---")
    
    # Initialize price keys - use single key per item
    for idx, row in df.iterrows():
        if f"price_{idx}" not in st.session_state:
            st.session_state[f"price_{idx}"] = ""
    
    if 'pending_prices' not in st.session_state:
        st.session_state.pending_prices = {}
    
    # Controls
    col1, col2, col3 = st.columns([2, 2, 6])
    with col1:
        expand_all = st.button("🔓 Expand All", use_container_width=True)
        if expand_all:
            st.session_state.keep_expanded = True
    with col2:
        collapse_all = st.button("🔒 Collapse All", use_container_width=True)
        if collapse_all:
            st.session_state.keep_expanded = False
    with col3:
        st.markdown("**Legend:** 🎯 = Custom | 📊 = Calculated | ⚠️ = Over Max")
    
    keep_expanded = st.session_state.get('keep_expanded', False)
    
    # Pricing fragment
    @st.fragment
    def pricing_fragment():
        grouped_df = df.groupby(["GroupName", "Sub Section"])
        
        for (group, subsection), group_df in grouped_df:
            has_custom = any(st.session_state.get(f"price_{idx}", "").strip() for idx in group_df.index)
            
            header = f"{group} - {subsection}"
            if has_custom:
                header += " 🎯"
            
            should_expand = keep_expanded or has_custom
            
            with st.expander(header, expanded=should_expand):
                for idx, row in group_df.iterrows():
                    price_key = f"price_{idx}"
                    
                    discount_key = f"{row['GroupName']}_{row['Sub Section']}_discount"
                    group_discount = st.session_state.get(discount_key, global_discount)
                    discounted_price = get_discounted_price(row, global_discount)
                    
                    col1, col2, col3, col4, col5 = st.columns([2, 3, 1.5, 1.5, 1.5])
                    
                    with col1:
                        st.markdown(f"**{row['ItemCategory']}**")
                    
                    with col2:
                        st.markdown(row["EquipmentName"])
                    
                    with col3:
                        st.markdown(f"**{format_price_display(row['HireRateWeekly'])}**")
                    
                    with col4:
                        # Use single key - widget manages its own state
                        st.text_input(
                            "", 
                            key=price_key,
                            label_visibility="collapsed", 
                            placeholder="Special Rate"
                        )
                    
                    with col5:
                        # Read from session state (the widget key)
                        user_input = st.session_state.get(price_key, "").strip()
                        
                        if user_input:
                            if is_poa_value(user_input):
                                st.markdown("**POA** 🎯")
                            else:
                                try:
                                    custom_price = float(user_input)
                                    discount_pct = calculate_discount_percent(row["HireRateWeekly"], custom_price)
                                    if discount_pct != "POA":
                                        if discount_pct > row["Max Discount"]:
                                            st.markdown(f"**{discount_pct:.2f}%** ⚠️")
                                        else:
                                            st.markdown(f"**{discount_pct:.2f}%** 🎯")
                                    else:
                                        st.markdown("**POA** 🎯")
                                except ValueError:
                                    st.markdown("**POA** 🎯")
                        else:
                            discount_pct = calculate_discount_percent(row["HireRateWeekly"], discounted_price)
                            if discount_pct != "POA":
                                st.markdown(f"**{discount_pct:.2f}%** 📊")
                            else:
                                st.markdown("**POA** 📊")
                        
                        # Update DataFrame
                        if user_input:
                            if is_poa_value(user_input):
                                df.at[idx, "CustomPrice"] = "POA"
                                df.at[idx, "DiscountPercent"] = "POA"
                            else:
                                try:
                                    df.at[idx, "CustomPrice"] = float(user_input)
                                    df.at[idx, "DiscountPercent"] = calculate_discount_percent(row["HireRateWeekly"], float(user_input))
                                except:
                                    df.at[idx, "CustomPrice"] = "POA"
                                    df.at[idx, "DiscountPercent"] = "POA"
                        else:
                            df.at[idx, "CustomPrice"] = discounted_price
                            df.at[idx, "DiscountPercent"] = calculate_discount_percent(row["HireRateWeekly"], discounted_price)
    
    pricing_fragment()
    
    st.session_state['df'] = df
    
    st.markdown("---")
    
    # Summary table
    st.markdown("### 📋 Custom Prices Summary")
    
    manual_entries = []
    for idx, row in df.iterrows():
        user_input = st.session_state.get(f"price_{idx}", "").strip()
        if user_input:
            if is_poa_value(user_input):
                manual_entries.append({
                    "Category": row["ItemCategory"],
                    "Equipment": row["EquipmentName"],
                    "Custom Price": "POA"
                })
            else:
                try:
                    manual_entries.append({
                        "Category": row["ItemCategory"],
                        "Equipment": row["EquipmentName"],
                        "Custom Price": f"£{float(user_input):.2f}"
                    })
                except:
                    pass
    
    if manual_entries:
        st.dataframe(pd.DataFrame(manual_entries), use_container_width=True)
    else:
        st.info("No custom prices entered yet.")

# -------------------------------
# Export Page
# -------------------------------
def export_page():
    st.title("📤 Export & Email")
    st.markdown("Generate and download price lists in various formats.")
    
    if not ensure_dataframe_loaded():
        st.error("❌ Failed to load equipment data.")
        return
    
    df = st.session_state['df']
    customer_name = st.session_state.get('customer_name', '')
    global_discount = st.session_state.get('global_discount', 0.0)
    
    if not customer_name:
        st.error("⚠️ Please enter a customer name on the **Discounts** page before exporting.")
        return
    
    # Update DataFrame with current prices
    for idx, row in df.iterrows():
        user_input = st.session_state.get(f"price_{idx}", "").strip()
        
        if user_input:
            if is_poa_value(user_input):
                df.at[idx, "CustomPrice"] = "POA"
                df.at[idx, "DiscountPercent"] = "POA"
            else:
                try:
                    df.at[idx, "CustomPrice"] = float(user_input)
                    df.at[idx, "DiscountPercent"] = calculate_discount_percent(row["HireRateWeekly"], float(user_input))
                except:
                    df.at[idx, "CustomPrice"] = "POA"
                    df.at[idx, "DiscountPercent"] = "POA"
        else:
            discount_key = f"{row['GroupName']}_{row['Sub Section']}_discount"
            discount = st.session_state.get(discount_key, global_discount)
            
            if is_poa_value(row["HireRateWeekly"]):
                df.at[idx, "CustomPrice"] = "POA"
                df.at[idx, "DiscountPercent"] = "POA"
            else:
                try:
                    original = float(row["HireRateWeekly"])
                    discounted = original * (1 - discount / 100)
                    df.at[idx, "CustomPrice"] = discounted
                    df.at[idx, "DiscountPercent"] = discount
                except:
                    df.at[idx, "CustomPrice"] = "POA"
                    df.at[idx, "DiscountPercent"] = "POA"
    
    admin_df = create_admin_dataframe(df, customer_name)
    transport_df = create_transport_dataframe()
    
    st.markdown("### 📥 Download Exports")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### 📊 Excel")
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
            admin_df.to_excel(writer, sheet_name='Price List', index=False)
            transport_df.to_excel(writer, sheet_name='Transport Charges', index=False)
            summary = pd.DataFrame({
                'Customer': [customer_name],
                'Total Items': [len(admin_df)],
                'Global Discount %': [global_discount],
                'Date Created': [get_uk_time().strftime("%Y-%m-%d %H:%M")]
            })
            summary.to_excel(writer, sheet_name='Summary', index=False)
        
        st.download_button(
            "📊 Download Excel", output_excel.getvalue(),
            f"{customer_name}_pricelist_{get_uk_time().strftime('%Y%m%d')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    with col2:
        st.markdown("#### 📄 CSV")
        csv_data = admin_df.to_csv(index=False)
        st.download_button(
            "📄 Download CSV", csv_data,
            f"{customer_name}_pricelist_{get_uk_time().strftime('%Y%m%d')}.csv",
            "text/csv", use_container_width=True
        )
    
    with col3:
        st.markdown("#### 💾 JSON")
        save_data = create_save_data(customer_name, df)
        json_data = json.dumps(save_data, indent=2)
        st.download_button(
            "💾 Download JSON", json_data,
            f"{customer_name}_progress_{get_uk_time().strftime('%Y-%m-%d_%H-%M-%S')}.json",
            "application/json", use_container_width=True
        )
    
    st.markdown("---")
    
    # Preview
    with st.expander("👁️ Preview Price List", expanded=False):
        st.dataframe(admin_df.head(20), use_container_width=True)
        if len(admin_df) > 20:
            st.info(f"Showing first 20 of {len(admin_df)} items")

# -------------------------------
# Sidebar with logout
# -------------------------------
def add_sidebar():
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🔐 Session")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()
        
        st.markdown("---")
        st.markdown("*Net Rates Calculator v2.0*")
        st.markdown("*Multi-Page Edition*")
        st.markdown("*The Hireman*")

# -------------------------------
# Main Navigation
# -------------------------------
if not st.session_state.get("authenticated", False):
    login_page()
else:
    # Define pages
    pages = {
        "🏠 Home": home_page,
        "⚙️ Discounts": discounts_page,
        "🎯 Custom Rates": custom_rates_page,
        "📤 Export": export_page
    }
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("## 📍 Navigation")
        selection = st.radio("Go to:", list(pages.keys()), label_visibility="collapsed")
    
    # Add logout and info
    add_sidebar()
    
    # Run selected page
    pages[selection]()
