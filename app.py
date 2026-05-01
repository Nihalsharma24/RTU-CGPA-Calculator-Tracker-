import streamlit as st
import pdfplumber
import pandas as pd
import json

# QoL: 'wide' layout gives us more horizontal space for a dashboard
st.set_page_config(page_title="RTU SGPA & CGPA Tracker", layout="wide")

with open('courses.json', 'r') as file:
    UNIVERSITY_DATA = json.load(file)

GRADE_POINTS = {
    'A++': 10.0, 'A+': 9.0, 'A': 8.5, 'B+': 8.0, 'B': 7.5,
    'C+': 7.0, 'C': 6.5, 'D+': 6.0, 'D': 5.5, 'E+': 5.0,
    'E': 4.0, 'F': 0.0
}

# --- THE CACHE: Prevents the app from slowing down when multiple PDFs are uploaded ---
@st.cache_data
def extract_grades_from_pdf(file_content, active_courses):
    # We pass file_content (bytes) so Streamlit can cache it easily
    import io
    pdf_file = io.BytesIO(file_content)
    
    extracted_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            
            for line in text.split('\n'):
                for code in active_courses.keys(): 
                    if code in line:
                        parts = line.strip().split()
                        try:
                            code_idx = parts.index(code)
                            grade = parts[-1] 
                            items_after_code = len(parts) - 1 - code_idx
                            
                            if items_after_code >= 3: 
                                internal = parts[code_idx + 1]
                                external = parts[code_idx + 2]
                            elif items_after_code == 2:
                                internal = "-"
                                external = parts[code_idx + 1]
                            else:
                                internal = "-"
                                external = "-"
                                
                            if grade in GRADE_POINTS:
                                extracted_data.append({
                                    'Course Code': code,
                                    'Subject Name': active_courses[code]['name'],
                                    'Internal Marks': internal,
                                    'External Marks': external,
                                    'Grade': grade
                                })
                        except ValueError:
                            continue
    return extracted_data

# --- UI: The Dashboard Header ---
st.title("🎓 RTU Performance Dashboard")
st.write("Upload your results below to build your running CGPA profile.")

# We create empty placeholders at the top for the final numbers
# We have to calculate the math below, but we want the score displayed at the top!
metric_container = st.container()

st.write("---")

# --- UI: The 2x2 Upload Grid ---
col1, col2 = st.columns(2)

# Organizing the layout: Sem 1 & 3 on the left, Sem 2 & 4 on the right
sem_layout = [("Sem 1", col1), ("Sem 2", col2), ("Sem 3", col1), ("Sem 4", col2)]

global_cgpa_points = 0.0
global_cgpa_credits = 0.0
semesters_uploaded = 0

for sem_name, col in sem_layout:
    with col:
        # A clean visual card for each semester
        with st.container(border=True):
            st.subheader(f"📄 {sem_name}")
            
            # Each uploader gets a unique key so Streamlit doesn't confuse them
            uploaded_file = st.file_uploader(f"Upload Result", type="pdf", key=f"file_{sem_name}", label_visibility="collapsed")
            
            if uploaded_file is not None:
                # Read the file to bytes for the caching function
                file_bytes = uploaded_file.getvalue()
                COURSE_INFO = UNIVERSITY_DATA["ECE"][sem_name]
                
                with st.spinner("Analyzing..."):
                    extracted_grades = extract_grades_from_pdf(file_bytes, COURSE_INFO)
                    
                    if not extracted_grades:
                        st.error("No valid codes found.")
                    else:
                        sem_points = 0.0
                        sem_credits = 0.0
                        results_for_display = []
                        
                        for item in extracted_grades:
                            code = item['Course Code']
                            original_grade = item['Grade']
                            
                            # Deduplicate subjects
                            if any(r['Subject Name'] == item['Subject Name'] for r in results_for_display):
                                continue
                                
                            credit = COURSE_INFO[code]['credits']
                            
                            # The Back-Exam Exception
                            if original_grade == 'F':
                                points = 4.0  
                                display_grade = 'F ➔ E'
                            else:
                                points = GRADE_POINTS[original_grade]
                                display_grade = original_grade
                            
                            sem_points += (credit * points)
                            sem_credits += credit
                            
                            results_for_display.append({
                                "Subject Name": item['Subject Name'],
                                "Credits": credit,
                                "Grade": display_grade
                            })
                        
                        if sem_credits > 0:
                            sgpa = sem_points / sem_credits
                            
                            # Add to the global CGPA buckets
                            global_cgpa_points += sem_points
                            global_cgpa_credits += sem_credits
                            semesters_uploaded += 1
                            
                            st.metric(label="Predicted SGPA", value=f"{sgpa:.2f}")
                            
                            with st.expander("View Subjects"):
                                st.dataframe(pd.DataFrame(results_for_display), use_container_width=True, hide_index=True)
            else:
                st.info(f"Awaiting {sem_name} PDF...")

# --- Math: Injecting the final CGPA into the top placeholders ---
with metric_container:
    if global_cgpa_credits > 0:
        running_cgpa = global_cgpa_points / global_cgpa_credits
        
        # Display massive metrics at the top
        cgpa_col, info_col = st.columns(2)
        cgpa_col.metric(label="🌟 Predicted CGPA", value=f"{running_cgpa:.2f}")
        info_col.metric(label="📚 Semesters Tracked", value=f"{semesters_uploaded} / 4")
        
        if running_cgpa >= 8.5:
            st.success("Honors Trajectory! Keep it up.")
