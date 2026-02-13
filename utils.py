# Shared utilities for Net Rates Calculator - Multi-page version
# This module contains functions shared across all pages

import streamlit as st
import pandas as pd
import io
import json
import os
from datetime import datetime

# Timezone support
try:
    from zoneinfo import ZoneInfo
    def get_uk_time():
        return datetime.now(ZoneInfo("Europe/London"))
except ImportError:
    from datetime import timezone, timedelta
    def get_uk_time():
        return datetime.now(timezone.utc) + timedelta(hours=1)

# -------------------------------
# Configuration Constants
# -------------------------------
CONFIG_FILE = "config.json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXCEL_PATH = os.path.join(SCRIPT_DIR, "Net rates Webapp.xlsx")

# Transport charge types and default values
TRANSPORT_TYPES = [
    "Standard - small tools", "Towables", "Non-mechanical", "Fencing",
    "Tower", "Powered Access", "Low-level Access", "Long Distance"
]
DEFAULT_TRANSPORT_CHARGES = ["5", "7.5", "10", "15", "5", "Negotiable", "5", "15"]

# Email Configuration
try:
    SENDGRID_API_KEY = st.secrets.get("sendgrid", {}).get("SENDGRID_API_KEY", "") or os.getenv("SENDGRID_API_KEY", "")
    SENDGRID_FROM_EMAIL = st.secrets.get("sendgrid", {}).get("SENDGRID_FROM_EMAIL", "") or os.getenv("SENDGRID_FROM_EMAIL", "netrates@thehireman.co.uk")
except (AttributeError, KeyError, Exception):
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "netrates@thehireman.co.uk")

# -------------------------------
# Configuration Management
# -------------------------------
def load_config():
    """Load configuration from JSON file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        st.error(f"Error loading config: {e}")
    
    return {
        "smtp_settings": {
            "provider": "SendGrid",
            "sendgrid_api_key": SENDGRID_API_KEY,
            "sendgrid_from_email": SENDGRID_FROM_EMAIL,
            "gmail_user": "",
            "gmail_password": "",
            "o365_user": "",
            "o365_password": "",
            "custom_server": "",
            "custom_port": 587,
            "custom_user": "",
            "custom_password": "",
            "custom_from": "",
            "custom_use_tls": True
        },
        "admin_settings": {
            "default_admin_email": "netrates@thehireman.co.uk",
            "cc_emails": ""
        }
    }

def save_config(config):
    """Save configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving config: {e}")
        return False

# -------------------------------
# Session State Initialization
# -------------------------------
def initialize_session_state():
    """Initialize all required session state variables"""
    if 'config' not in st.session_state:
        st.session_state.config = load_config()
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if "customer_name" not in st.session_state:
        st.session_state["customer_name"] = ""
    
    if "global_discount" not in st.session_state:
        st.session_state["global_discount"] = 0.0
    
    if 'pending_prices' not in st.session_state:
        st.session_state.pending_prices = {}
    
    if 'df' not in st.session_state:
        st.session_state['df'] = None

# -------------------------------
# Price/POA Helper Functions
# -------------------------------
def is_poa_value(value):
    """Check if a value represents POA (Price on Application)"""
    if pd.isna(value):
        return False
    return str(value).upper().strip() in ['POA', 'PRICE ON APPLICATION', 'CONTACT FOR PRICE']

