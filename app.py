import streamlit as st
import pdfplumber
import pandas as pd
import json
import io

# QoL: 'wide' layout is required for the split dashboard to look good
st.set_page_config(page_title="RTU SGPA & CGPA Tracker", layout="wide")

with open('courses.json', 'r') as file:
    UNIVERSITY_DATA = json.load(file)

GRADE_POINTS = {
    'A++': 10.0, 'A+': 9.0, 'A': 8.5, 'B+': 8.0, 'B': 7.5,
    'C+': 7.0, 'C': 6.5, 'D+': 6.0, 'D': 5.5, 'E+': 5.0,
    'E': 4.0, 'F': 0.0
}

# The cache prevents the app from re-reading old PDFs when a new one is uploaded
@st.cache_data
def extract_grades_from_pdf(file_content, active_courses):
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

st.title("🎓 RTU Performance Dashboard")
st.write("Upload your results on the left to build your running CGPA profile.")
st.write("---")

# --- UI: The 60/40 Split ---
left_panel, right_panel = st.columns([2, 1], gap="large")

# NEW: A dictionary to hold our data before we chart it
processed_semesters = {}

# --- THE ACTION AREA (Left Panel) ---
with left_panel:
    st.subheader("📥 Upload Results")
    
    col1, col2 = st.columns(2)
    sem_layout = [("Sem 1", col1), ("Sem 2", col2), ("Sem 3", col1), ("Sem 4", col2)]

    for sem_name, col in sem_layout:
        with col:
            with st.container(border=True):
                st.write(f"**{sem_name}**")
                uploaded_file = st.file_uploader(f"Upload Result", type="pdf", key=f"file_{sem_name}", label_visibility="collapsed")
                
                if uploaded_file is not None:
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
                                
                                if any(r['Subject Name'] == item['Subject Name'] for r in results_for_display):
                                    continue
                                    
                                credit = COURSE_INFO[code]['credits']
                                
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
                                
                                # NEW: Save the math into our dictionary instead of global variables
                                processed_semesters[sem_name] = {
                                    "sgpa": sgpa,
                                    "points": sem_points,
                                    "credits": sem_credits
                                }
                                
                                st.metric(label="Predicted SGPA", value=f"{sgpa:.2f}")
                                
                                with st.expander("View Subjects"):
                                    st.dataframe(pd.DataFrame(results_for_display), use_container_width=True, hide_index=True)
                else:
                    st.info(f"Awaiting {sem_name} PDF...")

# --- THE INSIGHTS AREA (Right Panel) ---
with right_panel:
    st.subheader("📊 Your Profile")
    
    with st.container(border=True):
        if processed_semesters:
            # 1. Sort the semesters chronologically so the graph flows left to right
            sorted_sems = sorted(processed_semesters.keys())
            
            # 2. Build the timeline data
            timeline_data = []
            run_points = 0.0
            run_credits = 0.0
            
            for sem in sorted_sems:
                data = processed_semesters[sem]
                run_points += data['points']
                run_credits += data['credits']
                
                timeline_data.append({
                    "Semester": sem,
                    "SGPA": data['sgpa'],
                    "CGPA": run_points / run_credits
                })
            
            # 3. Final global metrics
            final_cgpa = run_points / run_credits
            semesters_uploaded = len(processed_semesters)
            
            st.metric(label="🌟 Predicted CGPA", value=f"{final_cgpa:.2f}")
            st.caption(f"Tracking {semesters_uploaded} / 4 Semesters")
            
            st.write("---")
            
            # 4. DRAW THE CHART
            st.write("**Performance Trend**")
            # We convert our list of data into a Pandas DataFrame and tell it to use "Semester" as the X-axis
            df_chart = pd.DataFrame(timeline_data).set_index("Semester")
            
            # Streamlit's native line chart. We explicitly map the Y-axis lines and give them distinct colors.
            st.line_chart(df_chart, y=["SGPA", "CGPA"], color=["#FF4B4B", "#0068C9"])
            
            st.write("---")
            
            # 5. Dynamic Trajectory Feedback
            if final_cgpa >= 8.5:
                st.success("🔥 Honors Trajectory! Keep it up.")
            elif final_cgpa >= 7.0:
                st.info("👍 Solid standing. You're doing great.")
            else:
                st.warning("Keep pushing, you've got this!")
        else:
            st.write("Upload at least one semester on the left to see your dashboard insights here.")
            st.caption("Your overall metrics, trajectory graph, and insights will appear here once data is calculated.")
