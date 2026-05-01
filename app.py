import streamlit as st
import pdfplumber
import pandas as pd
import json
import io
from supabase import create_client

# --- INITIAL SETUP ---
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

# --- DATABASE FETCH ---
def get_cloud_data():
    try:
        res = supabase.table("rtu_data").select("*").eq("profile_id", CURRENT_USER).execute()
        return {row['semester']: row for row in res.data}
    except:
        return {}

cloud_data = get_cloud_data()

# --- PDF EXTRACTION LOGIC ---
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

# --- UI: TOP METRICS ---
st.title("🎓 RTU Performance Dashboard")
metric_col1, metric_col2 = st.columns(2)

if cloud_data:
    total_pts = sum(v['points'] for v in cloud_data.values())
    total_creds = sum(v['credits'] for v in cloud_data.values())
    final_cgpa = total_pts / total_creds if total_creds > 0 else 0
    
    metric_col1.metric("🌟 Predicted CGPA", f"{final_cgpa:.2f}")
    metric_col2.metric("📚 Semesters Sync'd", f"{len(cloud_data)} / 4")
else:
    metric_col1.metric("🌟 Predicted CGPA", "0.00")
    metric_col2.metric("📚 Semesters Sync'd", "0 / 4")

st.write("---")

# --- UI: 2x2 UPLOAD GRID ---
col1, col2 = st.columns(2)
sem_layout = [("Sem 1", col1), ("Sem 2", col2), ("Sem 3", col1), ("Sem 4", col2)]

for sem_name, col in sem_layout:
    with col:
        with st.container(border=True):
            st.subheader(f"📄 {sem_name}")
            
            # Show existing Cloud status
            if sem_name in cloud_data:
                st.success(f"Current SGPA: {cloud_data[sem_name]['sgpa']:.2f}")

            up_file = st.file_uploader(f"Upload Result", type="pdf", key=f"up_{sem_name}", label_visibility="collapsed")
            
            if up_file:
                file_bytes = up_file.getvalue()
                COURSE_INFO = UNIVERSITY_DATA["ECE"][sem_name]
                
                # AUTOMATIC EXTRACTION (No button needed)
                extracted = extract_grades_from_pdf(file_bytes, COURSE_INFO)
                
                if extracted:
                    sem_pts, sem_creds = 0.0, 0.0
                    display_list = []
                    seen = set()
                    
                    for item in extracted:
                        if item['Subject Name'] in seen: continue
                        seen.add(item['Subject Name'])
                        
                        code, grade = item['Course Code'], item['Grade']
                        cred = COURSE_INFO[code]['credits']
                        
                        # YOUR LOGIC: F -> E conversion
                        pts = 4.0 if grade == 'F' else GRADE_POINTS[grade]
                        disp_grade = 'F ➔ E' if grade == 'F' else grade
                        
                        sem_pts += (cred * pts)
                        sem_creds += cred
                        
                        display_list.append({
                            "Subject": item['Subject Name'],
                            "Credits": cred,
                            "Grade": disp_grade
                        })
                    
                    if sem_creds > 0:
                        sgpa = sem_pts / sem_creds
                        
                        # 1. SHOW THE BREAKDOWN (Dropdown/Expander)
                        st.metric(label="Extracted SGPA", value=f"{sgpa:.2f}")
                        with st.expander(f"View {sem_name} Subjects"):
                            st.dataframe(pd.DataFrame(display_list), use_container_width=True, hide_index=True)
                        
                        # 2. AUTOMATIC SYNC TO SUPABASE
                        # We only upsert if the data has changed to prevent infinite reruns
                        if sem_name not in cloud_data or abs(cloud_data[sem_name]['sgpa'] - sgpa) > 0.001:
                            payload = {
                                "profile_id": CURRENT_USER,
                                "semester": sem_name,
                                "sgpa": sgpa,
                                "points": sem_pts,
                                "credits": sem_creds
                            }
                            supabase.table("rtu_data").upsert(payload).execute()
                            st.rerun() 
                else:
                    st.error("No valid RTU codes detected in this PDF.")

# --- FOOTER ---
if cloud_data:
    st.write("---")
    if st.button("🗑️ Reset Cloud Dashboard"):
        supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).execute()
        st.rerun()
