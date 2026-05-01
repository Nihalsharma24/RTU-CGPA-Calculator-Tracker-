import streamlit as st
import pdfplumber
import pandas as pd
import json
import io
from supabase import create_client

# --- DASHBOARD THEME & CONFIG ---
st.set_page_config(page_title="RTU ECE Analytics", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for a modern, compact "Nothing-inspired" UI
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 2.2rem; font-weight: 700; color: #FF4B4B; }
    .stMetric { background: #111; padding: 15px; border-radius: 12px; border: 1px solid #333; }
    .upload-card { background: #0e1117; padding: 10px; border-radius: 8px; border: 1px dashed #444; }
    .stExpander { border: none !important; box-shadow: none !important; }
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

# --- UI HEADER: QUICK STATS ---
st.title("📊 ECE Performance Analytics")
m1, m2, m3, m4 = st.columns(4)

if cloud_data:
    # Sorting semesters numerically for the logic
    sorted_keys = sorted(cloud_data.keys(), key=lambda x: int(x.split()[-1]))
    total_pts = sum(v['points'] for v in cloud_data.values())
    total_creds = sum(v['credits'] for v in cloud_data.values())
    cgpa = total_pts / total_creds if total_creds > 0 else 0
    
    m1.metric("Current CGPA", f"{cgpa:.2f}")
    m2.metric("Total Credits", f"{int(total_creds)}")
    
    # Simple logic for "Trajectory" based on last upload
    last_sgpa = cloud_data[sorted_keys[-1]]['sgpa']
    m3.metric("Latest SGPA", f"{last_sgpa:.2f}", delta=f"{(last_sgpa - cgpa):.2f}" if len(cloud_data) > 1 else None)
    
    status = "Honors" if cgpa >= 8.5 else "First Div" if cgpa >= 6.0 else "Regular"
    m4.metric("Status", status)
else:
    for m in [m1, m2, m3, m4]: m.metric("-", "0.00")

st.write("---")

# --- MAIN DASHBOARD: GRAPH AREA ---
if cloud_data:
    # Prepare DataFrame for the "Beautiful Graph"
    plot_data = []
    run_pts, run_creds = 0.0, 0.0
    for sem in sorted_keys:
        d = cloud_data[sem]
        run_pts += d['points']
        run_creds += d['credits']
        plot_data.append({"Semester": sem, "SGPA": d['sgpa'], "Running CGPA": run_pts / run_creds})
    
    df = pd.DataFrame(plot_data).set_index("Semester")
    
    # Beautiful Line Chart with custom height
    st.write("### 📈 Performance Trend")
    st.line_chart(df, y=["SGPA", "Running CGPA"], color=["#FF4B4B", "#0068C9"], height=350)
else:
    st.info("No data found. Upload your first marksheet to generate the trend graph.")

st.write("---")

# --- UI: COMPACT ACTION BAR (Horizontal Uploaders) ---
st.write("### 📥 Semester Actions")
upload_cols = st.columns(4)
target_sems = ["Semester 1", "Semester 2", "Semester 3", "Semester 4"]

for i, sem in enumerate(target_sems):
    with upload_cols[i]:
        # Using a thin expander for "Less space"
        with st.expander(f"⚙️ {sem}", expanded=(sem not in cloud_data)):
            if sem in cloud_data:
                st.caption(f"Stored: {cloud_data[sem]['sgpa']:.2f}")
            
            up_file = st.file_uploader("Drop PDF", type="pdf", key=f"u_{sem}", label_visibility="collapsed")
            
            if up_file:
                file_bytes = up_file.getvalue()
                COURSE_INFO = UNIVERSITY_DATA["ECE"][sem]
                
                with st.spinner("Syncing..."):
                    extracted = extract_grades_from_pdf(file_bytes, COURSE_INFO)
                    if extracted:
                        sem_pts, sem_creds, seen = 0.0, 0.0, set()
                        for item in extracted:
                            if item['Subject Name'] in seen: continue
                            seen.add(item['Subject Name'])
                            
                            code, grade = item['Course Code'], item['Grade']
                            cred = COURSE_INFO[code]['credits']
                            pts = 4.0 if grade == 'F' else GRADE_POINTS[grade]
                            
                            sem_pts += (cred * pts)
                            sem_creds += cred
                        
                        if sem_creds > 0:
                            sgpa = sem_pts / sem_creds
                            payload = {"profile_id": CURRENT_USER, "semester": sem, "sgpa": sgpa, "points": sem_pts, "credits": sem_creds}
                            supabase.table("rtu_data").upsert(payload).execute()
                            st.rerun()

# --- QoL FOOTER ---
if cloud_data:
    st.write("---")
    with st.expander("🛠️ Advanced Options"):
        c1, c2 = st.columns([3, 1])
        c1.write("Download your cloud data as CSV for your own records.")
        if c1.button("Export CSV"):
            pd.DataFrame(list(cloud_data.values())).to_csv("my_grades.csv")
            st.toast("Exported!")
        
        if c2.button("🗑️ Reset All", use_container_width=True):
            supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).execute()
            st.rerun()
