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
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# Placeholder for user identification (Replace with Auth later)
CURRENT_USER = "demo_user"

# --- DATA LOADING ---
def load_courses():
    with open('courses.json', 'r') as f:
        return json.load(f)

COURSE_DATA = load_courses()

def get_saved_data():
    # Updated table name to rtu_data
    response = supabase.table("rtu_data").select("*").eq("profile_id", CURRENT_USER).execute()
    return pd.DataFrame(response.data)

# --- PDF PROCESSING ---
def extract_sgpa_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
            
    # Simple regex to find SGPA (Adjust based on your actual PDF layout)
    match = re.search(r"SGPA[:\s]+(\d+\.\d+)", text)
    return float(match.group(1)) if match else None

# --- MAIN UI ---
st.title("📈 RTU CGPA Calculator & Tracker")

saved_df = get_saved_data()

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Upload Semester Result")
    uploaded_file = st.file_uploader("Choose your RTU Result PDF", type="pdf")
    
    selected_sem = st.selectbox("Which semester is this?", 
                                ["Semester 1", "Semester 2", "Semester 3", "Semester 4", 
                                 "Semester 5", "Semester 6", "Semester 7", "Semester 8"])

    if uploaded_file and st.button("Analyze & Save to Cloud"):
        sgpa = extract_sgpa_from_pdf(uploaded_file)
        
        if sgpa:
            # Calculate credits/points from COURSE_DATA for the selected_sem
            sem_key = selected_sem.replace(" ", "_").lower()
            courses = COURSE_DATA.get(sem_key, [])
            total_credits = sum(c['credits'] for c in courses)
            total_points = sgpa * total_credits
            
            # Save to Supabase (Updated table name to rtu_data)
            data = {
                "profile_id": CURRENT_USER,
                "semester": selected_sem,
                "sgpa": sgpa,
                "credits": total_credits,
                "points": total_points
            }
            
            # Delete old record for this sem if it exists before inserting
            supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).eq("semester", selected_sem).execute()
            supabase.table("rtu_data").insert(data).execute()
            
            st.success(f"Saved {selected_sem}: {sgpa} SGPA")
            st.rerun()
        else:
            st.error("Could not find SGPA in PDF. Please check the file format.")

with col2:
    st.subheader("Your Progress")
    if not saved_df.empty:
        # Sort and Display
        saved_df = saved_df.sort_values("semester")
        st.dataframe(saved_df[["semester", "sgpa", "credits"]], use_container_width=True)
        
        # Calculate CGPA
        total_pts = saved_df["points"].sum()
        total_creds = saved_df["credits"].sum()
        cgpa = total_pts / total_creds if total_creds > 0 else 0
        
        st.metric("Current CGPA", f"{cgpa:.2f}")
        st.line_chart(saved_df.set_index("semester")["sgpa"])
        
        if st.button("Clear All Data"):
            supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).execute()
            st.rerun()
    else:
        st.info("No data found. Upload a PDF to get started!")
