# Net Rates Calculator - Multi-Page Version
# Main entry point with authentication
# Original single-page app backed up as app_original_backup.py

import streamlit as st
import os

# Import shared utilities
from utils import initialize_session_state, load_config, save_config, ensure_dataframe_loaded

# -------------------------------
# Page Configuration (MUST be first Streamlit command)
# -------------------------------
st.set_page_config(
    page_title="Net Rates Calculator V2",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
initialize_session_state()

# -------------------------------
# Authentication
# -------------------------------
def authenticate():
    """Handle user authentication"""
    
    # Try to get credentials from secrets or environment
    try:
        correct_username = st.secrets.get("auth", {}).get("username", "") or os.getenv("APP_USERNAME", "admin")
        correct_pin = st.secrets.get("auth", {}).get("pin", "") or os.getenv("APP_PIN", "1234")
    except Exception:
        correct_username = os.getenv("APP_USERNAME", "admin")
        correct_pin = os.getenv("APP_PIN", "1234")
    
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
    
    # Show help
    st.markdown("---")
    with st.expander("❓ Need Help?"):
        st.markdown("""
        **Access Issues:**
        - Contact your administrator for login credentials
        - Ensure you're using the correct username and 4-digit PIN
        
        **Support:** netrates@thehireman.co.uk
        """)
    
    return False

# Check authentication
if not st.session_state.get("authenticated", False):
    authenticate()
    st.stop()

# -------------------------------
# Main App (After Authentication)
# -------------------------------
st.title("🚀 Net Rates Calculator")
st.markdown("### Welcome! Choose a section from the sidebar to get started.")

# Ensure data is loaded
if not ensure_dataframe_loaded():
    st.error("❌ Failed to load equipment data. Please check the Excel file exists.")
    st.stop()

df = st.session_state.get('df')

# Dashboard overview
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

# Quick navigation cards
st.markdown("## 🧭 Navigation")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### ⚙️ Discounts
    Configure customer details, global discount, 
    and group-level discounts.
    
    **Use this page to:**
    - Set customer name
    - Configure global discount
    - Adjust group discounts
    - Set transport charges
    
    👉 **Select "Discounts" from sidebar**
    """)

with col2:
    st.markdown("""
    ### 🎯 Custom Rates
    Set individual prices for specific 
    equipment items.
    
    **Use this page to:**
    - Enter special rates
    - Override calculated prices
    - Set POA items
    - Review custom entries
    
    👉 **Select "Custom Rates" from sidebar**
    """)

with col3:
    st.markdown("""
    ### 📤 Export
    Generate and download price lists 
    in various formats.
    
    **Use this page to:**
    - Download Excel/CSV/JSON
    - Generate customer PDF
    - Email price lists
    - Preview final data
    
    👉 **Select "Export" from sidebar**
    """)

st.markdown("---")

# Quick start guide
with st.expander("📖 Quick Start Guide", expanded=False):
    st.markdown("""
    ## How to Use the Net Rates Calculator
    
    ### Step 1: Set Up Customer (Discounts Page)
    1. Enter the customer name
    2. Select a PDF header (sales person)
    3. Set the global discount percentage
    4. Optionally adjust group-level discounts
    
    ### Step 2: Custom Pricing (Custom Rates Page)
    1. Browse equipment groups
    2. Enter special rates where needed
    3. Apply changes when done
    
    ### Step 3: Export (Export Page)
    1. Review the preview
    2. Download Excel for admin
    3. Generate PDF for customer
    4. Email directly if configured
    
    ---
    
    **Tips:**
    - Changes are saved automatically in session
    - Use "Save Progress" to download a backup
    - Custom prices override calculated discounts
    """)

# Sidebar logout option
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

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: gray; font-size: 0.8em;">
Net Rates Calculator v2.0 - Multi-Page Edition - The Hireman<br>
For support: netrates@thehireman.co.uk
</div>
""", unsafe_allow_html=True)
