# Shared utilities for Net Rates Calculator - Multi-page version
# This module contains functions shared across all pages

import streamlit as st
import pandas as pd
import io
import json
import os
from datetime import datetime
import fitz  # PyMuPDF
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle

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
# ERP Import Functions
# -------------------------------
CONVERSION_TABLE_FILE = os.path.join(SCRIPT_DIR, "Conversion Table for Net Rates App.xlsx")

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_conversion_table():
    """Load the ERP conversion table from Excel file"""
    try:
        if os.path.exists(CONVERSION_TABLE_FILE):
            df = pd.read_excel(CONVERSION_TABLE_FILE)
            return df
        else:
            return None
    except Exception as e:
        st.error(f"Error loading conversion table: {e}")
        return None

def extract_tower_height(description):
    """Extract height value from tower description (e.g., 'H2.66xL2.0m' -> 2.66)"""
    import re
    # Match pattern like H2.66x or H2.66xL
    match = re.search(r'H(\d+\.?\d*)x', description, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None

def parse_erp_data(erp_text, conversion_table, rate_card_df):
    """
    Parse ERP copy-paste data and match against conversion table and rate card.
    
    Returns a list of dicts with:
    - erp_code: Original ERP code
    - erp_description: ERP description
    - erp_price: Price from ERP (£ stripped)
    - matched_code: ItemCategory code in rate card
    - matched_name: Equipment name in rate card
    - rate_card_idx: Index in rate card dataframe
    - final_price: Calculated price (divided by height for towers)
    - product_type: Fleet/Bulk/Tower
    - status: matched/unmatched/error
    - note: Any notes about the match
    """
    results = []
    
    if not erp_text or not erp_text.strip():
        return results
    
    if conversion_table is None:
        return [{"status": "error", "note": "Conversion table not loaded"}]
    
    # Build lookup dictionaries from conversion table
    # For Fleet: code -> code (direct match)
    # For Bulk/Tower: description -> code
    fleet_codes = set()
    bulk_desc_to_code = {}
    tower_desc_to_code = {}
    
    for _, row in conversion_table.iterrows():
        code = str(row['EQP_EQUIPMENT_CLASS']).strip()
        desc = str(row['EQP_NAME']).strip().lower()
        prod_type = str(row['Type']).strip()
        
        if prod_type == 'Fleet':
            fleet_codes.add(code)
        elif prod_type == 'Bulk':
            bulk_desc_to_code[desc] = code
        elif prod_type == 'Tower':
            tower_desc_to_code[desc] = code
    
    # Build rate card lookup by ItemCategory
    rate_card_lookup = {}
    for idx, row in rate_card_df.iterrows():
        item_cat = str(row['ItemCategory']).strip()
        rate_card_lookup[item_cat] = {
            'idx': idx,
            'name': row['EquipmentName'],
            'price': row['HireRateWeekly']
        }
    
    # Parse ERP data (tab-delimited)
    lines = erp_text.strip().split('\n')
    
    for line in lines:
        if not line.strip():
            continue
        
        # Split by tab
        parts = line.split('\t')
        
        if len(parts) < 7:
            continue
        
        erp_code = parts[0].strip()
        erp_desc_col2 = parts[1].strip() if len(parts) > 1 else ""  # Sometimes description is in col 2
        erp_price_raw = parts[2].strip() if len(parts) > 2 else ""  # Week rate in col 3
        erp_desc_col7 = parts[6].strip() if len(parts) > 6 else ""  # Main description in col 7
        
        # Use column 7 description if available, otherwise column 2
        erp_description = erp_desc_col7 if erp_desc_col7 else erp_desc_col2
        
        # Skip header row
        if erp_code == 'PAR_EQUIPMENT_CLASS' or 'EQC_NAME' in erp_description:
            continue
        
        # Parse price (remove £ symbol)
        erp_price = None
        if erp_price_raw:
            try:
                erp_price = float(erp_price_raw.replace('£', '').replace(',', '').strip())
            except ValueError:
                pass
        
        result = {
            'erp_code': erp_code,
            'erp_description': erp_description,
            'erp_price': erp_price,
            'matched_code': None,
            'matched_name': None,
            'rate_card_idx': None,
            'final_price': None,
            'product_type': None,
            'status': 'unmatched',
            'note': ''
        }
        
        # Determine product type and match
        if erp_code and erp_code[0].isdigit() and '/' in erp_code:
            # Fleet product - direct code match
            result['product_type'] = 'Fleet'
            
            if erp_code in rate_card_lookup:
                result['matched_code'] = erp_code
                result['matched_name'] = rate_card_lookup[erp_code]['name']
                result['rate_card_idx'] = rate_card_lookup[erp_code]['idx']
                result['final_price'] = erp_price
                result['status'] = 'matched'
            else:
                result['note'] = f"Code {erp_code} not found in rate card"
        
        elif erp_code.startswith('B') or erp_code.startswith('BNHOL'):
            # Bulk product - match by description
            result['product_type'] = 'Bulk'
            
            desc_lower = erp_description.lower().strip()
            if desc_lower in bulk_desc_to_code:
                matched_code = bulk_desc_to_code[desc_lower]
                if matched_code in rate_card_lookup:
                    result['matched_code'] = matched_code
                    result['matched_name'] = rate_card_lookup[matched_code]['name']
                    result['rate_card_idx'] = rate_card_lookup[matched_code]['idx']
                    result['final_price'] = erp_price
                    result['status'] = 'matched'
                else:
                    result['note'] = f"Converted code {matched_code} not in rate card"
            else:
                result['note'] = f"Description not found in conversion table"
        
        elif erp_code.startswith('TO'):
            # Tower product - match by description and calculate per-meter price
            result['product_type'] = 'Tower'
            
            desc_lower = erp_description.lower().strip()
            if desc_lower in tower_desc_to_code:
                matched_code = tower_desc_to_code[desc_lower]
                
                # Extract height for per-meter calculation
                height = extract_tower_height(erp_description)
                
                if matched_code in rate_card_lookup:
                    result['matched_code'] = matched_code
                    result['matched_name'] = rate_card_lookup[matched_code]['name']
                    result['rate_card_idx'] = rate_card_lookup[matched_code]['idx']
                    
                    if height and height > 0 and erp_price:
                        result['final_price'] = round(erp_price / height, 2)
                        result['note'] = f"£{erp_price:.2f} ÷ {height}m = £{result['final_price']:.2f}/m"
                    else:
                        result['final_price'] = erp_price
                        if not height:
                            result['note'] = "Could not extract height for per-meter calc"
                    
                    result['status'] = 'matched'
                else:
                    result['note'] = f"Converted code {matched_code} not in rate card"
            else:
                result['note'] = f"Tower description not found in conversion table"
        
        else:
            result['note'] = f"Unknown product type for code: {erp_code}"
        
        results.append(result)
    
    return results

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
    
    # Capture group discounts (exclude global_discount itself)
    group_discounts = {
        key: st.session_state[key]
        for key in st.session_state
        if key.endswith("_discount") and key != "global_discount"
    }
    
    return {
        "customer_name": customer_name,
        "global_discount": global_discount,
        "group_discounts": group_discounts,
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


# -------------------------------
# Shared Sidebar Function
# -------------------------------
def add_shared_sidebar():
    """Add shared sidebar content (Save/Logout) - call from every page"""
    with st.sidebar:
        # Save Progress Section
        st.markdown("### 💾 Progress")
        
        df = st.session_state.get('df')
        customer_name = st.session_state.get('customer_name', '')
        
        # Save Progress Button
        if df is not None:
            save_data = create_save_data(customer_name or "Unsaved", df)
            json_data = json.dumps(save_data, indent=2)
            timestamp = get_uk_time().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{customer_name or 'progress'}_{timestamp}.json"
            
            st.download_button(
                label="💾 Save Progress",
                data=json_data,
                file_name=filename,
                mime="application/json",
                use_container_width=True,
                help="Download your current progress as a JSON file"
            )
        
        st.caption("📂 Load progress on Discounts page")
        
        st.markdown("---")
        st.markdown("### 🔐 Session")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()
        
        st.markdown("---")
        st.markdown("*Net Rates Calculator v2.0*")
        st.markdown("*The Hireman*")


# -------------------------------
# PDF Generation Functions
# -------------------------------
def add_footer_logo(canvas, doc):
    """Add footer logo to PDF pages"""
    logo_path = os.path.join(SCRIPT_DIR, "HMChev.png")
    page_width = doc.pagesize[0]
    margin = 20
    logo_width = page_width - 2 * margin
    logo_height = 30

    x = margin
    y = 10

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


@st.cache_data
def read_pdf_header(file):
    """Read PDF header file bytes"""
    return file.read()


def generate_customer_pdf(df, customer_name, header_pdf_file, include_custom_table=True, 
                          special_rates_pagebreak=False, special_rates_spacing=0):
    """
    Generate customer PDF with price list - Single source of truth for PDF generation.
    
    Args:
        df: DataFrame with pricing data
        customer_name: Customer name for the PDF
        header_pdf_file: PDF header file (BytesIO object)
        include_custom_table: Whether to include special rates table at the top
        special_rates_pagebreak: Whether to put special rates on a separate page
        special_rates_spacing: Number of blank lines after special rates
    
    Returns:
        bytes: The merged PDF as bytes, or None if generation fails
    """
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
                                'original_index': idx
                            })
                        except ValueError:
                            continue

            if custom_price_items:
                customer_title = customer_name if customer_name else "Customer"
                elements.append(Paragraph(f"Net Rates for {customer_title}", styles['Title']))
                elements.append(Spacer(1, 12))
                elements.append(Paragraph("Special Rates", styles['Heading2']))
                elements.append(Spacer(1, 6))
                
                table_data = [["Category", "Equipment", "Special (£)"]]
                subsection_header_rows = []
                
                current_row = 1
                current_subsection = None
                
                for item in custom_price_items:
                    if item['subsection'] != current_subsection:
                        current_subsection = item['subsection']
                        subsection_title = str(current_subsection) if current_subsection and str(current_subsection) != "nan" else "General"
                        table_data.append(['', Paragraph(f"<b>{subsection_title}</b>", styles['BodyText']), ''])
                        subsection_header_rows.append(current_row)
                        current_row += 1
                    
                    table_data.append([
                        item['category'],
                        Paragraph(item['equipment'], styles['BodyText']),
                        f"£{item['price']:.2f}"
                    ])
                    current_row += 1
                
                row_styles = [
                    ('BACKGROUND', (0, 0), (-1, 0), '#FFD51D'),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ]
                
                for row_num in subsection_header_rows:
                    row_styles.append(('BACKGROUND', (0, row_num), (-1, row_num), '#FCE547'))
                    row_styles.append(('SPAN', (1, row_num), (2, row_num)))
                
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
        header_pdf_file.seek(0)
        header_data = header_pdf_file.read()
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
                email_font_color = (0 / 255, 90 / 255, 156 / 255)
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
            except Exception:
                pass

        # Draw Transport Charges table on page 3
        page3 = header_pdf[2]
        page_width = page3.rect.width
        page_height = page3.rect.height

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
            header_color = (125/255, 166/255, 216/255)
            page3.draw_rect(fitz.Rect(x0, y_rect, x1, y_rect + row_height), color=header_color, fill=header_color)
            page3.insert_text((x0 + text_padding_x, y_text), header, fontsize=font_size_transport, fontname="hebo")

        # Draw data rows with alternating colors
        for row_index, row in enumerate(transport_data):
            if row_index % 2 == 0:
                row_color = (247/255, 252/255, 255/255)
            else:
                row_color = (218/255, 233/255, 248/255)
            
            for col_index, cell in enumerate(row):
                x0 = margin_x + sum(col_widths_transport[:col_index])
                x1 = x0 + col_widths_transport[col_index]
                y_text = page_height - margin_y + row_height * (row_index + 1) + text_offset_y
                y_rect = page_height - margin_y + row_height * (row_index + 1) - 14
                page3.draw_rect(fitz.Rect(x0, y_rect, x1, y_rect + row_height), color=row_color, fill=row_color)
                cell_text = str(cell)
                if col_index == 1:
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