def get_numeric_price(value):
    """Convert price value to numeric, return None if POA"""
    if is_poa_value(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def format_price_display(value):
    """Format price for display - handles both numeric and POA values"""
    if is_poa_value(value):
        return "POA"
    numeric_value = get_numeric_price(value)
    if numeric_value is not None:
        return f"£{numeric_value:.2f}"
    return "POA"

def format_price_for_export(value):
    """Format price for export - numeric only, handles POA values"""
    if is_poa_value(value):
        return "POA"
    numeric_value = get_numeric_price(value)
    if numeric_value is not None:
        return f"{numeric_value:.2f}"
    return "POA"

def format_custom_price_for_export(value):
    """Format custom price for export"""
    if pd.isna(value) or is_poa_value(value) or value == "POA" or value is None:
        return "POA"
    try:
        if str(value).replace('.','').replace('-','').isdigit():
            return f"{float(value):.2f}"
        else:
            return str(value)
    except (ValueError, TypeError):
        return "POA"

def format_discount_for_export(value):
    """Format discount percentage for export"""
    if pd.isna(value) or value == "POA" or is_poa_value(value) or value is None:
        return "POA"
    try:
        if str(value).replace('.','').replace('-','').isdigit():
            return f"{float(value):.2f}%"
        else:
            return str(value)
    except (ValueError, TypeError):
        return "POA"

def format_custom_price_for_display(value):
    """Format custom price for display - includes £ symbol"""
    if pd.isna(value) or is_poa_value(value) or value == "POA" or value is None:
        return "POA"
    try:
        if str(value).replace('.','').replace('-','').isdigit():
            return f"£{float(value):.2f}"
        else:
            return str(value)
    except (ValueError, TypeError):
        return "POA"

# -------------------------------
# Calculation Functions
# -------------------------------
def get_discounted_price(row, global_discount):
    """Calculate discounted price, handling POA values"""
    key = f"{row['GroupName']}_{row['Sub Section']}_discount"
    discount = st.session_state.get(key, global_discount)
    
    if is_poa_value(row["HireRateWeekly"]):
        return "POA"
    
    numeric_price = get_numeric_price(row["HireRateWeekly"])
    if numeric_price is None:
        return "POA"
    
    return numeric_price * (1 - discount / 100)

def calculate_discount_percent(original, custom):
    """Calculate discount percentage, handling POA values"""
    if is_poa_value(original) or is_poa_value(custom):
        return "POA"
    
    orig_numeric = get_numeric_price(original)
    custom_numeric = get_numeric_price(custom)
    
    if orig_numeric is None or custom_numeric is None:
        return "POA"
    
    if orig_numeric == 0:
        return 0
    
    return ((orig_numeric - custom_numeric) / orig_numeric) * 100

# -------------------------------
# Data Loading Functions
# -------------------------------
@st.cache_data
def load_excel(file):
    """Load Excel file with caching"""
    return pd.read_excel(file, engine='openpyxl')

@st.cache_data
def load_excel_with_timestamp(file_path, timestamp):
    """Load Excel file with timestamp-based cache invalidation"""
    return pd.read_excel(file_path, engine='openpyxl')

def get_available_pdf_files():
    """Get list of available PDF files in the script directory"""
    import glob
    try:
        pdf_pattern = os.path.join(SCRIPT_DIR, "*.pdf")
        pdf_files = glob.glob(pdf_pattern)
        return sorted([os.path.basename(pdf_file) for pdf_file in pdf_files])
    except Exception as e:
        st.error(f"Error scanning for PDF files: {e}")
        return []

def load_dataframe():
    """Load and validate the main DataFrame"""
    df = None
    
    if os.path.exists(DEFAULT_EXCEL_PATH):
        try:
            mod_time = os.path.getmtime(DEFAULT_EXCEL_PATH)
            df = load_excel_with_timestamp(DEFAULT_EXCEL_PATH, mod_time)
            
            required_columns = {"ItemCategory", "EquipmentName", "HireRateWeekly", "GroupName", "Sub Section", "Max Discount", "Include", "Order"}
            if not required_columns.issubset(df.columns):
                st.error(f"Excel file must contain: {', '.join(required_columns)}")
                return None
            
            if "ExcludeFromGlobalDiscount" not in df.columns:
                df["ExcludeFromGlobalDiscount"] = False
            
            df = df[df["Include"] == True].copy()
            df.sort_values(by=["GroupName", "Sub Section", "Order"], inplace=True)
            
            if 'CustomPrice' not in df.columns:
                df['CustomPrice'] = None
            if 'DiscountPercent' not in df.columns:
                df['DiscountPercent'] = None
            
            return df
            
        except Exception as e:
            st.error(f"Failed to load Excel: {e}")
            return None
    else:
        st.error(f"No Excel file found at: {DEFAULT_EXCEL_PATH}")
        return None

def ensure_dataframe_loaded():
    """Ensure DataFrame is loaded into session state"""
    if st.session_state.get('df') is None or (hasattr(st.session_state.get('df'), 'empty') and st.session_state['df'].empty):
        df = load_dataframe()
        if df is not None:
            st.session_state['df'] = df
            return True
        return False
    return True

# -------------------------------
# Export Helper Functions
# -------------------------------
def create_admin_dataframe(df, customer_name):
    """Create admin-friendly DataFrame for export"""
    admin_df = df[[
        "ItemCategory", "EquipmentName", "HireRateWeekly", 
        "CustomPrice", "DiscountPercent", "GroupName", "Sub Section"
    ]].copy()
    
    admin_df["HireRateWeekly"] = admin_df["HireRateWeekly"].apply(format_price_for_export)
    admin_df["CustomPrice"] = admin_df["CustomPrice"].apply(format_custom_price_for_export)
    admin_df["DiscountPercent"] = admin_df["DiscountPercent"].apply(format_discount_for_export)
    
    admin_df.columns = [
        "Item Category", "Equipment Name", "Original Price (£)", 
        "Net Price (£)", "Discount %", "Group", "Sub Section"
    ]
    admin_df["Customer Name"] = customer_name
    admin_df["Date Created"] = get_uk_time().strftime("%Y-%m-%d %H:%M")
    
    admin_df = admin_df[[
        "Customer Name", "Date Created", "Item Category", "Equipment Name", 
        "Original Price (£)", "Net Price (£)", "Discount %", "Group", "Sub Section"
    ]]
    
    return admin_df

def create_transport_dataframe():
    """Create transport charges DataFrame"""
    transport_inputs = []
    for i, (transport_type, default_value) in enumerate(zip(TRANSPORT_TYPES, DEFAULT_TRANSPORT_CHARGES)):
        charge = st.session_state.get(f"transport_{i}", default_value)
        if charge:
            transport_inputs.append({
                "Delivery or Collection type": transport_type,
                "Charge (£)": charge
            })
    return pd.DataFrame(transport_inputs)

# -------------------------------
# Progress Save/Load Functions
# -------------------------------
def create_save_data(customer_name, df):
    """Create save data dictionary for progress saving"""
    global_discount = st.session_state.get('global_discount', 0)
    
    custom_prices = {}
    if df is not None and not df.empty:
        for idx, row in df.iterrows():
            price_key = f"price_{idx}"
            item_key = str(row["ItemCategory"])
            price_value = st.session_state.get(price_key, "")
            if price_value:
                custom_prices[item_key] = price_value
    
    return {
        "customer_name": customer_name,
        "global_discount": global_discount,
        "group_discounts": {
            key: st.session_state[key]
            for key in st.session_state
            if key.endswith("_discount")
        },
        "custom_prices": custom_prices,
        "transport_charges": {
            key: st.session_state[key]
            for key in st.session_state
            if key.startswith("transport_")
        }
    }

def apply_loaded_data(loaded_data, df):
    """Apply loaded progress data to session state"""
    st.session_state["customer_name"] = loaded_data.get("customer_name", "")
    st.session_state["global_discount"] = loaded_data.get("global_discount", 0.0)
    
    # Apply group discounts
    for key, value in loaded_data.get("group_discounts", {}).items():
        st.session_state[key] = value
    
    # Apply transport charges
    for key, value in loaded_data.get("transport_charges", {}).items():
        st.session_state[key] = value
    
    # Apply custom prices
    if df is not None and not df.empty:
        custom_prices = loaded_data.get("custom_prices", {})
        item_category_to_index = {str(row["ItemCategory"]): idx for idx, row in df.iterrows()}
        
        for item_category, price_value in custom_prices.items():
            if item_category in item_category_to_index and price_value:
                idx = item_category_to_index[item_category]
                price_key = f"price_{idx}"
                input_key = f"input_{idx}"
                price_str = str(price_value)
                st.session_state[price_key] = price_str
                st.session_state[input_key] = price_str
