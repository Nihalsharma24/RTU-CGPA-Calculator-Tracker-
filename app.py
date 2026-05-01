import streamlit as st
import pdfplumber
import pandas as pd
import re
from supabase import create_client, Client

# --- PAGE CONFIG ---
st.set_page_config(page_title="RTU CGPA Tracker", layout="wide")

# --- DATABASE CONNECTION ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"].strip()
        key = st.secrets["SUPABASE_KEY"].strip()
        return create_client(url, key)
    except Exception as e:
        st.error("🚨 Connection Error: check Streamlit Secrets.")
        return None

supabase = init_connection()
CURRENT_USER = "demo_user"

# --- HELPER FUNCTIONS ---
def get_saved_data():
    try:
        response = supabase.table("rtu_data").select("*").eq("profile_id", CURRENT_USER).execute()
        return pd.DataFrame(response.data)
    except:
        return pd.DataFrame()

def extract_sgpa(file):
    try:
        with pdfplumber.open(file) as pdf:
            text = "".join([page.extract_text() for page in pdf.pages])
        match = re.search(r"SGPA[:\s]+(\d+\.\d+)", text)
        return float(match.group(1)) if match else None
    except:
        return None

def save_to_cloud(sem_name, sgpa):
    total_credits = 25.0 # Standard RTU ECE semester average
    data = {
        "profile_id": CURRENT_USER,
        "semester": sem_name,
        "sgpa": sgpa,
        "credits": total_credits,
        "points": sgpa * total_credits
    }
    supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).eq("semester", sem_name).execute()
    supabase.table("rtu_data").insert(data).execute()

# --- UI LAYOUT ---
st.title("📈 RTU CGPA Calculator & Tracker")
st.markdown("---")

# 1. THE GRAPH SECTION (Top Priority)
saved_df = get_saved_data()

if not saved_df.empty:
    saved_df = saved_df.sort_values("semester")
    
    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        total_pts = saved_df["points"].sum()
        total_creds = saved_df["credits"].sum()
        cgpa = total_pts / total_creds if total_creds > 0 else 0
        st.metric("Current CGPA", f"{cgpa:.2f}")
    
    with col_stat2:
        st.write("**SGPA Trend Across Semesters**")
        st.line_chart(saved_df.set_index("semester")["sgpa"])

# 2. THE 4 UPLOAD BOXES (Grid Layout)
st.subheader("Upload Semester Results")
cols = st.columns(4)

semesters = ["Semester 1", "Semester 2", "Semester 3", "Semester 4"]

for i, sem in enumerate(semesters):
    with cols[i]:
        st.markdown(f"### {sem}")
        uploaded_file = st.file_uploader(f"Upload PDF", type="pdf", key=f"up_{sem}")
        
        if uploaded_file:
            if st.button(f"Save {sem}", key=f"btn_{sem}"):
                sgpa_val = extract_sgpa(uploaded_file)
                if sgpa_val:
                    save_to_cloud(sem, sgpa_val)
                    st.success(f"Saved: {sgpa_val}")
                    st.rerun()
                else:
                    st.error("SGPA not found.")

st.markdown("---")

# 3. DATA TABLE
if not saved_df.empty:
    with st.expander("View Detailed Records"):
        st.dataframe(saved_df[["semester", "sgpa", "credits", "created_at"]], use_container_width=True)
        if st.button("🗑️ Clear All Cloud Data"):
            supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).execute()
            st.rerun()
