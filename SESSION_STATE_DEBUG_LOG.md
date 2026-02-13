# Session State Persistence Issue - Debug Log

**Date:** February 13, 2026  
**Status:** UNRESOLVED - Session state not persisting between page navigation

---

## Problem Description

When users navigate between pages using the sidebar radio buttons:
- Global Discount set to 60% resets when returning to Discounts page
- Custom prices entered also reset when navigating away and back

## App Architecture

The app uses a **single-file multi-page approach** with sidebar radio buttons for navigation (the automatic `pages/` folder detection didn't work on Streamlit Cloud).

**Navigation flow:**
```
app.py
├── login_page() - Authentication (HM / 1985)
├── home_page() - Welcome + debug expander showing session state
├── discounts_page() - Global discount slider, transport charges, category discounts
├── custom_rates_page() - Per-product custom pricing
└── export_page() - PDF/Excel export and email
```

## What We've Tried

### Attempt 1: Multi-page with `pages/` folder
- Created separate page files in `pages/` directory
- Streamlit Cloud didn't detect them automatically
- **Result:** Pages didn't appear in sidebar

### Attempt 2: Single-file with radio navigation
- Rewrote app.py to embed all page functions
- Used `st.sidebar.radio()` for navigation
- **Result:** Pages visible but session state resets

### Attempt 3: Fix widget key conflicts
- Changed from using both `value=` and `key=` parameters
- Added `on_change` callbacks to sync values immediately
- Changed custom prices from dual keys (`input_{idx}` + `price_{idx}`) to single key (`price_{idx}`)
- Added debug expander on Home page to view session state
- **Result:** Still not persisting (as of Feb 13, 2026)

## Files Modified

| File | Status | Notes |
|------|--------|-------|
| `app.py` | Active | Main entry point with embedded pages |
| `utils.py` | Active | Shared utilities, `initialize_session_state()` |
| `pages/` folder | Unused | Contains page files but not being used |
| `app_singlepage.py` | Backup | Original 3079-line single-page app |

## Key Code Locations to Investigate

### 1. Session State Initialization (utils.py)
Check `initialize_session_state()` function - may need to verify it's not resetting values on every page change.

### 2. Discounts Page (app.py ~line 900+)
Look at global discount slider implementation and `on_change` callback.

### 3. Custom Rates Page (app.py ~line 1100+)
Check pricing fragment and how `price_{idx}` keys are managed.

### 4. Page Navigation (app.py ~line 2900+)
Check if something in the page routing logic is re-initializing state.

## Session State Keys to Monitor

```python
# Global discount
st.session_state.get('global_discount', 'NOT SET')

# Transport charges
st.session_state.get('transport_charges', 'NOT SET')

# Custom prices (per product)
st.session_state.get('price_0', 'NOT SET')  # First product
st.session_state.get('price_1', 'NOT SET')  # Second product
# etc.

# Category discounts
st.session_state.get('category_discounts', 'NOT SET')
```

## Debug Tools Added

A debug expander was added to `home_page()` that displays:
- Current global_discount value
- Transport charges
- Number of custom prices set
- All custom price keys and values

## Next Steps to Try

1. **Check if `initialize_session_state()` is overwriting values**
   - Look for any code that sets default values without checking if key already exists
   - Should use: `if 'key' not in st.session_state: st.session_state.key = default`

2. **Add logging to track when state changes**
   - Print session state at start of each page function
   - Compare before/after navigation

3. **Check for key name mismatches**
   - Widget keys vs session state keys might differ
   - Ensure `global_discount_slider` callback writes to correct key

4. **Consider using st.cache_data for persistent storage**
   - Session state resets on full page refresh
   - May need to persist to file/database for true persistence

5. **Check Streamlit version compatibility**
   - Running Streamlit 1.54.0 on Python 3.13.12
   - Some session state behaviors changed in recent versions

## GitHub Repository

- **Repo:** https://github.com/HMPorl/Net_Rate_Pr26
- **Branch:** main
- **Latest commit:** `62ea2d3` - "Fix session state persistence - use single keys, add callbacks, add debug display"

## Commands to Resume

```powershell
# Navigate to project
cd "C:\Users\paul.scott\OneDrive - The Hireman\Shared Documents - IT Support\Scripts and code\Python\Net_Rate_Pr26"

# Check current state
git status
git log --oneline -5

# Run locally for testing
streamlit run app.py
```

---

**To continue:** Share this log and describe what you observe when setting values and navigating between pages. The debug expander on the Home page will help show what's actually stored in session state.
