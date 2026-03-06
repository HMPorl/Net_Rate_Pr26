# Net Rates Calculator - Multi-Page Version
# Main entry point with authentication and home page
# Pages are auto-detected from the pages/ folder

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
    initialize_session_state, ensure_dataframe_loaded, add_shared_sidebar
)

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
    st.markdown("### Welcome! Use the sidebar to navigate between pages.")
    
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
        st.write(f"**Customer Name:** '{st.session_state.get('customer_name', 'NOT SET')}'")
        st.write(f"**Global Discount:** {st.session_state.get('global_discount', 'NOT SET')}")
        custom_prices_set = sum(1 for k, v in st.session_state.items() if k.startswith('price_') and v)
        st.write(f"**Custom Prices Count:** {custom_prices_set}")
    
    # Footer
    st.markdown("---")
    st.markdown("*Net Rates Calculator v2.0 - Multi-Page Edition - The Hireman*")


# -------------------------------
# Main App Logic
# -------------------------------
if not st.session_state.get("authenticated", False):
    login_page()
else:
    # Add shared sidebar (save/load/logout)
    add_shared_sidebar()
    
    # Show home page content
    home_page()
