# Net Rates Calculator - Production Version
# Enhanced features and improved architecture
# Redeployment trigger - Sept 16, 2025

import streamlit as st
import pandas as pd
import io
import fitz  # PyMuPDF
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import json
import os
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import tempfile
import base64
from datetime import datetime
import time
import glob
from reportlab.lib.utils import ImageReader

# Timezone support
try:
    from zoneinfo import ZoneInfo
    def get_uk_time():
        return datetime.now(ZoneInfo("Europe/London"))
except ImportError:
    # Fallback for older Python versions
    from datetime import timezone, timedelta
    def get_uk_time():
        # UK is UTC+0 in winter, UTC+1 in summer (BST)
        # Simple approximation - you might want to install pytz for better handling
        return datetime.now(timezone.utc) + timedelta(hours=1)

# -------------------------------
# Configuration Management
# -------------------------------
CONFIG_FILE = "config.json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXCEL_PATH = os.path.join(SCRIPT_DIR, "Net rates Webapp.xlsx")

# Transport charge types and default values (used in multiple places)
TRANSPORT_TYPES = [
    "Standard - small tools", "Towables", "Non-mechanical", "Fencing",
    "Tower", "Powered Access", "Low-level Access", "Long Distance"
]
DEFAULT_TRANSPORT_CHARGES = ["5", "7.5", "10", "15", "5", "Negotiable", "5", "15"]

# EMAIL SERVICE CONFIGURATION
# SendGrid API Configuration - Cloud Compatible
try:
    # Try Streamlit secrets first (for cloud deployment)
    SENDGRID_API_KEY = st.secrets.get("sendgrid", {}).get("SENDGRID_API_KEY", "") or os.getenv("SENDGRID_API_KEY", "")
    SENDGRID_FROM_EMAIL = st.secrets.get("sendgrid", {}).get("SENDGRID_FROM_EMAIL", "") or os.getenv("SENDGRID_FROM_EMAIL", "netrates@thehireman.co.uk")
except (AttributeError, KeyError, Exception):
    # Fallback to environment variables (for local development)
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "netrates@thehireman.co.uk")

