import streamlit as st
import pdfplumber
import pandas as pd

st.set_page_config(page_title="RTU ECE 3rd Sem SGPA Calc", layout="centered")

# RTU Grade to Points Mapping (From official guidelines)
GRADE_POINTS = {
    'A++': 10.0, 'A+': 9.0, 'A': 8.5, 'B+': 8.0, 'B': 7.5,
    'C+': 7.0, 'C': 6.5, 'D+': 6.0, 'D': 5.5, 'E+': 5.0,
    'E': 4.0, 'F': 0.0
}

# 3rd Sem ECE Credits Mapping (Hardcoded since PDFs lack credits)
COURSE_CREDITS = {
    '3EC1-02': 2.0,  # Technical Communication
    '3EC2-01': 3.0,  # Adv. Engineering Mathematics-I
    '3EC3-24': 1.0,  # Computer Programming Lab-I
    '3EC4-04': 3.0,  # Digital System Design
    '3EC4-05': 3.0,  # Signal & Systems
    '3EC4-06': 4.0,  # Network Theory
    '3EC4-07': 4.0,  # Electronics Devices
    '3EC4-21': 1.0,  # Electronics Devices Lab
    '3EC4-22': 1.0,  # Digital System Design Lab
    '3EC4-23': 1.0,  # Signal Processing Lab
    '3EC7-30': 1.0,  # Industrial Training
    'FEC18': 0.5     # Entrepreneurship development / SODECA
}

def extract_grades_from_pdf(pdf_file):
    extracted_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            
            # Read line by line and look for course codes
            for line in text.split('\n'):
                for code in COURSE_CREDITS.keys():
                    if code in line:
                        # The grade is typically the last word on the line
                        parts = line.strip().split()
                        grade = parts[-1] 
                        if grade in GRADE_POINTS:
                            extracted_data.append({
                                'Course Code': code,
                                'Grade': grade
                            })
    return extracted_data

# --- User Interface ---
st.title("🎓 RTU ECE 3rd Sem SGPA Calculator")
st.write("Upload your 3rd Semester result PDF to instantly calculate your SGPA. No manual math required.")

uploaded_file = st.file_uploader("Upload Result PDF", type="pdf")

if uploaded_file is not None:
    try:
        with st.spinner("Analyzing result..."):
            extracted_grades = extract_grades_from_pdf(uploaded_file)
            
            if not extracted_grades:
                st.error("Could not find valid course codes or grades. Ensure it's the 3rd Sem ECE result.")
            else:
                total_credit_points = 0.0
                total_credits = 0.0
                results_for_display = []
                
                for item in extracted_grades:
                    code = item['Course Code']
                    grade = item['Grade']
                    
                    # Prevent duplicates if a course appears twice in text extraction
                    if any(r['Course Code'] == code for r in results_for_display):
                        continue
                        
                    credit = COURSE_CREDITS[code]
                    points = GRADE_POINTS[grade]
                    
                    earned_points = credit * points
                    total_credit_points += earned_points
                    total_credits += credit
                    
                    results_for_display.append({
                        "Course Code": code,
                        "Credits": credit,
                        "Grade": grade,
                        "Points Earned": earned_points
                    })
                
                if total_credits > 0:
                    sgpa = total_credit_points / total_credits
                    
                    st.metric(label="Calculated SGPA", value=f"{sgpa:.2f}")
                    
                    st.write("### Detailed Breakdown")
                    st.dataframe(pd.DataFrame(results_for_display), use_container_width=True)
                    
                    if total_credits < 24.5:
                        st.warning(f"Note: Only found {total_credits} out of 24.5 total credits. Your PDF might be missing subjects.")
                        
    except Exception as e:
        st.error(f"An error occurred: {e}")
