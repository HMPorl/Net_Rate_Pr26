# Simple test page
import streamlit as st
from utils import initialize_session_state, add_shared_sidebar

initialize_session_state()

# Check authentication
if not st.session_state.get("authenticated", False):
    st.warning("🔐 Please log in from the main page first.")
    st.stop()

# Add shared sidebar
add_shared_sidebar()

st.title("🧪 Test Page")
st.write("If you can see this, pages are working!")
st.write("The issue is likely with imports in other pages.")
