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
st.title("🎓 RTU Universal SGPA Calculator")
st.write("Select your semester and upload your result PDF.")

# 2. Add the Dropdown Menu
selected_sem = st.selectbox("Select Semester", ["Sem 1", "Sem 2", "Sem 3", "Sem 4"])

# 3. Set the active course list based on what the user picked
COURSE_INFO = UNIVERSITY_DATA["ECE"][selected_sem]

# --- The Extractor Function ---
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
uploaded_file = st.file_uploader("Upload Result PDF", type="pdf")

if uploaded_file is not None:
    try:
        with st.spinner("Analyzing result..."):
            extracted_grades = extract_grades_from_pdf(uploaded_file, COURSE_INFO)
            
            if not extracted_grades:
                st.error("Could not find valid course codes or grades. Ensure you selected the correct semester.")
            else:
                total_credit_points = 0.0
                total_credits = 0.0
                results_for_display = []
                
                for item in extracted_grades:
                    code = item['Course Code']
                    grade = item['Grade']
                    
                    if any(r['Subject Name'] == item['Subject Name'] for r in results_for_display):
                        continue
                        
                    credit = COURSE_INFO[code]['credits']
                    points = GRADE_POINTS[grade]
                    
                    total_credit_points += (credit * points)
                    total_credits += credit
                    
                    results_for_display.append({
                        "Subject Name": item['Subject Name'],
                        "Credits": credit,
                        "Internal Marks": item['Internal Marks'],
                        "External Marks": item['External Marks'],
                        "Grade": grade
                    })
                
                if total_credits > 0:
                    sgpa = total_credit_points / total_credits
                    
                    st.metric(label="Calculated SGPA", value=f"{sgpa:.2f}")
                    
                    st.write("### Detailed Breakdown")
                    st.dataframe(pd.DataFrame(results_for_display), use_container_width=True)
                        
    except Exception as e:
        st.error(f"An error occurred: {e}")
