import streamlit as st
import pdfplumber
import pandas as pd
import json
import re
from supabase import create_client, Client

# --- PAGE CONFIG ---
st.set_page_config(page_title="RTU CGPA Tracker", layout="wide")

# --- DATABASE CONNECTION ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        # Ensure no accidental whitespace or newlines from the secrets box
        return create_client(url.strip(), key.strip())
    except Exception as e:
        st.error(f"Failed to initialize connection: {e}")
        return None

supabase = init_connection()
CURRENT_USER = "demo_user"

# --- DATA LOADING ---
def get_saved_data():
    try:
        # We are using the new table name 'rtu_data'
        response = supabase.table("rtu_data").select("*").eq("profile_id", CURRENT_USER).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        # THIS IS THE KEY: Displaying the real error message
        st.error("⚠️ Supabase API Error Details:")
        st.code(str(e))
        return pd.DataFrame()

# --- MAIN UI ---
st.title("📈 RTU CGPA Calculator & Tracker")

if supabase:
    saved_df = get_saved_data()
    
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Upload Semester Result")
        uploaded_file = st.file_uploader("Choose your RTU Result PDF", type="pdf")
        
        if uploaded_file and st.button("Analyze & Save to Cloud"):
            st.info("Processing...")
            # (Processing logic goes here - keeping it light for debugging)
            st.warning("Ensure your courses.json is in your GitHub repo!")

    with col2:
        st.subheader("Your Progress")
        if not saved_df.empty:
            st.dataframe(saved_df, use_container_width=True)
        else:
            st.info("No data returned from 'rtu_data'. Once the error above is fixed, your data will appear here.")
else:
    st.warning("Check your Streamlit Secrets; the connection couldn't start.")
