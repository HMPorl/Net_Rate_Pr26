# Net Rates Calculator - Price Increase 2026 (Pr26)

## Project Overview

This is an independent fork of the Net Rates Calculator V2, created specifically for the **2026 Price Increase Project**. This version is completely separate from the production V2 application, allowing for testing and development of new pricing structures without affecting the live system.

## Version History

### Pr26 (Current) - Price Increase 2026 Project
- Forked from NET_RATES_V2 on 2026-01-20
- Independent instance for price increase testing
- Separate configuration and data files
- Can run simultaneously with V2 without conflicts

### Parent Version: V2.0 (NET_RATES_V2)
- Complete rewrite with custom price management
- Transport charges integration across all exports
- UK timezone support and professional formatting
- Streamlined UI with visual indicators

## Key Differences from V2

| Aspect | NET_RATES_V2 | Net_Rate_Pr26 |
|--------|-------------|---------------|
| Purpose | Production | Price Increase Testing |
| Data File | Net rates Webapp.xlsx | Net rates Webapp.xlsx (can be different) |
| Config File | config.json | config.json (independent) |
| Page Title | Net Rates Calculator V2 | Net Rates Calculator Pr26 |
| Page Icon | 🚀 | 📈 |

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Email (Optional)
Copy `config.template.json` to `config.json` and update settings as needed.

### 3. Add Excel Data
Place your Excel file named `Net rates Webapp.xlsx` in this folder. You can use the same file as V2 or a modified version with new pricing.

### 4. Add PDF Headers
Copy any required PDF header files (e.g., `AS Header.pdf`, `JC Header.pdf`) to this folder.

### 5. Run the Application
```bash
streamlit run app.py
```

## Deployment

### Local Development
Run the app locally for testing new price structures.

### Streamlit Cloud (Recommended for sharing)
1. Create a new GitHub repository for this project
2. Push all files to the repository
3. Connect to Streamlit Cloud
4. Add secrets in Streamlit Cloud dashboard

## Architecture & Design Philosophy

This application inherits all the design principles from V2:

- **User-Centric Interface**: Streamlined workflow with visual indicators
- **Data Integrity**: Robust handling of pricing data and POA values
- **Professional Output**: Consistent formatting across all export formats
- **Performance Optimized**: Efficient handling of large datasets
- **Error Resilient**: Comprehensive error handling and graceful fallbacks

## Technical Stack

- **Framework**: Streamlit (web interface)
- **Data Processing**: Pandas (Excel/CSV handling)
- **PDF Generation**: ReportLab + PyMuPDF (professional layouts)
- **Email Services**: SendGrid API (primary), SMTP fallback
- **Timezone**: UK timezone (Europe/London) for all timestamps

## Key Features

### Price Testing Features
- Import new price lists for comparison
- Syrinx import functionality for bulk pricing
- Save/load progress for iterative testing
- Export to Excel, PDF, CSV, and JSON

### Visual Indicators
- **🎯 Custom Price**: User-entered specific pricing
- **📊 Calculated Price**: Automatic group discount application
- **💡 Helpful Tips**: Guidance text throughout interface
- **⚠️ Max Discount Warning**: Prevents excessive discounting

## File Structure

```
Net_Rate_Pr26/
├── app.py                      # Main application
├── config.template.json        # Configuration template
├── config.json                 # Your configuration (create from template)
├── requirements.txt            # Python dependencies
├── secrets_template.toml       # Streamlit secrets template
├── README.md                   # This file
├── Net rates Webapp.xlsx       # Excel data file (add your own)
├── *.pdf                       # PDF header files (add your own)
└── HMChev.png                  # Footer logo (optional)
```

## Important Notes

### Independence from V2
- This application is **completely independent** from NET_RATES_V2
- Changes made here do not affect the production V2 application
- Both can run simultaneously on different ports

### Data Isolation
- Uses its own `config.json` for settings
- Progress saves are stored separately
- Email configurations are independent

### Testing Workflow
1. Copy/modify Excel data with new prices
2. Test discount calculations
3. Generate sample PDFs and Excel exports
4. Validate email functionality
5. Once approved, apply changes to V2

## Support

- 📧 Email: netrates@thehireman.co.uk
- 💡 Check the built-in help system (❓ button in the app)

---

*Net Rates Calculator Pr26 - The Hireman | Price Increase 2026 Project*
*Forked from V2.0 on 2026-01-20*
