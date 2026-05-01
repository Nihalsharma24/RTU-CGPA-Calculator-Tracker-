import streamlit as st
import pdfplumber
import pandas as pd
import json

st.set_page_config(page_title="RTU Universal SGPA Calc", layout="centered")

# 1. Read the new JSON Database
with open('courses.json', 'r') as file:
    UNIVERSITY_DATA = json.load(file)

# RTU Grade to Points Mapping
GRADE_POINTS = {
    'A++': 10.0, 'A+': 9.0, 'A': 8.5, 'B+': 8.0, 'B': 7.5,
    'C+': 7.0, 'C': 6.5, 'D+': 6.0, 'D': 5.5, 'E+': 5.0,
    'E': 4.0, 'F': 0.0
}

# --- User Interface & Selection ---
st.title("🎓 RTU Universal SGPA & CGPA Tracker")
st.write("Upload your results semester by semester to build your running CGPA.")

# 1. Initialize the Short-Term Memory Locker
if 'saved_semesters' not in st.session_state:
    st.session_state.saved_semesters = {}

selected_sem = st.selectbox("Select Semester", ["Sem 1", "Sem 2", "Sem 3", "Sem 4"])
COURSE_INFO = UNIVERSITY_DATA["ECE"][selected_sem]

# ... [Keep your exact def extract_grades_from_pdf function here] ...
def extract_grades_from_pdf(pdf_file, active_courses):
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

# --- Math & Display Logic ---
uploaded_file = st.file_uploader(f"Upload {selected_sem} Result PDF", type="pdf")

if uploaded_file is not None:
    try:
        with st.spinner("Analyzing result..."):
            extracted_grades = extract_grades_from_pdf(uploaded_file, COURSE_INFO)
            
            if not extracted_grades:
                st.error("Could not find valid course codes. Ensure you selected the correct semester.")
            else:
                total_credit_points = 0.0
                total_credits = 0.0
                
                cgpa_points = 0.0
                cgpa_credits = 0.0
                
                results_for_display = []
                
                for item in extracted_grades:
                    code = item['Course Code']
                    original_grade = item['Grade']
                    
                    if any(r['Subject Name'] == item['Subject Name'] for r in results_for_display):
                        continue
                        
                    credit = COURSE_INFO[code]['credits']
                    
                    # --- THE NEW BACK-EXAM EXCEPTION LOGIC ---
                    if original_grade == 'F':
                        points = 4.0  # Force the minimum passing 'E' points
                        display_grade = 'F ➔ E (Predicted)'
                    else:
                        points = GRADE_POINTS[original_grade]
                        display_grade = original_grade
                    
                    # Both SGPA and CGPA now calculate including the predicted 4.0 points
                    total_credit_points += (credit * points)
                    total_credits += credit
                    
                    cgpa_points += (credit * points)
                    cgpa_credits += credit
                    
                    results_for_display.append({
                        "Subject Name": item['Subject Name'],
                        "Credits": credit,
                        "Internal Marks": item['Internal Marks'],
                        "External Marks": item['External Marks'],
                        "Grade": display_grade
                    })
                
                if total_credits > 0:
                    sgpa = total_credit_points / total_credits
                    
                    # Save the predicted CGPA numbers to the Locker
                    st.session_state.saved_semesters[selected_sem] = {
                        'points': cgpa_points,
                        'credits': cgpa_credits
                    }
                    
                    # Calculate the running total
                    running_cgpa_points = sum(sem['points'] for sem in st.session_state.saved_semesters.values())
                    running_cgpa_credits = sum(sem['credits'] for sem in st.session_state.saved_semesters.values())
                    
                    col1, col2 = st.columns(2)
                    col1.metric(label=f"Predicted {selected_sem} SGPA", value=f"{sgpa:.2f}")
                    
                    if running_cgpa_credits > 0:
                        running_cgpa = running_cgpa_points / running_cgpa_credits
                        col2.metric(label="Predicted CGPA", value=f"{running_cgpa:.2f}")
                    
                    st.write("### Detailed Breakdown")
                    st.dataframe(pd.DataFrame(results_for_display), use_container_width=True)
                    
                    st.write("---")
                    st.write(f"**Semesters currently tracked in CGPA:** {', '.join(st.session_state.saved_semesters.keys())}")
                        
    except Exception as e:
        st.error(f"An error occurred: {e}")
