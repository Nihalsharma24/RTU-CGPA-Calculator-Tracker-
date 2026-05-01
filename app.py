import streamlit as st
import pdfplumber
import pandas as pd
import json
import io
from supabase import create_client

# --- DASHBOARD CONFIG ---
st.set_page_config(page_title="RTU ECE Analytics", layout="wide")

# Custom Styling for a compact, clean look
st.markdown("""
    <style>
    .stMetric { background: #1a1c23; padding: 10px; border-radius: 10px; border: 1px solid #333; }
    [data-testid="stSidebar"] { background-color: #0e1117; width: 300px !important; }
    .upload-box { border: 1px solid #444; border-radius: 8px; padding: 15px; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()
CURRENT_USER = "demo_user"

# --- DATA & LOGIC ---
with open('courses.json', 'r') as file:
    UNIVERSITY_DATA = json.load(file)

GRADE_POINTS = {
    'A++': 10.0, 'A+': 9.0, 'A': 8.5, 'B+': 8.0, 'B': 7.5,
    'C+': 7.0, 'C': 6.5, 'D+': 6.0, 'D': 5.5, 'E+': 5.0,
    'E': 4.0, 'F': 0.0
}

def get_cloud_data():
    try:
        res = supabase.table("rtu_data").select("*").eq("profile_id", CURRENT_USER).execute()
        return {row['semester']: row for row in res.data}
    except: return {}

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
                            grade = parts[-1] 
                            if grade in GRADE_POINTS:
                                extracted_data.append({'Course Code': code, 'Subject Name': active_courses[code]['name'], 'Grade': grade})
                        except: continue
    return extracted_data

cloud_data = get_cloud_data()

# --- SIDEBAR: ANALYTICS & GRAPH ---
with st.sidebar:
    st.header("📊 Profile Stats")
    if cloud_data:
        sorted_keys = sorted(cloud_data.keys(), key=lambda x: int(x.split()[-1]))
        total_pts = sum(v['points'] for v in cloud_data.values())
        total_creds = sum(v['credits'] for v in cloud_data.values())
        cgpa = total_pts / total_creds if total_creds > 0 else 0
        
        st.metric("Aggregate CGPA", f"{cgpa:.2f}")
        st.write("---")
        
        # Compact Trend Graph
        st.write("**Trend**")
        plot_data = []
        run_pts, run_creds = 0.0, 0.0
        for sem in sorted_keys:
            d = cloud_data[sem]
            run_pts += d['points']
            run_creds += d['credits']
            plot_data.append({"Sem": sem.replace("Semester ", "S"), "SGPA": d['sgpa']})
        
        df = pd.DataFrame(plot_data).set_index("Sem")
        st.line_chart(df, height=200, use_container_width=True)
        
        if st.button("🗑️ Reset All Data", use_container_width=True):
            supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).execute()
            st.rerun()
    else:
        st.info("Upload data to see trends.")

# --- MAIN CONTENT: ACTION AREA ---
st.title("🎓 RTU Performance Dashboard")

# Top row metrics (compact)
m1, m2, m3 = st.columns(3)
if cloud_data:
    m1.write(f"**Semesters:** {len(cloud_data)}/4")
    m2.write(f"**Total Credits:** {int(total_creds)}")
    m3.write(f"**Status:** {'Honors' if cgpa >= 8.5 else 'Pass'}")

st.write("---")

# Compact 2x2 Grid for Uploads
col1, col2 = st.columns(2)
target_sems = [("Semester 1", col1), ("Semester 2", col2), ("Semester 3", col1), ("Semester 4", col2)]

for sem_name, col in target_sems:
    with col:
        with st.container(border=True):
            head_col, status_col = st.columns([2, 1])
            head_col.subheader(sem_name)
            
            if sem_name in cloud_data:
                status_col.success(f"SGPA: {cloud_data[sem_name]['sgpa']:.2f}")
            
            up_file = st.file_uploader(f"Upload Result", type="pdf", key=f"u_{sem_name}", label_visibility="collapsed")
            
            if up_file:
                file_bytes = up_file.getvalue()
                COURSE_INFO = UNIVERSITY_DATA["ECE"][sem_name]
                
                with st.spinner("Syncing..."):
                    extracted = extract_grades_from_pdf(file_bytes, COURSE_INFO)
                    if extracted:
                        sem_pts, sem_creds, seen = 0.0, 0.0, set()
                        display_list = []
                        for item in extracted:
                            if item['Subject Name'] in seen: continue
                            seen.add(item['Subject Name'])
                            
                            code, grade = item['Course Code'], item['Grade']
                            cred = COURSE_INFO[code]['credits']
                            # F -> E conversion logic
                            pts = 4.0 if grade == 'F' else GRADE_POINTS[grade]
                            
                            sem_pts += (cred * pts)
                            sem_creds += cred
                            display_list.append({"Subject": item['Subject Name'], "Grade": 'F➔E' if grade=='F' else grade})
                        
                        if sem_creds > 0:
                            sgpa = sem_pts / sem_creds
                            payload = {"profile_id": CURRENT_USER, "semester": sem_name, "sgpa": sgpa, "points": sem_pts, "credits": sem_creds}
                            supabase.table("rtu_data").upsert(payload).execute()
                            
                            with st.expander("✅ Extraction Complete - View Subjects"):
                                st.table(pd.DataFrame(display_list))
                            
                            st.rerun()
