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
            # Extract all text and normalize for searching
            raw_text = "".join([page.extract_text() for page in pdf.pages])
            clean_text = raw_text.upper()
        
        if not clean_text.strip():
            st.error("No text detected. If this is a photo/scan, use a digital PDF instead.")
            return None

        # Enhanced patterns for RTU Marksheets
        patterns = [
            r"S\.?G\.?P\.?A\.?[\s:]+([\d.]+)",           # SGPA: 8.50, S.G.P.A 7.0
            r"SEMESTER GRADE POINT AVERAGE[\s:]+([\d.]+)", # Full label
            r"SGPA\s+([\d.]+)",                          # SGPA followed by number
            r"RESULT[\s:]+PASS[\s\w]+([\d.]+)"           # Near the final status
        ]
        
        for p in patterns:
            match = re.search(p, clean_text)
            if match:
                return float(match.group(1))
        
        # If it still fails, show the raw text to debug the layout
        with st.expander("🔍 Debug: Why did it fail? (View Extracted Text)"):
            st.write("The app searched for SGPA in the text below but couldn't find a match:")
            st.code(raw_text)
        
        return None
    except Exception as e:
        st.error(f"Extraction Error: {e}")
        return None

def save_to_cloud(sem_name, sgpa):
    # Default credits for RTU ECE semesters (can be refined later)
    total_credits = 24.0 
    data = {
        "profile_id": CURRENT_USER,
        "semester": sem_name,
        "sgpa": sgpa,
        "credits": total_credits,
        "points": sgpa * total_credits
    }
    # Clear old data for this sem before saving new one
    supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).eq("semester", sem_name).execute()
    supabase.table("rtu_data").insert(data).execute()

# --- MAIN UI ---
st.title("📈 RTU CGPA Calculator & Tracker")
st.markdown("---")

if supabase:
    saved_df = get_saved_data()

    # 1. METRICS & PERFORMANCE GRAPH
    if not saved_df.empty:
        # Sort semesters logically for the graph
        saved_df = saved_df.sort_values("semester")
        
        col_stat1, col_stat2 = st.columns([1, 2])
        
        with col_stat1:
            total_pts = saved_df["points"].sum()
            total_creds = saved_df["credits"].sum()
            
            # CGPA Formula
            # $$CGPA = \frac{\sum (SGPA_i \times Credits_i)}{\sum Credits_i}$$
            cgpa = total_pts / total_creds if total_creds > 0 else 0
            
            st.metric("Aggregate CGPA", f"{cgpa:.2f}")
            st.write(f"Total Credits: **{total_creds}**")
        
        with col_stat2:
            st.line_chart(saved_df.set_index("semester")["sgpa"])
    else:
        st.info("Upload your first PDF to see your trend!")

    st.markdown("---")

    # 2. THE 4-COLUMN UPLOAD GRID
    st.subheader("Upload Semester Results")
    cols = st.columns(4)
    target_sems = ["Semester 1", "Semester 2", "Semester 3", "Semester 4"]

    for i, sem in enumerate(target_sems):
        with cols[i]:
            st.markdown(f"### {sem}")
            
            # Show existing SGPA if available
            if not saved_df.empty:
                existing = saved_df[saved_df["semester"] == sem]
                if not existing.empty:
                    st.success(f"Current SGPA: {existing.iloc[0]['sgpa']}")
            
            up_file = st.file_uploader(f"Choose PDF", type="pdf", key=f"file_{sem}")
            
            if up_file:
                if st.button(f"Save {sem}", key=f"btn_{sem}"):
                    with st.spinner("Reading PDF..."):
                        val = extract_sgpa(up_file)
                        if val:
                            save_to_cloud(sem, val)
                            st.success(f"Successfully saved {val}")
                            st.rerun()
                        else:
                            st.error("SGPA not found in PDF.")

    st.markdown("---")

    # 3. DATABASE MANAGEMENT
    if not saved_df.empty:
        with st.expander("Cloud Database Management"):
            st.dataframe(saved_df[["semester", "sgpa", "credits"]], use_container_width=True)
            if st.button("🗑️ Clear All Saved Data"):
                supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).execute()
                st.rerun()
else:
    st.warning("Database connection is inactive. Check your Supabase credentials.")
