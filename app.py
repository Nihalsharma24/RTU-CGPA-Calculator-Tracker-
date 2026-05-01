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
        # Using .strip() to handle any accidental whitespace in the Secrets box
        url = st.secrets["SUPABASE_URL"].strip()
        key = st.secrets["SUPABASE_KEY"].strip()
        return create_client(url, key)
    except Exception as e:
        st.error("🚨 Connection Error: Please check your Streamlit Secrets.")
        return None

supabase = init_connection()
CURRENT_USER = "demo_user"

# --- HELPER FUNCTIONS ---
def get_saved_data():
    try:
        # Connecting to the 'rtu_data' table
        response = supabase.table("rtu_data").select("*").eq("profile_id", CURRENT_USER).execute()
        return pd.DataFrame(response.data)
    except:
        return pd.DataFrame()

def extract_sgpa(file):
    try:
        with pdfplumber.open(file) as pdf:
            # Extract text and normalize to uppercase to handle all variations
            text = "".join([page.extract_text() for page in pdf.pages]).upper()
        
        # Robust patterns to catch different RTU marksheet formats
        patterns = [
            r"S\.?G\.?P\.?A\.?[:\s]+(\d+\.\d+)",  # SGPA: 8.50, S.G.P.A 7.0, etc.
            r"SGPA\s+(\d+\.\d+)",                # SGPA followed by direct spaces
            r"RESULT[:\s]+PASS\s+(\d+\.\d+)"      # Near the final result status
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))
        
        # If extraction fails, show the text for debugging
        # st.text_area("Debug: Extracted Text", text) 
        return None
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return None

def save_to_cloud(sem_name, sgpa):
    # Standard RTU credit estimate (Adjust via courses.json for 100% accuracy)
    total_credits = 25.0 
    data = {
        "profile_id": CURRENT_USER,
        "semester": sem_name,
        "sgpa": sgpa,
        "credits": total_credits,
        "points": sgpa * total_credits
    }
    # Upsert logic: Delete old record for this semester before inserting the new one
    supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).eq("semester", sem_name).execute()
    supabase.table("rtu_data").insert(data).execute()

# --- MAIN UI ---
st.title("📈 RTU CGPA Calculator & Tracker")
st.markdown("---")

if supabase:
    saved_df = get_saved_data()

    # 1. METRICS & TREND GRAPH
    if not saved_df.empty:
        # Sort semesters properly for the chart
        saved_df = saved_df.sort_values("semester")
        
        col_stat1, col_stat2 = st.columns([1, 2])
        
        with col_stat1:
            total_pts = saved_df["points"].sum()
            total_creds = saved_df["credits"].sum()
            # CGPA calculation formula:
            # $$CGPA = \frac{\sum (SGPA_i \times Credits_i)}{\sum Credits_i}$$
            cgpa = total_pts / total_creds if total_creds > 0 else 0
            st.metric("Aggregate CGPA", f"{cgpa:.2f}")
            st.write(f"Total Credits Tracked: **{total_creds}**")
        
        with col_stat2:
            st.write("**SGPA Performance Trend**")
            st.line_chart(saved_df.set_index("semester")["sgpa"])
    else:
        st.info("Upload your first PDF to see your CGPA trend!")

    st.markdown("---")

    # 2. THE 4-COLUMN UPLOAD GRID
    st.subheader("Upload Semester Results")
    cols = st.columns(4)
    target_sems = ["Semester 1", "Semester 2", "Semester 3", "Semester 4"]

    for i, sem in enumerate(target_sems):
        with cols[i]:
            st.markdown(f"### {sem}")
            # Check if this sem already has data
            existing = saved_df[saved_df["semester"] == sem] if not saved_df.empty else pd.DataFrame()
            
            if not existing.empty:
                st.success(f"Current: {existing.iloc[0]['sgpa']}")
            
            up_file = st.file_uploader(f"Choose PDF", type="pdf", key=f"file_{sem}")
            
            if up_file:
                if st.button(f"Save {sem}", key=f"btn_{sem}"):
                    with st.spinner("Processing..."):
                        val = extract_sgpa(up_file)
                        if val:
                            save_to_cloud(sem, val)
                            st.success(f"Updated {sem} to {val}")
                            st.rerun()
                        else:
                            st.error("SGPA not found in PDF.")

    st.markdown("---")

    # 3. DETAILED DATA VIEW
    if not saved_df.empty:
        with st.expander("Cloud Data Management"):
            st.dataframe(saved_df[["semester", "sgpa", "credits", "points"]], use_container_width=True)
            if st.button("🗑️ Wipe All Database Records"):
                supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).execute()
                st.rerun()
else:
    st.warning("Please check your database configuration in the Streamlit Dashboard.")
