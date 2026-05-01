import streamlit as st
import pdfplumber
import pandas as pd
import json
import io
from supabase import create_client

# --- CONFIG & DATABASE ---
st.set_page_config(page_title="RTU Performance Dashboard", layout="wide")

@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()
CURRENT_USER = "demo_user"

# --- DATA LOADING ---
with open('courses.json', 'r') as file:
    UNIVERSITY_DATA = json.load(file)

GRADE_POINTS = {
    'A++': 10.0, 'A+': 9.0, 'A': 8.5, 'B+': 8.0, 'B': 7.5,
    'C+': 7.0, 'C': 6.5, 'D+': 6.0, 'D': 5.5, 'E+': 5.0,
    'E': 4.0, 'F': 0.0
}

# --- PERSISTENCE: FETCH FROM CLOUD ---
def get_cloud_data():
    res = supabase.table("rtu_data").select("*").eq("profile_id", CURRENT_USER).execute()
    return {row['semester']: row for row in res.data}

cloud_data = get_cloud_data()

# --- EXTRACTION LOGIC (Preserved) ---
@st.cache_data
def extract_grades_from_pdf(file_content, active_courses):
    pdf_file = io.BytesIO(file_content)
    extracted_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            for line in text.split('\n'):
                for code in active_courses.keys(): 
                    if code in line:
                        parts = line.strip().split()
                        try:
                            code_idx = parts.index(code)
                            grade = parts[-1] 
                            if grade in GRADE_POINTS:
                                extracted_data.append({
                                    'Course Code': code,
                                    'Subject Name': active_courses[code]['name'],
                                    'Grade': grade
                                })
                        except ValueError: continue
    return extracted_data

# --- UI: HEADER & METRICS ---
st.title("🎓 RTU Performance Dashboard")
metric_container = st.container()

# Calculate Global CGPA from Cloud Data
if cloud_data:
    total_pts = sum(v['points'] for v in cloud_data.values())
    total_creds = sum(v['credits'] for v in cloud_data.values())
    running_cgpa = total_pts / total_creds if total_creds > 0 else 0
    
    with metric_container:
        c1, c2 = st.columns(2)
        c1.metric("🌟 Predicted CGPA", f"{running_cgpa:.2f}")
        c2.metric("📚 Semesters Sync'd", f"{len(cloud_data)} / 4")
        if running_cgpa >= 8.5: st.success("Honors Trajectory! Keep it up.")

st.write("---")

# --- UI: 2x2 GRID ---
col1, col2 = st.columns(2)
sem_layout = [("Sem 1", col1), ("Sem 2", col2), ("Sem 3", col1), ("Sem 4", col2)]

for sem_name, col in sem_layout:
    with col:
        with st.container(border=True):
            st.subheader(f"📄 {sem_name}")
            
            # Check if we already have this sem in the cloud
            if sem_name in cloud_data:
                st.success(f"Current SGPA: {cloud_data[sem_name]['sgpa']:.2f}")
            
            uploaded_file = st.file_uploader(f"Upload", type="pdf", key=f"file_{sem_name}", label_visibility="collapsed")
            
            if uploaded_file:
                file_bytes = uploaded_file.getvalue()
                COURSE_INFO = UNIVERSITY_DATA["ECE"][sem_name]
                
                with st.spinner("Processing & Syncing..."):
                    extracted = extract_grades_from_pdf(file_bytes, COURSE_INFO)
                    
                    if extracted:
                        sem_points, sem_credits = 0.0, 0.0
                        seen_subjects = set()
                        
                        for item in extracted:
                            if item['Subject Name'] in seen_subjects: continue
                            seen_subjects.add(item['Subject Name'])
                            
                            code = item['Course Code']
                            grade = item['Grade']
                            credit = COURSE_INFO[code]['credits']
                            
                            # YOUR LOGIC: F -> E conversion
                            points = 4.0 if grade == 'F' else GRADE_POINTS[grade]
                            
                            sem_points += (credit * points)
                            sem_credits += credit
                        
                        if sem_credits > 0:
                            sgpa = sem_points / sem_credits
                            
                            # SYNC TO SUPABASE
                            payload = {
                                "profile_id": CURRENT_USER,
                                "semester": sem_name,
                                "sgpa": sgpa,
                                "points": sem_points,
                                "credits": sem_credits
                            }
                            supabase.table("rtu_data").upsert(payload).execute()
                            st.rerun() # Refresh to update the top metrics
                    else:
                        st.error("No valid course codes detected.")

# --- FOOTER ---
if cloud_data:
    with st.expander("🗑️ Database Management"):
        if st.button("Clear All Cloud Records"):
            supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).execute()
            st.rerun()
