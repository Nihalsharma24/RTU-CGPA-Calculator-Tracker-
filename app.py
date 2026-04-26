import streamlit as st
import pdfplumber
import pandas as pd

st.set_page_config(page_title="RTU ECE 3rd Sem SGPA Calc", layout="centered")

# RTU Grade to Points Mapping
GRADE_POINTS = {
    'A++': 10.0, 'A+': 9.0, 'A': 8.5, 'B+': 8.0, 'B': 7.5,
    'C+': 7.0, 'C': 6.5, 'D+': 6.0, 'D': 5.5, 'E+': 5.0,
    'E': 4.0, 'F': 0.0
}

# 3rd Sem ECE Info: Course Code -> Subject Name & Credits
COURSE_INFO = {
    '3EC1-02': {'name': 'Technical Communication', 'credits': 2.0},
    '3EC2-01': {'name': 'Adv. Engineering Mathematics-I', 'credits': 3.0},
    '3EC3-24': {'name': 'Computer Programming Lab-I', 'credits': 1.0},
    '3EC4-04': {'name': 'Digital System Design', 'credits': 3.0},
    '3EC4-05': {'name': 'Signal & Systems', 'credits': 3.0},
    '3EC4-06': {'name': 'Network Theory', 'credits': 4.0},
    '3EC4-07': {'name': 'Electronics Devices', 'credits': 4.0},
    '3EC4-21': {'name': 'Electronics Devices Lab', 'credits': 1.0},
    '3EC4-22': {'name': 'Digital System Design Lab', 'credits': 1.0},
    '3EC4-23': {'name': 'Signal Processing Lab', 'credits': 1.0},
    '3EC7-30': {'name': 'Industrial Training', 'credits': 1.0},
    'FEC18': {'name': 'Entrepreneurship Development', 'credits': 0.5}
}

def extract_grades_from_pdf(pdf_file):
    extracted_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            
            for line in text.split('\n'):
                for code in COURSE_INFO.keys():
                    if code in line:
                        parts = line.strip().split()
                        try:
                            # Find where the course code is in the line
                            code_idx = parts.index(code)
                            grade = parts[-1] 
                            
                            # Calculate how many items are after the course code
                            items_after_code = len(parts) - 1 - code_idx
                            
                            # Standard subjects have Midterm, Endterm, and Grade after the code
                            if items_after_code == 3: 
                                internal = parts[code_idx + 1]
                                external = parts[code_idx + 2]
                            # Some subjects (like SODECA/FEC18) might only have an Endterm mark
                            elif items_after_code == 2:
                                internal = "-"
                                external = parts[code_idx + 1]
                            else:
                                internal = "-"
                                external = "-"
                                
                            if grade in GRADE_POINTS:
                                extracted_data.append({
                                    'Course Code': code,
                                    'Subject Name': COURSE_INFO[code]['name'],
                                    'Internal Marks': internal,
                                    'External Marks': external,
                                    'Grade': grade
                                })
                        except ValueError:
                            continue
    return extracted_data

# --- User Interface ---
st.title("🎓 RTU ECE 3rd Sem SGPA Calculator")
st.write("Upload your 3rd Semester result PDF to instantly calculate your SGPA and view your exact marks.")

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
                    
                    # Prevent duplicates
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
                    
                    if total_credits < 24.5:
                        st.warning(f"Note: Only found {total_credits} out of 24.5 total credits. Your PDF might be missing subjects.")
                        
    except Exception as e:
        st.error(f"An error occurred: {e}")