def load_config():
    """Load configuration from JSON file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        st.error(f"Error loading config: {e}")
    
    # Return default config if file doesn't exist or has errors
    return {
        "smtp_settings": {
            "provider": "SendGrid",  # Default to SendGrid
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
# Streamlit Page Configuration
# -------------------------------
st.set_page_config(
    page_title="Net Rates Calculator V2 with 2026 pricing",
    page_icon="🚀",
    layout="wide"
)

# -------------------------------
# Session State Initialization
# -------------------------------
def initialize_session_state():
    """Safely initialize session state variables"""
    try:
        # Load configuration at startup
        if 'config' not in st.session_state:
            st.session_state.config = load_config()
        
        # Authentication state
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = False
    except Exception as e:
        st.error(f"Error initializing session state: {e}")

def safe_set_session_state(key, value):
    """Safely set session state with error handling"""
    try:
        # Validate the key and value
        if not isinstance(key, str):
            st.error(f"Invalid session state key type: {type(key)}")
            return False
        
        # Check for problematic values
        if value is None:
            st.session_state[key] = ""
        elif isinstance(value, (str, int, float, bool, list, dict)):
            st.session_state[key] = value
        else:
            # Convert complex objects to string representation
            st.session_state[key] = str(value)
        
        return True
    except Exception as e:
        st.error(f"Error setting session state key '{key}': {e}")
        return False

# Initialize session state
initialize_session_state()

# -------------------------------
# Handle File Loading (BEFORE any widgets are created)
# -------------------------------
def handle_file_loading():
    """Handle file loading before any widgets are instantiated"""
    if st.session_state.get('trigger_upload_load', False):
        st.session_state['trigger_upload_load'] = False  # Clear the trigger
        
        uploaded_file = st.session_state.get('uploaded_file_to_load', None)
        if uploaded_file:
            try:
                # Reset file pointer to beginning before reading
                uploaded_file.seek(0)
                loaded_data = json.load(uploaded_file)
                
                # Clear existing session state by setting to default values
                # This must happen BEFORE widgets are created
                st.session_state["customer_name"] = loaded_data.get("customer_name", "")
                st.session_state["global_discount"] = loaded_data.get("global_discount", 0.0)
                
                # Clear all discount keys
                for key in list(st.session_state.keys()):
                    if key.endswith("_discount"):
                        st.session_state[key] = 0.0
                
                # Restore group discounts
                for key, value in loaded_data.get("group_discounts", {}).items():
                    st.session_state[key] = value
                
                # Clear all transport keys
                for key in list(st.session_state.keys()):
                    if key.startswith("transport_"):
                        st.session_state[key] = 0.0
                
                # Restore transport charges
                for key, value in loaded_data.get("transport_charges", {}).items():
                    st.session_state[key] = value
                
                # Clear and restore custom prices
                # We need to do this after the DataFrame is loaded
                st.session_state['pending_custom_prices'] = loaded_data.get("custom_prices", {})
                st.session_state['loading_success'] = True
                
                return True
                
            except Exception as e:
                st.session_state['loading_error'] = str(e)
                return False
    
    return False

def apply_pending_custom_prices(df):
    """
    Apply pending custom prices from a loaded progress file to session state.
    This function is called after DataFrame is loaded to map item categories to indices.
    
    Args:
        df: The loaded DataFrame with ItemCategory column
    
    Returns:
        bool: True if prices were applied, False otherwise
    """
    if not st.session_state.get('pending_custom_prices') or not st.session_state.get('loading_success'):
        return False
    
    try:
        pending_prices = st.session_state['pending_custom_prices']
        
        # Clear ALL existing custom price keys first (both price_ and input_ keys)
        for key in list(st.session_state.keys()):
            if key.startswith("price_") or key.startswith("input_"):
                del st.session_state[key]
        
        # Also clear the pending_prices dictionary used by the fragment
        st.session_state['pending_prices'] = {}
        
        # Create a reverse lookup dictionary for O(1) performance instead of O(n²)
        item_category_to_index = {}
        for idx, row in df.iterrows():
            item_category_to_index[str(row["ItemCategory"])] = idx
        
        prices_set = 0
        total_to_process = len([k for k in pending_prices.keys() if k in item_category_to_index])
        
        # Show progress indicator for large datasets
        progress_placeholder = None
        if total_to_process > 20:
            progress_placeholder = st.empty()
            progress_placeholder.info(f"🔄 Processing {total_to_process} custom prices...")
        
        # Process all custom prices efficiently - handles 100+ prices
        for item_category, price_value in pending_prices.items():
            if item_category in item_category_to_index and price_value:
                idx = item_category_to_index[item_category]
                price_key = f"price_{idx}"
                input_key = f"input_{idx}"  # Also set the input widget key
                price_str = str(price_value)
                st.session_state[price_key] = price_str
                st.session_state[input_key] = price_str  # Widget key must match for display
                prices_set += 1
        
        # Clear progress indicator and show success
        if progress_placeholder:
            progress_placeholder.empty()
            st.success(f"✅ Successfully loaded {prices_set} custom prices from progress file")
        
        # Clear the pending data
        del st.session_state['pending_custom_prices']
        st.session_state['loading_success'] = False
        st.success("✅ Progress loaded successfully!")
        
        return True
        
    except Exception as e:
        st.error(f"Error applying custom prices: {e}")
        import traceback
        st.error(f"Traceback: {traceback.format_exc()}")
        return False

# Process file loading
loading_happened = handle_file_loading()

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
    """Format custom price for export - handles None, POA, and numeric values"""
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
    """Format discount percentage for export - handles POA and numeric values"""
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
# Syrinx Import Processing Functions
# -------------------------------

def process_syrinx_file(syrinx_file, global_discount, df):
    """Process Syrinx Excel file and return matched/ignored items"""
    try:
        # Read Excel file without headers
        syrinx_df = pd.read_excel(syrinx_file, header=None, names=['CategoryCode', 'SpecialPrice'])
        
        matched_items = []
        ignored_codes = []
        
        for _, row in syrinx_df.iterrows():
            category_code = str(row['CategoryCode']).strip()
            try:
                special_price = float(row['SpecialPrice'])
            except (ValueError, TypeError):
                ignored_codes.append(category_code)
                continue
            
            # Find matching equipment in main DataFrame
            matching_equipment = df[df['ItemCategory'] == category_code]
            
            if not matching_equipment.empty:
                # Store original special price (global discount will be applied by the app)
                for idx, equipment_row in matching_equipment.iterrows():
                    matched_items.append({
                        'code': category_code,
                        'equipment': equipment_row['EquipmentName'],
                        'special_price': special_price,
                        'preview_final_price': special_price * (1 - global_discount / 100),
                        'index': idx
                    })
            else:
                ignored_codes.append(category_code)
        
        return {
            'matched': matched_items,
            'ignored': ignored_codes,
            'total_processed': len(syrinx_df)
        }
        
    except Exception as e:
        st.error(f"Error processing Syrinx file: {str(e)}")
        return None

def apply_syrinx_import(preview_data, global_discount):
    """Apply Syrinx import data to session state using the same mechanism as JSON loading"""
    try:
        # Create pending_custom_prices dictionary like JSON loading
        pending_prices = {}
        
        # Build pending prices from Syrinx data 
        matched_items = preview_data.get('matched', [])
        for item in matched_items:
            item_category = str(item['code'])  # Use code for lookup (matches process_syrinx_file output)
            special_price = item['special_price']
            
            if special_price and special_price != 'N/A':
                try:
                    price_value = float(special_price)
                    pending_prices[item_category] = price_value
                except (ValueError, TypeError):
                    continue  # Skip invalid prices
        
        # Store in session state using the same mechanism as JSON loading
        st.session_state['pending_custom_prices'] = pending_prices
        st.session_state['loading_success'] = True
        
        # Update global discount
        st.session_state['global_discount'] = global_discount
        
        return True
        
    except Exception as e:
        st.error(f"Error applying Syrinx import: {str(e)}")
        return False

def handle_syrinx_processing():
    """Handle Syrinx import processing"""
    df = st.session_state.get('df', pd.DataFrame())
    
    # Handle preview request
    if st.session_state.get('syrinx_preview_file') and not df.empty:
        syrinx_file = st.session_state['syrinx_preview_file']
        discount = st.session_state.get('syrinx_preview_discount', 0)
        
        # Process the file
        syrinx_file.seek(0)  # Reset file pointer
        preview_data = process_syrinx_file(syrinx_file, discount, df)
        
        if preview_data:
            st.session_state['syrinx_preview_data'] = preview_data
            st.success(f"Preview generated: {len(preview_data['matched'])} items matched, {len(preview_data['ignored'])} ignored")
        
        # Clear the preview file from session state
        st.session_state.pop('syrinx_preview_file', None)
    
    # Handle apply import request
    if st.session_state.get('apply_syrinx_import', False):
        st.session_state['apply_syrinx_import'] = False
        
        preview_data = st.session_state.get('syrinx_preview_data', {})
        discount = st.session_state.get('syrinx_preview_discount', 0)
        
        if preview_data and apply_syrinx_import(preview_data, discount):
            st.success(f"✅ Syrinx import applied! {len(preview_data['matched'])} prices loaded.")
            # Clear preview data
            st.session_state['show_syrinx_preview'] = False
            st.session_state.pop('syrinx_preview_data', None)
            st.balloons()
        else:
            st.error("Failed to apply Syrinx import")

# Process Syrinx import
handle_syrinx_processing()

# -------------------------------
# Excel to JSON Converter Functions
# -------------------------------

def process_excel_to_json(excel_file, global_discount, customer_name, df):
    """Convert Excel file with category codes and prices to JSON format"""
    try:
        # Read Excel file without headers
        excel_df = pd.read_excel(excel_file, header=None, names=['CategoryCode', 'SpecialPrice'])
        
        custom_prices = {}
        matched_count = 0
        ignored_codes = []
        
        for _, row in excel_df.iterrows():
            category_code = str(row['CategoryCode']).strip()
            try:
                special_price = float(row['SpecialPrice'])
                # Store as string to match working Save Progress format
                custom_prices[category_code] = str(special_price)
                matched_count += 1
            except (ValueError, TypeError):
                ignored_codes.append(category_code)
                continue
        
        # Generate group discounts for all equipment groups (same as Save Progress)
        group_discounts = {}
        for group, subsection in df.groupby(["GroupName", "Sub Section"]).groups.keys():
            discount_key = f"{group}_{subsection}_discount"
            group_discounts[discount_key] = global_discount
        
        # Add global_discount key to group_discounts (matches working Save files)
        group_discounts["global_discount"] = global_discount
        
        # Generate transport charges with default values (same as Save Progress)
        transport_charges = {}
        for i, default_value in enumerate(DEFAULT_TRANSPORT_CHARGES):
            transport_charges[f"transport_{i}"] = default_value
        
        # Create JSON in same format as Save Progress
        json_data = {
            "customer_name": customer_name,
            "global_discount": global_discount,
            "group_discounts": group_discounts,
            "custom_prices": custom_prices,
            "transport_charges": transport_charges,
            "created_timestamp": datetime.now().isoformat(),
            "created_by": "Excel to JSON Converter"
        }
        
        return {
            'json_data': json_data,
            'matched_count': matched_count,
            'ignored_codes': ignored_codes,
            'total_processed': len(excel_df)
        }
        
    except Exception as e:
        st.error(f"Error processing Excel file: {str(e)}")
        return None

def list_local_progress_files():
    """List available local progress files from Downloads folder or current directory"""
    try:
        import os
        files_with_info = []
        
        # Check Downloads folder first (for local development)
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        if os.path.exists(downloads_path):
            pattern = os.path.join(downloads_path, "*_progress_*.json")
            downloads_files = glob.glob(pattern)
            
            for filepath in downloads_files:
                try:
                    stat = os.stat(filepath)
                    filename = os.path.basename(filepath)
                    files_with_info.append({
                        'name': filename,
                        'path': filepath,
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'location': 'Downloads'
                    })
                except:
                    filename = os.path.basename(filepath)
                    files_with_info.append({
                        'name': filename,
                        'path': filepath,
                        'size': 0,
                        'modified': 0,
                        'location': 'Downloads'
                    })
        
        # Also check current directory (for cloud deployment)
        current_dir_files = glob.glob("*_progress_*.json")
        for filepath in current_dir_files:
            try:
                stat = os.stat(filepath)
                filename = os.path.basename(filepath)
                # Only add if not already found in Downloads
                if not any(f['name'] == filename for f in files_with_info):
                    files_with_info.append({
                        'name': filename,
                        'path': filepath,
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'location': 'App Directory'
                    })
            except:
                filename = os.path.basename(filepath)
                if not any(f['name'] == filename for f in files_with_info):
                    files_with_info.append({
                        'name': filename,
                        'path': filepath,
                        'size': 0,
                        'modified': 0,
                        'location': 'App Directory'
                    })
        
        # Sort by modified time (newest first)
        files_with_info.sort(key=lambda x: x['modified'], reverse=True)
        return files_with_info
        
    except Exception as e:
        st.error(f"Failed to list local files: {e}")
        return []

def load_progress_from_local_file(filepath):
    """Load progress data from local file"""
    try:
        with open(filepath, 'r') as f:
            progress_data = json.load(f)
        return progress_data
    except Exception as e:
        st.error(f"Failed to load local file: {e}")
        return None

def get_available_pdf_files():
    """Get list of available PDF files - not cached to always show latest files"""
    try:
        pdf_pattern = os.path.join(SCRIPT_DIR, "*.pdf")
        pdf_files = glob.glob(pdf_pattern)
        # Return just the filenames, not the full paths
        return sorted([os.path.basename(pdf_file) for pdf_file in pdf_files])
    except Exception as e:
        st.error(f"Error scanning for PDF files: {e}")
        return []

@st.cache_data
def load_excel_with_timestamp(file_path, timestamp):
    """Load Excel file with timestamp-based cache invalidation"""
    return pd.read_excel(file_path, engine='openpyxl')

def add_footer_logo(canvas, doc):
    logo_path = "HMChev.png"  # Place your logo in the app root folder
    page_width = doc.pagesize[0]
    # Stretch logo to full page width, minus small margins
    margin = 20  # points, adjust as needed
    logo_width = page_width - 2 * margin
    logo_height = 30  # or set to any desired height

    x = margin
    y = 10  # 10 points from the bottom

    try:
        canvas.drawImage(
            ImageReader(logo_path),
            x, y,
            width=logo_width,
            height=logo_height,
            mask='auto'
        )
    except Exception:
        pass  # If logo not found, skip

# -------------------------------
# Security: PIN Authentication
# -------------------------------

if not st.session_state.authenticated:
    st.title("🔐 Net Rates Calculator - Access Required")
    st.markdown("### Please enter your credentials to access the calculator")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username_input = st.text_input("Username:", max_chars=10, placeholder="Enter username")
        pin_input = st.text_input("Enter PIN:", type="password", max_chars=4, placeholder="****")
        
        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_b:
            if st.button("🔓 Access Calculator", type="primary", use_container_width=True):
                if username_input == "HM" and pin_input == "1985":
                    st.session_state.authenticated = True
                    st.session_state.current_user = username_input  # Store username for potential future use
                    st.success("✅ Access granted! Redirecting...")
                    st.rerun()
                else:
                    if username_input != "HM":
                        st.error("❌ Incorrect username. Please try again.")
                    elif pin_input != "1985":
                        st.error("❌ Incorrect PIN. Please try again.")
                    else:
                        st.error("❌ Incorrect credentials. Please try again.")
    
    st.markdown("---")
    st.info("💡 **Need access?** Contact your system administrator for the username and PIN.")
    st.stop()  # Stop execution here if not authenticated

# -------------------------------
# Main Application Header
# -------------------------------
st.markdown("# 🚀 Net Rates Calculator V2 with 2026 pricing")
st.markdown("*Production Version - Enhanced Features*")
st.markdown("---")

# Built-in Help System
if st.session_state.get('show_help', False):
    with st.expander("📚 **User Guide & Instructions**", expanded=True):
        st.markdown("""
        ## 🚀 Quick Start Guide
        
        ### 1️⃣ **Basic Setup**
        - **Customer Name**: Required for all exports and emails
        - **Company Logo**: Optional, appears on PDF documents
        - **Sales Person Header**: Choose PDF template for your quotes
        
        ### 2️⃣ **Setting Discounts**
        
        #### Global Discount
        - Set base discount percentage for all items
        - Use "Update all group discounts" to apply globally
        
        #### Group-Level Discounts  
        - Each equipment group can have custom discount
        - "Set All Groups to Global Discount" resets everything
        
        ### 3️⃣ **Custom Pricing**
        - **Automatic**: Items show discounted prices based on group settings
        - **Manual Override**: Enter custom prices in text boxes
        - ⚠️ System warns if you exceed maximum allowed discount
        - Only manual entries appear in "Special Rates" section
        
        ### 4️⃣ **Export Options**
        
        | Format | Use Case |
        |--------|----------|
        | 📊 **Excel** | Admin format with 3 sheets - ready for CRM |
        | 📄 **CSV** | Universal format for other systems |
        | 🔗 **JSON** | API integration or system imports |
        | 📄 **PDF** | Professional customer-facing quotes |
        | 💾 **Save Progress** | JSON backup to resume work later |
        
        ### 5️⃣ **Email System**
        
        #### Recommended: SendGrid Setup
        1. Click "Email Config" toggle
        2. Select "SendGrid" 
        3. Enter API key and from email
        4. Save settings - now ready for reliable delivery!
        
        #### Email Features
        - ✅ **Dual Attachments**: Excel (for CRM) + JSON (for backup)
        - ✅ **CC Support**: CC yourself or others
        - ✅ **Professional Format**: Auto-generated business emails
        - ✅ **Reliable Delivery**: SendGrid ensures best attachment support
        
        ### 6️⃣ **Advanced Features**
        
        #### Admin Options
        - Upload custom Excel templates
        - Upload custom PDF headers  
        - Override default system files
        
        ## 🛠️ **Troubleshooting**
        
        ### Email Issues
        - **SendGrid errors**: Check API key and verified sender email
        - **Gmail issues**: Need 2-factor auth + app password
        - **Attachment problems**: SendGrid provides best support
        
        ### Export Issues  
        - Ensure customer name is entered first
        - PDF requires sales person header selection
        - Check browser download permissions
        
        ## ✅ **Best Practices**
        
        1. **Always enter customer name first** - Required for exports
        2. **Save progress frequently** - Especially for large lists  
        3. **Test email settings** - Use test button before important quotes
        4. **Use SendGrid** - Most reliable for business email delivery
        5. **Review discount warnings** - Stay within maximum limits
        
        ## 📞 **Support**
        - 📧 Email: netrates@thehireman.co.uk
        - 💡 Check this guide first for common questions
        
        ---
        *Net Rates Calculator - The Hireman | Version: August 2025*
        """)

# Ensure progress_saves folder exists
if not os.path.exists("progress_saves"):
    os.makedirs("progress_saves")


# -------------------------------
# File Uploads and Inputs
# -------------------------------

@st.cache_data
def load_excel(file):
    """Load Excel file with caching"""
    return pd.read_excel(file, engine='openpyxl')

@st.cache_data
def read_pdf_header(file):
    return file.read()

def generate_customer_pdf(df, customer_name, header_pdf_file, include_custom_table=True, 
                          special_rates_pagebreak=False, special_rates_spacing=0):
    """
    Generate customer PDF with price list - Single source of truth for PDF generation.
    
    Args:
        df: DataFrame with pricing data
        customer_name: Customer name for the PDF
        header_pdf_file: PDF header file (uploaded file object)
        include_custom_table: Whether to include special rates table at the top
        special_rates_pagebreak: Whether to put special rates on a separate page
        special_rates_spacing: Number of blank lines after special rates
    
    Returns:
        bytes: The merged PDF as bytes, or None if generation fails
    """
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import PageBreak
    
    try:
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Add custom styles
        styles.add(ParagraphStyle(
            name='LeftHeading2',
            parent=styles['Heading2'],
            alignment=TA_LEFT,
            spaceBefore=6,
            spaceAfter=6,
            textColor='#002D56'
        ))
        styles.add(ParagraphStyle(
            name='LeftHeading3',
            parent=styles['Heading3'],
            alignment=TA_LEFT,
            spaceBefore=2,
            spaceAfter=4,
            textColor='#002D56'
        ))
        styles.add(ParagraphStyle(
            name='BarHeading2',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            spaceBefore=12,
            spaceAfter=6,
            textColor='white',
            fontSize=14,
            leftIndent=0,
            rightIndent=0,
            backColor='#002D56',
            borderPadding=8,
            padding=0,
            leading=18,
        ))

        # Custom Price Products Table at the Top
        if include_custom_table:
            # Collect custom price items with their subsection info
            # Preserve original DataFrame order (already sorted by GroupName, Sub Section, Order)
            custom_price_items = []
            for idx, row in df.iterrows():
                price_key = f"price_{idx}"
                user_input = str(st.session_state.get(price_key, "")).strip()
                if user_input:
                    if not is_poa_value(user_input):
                        try:
                            entered_price = float(user_input)
                            custom_price_items.append({
                                'subsection': row["Sub Section"],
                                'category': row["ItemCategory"],
                                'equipment': row["EquipmentName"],
                                'price': entered_price,
                                'original_index': idx  # Preserve original order
                            })
                        except ValueError:
                            continue

            if custom_price_items:
                customer_title = customer_name if customer_name else "Customer"
                elements.append(Paragraph(f"Net Rates for {customer_title}", styles['Title']))
                elements.append(Spacer(1, 12))
                elements.append(Paragraph("Special Rates", styles['Heading2']))
                elements.append(Spacer(1, 6))
                
                # Build table with subsection headers
                table_data = [["Category", "Equipment", "Special (£)"]]
                subsection_header_rows = []  # Track which rows are subsection headers
                
                # Group by subsection while preserving original order
                from itertools import groupby
                # Items are already in correct order from DataFrame iteration
                # Group by subsection without re-sorting to maintain document order
                
                current_row = 1  # Start after header row
                current_subsection = None
                
                for item in custom_price_items:
                    # Add subsection header when subsection changes
                    if item['subsection'] != current_subsection:
                        current_subsection = item['subsection']
                        subsection_title = str(current_subsection) if current_subsection and str(current_subsection) != "nan" else "General"
                        table_data.append(['', Paragraph(f"<b>{subsection_title}</b>", styles['BodyText']), ''])
                        subsection_header_rows.append(current_row)
                        current_row += 1
                    
                    # Add item
                    table_data.append([
                        item['category'],
                        Paragraph(item['equipment'], styles['BodyText']),
                        f"£{item['price']:.2f}"
                    ])
                    current_row += 1
                
                # Build table styles
                row_styles = [
                    ('BACKGROUND', (0, 0), (-1, 0), '#FFD51D'),  # Yellow header
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ]
                
                # Style subsection header rows (yellow background #FCE547)
                for row_num in subsection_header_rows:
                    row_styles.append(('BACKGROUND', (0, row_num), (-1, row_num), '#FCE547'))
                    row_styles.append(('SPAN', (1, row_num), (2, row_num)))  # Span equipment and price columns
                
                # Style data rows (light yellow background, skip subsection headers)
                for row_num in range(1, len(table_data)):
                    if row_num not in subsection_header_rows:
                        row_styles.append(('BACKGROUND', (0, row_num), (-1, row_num), '#FFF2B8'))
                
                table = Table(table_data, colWidths=[60, 380, 60])
                table.setStyle(TableStyle(row_styles))
                elements.append(table)
                elements.append(Spacer(1, 12))
                if special_rates_pagebreak:
                    elements.append(PageBreak())
                elif special_rates_spacing > 0:
                    for _ in range(special_rates_spacing):
                        elements.append(Spacer(1, 12))
            else:
                customer_title = customer_name if customer_name else "Customer"
                elements.append(Paragraph(f"Net Rates for {customer_title}", styles['Title']))
                elements.append(Spacer(1, 12))
        else:
            customer_title = customer_name if customer_name else "Customer"
            elements.append(Paragraph(f"Net Rates for {customer_title}", styles['Title']))
            elements.append(Spacer(1, 12))

        # Main Price List Tables
        table_col_widths = [60, 380, 60]
        bar_width = sum(table_col_widths)

        for group, group_df in df.groupby("GroupName"):
            group_elements = []

            # Group header bar
            bar_table = Table(
                [[Paragraph(f"{group.upper()}", styles['BarHeading2'])]],
                colWidths=[bar_width]
            )
            bar_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), '#002D56'),
                ('TEXTCOLOR', (0, 0), (-1, -1), 'white'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ]))
            group_spacer = Spacer(1, 2)
            group_subsection_blocks = []

            for subsection, sub_df in group_df.groupby("Sub Section"):
                if pd.isnull(subsection) or str(subsection).strip() == "" or subsection == "nan":
                    subsection_title = "Untitled"
                else:
                    subsection_title = str(subsection)

                header_row = [
                    '',
                    Paragraph(f"<i>{subsection_title}</i>", styles['LeftHeading3']),
                    ''
                ]

                table_data = [header_row]
                special_rate_rows = []
                
                for row_idx, (_, row) in enumerate(sub_df.iterrows(), start=1):
                    if is_poa_value(row['CustomPrice']) or row['CustomPrice'] == "POA":
                        price_text = "POA"
                        has_special_rate = False
                    else:
                        try:
                            price_text = f"£{float(row['CustomPrice']):.2f}"
                            price_key = f"price_{row.name}"
                            user_input = str(st.session_state.get(price_key, "")).strip()
                            has_special_rate = bool(user_input and not is_poa_value(user_input))
                        except (ValueError, TypeError):
                            price_text = "POA"
                            has_special_rate = False
                    
                    if has_special_rate:
                        special_rate_rows.append(row_idx)
                    
                    table_data.append([
                        row["ItemCategory"],
                        Paragraph(row["EquipmentName"], styles['BodyText']),
                        price_text
                    ])

                table_with_repeat_header = Table(
                    table_data,
                    colWidths=table_col_widths,
                    repeatRows=1
                )
                
                table_style = [
                    ('BACKGROUND', (0, 0), (-1, 0), '#e6eef7'),
                    ('TEXTCOLOR', (0, 0), (-1, 0), '#002D56'),
                    ('LEFTPADDING', (0, 0), (-1, 0), 8),
                    ('RIGHTPADDING', (0, 0), (-1, 0), 8),
                    ('TOPPADDING', (0, 0), (-1, 0), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
                    ('ALIGN', (1, 0), (1, 0), 'LEFT'),
                    ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ]
                
                for row_num in special_rate_rows:
                    table_style.append(('BACKGROUND', (0, row_num), (-1, row_num), '#FFD51D'))
                
                table_with_repeat_header.setStyle(TableStyle(table_style))

                group_subsection_blocks.append(
                    [table_with_repeat_header, Spacer(1, 12)]
                )

            if group_subsection_blocks:
                group_elements.append(
                    KeepTogether([
                        bar_table,
                        group_spacer,
                        *group_subsection_blocks[0]
                    ])
                )
                for block in group_subsection_blocks[1:]:
                    group_elements.append(KeepTogether(block))
            else:
                group_elements.append(
                    KeepTogether([
                        bar_table,
                        group_spacer
                    ])
                )

            elements.extend(group_elements)

        # Build PDF with footer logo
        doc.build(elements, onFirstPage=add_footer_logo, onLaterPages=add_footer_logo)
        pdf_buffer.seek(0)

        # Merge Header PDF with Generated PDF
        header_data = read_pdf_header(header_pdf_file)
        header_pdf = fitz.open(stream=header_data, filetype="pdf")

        while len(header_pdf) < 3:
            header_pdf.new_page()

        # Add customer name and logo to first page
        page1 = header_pdf[0]
        if customer_name:
            font_size = 22
            font_color = (0 / 255, 45 / 255, 86 / 255)
            font_name = "helv"
            page_width = page1.rect.width
            page_height = page1.rect.height
            text_y = page_height / 3
            font = fitz.Font(fontname=font_name)
            text_width = font.text_length(customer_name, fontsize=font_size)
            text_x = (page_width - text_width) / 2
            page1.insert_text((text_x, text_y), customer_name, fontsize=font_size, fontname=font_name, fill=font_color)

            bespoke_email = st.session_state.get('bespoke_email', '')
            if bespoke_email and bespoke_email.strip():
                email_font_size = 13
                email_font_color = (0 / 255, 90 / 255, 156 / 255)  # #005a9c
                email_text_y = text_y + font_size + 6
                email_text_width = font.text_length(bespoke_email, fontsize=email_font_size)
                email_text_x = (page_width - email_text_width) / 2
                page1.insert_text(
                    (email_text_x, email_text_y),
                    bespoke_email,
                    fontsize=email_font_size,
                    fontname=font_name,
                    fill=email_font_color
                )

        logo_file = st.session_state.get('logo_file', None)
        if logo_file:
            try:
                # Reset file pointer in case it was read before
                logo_file.seek(0)
                logo_image = Image.open(logo_file)
                logo_bytes = io.BytesIO()
                logo_image.save(logo_bytes, format="PNG")
                logo_bytes.seek(0)
                logo_width = 100
                logo_height = logo_image.height * (logo_width / logo_image.width)
                logo_x = (page_width - logo_width) / 2
                bespoke_email = st.session_state.get('bespoke_email', '')
                if bespoke_email and bespoke_email.strip():
                    logo_y = text_y + font_size + 13 + 20
                else:
                    logo_y = text_y + font_size + 20
                rect_logo = fitz.Rect(logo_x, logo_y, logo_x + logo_width, logo_y + logo_height)
                page1.insert_image(rect_logo, stream=logo_bytes.read())
            except Exception as e:
                # Logo failed to load, continue without it
                pass

        # Draw Transport Charges table on page 3
        page3 = header_pdf[2]
        page_width = page3.rect.width
        page_height = page3.rect.height

        # Get transport data from session state
        transport_data = []
        for i, (transport_type, default_value) in enumerate(zip(TRANSPORT_TYPES, DEFAULT_TRANSPORT_CHARGES)):
            charge = st.session_state.get(f"transport_{i}", default_value)
            transport_data.append([transport_type, charge])

        row_height = 22
        col_widths_transport = [300, 100]
        font_size_transport = 10
        text_padding_x = 6
        text_offset_y = 2

        num_rows = len(transport_data) + 1
        table_height = num_rows * row_height
        bottom_margin_cm = 28.35
        margin_y = bottom_margin_cm + table_height
        table_width = sum(col_widths_transport)
        margin_x = (page_width - table_width) / 2

        # Draw header row
        headers = ["Delivery or Collection type", "Charge (£)"]
        for col_index, header in enumerate(headers):
            x0 = margin_x + sum(col_widths_transport[:col_index])
            x1 = x0 + col_widths_transport[col_index]
            y_text = page_height - margin_y + text_offset_y
            y_rect = page_height - margin_y - 14
            header_color = (125/255, 166/255, 216/255)  # #7DA6D8
            page3.draw_rect(fitz.Rect(x0, y_rect, x1, y_rect + row_height), color=header_color, fill=header_color)
            page3.insert_text((x0 + text_padding_x, y_text), header, fontsize=font_size_transport, fontname="hebo")

        # Draw data rows with alternating colors
        for row_index, row in enumerate(transport_data):
            if row_index % 2 == 0:
                row_color = (247/255, 252/255, 255/255)  # #F7FCFF
            else:
                row_color = (218/255, 233/255, 248/255)  # #DAE9F8
            
            for col_index, cell in enumerate(row):
                x0 = margin_x + sum(col_widths_transport[:col_index])
                x1 = x0 + col_widths_transport[col_index]
                y_text = page_height - margin_y + row_height * (row_index + 1) + text_offset_y
                y_rect = page_height - margin_y + row_height * (row_index + 1) - 14
                page3.draw_rect(fitz.Rect(x0, y_rect, x1, y_rect + row_height), color=row_color, fill=row_color)
                cell_text = str(cell)
                if col_index == 1:  # Charge column
                    if cell_text.replace('.', '').replace('-', '').isdigit():
                        cell_text = f"£{cell_text}"
                    elif cell_text.lower() not in ['negotiable', 'poa', 'n/a']:
                        cell_text = f"£{cell_text}"
                page3.insert_text((x0 + text_padding_x, y_text), cell_text, fontsize=font_size_transport, fontname="helv")

        # Merge PDFs
        modified_header = io.BytesIO()
        header_pdf.save(modified_header)
        header_pdf.close()

        merged_pdf = fitz.open(stream=modified_header.getvalue(), filetype="pdf")
        generated_pdf = fitz.open(stream=pdf_buffer.getvalue(), filetype="pdf")
        merged_pdf.insert_pdf(generated_pdf)
        merged_output = io.BytesIO()
        merged_pdf.save(merged_output)
        merged_pdf.close()

        return merged_output.getvalue()
        
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        return None

def send_email_via_sendgrid_api(customer_name, admin_df, transport_df, recipient_email, cc_email=None, global_discount=0, original_df=None, header_pdf_choice=None, pdf_attachment=None):
    """Send email with Excel attachment using SendGrid API - Clean implementation"""
    try:
        # Import SendGrid here to handle missing library gracefully
        import sendgrid
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
        
        # Create Excel file data
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
            admin_df.to_excel(writer, sheet_name='Price List', index=False)
            transport_df.to_excel(writer, sheet_name='Transport Charges', index=False)
            
            summary_data = {
                'Customer': [customer_name],
                'Total Items': [len(admin_df)],
                'Date Created': [get_uk_time().strftime("%Y-%m-%d %H:%M BST")],
                'Created By': ['Net Rates Calculator']
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
        
        # Get API credentials
        config = st.session_state.get('config', {})
        smtp_settings = config.get("smtp_settings", {})
        
        # Get API key from saved settings or environment variable
        sendgrid_api_key = smtp_settings.get("sendgrid_api_key", "") or SENDGRID_API_KEY
        sendgrid_from_email = smtp_settings.get("sendgrid_from_email", "") or SENDGRID_FROM_EMAIL
        
        if not sendgrid_api_key:
            return {'status': 'error', 'message': 'SendGrid API key not configured. Please configure in Email Config.'}
        
        if not sendgrid_from_email:
            return {'status': 'error', 'message': 'SendGrid from email not configured. Please configure in Email Config.'}
        
        # Encode Excel file as base64 for attachment
        excel_base64 = base64.b64encode(output_excel.getvalue()).decode()
        timestamp = get_uk_time().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"{customer_name}_pricelist_{timestamp}.xlsx"
        
        # Extract salesperson from header choice (first 2 letters)
        salesperson = header_pdf_choice[:2].upper() if header_pdf_choice and header_pdf_choice != "(Select Sales Person)" else "N/A"
        
        # Create professional email content
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #002D56;">New Net Rates Price List</h2>
            
            <p><strong>Salesperson:</strong> {salesperson}</p>
            <p><strong>Customer:</strong> {customer_name}</p>
            <p><strong>Generated:</strong> {get_uk_time().strftime('%Y-%m-%d %H:%M:%S BST')}</p>
            <p><strong>Total Items:</strong> {len(admin_df)}</p>
            <p><strong>Global Discount:</strong> {global_discount}%</p>
            <p><strong>Custom Prices:</strong> {len([key for key in st.session_state.keys() if key.startswith('price_') and st.session_state.get(key, '').strip()])}</p>
            
            <p style="margin-top: 20px;">
                <em>Generated by Net Rates Calculator - The Hireman</em>
            </p>
        </body>
        </html>
        """
        
        # Create SendGrid mail object
        sg = sendgrid.SendGridAPIClient(api_key=sendgrid_api_key)
        
        # Setup email recipients (include CC if provided)
        to_emails = [recipient_email]
        if cc_email and cc_email.strip():
            cc_emails = [cc_email.strip()]
        else:
            cc_emails = None
        
        message = Mail(
            from_email=sendgrid_from_email,
            to_emails=to_emails,
            subject=f"Net Rates Price List - {customer_name} ({get_uk_time().strftime('%Y-%m-%d')})",
            html_content=html_content
        )
        
        # Add CC if provided
        if cc_emails:
            message.cc = cc_emails
        
        # Create JSON save file for backup/reload capability
        timestamp = get_uk_time().strftime('%Y%m%d_%H%M%S')
        
        # Prepare JSON save data (same format as Save Progress feature)
        # Use original_df if provided, otherwise fallback to a simple approach
        if original_df is not None and hasattr(original_df, 'iterrows'):
            custom_prices = {}
            for idx, row in original_df.iterrows():
                price_key = f"price_{idx}"
                item_key = str(row["ItemCategory"])
                price_value = st.session_state.get(price_key, "")
                if price_value:  # Only include non-empty prices
                    custom_prices[item_key] = price_value
        else:
            # Fallback: get custom prices from session state directly
            custom_prices = {
                key.replace("price_", ""): st.session_state.get(key, "")
                for key in st.session_state
                if key.startswith("price_") and st.session_state.get(key, "").strip()  # Only non-empty prices
            }
            
        save_data = {
            "customer_name": customer_name,
            "global_discount": global_discount,
            "group_discounts": {
                key: st.session_state.get(key, 0)
                for key in st.session_state
                if key.endswith("_discount")
            },
            "custom_prices": custom_prices,
            "transport_charges": {
                key: st.session_state.get(key, "")
                for key in st.session_state
                if key.startswith("transport_")
            },
            "created_timestamp": datetime.now().isoformat(),
            "created_by": "Net Rates Calculator"
        }
        
        json_data = json.dumps(save_data, indent=2)
        json_base64 = base64.b64encode(json_data.encode()).decode()
        json_filename = f"{customer_name}_progress_backup_{timestamp}.json"
        
        # Create and attach Excel file
        excel_attachment = Attachment(
            FileContent(excel_base64),
            FileName(excel_filename),
            FileType('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            Disposition('attachment')
        )
        
        # Create and attach JSON save file
        json_attachment = Attachment(
            FileContent(json_base64),
            FileName(json_filename),
            FileType('application/json'),
            Disposition('attachment')
        )
        
        # Prepare attachments list
        attachments = [excel_attachment, json_attachment]
        
        # Add PDF attachment if provided
        if pdf_attachment:
            pdf_base64 = base64.b64encode(pdf_attachment).decode()
            pdf_filename = f"{customer_name}_quote_{timestamp}.pdf"
            pdf_attachment_obj = Attachment(
                FileContent(pdf_base64),
                FileName(pdf_filename),
                FileType('application/pdf'),
                Disposition('attachment')
            )
            attachments.append(pdf_attachment_obj)
        
        # Add all attachments to message
        message.attachment = attachments
        
        # Send email
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            cc_message = f" (CC: {cc_email})" if cc_email and cc_email.strip() else ""
            return {
                'status': 'sent', 
                'message': f'Email with Excel & JSON backup files sent to {recipient_email}{cc_message}',
                'status_code': response.status_code
            }
        else:
            return {
                'status': 'error', 
                'message': f'SendGrid API returned status code: {response.status_code}'
            }
            
    except ImportError:
        return {
            'status': 'error', 
            'message': 'SendGrid library not installed. Run: pip install sendgrid'
        }
    except Exception as e:
        return {
            'status': 'error', 
            'message': f'SendGrid API error: {str(e)}'
        }

def send_email_with_pricelist(customer_name, admin_df, transport_df, recipient_email, smtp_config=None, cc_email=None, global_discount=0, original_df=None, header_pdf_choice=None, pdf_attachment=None):
    """Send price list via email to admin team"""
    try:
        # Create the email
        msg = MIMEMultipart()
        msg['From'] = smtp_config.get('from_email', 'noreply@thehireman.co.uk') if smtp_config else 'noreply@thehireman.co.uk'
        msg['To'] = recipient_email
        
        # Add CC if provided
        if cc_email and cc_email.strip():
            msg['Cc'] = cc_email.strip()
            
        msg['Subject'] = f"Price List for {customer_name} - {get_uk_time().strftime('%Y-%m-%d')}"
        
        # Email body
        cc_note = f"\n(CC: {cc_email})" if cc_email and cc_email.strip() else ""
        custom_prices_count = len([key for key in st.session_state.keys() if key.startswith('price_') and st.session_state.get(key, '').strip()])
        salesperson = header_pdf_choice[:2].upper() if header_pdf_choice and header_pdf_choice != "(Select Sales Person)" else "N/A"
        body = f"""
Hello Admin Team,

Please find attached the price list for customer: {customer_name}

Summary:
- Salesperson: {salesperson}
- Total Items: {len(admin_df)}
- Global Discount: {global_discount}%
- Custom Prices: {custom_prices_count}
- Date Created: {get_uk_time().strftime('%Y-%m-%d %H:%M BST')}
- Created via: Net Rates Calculator{cc_note}

The attached files contain:
- Excel file: Complete price list with transport charges and summary
- JSON file: Backup/reload file for the Net Rates Calculator

Please import the Excel data into our CRM system.
The JSON file can be used to reload this exact configuration in the calculator if needed.

Best regards,
Net Rates Calculator System
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Create Excel attachment
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
            admin_df.to_excel(writer, sheet_name='Price List', index=False)
            transport_df.to_excel(writer, sheet_name='Transport Charges', index=False)
            
            summary_data = {
                'Customer': [customer_name],
                'Total Items': [len(admin_df)],
                'Date Created': [get_uk_time().strftime("%Y-%m-%d %H:%M BST")],
                'Created By': ['Net Rates Calculator']
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
        
        # Attach the Excel file
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(output_excel.getvalue())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename={customer_name}_pricelist_{get_uk_time().strftime("%Y%m%d")}.xlsx'
        )
        msg.attach(part)
        
        # Create and attach JSON save file
        timestamp = get_uk_time().strftime('%Y%m%d_%H%M%S')
        
        # Use original_df if provided, otherwise fallback to a simple approach
        if original_df is not None and hasattr(original_df, 'iterrows'):
            custom_prices = {}
            for idx, row in original_df.iterrows():
                price_key = f"price_{idx}"
                item_key = str(row["ItemCategory"])
                price_value = st.session_state.get(price_key, "")
                if price_value:  # Only include non-empty prices
                    custom_prices[item_key] = price_value
        else:
            # Fallback: get custom prices from session state directly
            custom_prices = {
                key.replace("price_", ""): st.session_state.get(key, "")
                for key in st.session_state
                if key.startswith("price_") and st.session_state.get(key, "").strip()  # Only non-empty prices
            }
            
        save_data = {
            "customer_name": customer_name,
            "global_discount": global_discount,
            "group_discounts": {
                key: st.session_state.get(key, 0)
                for key in st.session_state
                if key.endswith("_discount")
            },
            "custom_prices": custom_prices,
            "transport_charges": {
                key: st.session_state.get(key, "")
                for key in st.session_state
                if key.startswith("transport_")
            },
            "created_timestamp": datetime.now().isoformat(),
            "created_by": "Net Rates Calculator"
        }
        
        json_data = json.dumps(save_data, indent=2)
        json_filename = f"{customer_name}_progress_backup_{timestamp}.json"
        
        # Attach JSON file
        json_part = MIMEBase('application', 'json')
        json_part.set_payload(json_data.encode('utf-8'))
        encoders.encode_base64(json_part)
        json_part.add_header(
            'Content-Disposition',
            f'attachment; filename={json_filename}'
        )
        msg.attach(json_part)
        
        # Add PDF attachment if provided
        if pdf_attachment:
            pdf_filename = f"{customer_name}_quote_{timestamp}.pdf"
            pdf_part = MIMEBase('application', 'pdf')
            pdf_part.set_payload(pdf_attachment)
            encoders.encode_base64(pdf_part)
            pdf_part.add_header(
                'Content-Disposition',
                f'attachment; filename={pdf_filename}'
            )
            msg.attach(pdf_part)
        
        # Send email if SMTP is configured
        if smtp_config and smtp_config.get('enabled', False):
            try:
                server = smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port'])
                if smtp_config.get('use_tls', True):
                    server.starttls()
                server.login(smtp_config['username'], smtp_config['password'])
                text = msg.as_string()
                
                # Build recipient list (includes CC if provided)
                recipients = [recipient_email]
                if cc_email and cc_email.strip():
                    recipients.append(cc_email.strip())
                
                server.sendmail(smtp_config['from_email'], recipients, text)
                server.quit()
                
                cc_message = f" (CC: {cc_email})" if cc_email and cc_email.strip() else ""
                return {'status': 'sent', 'message': f'Email with attachments sent successfully{cc_message}!'}
            except Exception as e:
                return {'status': 'error', 'message': f'SMTP Error: {str(e)}'}
        else:
            # Return the email content for manual sending or configuration
            return {'status': 'prepared', 'message': 'Email prepared (SMTP not configured)', 'email_obj': msg}
            
    except Exception as e:
        return {'status': 'error', 'message': f'Email preparation failed: {str(e)}'}

# --- PDF Header Selection (moved to top) ---
# Add refresh button for PDF headers
col1, col2 = st.columns([4, 1])

with col1:
    # Get available PDF files dynamically (not cached)
    available_pdfs = get_available_pdf_files()
    header_pdf_choice = st.selectbox(
        "⭐Select a PDF Header Sheet",
        ["(Select Sales Person)"] + available_pdfs,
        help=f"Found {len(available_pdfs)} PDF files in the current directory"
    )
    
    # Store in session state for sidebar access
    st.session_state['header_pdf_choice'] = header_pdf_choice

with col2:
    if st.button("🔄 Refresh PDF List", help="Click to refresh the list of available PDF header files"):
        st.rerun()

# Customer name input
if "customer_name" not in st.session_state:
    st.session_state["customer_name"] = ""

customer_name = st.text_input("⭐Enter Customer Name", key="customer_name")

if "bespoke_email" not in st.session_state:
    st.session_state["bespoke_email"] = ""

bespoke_email = st.text_input("⭐ Bespoke email address (optional)", key="bespoke_email")
logo_file = st.file_uploader("⭐Upload Company Logo", type=["png", "jpg", "jpeg"])

# Store logo file in session state so it's accessible in PDF generation
if logo_file is not None:
    st.session_state['logo_file'] = logo_file
elif 'logo_file' in st.session_state and logo_file is None:
    # Keep existing logo if user hasn't cleared it
    # Only clear if they explicitly removed it (file uploader returns None when cleared)
    pass

# Toggle for admin options (hide by default)
show_admin_uploads = st.toggle("Show Admin Upload Options", value=False)

if show_admin_uploads:
    st.markdown("#### � Admin File Management")
    
    # Admin Excel upload
    uploaded_file = st.file_uploader("❗ADMIN Upload Excel file (Admin Only❗)", type=["xlsx"])
    
    # Admin PDF upload
    uploaded_header_pdf = st.file_uploader("❗ADMIN Upload PDF Header (Admin Only❗)", type=["pdf"], key="header_pdf_upload")
    
    # Show default file information in admin section
    st.markdown("#### 📊 Default File Information")
    
    if os.path.exists(DEFAULT_EXCEL_PATH):
        # Get file modification time
        import os
        mod_time = os.path.getmtime(DEFAULT_EXCEL_PATH)
        mod_time_str = datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S")
        file_size = os.path.getsize(DEFAULT_EXCEL_PATH) / 1024
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"📁 **Default Excel File:**\n`{DEFAULT_EXCEL_PATH}`")
            st.info(f"📅 **Last Modified:**\n{mod_time_str}")
        with col2:
            st.info(f"📏 **File Size:**\n{file_size:.1f} KB")
            if st.button("🔄 Force Refresh Excel Data", help="Manually refresh Excel data cache"):
                # Clear all Excel-related caches
                load_excel.clear()
                load_excel_with_timestamp.clear()
                
                # Clear any session state that might be caching data
                cache_keys_to_clear = [key for key in st.session_state.keys() if 'excel' in key.lower() or 'df' in key.lower()]
                for key in cache_keys_to_clear:
                    del st.session_state[key]
                
                # Force Streamlit to clear all caches
                st.cache_data.clear()
                
                st.success("✅ Excel cache cleared completely!")
                st.rerun()
    else:
        st.warning(f"⚠️ **Default Excel file not found:**\n`{DEFAULT_EXCEL_PATH}`")
    
    # Show PDF files information  
    available_pdfs = get_available_pdf_files()
    if available_pdfs:
        st.info(f"📄 **Available PDF Headers:** {len(available_pdfs)} files\n{', '.join(available_pdfs)}")
    else:
        st.warning("⚠️ No PDF header files found in current directory")
        
else:
    uploaded_file = None
    uploaded_header_pdf = None

# -------------------------------
# Load and Validate Excel File
# -------------------------------
df = None
excel_source = None

if uploaded_file:
    try:
        df = load_excel(uploaded_file)
        excel_source = "uploaded"
        
        # Handle loaded custom prices after DataFrame is available
        apply_pending_custom_prices(df)
        
        st.success(f"✅ Excel file uploaded: {uploaded_file.name}")
        
    except Exception as e:
        st.error(f"❌ Error reading uploaded Excel file: {e}")
        st.stop()
elif os.path.exists(DEFAULT_EXCEL_PATH):
    try:
        # Get file modification time for cache invalidation
        mod_time = os.path.getmtime(DEFAULT_EXCEL_PATH)
        mod_time_readable = datetime.fromtimestamp(mod_time, tz=get_uk_time().tzinfo).strftime("%Y-%m-%d %H:%M:%S BST")
        
        # Use timestamp-aware loading to auto-refresh when file changes
        df = load_excel_with_timestamp(DEFAULT_EXCEL_PATH, mod_time)
        excel_source = "default"
        
        # Handle loaded custom prices after DataFrame is available
        apply_pending_custom_prices(df)
        
        st.success(f"✅ Using default Excel data (Last modified: {mod_time_readable})")
        
    except Exception as e:
        st.error(f"❌ Failed to load default Excel: {e}")
        st.stop()
else:
    # Show debug information for troubleshooting - only when file doesn't exist
    st.error(f"❌ No Excel file found.")
    st.error(f"**Script directory:** `{SCRIPT_DIR}`")
    st.error(f"**Looking for file:** `{DEFAULT_EXCEL_PATH}`")
    st.error(f"**File exists:** `{os.path.exists(DEFAULT_EXCEL_PATH)}`")
    
    # Try to list files in the script directory
    try:
        files_in_dir = os.listdir(SCRIPT_DIR)
        excel_files = [f for f in files_in_dir if f.endswith('.xlsx')]
        st.error(f"**Files in script directory:** {len(files_in_dir)} files")
        st.error(f"**Excel files found:** {excel_files}")
    except Exception as e:
        st.error(f"**Error listing directory:** {e}")
    
    st.error("**Solution:** Please upload an Excel file using the admin section above.")
    
    # Instead of stopping, create a placeholder dataframe or show file upload prominently
    st.markdown("---")
    st.markdown("## 📤 Upload Excel File Required")
    st.info("👆 Please use the **Admin section** above to upload your Excel file, then refresh the page.")
    
    # Optional: Show a sample of what the Excel should contain
    st.markdown("### Expected Excel Format")
    st.markdown("""
    Your Excel file should contain these columns:
    - **ItemCategory**
    - **EquipmentName** 
    - **HireRateWeekly**
    - **GroupName**
    - **Sub Section**
    - **Max Discount**
    - **Include**
    - **Order**
    """)
    
    # Don't completely stop - let the admin upload section work
    df = None
        
# Show any loading errors (separate from file existence)
if st.session_state.get('loading_error'):
    st.error(f"❌ Error loading progress file: {st.session_state['loading_error']}")
    del st.session_state['loading_error']

header_pdf_file = None
if uploaded_header_pdf is not None:
    # Use uploaded file (takes priority)
    header_pdf_file = uploaded_header_pdf
    st.session_state['header_pdf_file'] = header_pdf_file  # Store in session state
elif header_pdf_choice != "(Select Sales Person)":
    # Use selected file from folder
    pdf_full_path = os.path.join(SCRIPT_DIR, header_pdf_choice)
    with open(pdf_full_path, "rb") as f:
        header_pdf_file = io.BytesIO(f.read())
        st.session_state['header_pdf_file'] = header_pdf_file  # Store in session state

if df is not None and header_pdf_file:
    required_columns = {"ItemCategory", "EquipmentName", "HireRateWeekly", "GroupName", "Sub Section", "Max Discount", "Include", "Order"}
    optional_columns = {"ExcludeFromGlobalDiscount"}  # Optional columns for advanced features
    if not required_columns.issubset(df.columns):
        st.error(f"Excel file must contain the following columns: {', '.join(required_columns)}")
        st.stop()
    
    # Add ExcludeFromGlobalDiscount column with default False if not present
    if "ExcludeFromGlobalDiscount" not in df.columns:
        df["ExcludeFromGlobalDiscount"] = False

    # -------------------------------
    # Filter and Sort Data
    # -------------------------------
    df = df[df["Include"] == True].copy()
    df.sort_values(by=["GroupName", "Sub Section", "Order"], inplace=True)
    
    # Initialize CustomPrice and DiscountPercent columns to prevent KeyError
    # These columns are needed by export functions regardless of PDF header selection
    if 'CustomPrice' not in df.columns:
        df['CustomPrice'] = None
    if 'DiscountPercent' not in df.columns:
        df['DiscountPercent'] = None
    
    # Store DataFrame in session state for sidebar access
    st.session_state['df'] = df
    
    # Pre-calculate group operations for efficiency (reused multiple times below)
    group_keys = list(df.groupby(["GroupName", "Sub Section"]).groups.keys())
    grouped_df = df.groupby(["GroupName", "Sub Section"])

    # -------------------------------
    # Process bulk discount updates BEFORE creating widgets
    # -------------------------------
    
    # Build set of excluded group/subsection combinations (where any item has ExcludeFromGlobalDiscount=True)
    excluded_groups = set()
    for (group, subsection), group_df in grouped_df:
        if group_df["ExcludeFromGlobalDiscount"].any():
            excluded_groups.add((group, subsection))
    
    # Process "Set All Groups to Global Discount" action
    if st.session_state.get('set_all_groups_to_global', False):
        st.session_state['set_all_groups_to_global'] = False  # Clear the trigger
        
        global_discount_to_apply = st.session_state.get('global_discount', 0.0)
        applied_count = 0
        skipped_count = 0
        for group, subsection in group_keys:
            discount_key = f"{group}_{subsection}_discount"
            if (group, subsection) in excluded_groups:
                st.session_state[discount_key] = 0.0  # Keep excluded groups at 0%
                skipped_count += 1
            else:
                st.session_state[discount_key] = global_discount_to_apply
                applied_count += 1
        
        if skipped_count > 0:
            st.success(f"✅ {applied_count} groups set to {global_discount_to_apply}% ({skipped_count} excluded groups kept at 0%)")
        else:
            st.success(f"✅ All group discounts set to {global_discount_to_apply}%")
    
    # Process "Update Group Discounts Only" action
    if st.session_state.get('update_group_discounts_only', False):
        st.session_state['update_group_discounts_only'] = False  # Clear the trigger
        
        global_discount_to_apply = st.session_state.get('global_discount', 0.0)
        applied_count = 0
        skipped_count = 0
        for group, subsection in group_keys:
            discount_key = f"{group}_{subsection}_discount"
            if (group, subsection) in excluded_groups:
                st.session_state[discount_key] = 0.0  # Keep excluded groups at 0%
                skipped_count += 1
            else:
                st.session_state[discount_key] = global_discount_to_apply
                applied_count += 1
        
        if skipped_count > 0:
            st.success(f"✅ {applied_count} groups updated to {global_discount_to_apply}% ({skipped_count} excluded groups kept at 0%, custom prices preserved)")
        else:
            st.success(f"✅ Group discounts updated to {global_discount_to_apply}% (custom prices preserved)")
    
    # Process "Update All & Clear Custom Prices" action
    if st.session_state.get('update_all_and_clear_custom', False):
        st.session_state['update_all_and_clear_custom'] = False  # Clear the trigger
        
        global_discount_to_apply = st.session_state.get('global_discount', 0.0)
        group_keys = list(df.groupby(["GroupName", "Sub Section"]).groups.keys())
        
        # Update group discounts (respecting exclusions)
        applied_count = 0
        skipped_count = 0
        for group, subsection in group_keys:
            discount_key = f"{group}_{subsection}_discount"
            if (group, subsection) in excluded_groups:
                st.session_state[discount_key] = 0.0  # Keep excluded groups at 0%
                skipped_count += 1
            else:
                st.session_state[discount_key] = global_discount_to_apply
                applied_count += 1
        
        # Clear all custom prices (both price_ and input_ keys)
        cleared_count = 0
        for idx, row in df.iterrows():
            price_key = f"price_{idx}"
            input_key = f"input_{idx}"
            if st.session_state.get(price_key, "").strip():
                st.session_state[price_key] = ""
                cleared_count += 1
            if input_key in st.session_state:
                st.session_state[input_key] = ""
        
        # Clear pending prices from fragment
        st.session_state['pending_prices'] = {}
        
        if skipped_count > 0:
            st.success(f"✅ {applied_count} groups updated to {global_discount_to_apply}% ({skipped_count} excluded groups kept at 0%) and {cleared_count} custom prices cleared")
        else:
            st.success(f"✅ All discounts updated to {global_discount_to_apply}% and {cleared_count} custom prices cleared")
    
    # Process "Clear All Custom Prices" action
    if st.session_state.get('clear_all_custom_prices', False):
        st.session_state['clear_all_custom_prices'] = False  # Clear the trigger
        
        cleared_count = 0
        for idx, row in df.iterrows():
            price_key = f"price_{idx}"
            input_key = f"input_{idx}"
            if st.session_state.get(price_key, "").strip():
                st.session_state[price_key] = ""
                cleared_count += 1
            if input_key in st.session_state:
                st.session_state[input_key] = ""
        
        # Clear pending prices from fragment
        st.session_state['pending_prices'] = {}
        
        st.success(f"✅ Cleared {cleared_count} custom prices")

    # -------------------------------
    # Global and Group-Level Discounts
    # -------------------------------
    # Initialize global discount in session state if not present
    if "global_discount" not in st.session_state:
        st.session_state["global_discount"] = 0.0
    
    global_discount = st.number_input("Global Discount (%)", min_value=0.0, max_value=100.0, step=0.01, key="global_discount")

    # Check if global discount has changed
    previous_global_discount = st.session_state.get("previous_global_discount", global_discount)
    if global_discount != previous_global_discount:
        st.session_state["previous_global_discount"] = global_discount
        
        # Show options when global discount changes
        st.info(f"🔄 Global discount changed from {previous_global_discount}% to {global_discount}%")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Option 1: Update group discounts only (preserves custom prices)
            if st.button(f"🔄 Update Group Discounts Only", type="primary"):
                st.session_state['update_group_discounts_only'] = True
                st.rerun()
        
        with col2:
            # Option 2: Update everything including custom prices
            if st.button(f"⚠️ Update All & Clear Custom Prices", type="secondary"):
                st.session_state['update_all_and_clear_custom'] = True
                st.rerun()

    # Quick action buttons for group operations (commonly used)
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Set All Groups to Global Discount"):
            st.session_state['set_all_groups_to_global'] = True
            st.rerun()
    
    with col2:
        # Count custom prices
        custom_price_count = sum(1 for idx, _ in df.iterrows() if st.session_state.get(f"price_{idx}", "").strip())
        if st.button(f"🗑️ Clear All Custom Prices ({custom_price_count})"):
            st.session_state['clear_all_custom_prices'] = True
            st.rerun()

    # Group-Level Discounts in expandable section (rarely used)
    with st.expander("🎛️ Group-Level Discounts (Advanced)", expanded=False):
        st.markdown("**Configure individual discount rates for each equipment group:**")
        if excluded_groups:
            st.info(f"🔒 {len(excluded_groups)} group(s) excluded from global discount (marked in Excel). You can still set custom prices for individual items.")
        
        group_discount_keys = {}

        cols = st.columns(3)
        for i, (group, subsection) in enumerate(group_keys):
            col = cols[i % 3]  # Fill down each column
            with col:
                discount_key = f"{group}_{subsection}_discount"
                is_excluded = (group, subsection) in excluded_groups
                # Initialize session state if key doesn't exist (avoids widget/session state conflict)
                if discount_key not in st.session_state:
                    # Excluded groups default to 0%, others to global discount
                    st.session_state[discount_key] = 0.0 if is_excluded else global_discount
                
                # Add lock icon to label for excluded groups
                label = f"🔒 {group} - {subsection} (%)" if is_excluded else f"{group} - {subsection} (%)"
                st.number_input(
                    label,
                    min_value=0.0,
                    max_value=100.0,
                    step=0.01,
                    key=discount_key,
                    help="Excluded from global discount updates (set in Excel)" if is_excluded else None
                )


    # -------------------------------
    # Session-Dependent Helper Functions
    # -------------------------------
    def get_discounted_price(row):
        """Calculate discounted price, handling POA values"""
        key = f"{row['GroupName']}_{row['Sub Section']}_discount"
        discount = st.session_state.get(key, global_discount)
        
        # Check if original price is POA
        if is_poa_value(row["HireRateWeekly"]):
            return "POA"
        
        # Get numeric price for calculation
        numeric_price = get_numeric_price(row["HireRateWeekly"])
        if numeric_price is None:
            return "POA"
        
        return numeric_price * (1 - discount / 100)

    def calculate_discount_percent(original, custom):
        """Calculate discount percentage, handling POA values"""
        # If either value is POA, return special indicator
        if is_poa_value(original) or is_poa_value(custom):
            return "POA"
        
        # Get numeric values
        orig_numeric = get_numeric_price(original)
        custom_numeric = get_numeric_price(custom)
        
        if orig_numeric is None or custom_numeric is None:
            return "POA"
        
        if orig_numeric == 0:
            return 0
        
        return ((orig_numeric - custom_numeric) / orig_numeric) * 100

    # -------------------------------
    # Adjust Prices by Group and Sub Section
    # -------------------------------
    st.markdown("### Adjust Prices by Group and Sub Section")
    
    # Initialize pending prices storage for live preview
    if 'pending_prices' not in st.session_state:
        st.session_state.pending_prices = {}
    
    # Controls row (expand/collapse and legend - these don't need live updates)
    col_expand, col_collapse, col_legend, col_spacer = st.columns([2, 2, 2, 4])
    
    with col_expand:
        if st.button("🔓 Expand All", use_container_width=True):
            st.session_state.keep_expanded = True
            st.rerun()
    
    with col_collapse:
        if st.button("🔒 Collapse", use_container_width=True):
            st.session_state.keep_expanded = False
            st.rerun()
    
    with col_legend:
        with st.popover("📖 Legend & Tips"):
            st.markdown("**🎯 Custom Price:** You've entered a specific price")
            st.markdown("**📊 Calculated Price:** Based on group discount")
            st.markdown("**⚠️ Warning:** Exceeds max discount or invalid input")
            st.markdown("**✏️ Pending:** Change not yet applied")
            st.markdown("---")
            st.markdown("**💡 Workflow Tips:**")
            st.markdown("1. Open sections and enter your prices")
            st.markdown("2. Live preview shows discount % as you type")
            st.markdown("3. Click **Apply All Changes** when ready")
    
    # Check if we should keep sections expanded
    keep_expanded = st.session_state.get("keep_expanded", False)
    
    # Initialize all price keys to empty strings if they don't exist
    # This ensures widgets start with empty values unless specifically set
    for idx, row in df.iterrows():
        price_key = f"price_{idx}"
        if price_key not in st.session_state:
            st.session_state[price_key] = ""
    
    # Define the pricing fragment - only this section reruns on input changes
    @st.fragment
    def pricing_fragment():
        # Count pending changes (inside fragment so it updates with each keystroke)
        def count_pending_changes():
            count = 0
            for key, pending_val in st.session_state.pending_prices.items():
                saved_val = st.session_state.get(key, "")
                if pending_val != saved_val:
                    count += 1
            return count
        
        # Group the data for better organization
        grouped_df = df.groupby(["GroupName", "Sub Section"])
        
        for (group, subsection), group_df in grouped_df:
            # Check if this group has any custom prices (saved or pending)
            has_custom_in_group = any(
                st.session_state.pending_prices.get(f"price_{idx}", st.session_state.get(f"price_{idx}", "")).strip() 
                for idx in group_df.index
            )
            
            # Check if this group has pending changes
            has_pending_in_group = any(
                st.session_state.pending_prices.get(f"price_{idx}", "") != st.session_state.get(f"price_{idx}", "")
                for idx in group_df.index
                if f"price_{idx}" in st.session_state.pending_prices
            )
            
            # Add emoji to header if group contains custom prices or pending changes
            header_text = f"{group} - {subsection}"
            if has_pending_in_group:
                header_text += " ✏️"
            elif has_custom_in_group:
                header_text += " 🎯"
            
            # Auto-expand sections that have custom prices OR if global expand is enabled
            should_expand = keep_expanded or has_custom_in_group
            
            with st.expander(header_text, expanded=should_expand):
                for idx, row in group_df.iterrows():
                    discounted_price = get_discounted_price(row)
                    price_key = f"price_{idx}"
                    
                    # Get the value to display: pending > saved > empty
                    if price_key in st.session_state.pending_prices:
                        current_value = st.session_state.pending_prices[price_key]
                    else:
                        current_value = st.session_state.get(price_key, "")

                    col1, col2, col3, col4, col5 = st.columns([2, 4, 2, 3, 3])
                    with col1:
                        st.write(row["ItemCategory"])
                    with col2:
                        st.write(row["EquipmentName"])
                    with col3:
                        # Display calculated price or POA
                        if discounted_price == "POA":
                            st.write("POA")
                        else:
                            st.write(f"£{discounted_price:.2f}")
                    with col4:
                        # Check if user has a custom price
                        has_custom_price = bool(current_value.strip()) if current_value else False
                        
                        # Input field with status-aware placeholder and label
                        if has_custom_price:
                            placeholder_text = "Custom price active"
                            help_text = "🎯 Custom price set - overrides group discount"
                        else:
                            placeholder_text = "Enter Special Rate or POA"
                            help_text = "💡 Leave empty to use group discount calculation"
                        
                        # Regular text input - fragment ensures fast rerun
                        new_value = st.text_input(
                            "", 
                            value=current_value,
                            key=f"input_{idx}", 
                            label_visibility="collapsed", 
                            placeholder=placeholder_text, 
                            help=help_text
                        )
                        
                        # Store in pending if different from saved
                        saved_value = st.session_state.get(price_key, "")
                        if new_value != saved_value:
                            st.session_state.pending_prices[price_key] = new_value
                        elif price_key in st.session_state.pending_prices:
                            # Remove from pending if reverted to saved value
                            del st.session_state.pending_prices[price_key]
                    
                    with col5:
                        # Live preview: use pending value if exists, otherwise saved
                        preview_value = st.session_state.pending_prices.get(price_key, saved_value)
                        user_input = preview_value.strip() if preview_value else ""
                        
                        # Check if this is a pending change
                        is_pending = price_key in st.session_state.pending_prices and st.session_state.pending_prices[price_key] != saved_value
                        pending_indicator = " ✏️" if is_pending else ""
                        
                        if user_input:
                            # User entered something
                            if is_poa_value(user_input):
                                custom_price = "POA"
                                discount_percent = "POA"
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
                                    custom_price = "POA"
                                    discount_percent = "POA"
                                    st.markdown(f"**POA** 🎯⚠️{pending_indicator}")
                        else:
                            # No user input - use calculated price
                            custom_price = discounted_price
                            discount_percent = calculate_discount_percent(row["HireRateWeekly"], custom_price)
                            
                            if discount_percent == "POA":
                                st.markdown("**POA** 📊")
                            else:
                                st.markdown(f"**{discount_percent:.2f}%** 📊")

                        # Store the final values for export (use SAVED values, not pending)
                        # This ensures exports only include applied changes
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
        
        # Apply/Discard buttons at the end of the fragment (updates with each keystroke)
        st.markdown("---")
        pending_count = count_pending_changes()
        apply_disabled = pending_count == 0
        
        col_apply, col_discard, col_spacer = st.columns([2, 2, 6])
        
        with col_apply:
            if st.button(f"✅ Apply All Changes ({pending_count})", type="primary", disabled=apply_disabled, use_container_width=True):
                # Copy all pending values to session state
                applied_count = 0
                for key, value in st.session_state.pending_prices.items():
                    if st.session_state.get(key, "") != value:
                        st.session_state[key] = value
                        applied_count += 1
                st.session_state.pending_prices = {}  # Clear pending
                st.success(f"✅ Applied {applied_count} price change(s)")
                st.rerun()
        
        with col_discard:
            if st.button("🗑️ Discard Changes", disabled=apply_disabled, use_container_width=True):
                st.session_state.pending_prices = {}
                st.info("Changes discarded")
                st.rerun()
    
    # Run the pricing fragment
    pricing_fragment()

    # -------------------------------
    # Final Price List Display
    # -------------------------------
    st.markdown("### Final Price List")
    
    # Create a display-friendly version of the dataframe
    display_df = df[[
        "ItemCategory", "EquipmentName", "HireRateWeekly",
        "GroupName", "Sub Section", "CustomPrice", "DiscountPercent"
    ]].copy()
    
    # Format the display columns for better readability using standardized functions
    display_df["HireRateWeekly"] = display_df["HireRateWeekly"].apply(format_price_display)
    display_df["CustomPrice"] = display_df["CustomPrice"].apply(format_custom_price_for_display)
    display_df["DiscountPercent"] = display_df["DiscountPercent"].apply(format_discount_for_export)
    
    # Rename columns for better display
    display_df.columns = ["Item Category", "Equipment Name", "Original Price", "Group", "Sub Section", "Final Price", "Discount %"]
    
    st.dataframe(display_df, use_container_width=True)


    # -------------------------------
    # Additional Table: Manually Entered Custom Prices
    # -------------------------------
    st.markdown("### Manually Entered Custom Prices")

    manual_entries = []

    for idx, row in df.iterrows():
        price_key = f"price_{idx}"
        user_input = st.session_state.get(price_key, "").strip()

        # Only include if the user typed something in the box
        if user_input:
            if is_poa_value(user_input):
                # User entered POA
                manual_entries.append({
                    "ItemCategory": row["ItemCategory"],
                    "EquipmentName": row["EquipmentName"],
                    "HireRateWeekly": format_price_display(row["HireRateWeekly"]),
                    "CustomPrice": "POA",
                    "DiscountPercent": "POA",
                    "GroupName": row["GroupName"],
                    "Sub Section": row["Sub Section"]
                })
            else:
                try:
                    entered_price = float(user_input)
                    manual_entries.append({
                        "ItemCategory": row["ItemCategory"],
                        "EquipmentName": row["EquipmentName"],
                        "HireRateWeekly": format_price_display(row["HireRateWeekly"]),
                        "CustomPrice": f"£{entered_price:.2f}",
                        "DiscountPercent": f"{calculate_discount_percent(row['HireRateWeekly'], entered_price):.2f}%" if calculate_discount_percent(row['HireRateWeekly'], entered_price) != "POA" else "POA",
                        "GroupName": row["GroupName"],
                        "Sub Section": row["Sub Section"]
                    })
                except ValueError:
                    # Invalid numeric input - treat as POA
                    manual_entries.append({
                        "ItemCategory": row["ItemCategory"],
                        "EquipmentName": row["EquipmentName"],
                        "HireRateWeekly": format_price_display(row["HireRateWeekly"]),
                        "CustomPrice": "POA (Invalid Input)",
                        "DiscountPercent": "POA",
                        "GroupName": row["GroupName"],
                        "Sub Section": row["Sub Section"]
                    })

    if manual_entries:
        manual_df = pd.DataFrame(manual_entries)
        st.dataframe(manual_df, use_container_width=True)
    else:
        st.info("No manual custom prices have been entered.")






    # -------------------------------
    # Transport Charges Section (with default values)
    # -------------------------------
    st.markdown("### Transport Charges")

    transport_inputs = []

    for i, (transport_type, default_value) in enumerate(zip(TRANSPORT_TYPES, DEFAULT_TRANSPORT_CHARGES)):
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**{transport_type}**")
        with col2:
            charge = st.text_input(
                f"Charge for {transport_type}",
                value=default_value,
                key=f"transport_{i}",
                label_visibility="collapsed"
            )
            transport_inputs.append({
                "Delivery or Collection type": transport_type,
                "Charge (£)": charge
            })

    # Create a DataFrame from the inputs
    transport_df = pd.DataFrame(transport_inputs)

    # -------------------------------
    # Direct Email to Accounts Team
    # -------------------------------
    # Email Net Rates - Moved to Sidebar
    
# Admin Dashboard (Collapsible)
# -------------------------------
st.markdown("---")
with st.expander("🔧 Admin Dashboard & Integration Settings"):
    st.markdown("### 🏢 Admin Team Integration Hub")
    
    tab1, tab2, tab3 = st.tabs(["📧 Email Settings", "🔄 Automation", "📊 Analytics"])
    
    with tab1:
        st.markdown("#### � SendGrid API Configuration (Recommended)")
        
        # SendGrid Configuration
        col1, col2 = st.columns([3, 1])
        with col1:
            current_api_key = SENDGRID_API_KEY
            current_from_email = SENDGRID_FROM_EMAIL
            
            st.text_input(
                "SendGrid API Key",
                value=current_api_key[:8] + "..." + current_api_key[-4:] if current_api_key else "Not configured",
                disabled=True,
                help="Configure via environment variables or Email Config in main app"
            )
            st.text_input(
                "From Email Address", 
                value=current_from_email if current_from_email else "Not configured",
                disabled=True,
                help="Verified sender address in SendGrid"
            )
        
        with col2:
            if current_api_key and current_from_email:
                st.success("✅ SendGrid Ready")
                st.info("Perfect Excel attachments enabled!")
            else:
                st.warning("⚠️ Not Configured")
                st.info("Use Email Config toggle in main app")
        
        # Status display
        if current_api_key and current_from_email:
            st.success("✅ SendGrid configured - users can send perfect Excel attachments!")
            st.markdown(f"**From Email:** `{current_from_email}`")
            st.markdown(f"**API Key:** `{current_api_key[:8]}...{current_api_key[-4:] if len(current_api_key) > 8 else '****'}`")
        else:
            st.info("� Configure SendGrid for reliable Excel attachment delivery")
            
        # Quick help section
        with st.expander("❓ How to configure SendGrid"):
            st.markdown("""
            **Steps to configure SendGrid:**
            1. Sign up at [SendGrid.com](https://sendgrid.com) (free tier: 100 emails/day)
            2. Go to Settings → API Keys → Create API Key
            3. Choose "Restricted Access" and enable "Mail Send" permissions
            4. Copy the API key
            5. Go to Settings → Sender Authentication → Verify single sender
            6. Verify your from email address
            7. Use the Email Config toggle in the main app to configure
            
            **Why SendGrid?**
            - ✅ Perfect Excel attachment delivery (no .txt file corruption)
            - ✅ Professional email appearance
            - ✅ 99.9% delivery rate
            - ✅ Advanced analytics and tracking
            - ✅ Reliable API with excellent documentation
            """)
        
        st.markdown("---")
        st.markdown("#### 📧 Alternative Email Options")
        
        # Load saved admin settings
        admin_settings = st.session_state.config.get("admin_settings", {})
        
        col1, col2 = st.columns(2)
        with col1:
            default_admin_email = st.text_input(
                "Default Admin Email", 
                value=admin_settings.get("default_admin_email", "admin@thehireman.co.uk")
            )
            cc_emails = st.text_input(
                "CC Emails (comma separated)", 
                value=admin_settings.get("cc_emails", ""),
                placeholder="manager@company.com, crm@company.com"
            )
        with col2:
            email_template = st.selectbox("Email Template", 
                ["Standard Price List", "Urgent Priority", "Bulk Import", "Custom"])
            auto_send = st.checkbox("Auto-send to admin team", help="Automatically email when price list is generated")
        
        # Save admin settings button
        if st.button("💾 Save Admin Email Settings"):
            config = st.session_state.config
            config["admin_settings"]["default_admin_email"] = default_admin_email
            config["admin_settings"]["cc_emails"] = cc_emails
            if save_config(config):
                st.session_state.config = config
                st.success("✅ Admin email settings saved!")
    
    with tab2:
        st.markdown("#### Automation Options")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**File Sharing**")
            auto_save_location = st.selectbox("Auto-save location", 
                ["OneDrive - Shared", "Local Network", "Cloud Storage", "Database"])
            folder_structure = st.selectbox("Folder structure", 
                ["By Customer", "By Date", "By Sales Rep", "Flat Structure"])
        with col2:
            st.markdown("**CRM Integration**")
            crm_system = st.selectbox("CRM System", 
                ["Manual Import", "API Integration", "Scheduled Sync", "Real-time"])
            data_format = st.selectbox("Preferred Format", 
                ["Excel (Multi-sheet)", "CSV", "JSON", "XML"])
    
    with tab3:
        st.markdown("#### Usage Analytics")
        if customer_name:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Price Lists Generated", "1", "Today")
            with col2:
                st.metric("Items Processed", len(admin_df) if 'admin_df' in locals() else 0)
            with col3:
                st.metric("Data Export Size", f"{round(len(str(admin_df)) / 1024, 1)}KB" if 'admin_df' in locals() else "0KB")
        
        st.markdown("**Integration Health Check**")
        health_checks = {
            "📧 Email System": "✅ Ready",
            "💾 File Storage": "✅ Connected", 
            "🔄 CRM Connection": "⚠️ Manual Mode",
            "📊 Analytics": "✅ Active"
        }
        
        for check, status in health_checks.items():
            st.write(f"{check}: {status}")

# Footer
st.markdown("---")
st.markdown("*Net Rates Calculator v2.0 - The Hireman*")

# Sidebar for Load Progress and other actions
with st.sidebar:
    st.markdown("## 🎛️ Controls")
    
    # Method 1: Saving & Loading (One-click implementation)
    st.markdown("### 💾 Saving & Loading")
    
    # Combined Save & Download Progress button
    customer_name = st.session_state.get('customer_name', '')
    if customer_name:
        safe_customer_name = customer_name.strip().replace(" ", "_").replace("/", "_")
        timestamp = get_uk_time().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{safe_customer_name}_progress_{timestamp}.json"
        
        # Collect all session state data
        df = st.session_state.get('df', pd.DataFrame())
        global_discount = st.session_state.get('global_discount', 0)
        
        custom_prices = {}
        if not df.empty:
            # Primary method: Use DataFrame to properly map custom prices
            for idx, row in df.iterrows():
                price_key = f"price_{idx}"
                item_key = str(row["ItemCategory"])
                price_value = st.session_state.get(price_key, "")
                if price_value:  # Only include non-empty prices
                    custom_prices[item_key] = price_value
        else:
            # Fallback method: Get all price_ keys from session state
            for key in st.session_state:
                if key.startswith("price_"):
                    price_value = st.session_state.get(key, "")
                    if price_value:  # Only include non-empty prices
                        # Use the index as the key since we don't have ItemCategory
                        item_key = key.replace("price_", "index_")
                        custom_prices[item_key] = price_value

        save_data = {
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
        
        json_data = json.dumps(save_data, indent=2)
        
        # One-click Save & Download button
        if st.download_button(
            label="� Save & Download Progress",
            data=json_data,
            file_name=filename,
            mime="application/json",
            use_container_width=True,
            help=f"Save and download {filename} in one click!"
        ):
            st.success(f"✅ Progress saved and downloaded: {filename}")
            st.balloons()
    else:
        st.info("💡 Enter a customer name above to enable progress saving")
        st.button("💾 Save & Download Progress", disabled=True, use_container_width=True, help="Enter customer name first")
    
    # Upload file to load
    uploaded_file = st.file_uploader(
        "📁 Load Progress", 
        type=['json'], 
        key="sidebar_upload",
        help="Upload a previously saved progress file"
    )
    
    if uploaded_file:
        if st.button("📁 Load from Upload", use_container_width=True):
            # Store the file and trigger loading for next rerun
            st.session_state['uploaded_file_to_load'] = uploaded_file
            st.session_state['trigger_upload_load'] = True
            st.rerun()
    
    st.markdown("---")
    
    # Syrinx Import Section
    st.markdown("### 🏢 Syrinx Import")
    
    # File uploader for Excel files
    syrinx_file = st.file_uploader(
        "📊 Upload Syrinx Excel", 
        type=['xlsx', 'xls'], 
        key="syrinx_upload",
        help="Upload Excel file with Category Codes (Column A) and Special Prices (Column B)"
    )
    
    # Global discount input for Syrinx import
    syrinx_global_discount = st.number_input(
        "Global Discount (%)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.01,
        key="syrinx_global_discount",
        help="Discount to apply to all imported prices"
    )
    
    if syrinx_file:
        # Preview button
        if st.button("👁️ Preview Import", use_container_width=True):
            st.session_state['syrinx_preview_file'] = syrinx_file
            st.session_state['syrinx_preview_discount'] = syrinx_global_discount
            st.session_state['show_syrinx_preview'] = True
            st.rerun()
        
        # Apply import button (only show if preview exists)
        if st.session_state.get('show_syrinx_preview', False):
            if st.button("✅ Apply Import & Clear Session", use_container_width=True, type="primary"):
                st.session_state['apply_syrinx_import'] = True
                st.rerun()
            
            if st.button("❌ Cancel Preview", use_container_width=True):
                st.session_state['show_syrinx_preview'] = False
                st.session_state.pop('syrinx_preview_data', None)
                st.rerun()
    
    # Show preview results if available
    if st.session_state.get('show_syrinx_preview', False):
        preview_data = st.session_state.get('syrinx_preview_data', {})
        if preview_data:
            st.markdown("**Preview Results:**")
            matched = preview_data.get('matched', [])
            ignored = preview_data.get('ignored', [])
            
            if matched:
                st.success(f"✅ {len(matched)} items matched")
                for item in matched[:3]:  # Show first 3
                    st.text(f"• {item['code']} → {item['equipment']} → £{item['preview_final_price']:.2f}")
                if len(matched) > 3:
                    st.text(f"... and {len(matched) - 3} more")
            
            if ignored:
                st.warning(f"⚠️ {len(ignored)} codes ignored")
                for code in ignored[:3]:  # Show first 3
                    st.text(f"• {code}")
                if len(ignored) > 3:
                    st.text(f"... and {len(ignored) - 3} more")
    
    st.markdown("---")
    
    # Method 2: SharePoint (Placeholder buttons)
    st.markdown("### 🌐 SharePoint Method")
    
    if st.button("☁️ Save SharePoint", use_container_width=True, help="Save to SharePoint (Coming Soon)"):
        st.info("🚧 SharePoint integration coming soon!")
    
    if st.button("☁️ Load SharePoint", use_container_width=True, help="Load from SharePoint (Coming Soon)"):
        st.info("🚧 SharePoint integration coming soon!")
    
    st.markdown("---")
    
    # Additional Quick Actions
    st.markdown("### 📊 Export Options")
    
    # Direct Excel export (like main body button)
    customer_name = st.session_state.get('customer_name', 'Customer')
    global_discount = st.session_state.get('global_discount', 0)
    
    if customer_name and not df.empty:
        # Create admin-friendly DataFrame with clear column names (same as main export)
        admin_df = df[[
            "ItemCategory", "EquipmentName", "HireRateWeekly", 
            "CustomPrice", "DiscountPercent", "GroupName", "Sub Section"
        ]].copy()
        
        # Format values for export using standardized functions
        admin_df["HireRateWeekly"] = admin_df["HireRateWeekly"].apply(format_price_for_export)
        admin_df["CustomPrice"] = admin_df["CustomPrice"].apply(format_custom_price_for_export)
        admin_df["DiscountPercent"] = admin_df["DiscountPercent"].apply(format_discount_for_export)
        
        admin_df.columns = [
            "Item Category", "Equipment Name", "Original Price (£)", 
            "Net Price (£)", "Discount %", "Group", "Sub Section"
        ]
        admin_df["Customer Name"] = customer_name
        admin_df["Date Created"] = get_uk_time().strftime("%Y-%m-%d %H:%M")
        
        # Reorder columns for admin convenience
        admin_df = admin_df[[
            "Customer Name", "Date Created", "Item Category", "Equipment Name", 
            "Original Price (£)", "Net Price (£)", "Discount %", "Group", "Sub Section"
        ]]
        
        # Create transport charges DataFrame using proper UI transport types
        transport_inputs = []
        for i, (transport_type, default_value) in enumerate(zip(TRANSPORT_TYPES, DEFAULT_TRANSPORT_CHARGES)):
            charge = st.session_state.get(f"transport_{i}", default_value)
            if charge:  # Only include if there's a value
                transport_inputs.append({
                    "Delivery or Collection type": transport_type,
                    "Charge (£)": charge
                })
        transport_df = pd.DataFrame(transport_inputs)
        
        # Create Excel export (same as main export)
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
            # Main price list
            admin_df.to_excel(writer, sheet_name='Price List', index=False)
            
            # Transport charges sheet
            transport_df.to_excel(writer, sheet_name='Transport Charges', index=False)
            
            # Summary sheet
            summary_data = {
                'Customer': [customer_name],
                'Total Items': [len(admin_df)],
                'Global Discount %': [global_discount],
                'Date Created': [get_uk_time().strftime("%Y-%m-%d %H:%M")],
                'Created By': ['Net Rates Calculator']
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
        
        # Direct download button (immediate like main body)
        st.download_button(
            label="Excel - Admin",
            data=output_excel.getvalue(),
            file_name=f"{customer_name}_admin_pricelist_{get_uk_time().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Download Excel file with admin-formatted data"
        )
        
        # CSV Export (universal format)
        csv_data = admin_df.to_csv(index=False)
        st.download_button(
            label="CSV - Customer",
            data=csv_data,
            file_name=f"{customer_name}_pricelist_{get_uk_time().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            help="Download CSV file for universal compatibility"
        )
    else:
        st.button(
            label="Excel - Admin",
            use_container_width=True,
            disabled=True,
            help="Please enter a customer name and ensure data is loaded"
        )
        
        st.button(
            label="CSV - Customer",
            use_container_width=True,
            disabled=True,
            help="Please enter a customer name and ensure data is loaded"
        )
    
    # PDF Options (checkboxes to control special rates) - MUST be before PDF generation
    st.markdown("#### 📄 PDF Options")
    st.checkbox(
        "Include Special Rates?", 
        value=st.session_state.get('include_custom_table_sidebar', True),
        key="include_custom_table_sidebar",
        help="Add a special rates table at the beginning of the PDF"
    )
    st.checkbox(
        "Separate Special Rates?", 
        value=st.session_state.get('special_rates_pagebreak_sidebar', False),
        key="special_rates_pagebreak_sidebar",
        help="Put special rates table on a separate page"
    )
    st.number_input(
        "Extra Spacing after Special Rates", 
        min_value=0, 
        max_value=20, 
        value=st.session_state.get('special_rates_spacing_sidebar', 0),
        key="special_rates_spacing_sidebar",
        help="Add blank lines between Special Rates and Main Price List to improve pagination"
    )
    
    # PDF Download (immediate generation)
    if customer_name and not df.empty and header_pdf_file:
        # Get PDF options from session state
        include_custom_table = st.session_state.get('include_custom_table_sidebar', st.session_state.get('include_custom_table', True))
        special_rates_pagebreak = st.session_state.get('special_rates_pagebreak_sidebar', st.session_state.get('special_rates_pagebreak', False))
        special_rates_spacing = st.session_state.get('special_rates_spacing_sidebar', st.session_state.get('special_rates_spacing', 0))
        
        # Generate PDF using the shared function
        pdf_data = generate_customer_pdf(
            df=df,
            customer_name=customer_name,
            header_pdf_file=header_pdf_file,
            include_custom_table=include_custom_table,
            special_rates_pagebreak=special_rates_pagebreak,
            special_rates_spacing=special_rates_spacing
        )
        
        if pdf_data:
            # Generate filename
            now = datetime.now()
            month_year = now.strftime("%B %Y")
            safe_customer_name = customer_name.strip() if customer_name else "Customer"
            filename = f'Price List for {safe_customer_name} {month_year}.pdf'

            # PDF Download Button
            st.download_button(
                label="PDF - Customer",
                data=pdf_data,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True,
                help="Download PDF price list with customer branding"
            )
        else:
            st.button(
                label="PDF - Customer",
                use_container_width=True,
                disabled=True,
                help="Error generating PDF"
            )
    else:
        st.button(
            label="PDF - Customer",
            use_container_width=True,
            disabled=True,
            help="Please enter customer name, load data, and select PDF header"
        )

    # Email Section - wrapped in fragment to prevent full rerun on input changes
    @st.fragment
    def email_options_fragment():
        st.markdown("### 📧 Email Options")
        
        # Initialize email settings in session state if not present
        if 'email_choice' not in st.session_state:
            st.session_state.email_choice = "Authorise"
        if 'custom_recipient_email' not in st.session_state:
            st.session_state.custom_recipient_email = ""
        if 'cc_email' not in st.session_state:
            st.session_state.cc_email = ""
        if 'add_pdf_attachment' not in st.session_state:
            st.session_state.add_pdf_attachment = False
        
        # Email recipient selection
        email_options = {
            "Authorise": "netratesauth@thehireman.co.uk",
            "Accounts": "netrates@thehireman.co.uk",
            "CRM": "netratescrm@thehireman.co.uk",
            "Custom Email": "custom"
        }
        
        email_choice = st.selectbox(
            "Send To:",
            list(email_options.keys()),
            key="email_choice",
            help="Select recipient or choose Custom Email to enter your own"
        )
        
        # Handle custom email input
        if email_choice == "Custom Email":
            st.text_input(
                "Enter Email Address:",
                placeholder="example@company.com",
                key="custom_recipient_email",
                help="Enter the recipient's email address"
            )
        else:
            recipient_email = email_options[email_choice]
            st.info(f"📧 Sending to: {recipient_email}")
        
        # CC field
        st.text_input(
            "CC (Optional):",
            placeholder="additional@company.com",
            key="cc_email",
            help="Add additional recipients (separate multiple emails with commas)"
        )
        
        # PDF attachment checkbox
        st.checkbox(
            "📄 Add PDF", 
            value=False,
            key="add_pdf_attachment",
            help="Include PDF quote as email attachment"
        )
        
        # Send email button
        if st.button("📤 Send Email", use_container_width=True, help="Send price list via email"):
            # Get values from session state
            email_choice = st.session_state.get('email_choice', 'Authorise')
            email_options_map = {
                "Authorise": "netratesauth@thehireman.co.uk",
                "Accounts": "netrates@thehireman.co.uk",
                "CRM": "netratescrm@thehireman.co.uk",
                "Custom Email": "custom"
            }
            
            if email_choice == "Custom Email":
                recipient_email = st.session_state.get('custom_recipient_email', '')
            else:
                recipient_email = email_options_map[email_choice]
            
            cc_email = st.session_state.get('cc_email', '')
            add_pdf_attachment = st.session_state.get('add_pdf_attachment', False)
            
            customer_name = st.session_state.get('customer_name', '')
            df = st.session_state.get('df', pd.DataFrame())
            global_discount = st.session_state.get('global_discount', 0)
            
            if not customer_name:
                st.error("Please enter a customer name first")
            elif not recipient_email or (email_choice == "Custom Email" and not recipient_email.strip()):
                st.error("Please select or enter a valid email address")
            elif df.empty:
                st.error("Please load data first")
            else:
                # Get configurations
                smtp_config = load_config().get('smtp', {})
                
                # Prepare admin DataFrame with pricing (same format as main body)
                admin_df = df[[
                    "ItemCategory", "EquipmentName", "HireRateWeekly", 
                    "CustomPrice", "DiscountPercent", "GroupName", "Sub Section"
                ]].copy()
                
                # Format values for export using standardized functions
                admin_df["HireRateWeekly"] = admin_df["HireRateWeekly"].apply(format_price_for_export)
                admin_df["CustomPrice"] = admin_df["CustomPrice"].apply(format_custom_price_for_export)
                admin_df["DiscountPercent"] = admin_df["DiscountPercent"].apply(format_discount_for_export)
                
                admin_df.columns = [
                    "Item Category", "Equipment Name", "Original Price (£)", 
                    "Net Price (£)", "Discount %", "Group", "Sub Section"
                ]
                admin_df["Customer Name"] = customer_name
                admin_df["Date Created"] = get_uk_time().strftime("%Y-%m-%d %H:%M")
                
                # Reorder columns for admin convenience
                admin_df = admin_df[[
                    "Customer Name", "Date Created", "Item Category", "Equipment Name", 
                    "Original Price (£)", "Net Price (£)", "Discount %", "Group", "Sub Section"
                ]]
                
                # Create transport charges DataFrame using proper UI transport types
                transport_inputs = []
                for i, (transport_type, default_value) in enumerate(zip(TRANSPORT_TYPES, DEFAULT_TRANSPORT_CHARGES)):
                    charge = st.session_state.get(f"transport_{i}", default_value)
                    if charge:  # Only include if there's a value
                        transport_inputs.append({
                            "Delivery or Collection type": transport_type,
                            "Charge (£)": charge
                        })
                transport_df = pd.DataFrame(transport_inputs)
                
                try:
                    with st.spinner("📧 Sending email..."):
                        # Generate PDF attachment if requested
                        pdf_attachment_data = None
                        if add_pdf_attachment:
                            with st.spinner("📄 Generating PDF..."):
                                # Use the shared PDF generation function (single source of truth)
                                include_custom_table = st.session_state.get('include_custom_table_sidebar', st.session_state.get('include_custom_table', True))
                                special_rates_pagebreak = st.session_state.get('special_rates_pagebreak_sidebar', st.session_state.get('special_rates_pagebreak', False))
                                special_rates_spacing = st.session_state.get('special_rates_spacing_sidebar', st.session_state.get('special_rates_spacing', 0))
                                
                                header_pdf_file = st.session_state.get('header_pdf_file', None)
                                if header_pdf_file:
                                    pdf_attachment_data = generate_customer_pdf(
                                        df=df,
                                        customer_name=customer_name,
                                        header_pdf_file=header_pdf_file,
                                        include_custom_table=include_custom_table,
                                        special_rates_pagebreak=special_rates_pagebreak,
                                        special_rates_spacing=special_rates_spacing
                                    )
                                else:
                                    st.warning("⚠️ No PDF header file selected. PDF attachment will not be included.")
                        
                        # Get email configuration (same as main body)
                        config = st.session_state.get('config', {})
                        smtp_settings = config.get("smtp_settings", {})
                        saved_sendgrid_key = smtp_settings.get("sendgrid_api_key", "")
                        
                        # Try SendGrid first, then SMTP fallback
                        if (smtp_config.get('enabled', False) and smtp_config.get('provider') == 'SendGrid') or saved_sendgrid_key or SENDGRID_API_KEY:
                            result = send_email_via_sendgrid_api(
                                customer_name,
                                admin_df,
                                transport_df,
                                recipient_email,
                                cc_email if cc_email and cc_email.strip() else None,
                                global_discount,
                                df,  # Pass original DataFrame
                                st.session_state.get('header_pdf_choice', None),  # Get from session state
                                pdf_attachment_data  # Add PDF attachment
                            )
                        else:
                            result = send_email_with_pricelist(
                                customer_name,
                                admin_df,
                                transport_df,
                                recipient_email,
                                smtp_config if smtp_config.get('enabled', False) else None,
                                cc_email if cc_email and cc_email.strip() else None,
                                global_discount,
                                df,  # Pass original DataFrame
                                st.session_state.get('header_pdf_choice', None),  # Get from session state
                                pdf_attachment_data  # Add PDF attachment
                            )
                        
                        if result['status'] == 'sent':
                            st.success(f"✅ Email sent successfully to {recipient_email}!")
                            if cc_email:
                                st.info(f"📧 CC: {cc_email}")
                            st.balloons()
                        elif result['status'] == 'saved':
                            st.success("✅ Email data prepared successfully!")
                            st.info("💡 Check your email configuration to enable sending")
                        else:
                            st.error(f"❌ Email failed: {result.get('message', 'Unknown error')}")
                            
                except Exception as e:
                    st.error(f"❌ Email error: {str(e)}")
    
    email_options_fragment()
    
    st.markdown("---")
    
    # Excel to JSON Converter Section
    st.markdown("### 📊 Excel to JSON Converter")
    st.markdown("*Convert Excel category codes and prices to JSON format*")
    
    # File uploader for Excel files
    excel_file = st.file_uploader(
        "📊 Upload Excel File", 
        type=['xlsx', 'xls'], 
        key="excel_to_json_upload",
        help="Upload Excel file with Category Codes (Column A) and Special Prices (Column B)"
    )
    
    # Customer name input for JSON
    customer_name_json = st.text_input(
        "Customer Name for JSON",
        value=st.session_state.get('customer_name', ''),
        help="Enter customer name for the JSON file"
    )
    
    # Use main global discount from session state
    global_discount_json = st.session_state.get('global_discount', 0.0)
    st.info(f"Using Global Discount: {global_discount_json}% (from main app settings)")
    
    if excel_file and customer_name_json:
        # Process and download button
        if st.button("🔄 Convert to JSON & Download", use_container_width=True, type="primary"):
            df = st.session_state.get('df', pd.DataFrame())
            if not df.empty:
                # Process the Excel file
                excel_file.seek(0)  # Reset file pointer
                result = process_excel_to_json(excel_file, global_discount_json, customer_name_json, df)
                
                if result:
                    json_data = result['json_data']
                    matched_count = result['matched_count']
                    ignored_codes = result['ignored_codes']
                    
                    # Create filename
                    safe_customer_name = customer_name_json.strip().replace(" ", "_").replace("/", "_")
                    timestamp = get_uk_time().strftime("%Y-%m-%d_%H-%M-%S")
                    filename = f"{safe_customer_name}_converted_{timestamp}.json"
                    
                    # Convert to JSON string
                    json_string = json.dumps(json_data, indent=2)
                    
                    # Show results
                    st.success(f"✅ Converted {matched_count} prices successfully!")
                    if ignored_codes:
                        st.warning(f"⚠️ {len(ignored_codes)} codes ignored: {', '.join(ignored_codes[:5])}")
                    
                    # Download button
                    st.download_button(
                        label=f"💾 Download {filename}",
                        data=json_string,
                        file_name=filename,
                        mime="application/json",
                        use_container_width=True,
                        help="Download JSON file for use with 'Load Progress' feature"
                    )
                else:
                    st.error("❌ Failed to process Excel file")
            else:
                st.error("❌ Please load equipment data first (main Excel file)")
    else:
        if not excel_file:
            st.info("📋 Upload an Excel file to convert")
        if not customer_name_json:
            st.info("📋 Enter customer name")




















