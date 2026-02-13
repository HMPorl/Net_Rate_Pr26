# Page 3: Export - Generate and Download Files
import streamlit as st
import pandas as pd
import io
import os
import json

# Import shared utilities (Streamlit runs from project root)
from utils import (
    initialize_session_state, ensure_dataframe_loaded, get_uk_time,
    format_price_display, format_price_for_export, format_custom_price_for_export,
    format_discount_for_export, format_custom_price_for_display,
    create_admin_dataframe, create_transport_dataframe, create_save_data,
    TRANSPORT_TYPES, DEFAULT_TRANSPORT_CHARGES, SCRIPT_DIR,
    SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, is_poa_value, calculate_discount_percent
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
customer_name = st.session_state.get('customer_name', '')
global_discount = st.session_state.get('global_discount', 0.0)

st.title("📤 Export & Email")
st.markdown("Generate and download price lists in various formats.")

# Show current settings
col1, col2, col3 = st.columns(3)
with col1:
    if customer_name:
        st.success(f"**Customer:** {customer_name}")
    else:
        st.warning("**Customer:** Not set - Required for exports")
with col2:
    st.info(f"**Global Discount:** {global_discount}%")
with col3:
    custom_count = sum(1 for idx, _ in df.iterrows() if st.session_state.get(f"price_{idx}", "").strip())
    st.info(f"**Custom Prices:** {custom_count}")

if not customer_name:
    st.error("⚠️ Please enter a customer name on the **Discounts** page before exporting.")
    st.stop()

st.markdown("---")

# Update CustomPrice and DiscountPercent in DataFrame from session state
for idx, row in df.iterrows():
    price_key = f"price_{idx}"
    user_input = st.session_state.get(price_key, "").strip()
    
    if user_input:
        if is_poa_value(user_input):
            df.at[idx, "CustomPrice"] = "POA"
            df.at[idx, "DiscountPercent"] = "POA"
        else:
            try:
                df.at[idx, "CustomPrice"] = float(user_input)
                df.at[idx, "DiscountPercent"] = calculate_discount_percent(row["HireRateWeekly"], float(user_input))
            except ValueError:
                df.at[idx, "CustomPrice"] = "POA"
                df.at[idx, "DiscountPercent"] = "POA"
    else:
        # Use calculated price based on group discount
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
            except (ValueError, TypeError):
                df.at[idx, "CustomPrice"] = "POA"
                df.at[idx, "DiscountPercent"] = "POA"

# Create export DataFrames
admin_df = create_admin_dataframe(df, customer_name)
transport_df = create_transport_dataframe()

# -------------------------------
# Preview Section
# -------------------------------
st.markdown("### 👁️ Preview")

with st.expander("📊 Price List Preview", expanded=False):
    st.dataframe(admin_df.head(20), use_container_width=True)
    if len(admin_df) > 20:
        st.info(f"Showing first 20 of {len(admin_df)} items")

with st.expander("🚚 Transport Charges Preview", expanded=False):
    st.dataframe(transport_df, use_container_width=True)

st.markdown("---")

# -------------------------------
# Export Options Section
# -------------------------------
st.markdown("### 📥 Download Exports")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 📊 Excel (Admin)")
    
    output_excel = io.BytesIO()
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        admin_df.to_excel(writer, sheet_name='Price List', index=False)
        transport_df.to_excel(writer, sheet_name='Transport Charges', index=False)
        
        summary_data = {
            'Customer': [customer_name],
            'Total Items': [len(admin_df)],
            'Global Discount %': [global_discount],
            'Date Created': [get_uk_time().strftime("%Y-%m-%d %H:%M")],
            'Created By': ['Net Rates Calculator']
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
    
    st.download_button(
        label="📊 Download Excel",
        data=output_excel.getvalue(),
        file_name=f"{customer_name}_admin_pricelist_{get_uk_time().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

with col2:
    st.markdown("#### 📄 CSV (Universal)")
    
    csv_data = admin_df.to_csv(index=False)
    st.download_button(
        label="📄 Download CSV",
        data=csv_data,
        file_name=f"{customer_name}_pricelist_{get_uk_time().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )

with col3:
    st.markdown("#### 💾 JSON (Backup)")
    
    save_data = create_save_data(customer_name, df)
    json_data = json.dumps(save_data, indent=2)
    timestamp = get_uk_time().strftime("%Y-%m-%d_%H-%M-%S")
    
    st.download_button(
        label="💾 Download JSON",
        data=json_data,
        file_name=f"{customer_name}_progress_{timestamp}.json",
        mime="application/json",
        use_container_width=True
    )

st.markdown("---")

# -------------------------------
# PDF Export Section
# -------------------------------
st.markdown("### 📄 PDF Export")

header_pdf_file = st.session_state.get('header_pdf_file', None)
header_pdf_choice = st.session_state.get('header_pdf_choice', "(Select Sales Person)")

if header_pdf_choice == "(Select Sales Person)" or header_pdf_file is None:
    st.warning("⚠️ Please select a Sales Person PDF header on the **Discounts** page to enable PDF export.")
else:
    col1, col2 = st.columns(2)
    
    with col1:
        include_custom_table = st.checkbox("Include Special Rates table", value=True, key="include_custom_table")
        special_rates_pagebreak = st.checkbox("Special rates on separate page", value=False, key="special_rates_pagebreak")
    
    with col2:
        special_rates_spacing = st.number_input(
            "Spacing after special rates (lines)",
            min_value=0, max_value=10, value=0,
            key="special_rates_spacing"
        )
    
    if st.button("📄 Generate PDF", type="primary", use_container_width=True):
        try:
            # Import PDF generation functions from main app
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
            import fitz  # PyMuPDF
            
            st.info("📄 PDF generation would happen here. Full implementation requires the generate_customer_pdf function from the original app.")
            st.warning("Note: PDF generation requires additional code migration. For now, use Excel export.")
            
        except Exception as e:
            st.error(f"PDF generation error: {e}")

st.markdown("---")

# -------------------------------
# Email Section
# -------------------------------
st.markdown("### 📧 Email Options")

@st.fragment
def email_options_fragment():
    if 'email_choice' not in st.session_state:
        st.session_state.email_choice = "Authorise"
    if 'custom_recipient_email' not in st.session_state:
        st.session_state.custom_recipient_email = ""
    if 'cc_email' not in st.session_state:
        st.session_state.cc_email = ""
    
    email_options = {
        "Authorise": "netratesauth@thehireman.co.uk",
        "Accounts": "netrates@thehireman.co.uk",
        "CRM": "netratescrm@thehireman.co.uk",
        "Custom Email": "custom"
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        email_choice = st.selectbox(
            "Send To:",
            list(email_options.keys()),
            key="email_choice"
        )
        
        if email_choice == "Custom Email":
            st.text_input(
                "Enter Email Address:",
                placeholder="example@company.com",
                key="custom_recipient_email"
            )
        else:
            recipient_email = email_options[email_choice]
            st.info(f"📧 Will send to: {recipient_email}")
    
    with col2:
        st.text_input(
            "CC Email (optional):",
            placeholder="cc@company.com",
            key="cc_email"
        )
        
        add_pdf = st.checkbox("Attach PDF", value=False, key="add_pdf_attachment")
    
    # Email status
    if SENDGRID_API_KEY:
        st.success("✅ SendGrid configured - ready to send")
    else:
        st.warning("⚠️ SendGrid not configured - email sending disabled")
    
    if st.button("📧 Send Email", type="primary", use_container_width=True, disabled=not SENDGRID_API_KEY):
        st.info("📧 Email sending would happen here. Full implementation requires the email functions from the original app.")
        st.warning("Note: Email functionality requires additional code migration.")

email_options_fragment()

st.markdown("---")

# -------------------------------
# Final Price List Display
# -------------------------------
st.markdown("### 📋 Complete Price List")

display_df = df[[
    "ItemCategory", "EquipmentName", "HireRateWeekly",
    "GroupName", "Sub Section", "CustomPrice", "DiscountPercent"
]].copy()

display_df["HireRateWeekly"] = display_df["HireRateWeekly"].apply(format_price_display)
display_df["CustomPrice"] = display_df["CustomPrice"].apply(format_custom_price_for_display)
display_df["DiscountPercent"] = display_df["DiscountPercent"].apply(format_discount_for_export)

display_df.columns = ["Category", "Equipment", "Original", "Group", "Sub Section", "Final Price", "Discount %"]

st.dataframe(display_df, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("*Net Rates Calculator v2.0 - Multi-Page Edition - The Hireman*")
