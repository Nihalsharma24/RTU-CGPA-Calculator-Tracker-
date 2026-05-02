import streamlit as st
import pdfplumber
import pandas as pd
import json
import io
from supabase import create_client

# ═══════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="RTU Performance Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
/* Enhanced metric cards */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1a1c23 0%, #23263a 100%);
    padding: 18px 20px;
    border-radius: 14px;
    border: 1px solid #2e3040;
}
[data-testid="stMetricValue"] { font-size: 1.8rem !important; }

/* SGPA colour badges */
.badge { display:inline-block; padding:3px 11px; border-radius:20px; font-size:.78rem; font-weight:600; }
.badge-s { background:#1a3a2a; color:#4ade80; }   /* ≥ 9.0  — Outstanding */
.badge-a { background:#1e3a1a; color:#86efac; }   /* ≥ 8.0  — Excellent   */
.badge-b { background:#3a3a1a; color:#fde047; }   /* ≥ 7.0  — Good        */
.badge-c { background:#3a2a1a; color:#fb923c; }   /* ≥ 5.5  — Average     */
.badge-d { background:#3a1a1a; color:#f87171; }   /* < 5.5  — Poor        */

/* Sidebar */
[data-testid="stSidebar"] { background-color:#0e1117; width:320px !important; }
.stExpander { border:none !important; }

</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# CONSTANTS & COURSE DATA
# ═══════════════════════════════════════════════════════════
GRADE_POINTS = {
    'A++':10.0, 'A+':9.0, 'A':8.5, 'B+':8.0, 'B':7.5,
    'C+':7.0,  'C':6.5,  'D+':6.0, 'D':5.5,  'E+':5.0,
    'E':4.0,   'F':0.0
}
ALL_GRADES = list(GRADE_POINTS.keys())
SEMESTERS  = ["Sem 1", "Sem 2", "Sem 3", "Sem 4"]

with open('courses.json', 'r') as f:
    UNIVERSITY_DATA = json.load(f)
BRANCHES = list(UNIVERSITY_DATA.keys())   # ['ECE', 'CSE', 'EE', ...]


# ═══════════════════════════════════════════════════════════
# SUPABASE CLIENT
# ═══════════════════════════════════════════════════════════
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()


# ═══════════════════════════════════════════════════════════
# AUTH  ─  Email + Password via Supabase
# ═══════════════════════════════════════════════════════════
def show_auth_page():
    """Renders a centred Login / Sign Up card with two tabs."""
    _, c, _ = st.columns([1, 2, 1])
    with c:
        st.markdown("""
            <div style="text-align:center; padding: 40px 0 20px;">
                <span style="font-size:2.6rem;">🎓</span>
                <h2 style="margin:8px 0 4px;">RTU Performance Dashboard</h2>
                <p style="color:#888; font-size:.9rem;">
                    Track your semester results, SGPA &amp; CGPA in one place.
                </p>
            </div>
        """, unsafe_allow_html=True)

        # ── GUEST CTA  (primary, above the fold) ─────────────
        st.markdown("""
            <p style="text-align:center; color:#aaa; font-size:.85rem; margin-bottom:6px;">
                No account? No problem.
            </p>
        """, unsafe_allow_html=True)

        if st.button(
            "👀  Continue as Guest",
            type="primary",
            use_container_width=True,
            key="btn_guest"
        ):
            st.session_state["user"]      = None
            st.session_state["is_guest"]  = True
            st.rerun()

        st.markdown("""
            <p style="text-align:center; color:#555; font-size:.78rem; margin-top:6px;">
                Guest data is temporary and not saved between sessions.
            </p>
            <div style="display:flex;align-items:center;gap:10px;margin:18px 0;">
                <hr style="flex:1;border-color:#2e3040;">
                <span style="color:#555;font-size:.8rem;">or sign in</span>
                <hr style="flex:1;border-color:#2e3040;">
            </div>
        """, unsafe_allow_html=True)

        # ── LOGIN / SIGNUP tabs (secondary) ──────────────────
        tab_login, tab_signup = st.tabs(["🔑 Log In", "📝 Sign Up"])

        with tab_login:
            email_l    = st.text_input("Email",    key="login_email",    placeholder="you@example.com")
            password_l = st.text_input("Password", key="login_password", type="password", placeholder="••••••••")

            if st.button("Log In", type="primary", use_container_width=True, key="btn_login"):
                if not email_l or not password_l:
                    st.warning("Please fill in both fields.")
                else:
                    try:
                        resp = supabase.auth.sign_in_with_password({
                            "email":    email_l.strip(),
                            "password": password_l
                        })
                        st.session_state["user"]     = resp.user
                        st.session_state["session"]  = resp.session
                        st.session_state["is_guest"] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Login failed: {e}")

        with tab_signup:
            email_s    = st.text_input("Email",            key="signup_email",    placeholder="you@example.com")
            password_s = st.text_input("Password",         key="signup_password", type="password", placeholder="Min. 6 characters")
            password_c = st.text_input("Confirm Password", key="signup_confirm",  type="password", placeholder="Repeat password")

            if st.button("Create Account", type="primary", use_container_width=True, key="btn_signup"):
                if not email_s or not password_s or not password_c:
                    st.warning("Please fill in all fields.")
                elif password_s != password_c:
                    st.error("Passwords do not match.")
                elif len(password_s) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    try:
                        resp = supabase.auth.sign_up({
                            "email":    email_s.strip(),
                            "password": password_s
                        })
                        if resp.user:
                            st.session_state["user"]     = resp.user
                            st.session_state["session"]  = resp.session
                            st.session_state["is_guest"] = False
                            st.rerun()
                        else:
                            st.success("Account created! Check your email to confirm, then log in.")
                    except Exception as e:
                        st.error(f"Sign-up failed: {e}")


if "user" not in st.session_state and "is_guest" not in st.session_state:
    show_auth_page()
    st.stop()

# ── Resolve identity ──────────────────────────────────────────────────────────
IS_GUEST     = st.session_state.get("is_guest", False)
CURRENT_USER = "guest_user" if IS_GUEST else st.session_state["user"].id
USER_EMAIL   = "Guest"      if IS_GUEST else st.session_state["user"].email


# ═══════════════════════════════════════════════════════════
# BRANCH SETUP  ─  shown once on first login
# ═══════════════════════════════════════════════════════════
def get_profile():
    try:
        r = supabase.table("rtu_profiles").select("*").eq("user_id", CURRENT_USER).execute()
        return r.data[0] if r.data else None
    except:
        return None


profile = None if IS_GUEST else get_profile()

if not IS_GUEST and not profile:
    st.title("🎓 RTU Dashboard — First-Time Setup")
    st.info("We just need your branch to get started. This is saved to your account.")
    branch_sel = st.selectbox("Select your Branch", BRANCHES)
    if st.button("Save & Launch Dashboard", type="primary"):
        supabase.table("rtu_profiles").insert({
            "user_id": CURRENT_USER,
            "email":   USER_EMAIL,
            "branch":  branch_sel
        }).execute()
        st.rerun()
    st.stop()

CURRENT_BRANCH = BRANCHES[0] if IS_GUEST else profile["branch"]


# ═══════════════════════════════════════════════════════════
# DB HELPERS
# ═══════════════════════════════════════════════════════════
def get_cloud_data():
    try:
        r = supabase.table("rtu_data").select("*").eq("profile_id", CURRENT_USER).execute()
        return {row['semester']: row for row in sorted(r.data, key=lambda x: x['semester'])}
    except:
        return {}

cloud_data = get_cloud_data()


# ═══════════════════════════════════════════════════════════
# PDF EXTRACTION  (unchanged logic, cached)
# ═══════════════════════════════════════════════════════════
@st.cache_data
def extract_grades_from_pdf(file_content, active_courses):
    extracted = []
    with pdfplumber.open(io.BytesIO(file_content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            for line in text.split('\n'):
                for code in active_courses:
                    if code in line:
                        parts = line.strip().split()
                        try:
                            grade = parts[-1]
                            if grade in GRADE_POINTS:
                                extracted.append({
                                    'Course Code':  code,
                                    'Subject Name': active_courses[code]['name'],
                                    'Grade':        grade
                                })
                        except ValueError:
                            continue
    return extracted


# ═══════════════════════════════════════════════════════════
# UTILITY HELPERS
# ═══════════════════════════════════════════════════════════
def sgpa_badge(sgpa: float) -> str:
    """Return coloured HTML badge for a given SGPA."""
    if sgpa >= 9.0:   cls, icon = "badge-s", "⭐"
    elif sgpa >= 8.0: cls, icon = "badge-a", "✅"
    elif sgpa >= 7.0: cls, icon = "badge-b", "🟡"
    elif sgpa >= 5.5: cls, icon = "badge-c", "🟠"
    else:             cls, icon = "badge-d", "🔴"
    return f'<span class="badge {cls}">{icon} {sgpa:.2f}</span>'


def compute_cgpa(data: dict) -> float:
    """Weighted CGPA: Σ(points) / Σ(credits)."""
    pts   = sum(v['points']  for v in data.values())
    creds = sum(v['credits'] for v in data.values())
    return pts / creds if creds > 0 else 0.0


def sem_total_credits(sem_name: str) -> float:
    """Sum of credits for a semester from courses.json."""
    try:
        return float(sum(v['credits'] for v in UNIVERSITY_DATA[CURRENT_BRANCH][sem_name].values()))
    except KeyError:
        return 20.0


def highlight_fail_rows(row):
    """Red highlight for F ➔ E rows in the subject dataframe."""
    if row.get('Grade') == 'F ➔ E':
        return ['background-color:#3a1a1a; color:#f87171'] * len(row)
    return [''] * len(row)



# ═══════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    # User identity
    if IS_GUEST:
        st.markdown("**👀 Guest Session**")
        st.caption("Data is not saved between sessions.")
        if st.button("🔑 Sign In / Sign Up", use_container_width=True, type="primary"):
            for k in ["user", "session", "is_guest"]:
                st.session_state.pop(k, None)
            st.rerun()
    else:
        st.markdown(f"**👤** {USER_EMAIL}")
        st.caption(f"Branch: **{CURRENT_BRANCH}**")
        if st.button("🚪 Sign Out", use_container_width=True):
            supabase.auth.sign_out()
            for k in ["user", "session", "is_guest"]:
                st.session_state.pop(k, None)
            st.rerun()

    st.write("---")

    # Mobile view toggle
    if "mobile_view" not in st.session_state:
        st.session_state["mobile_view"] = False
    st.session_state["mobile_view"] = st.toggle(
        "📱 Mobile View", value=st.session_state["mobile_view"]
    )

    st.write("---")
    st.markdown("### 📊 Analytics")

    if cloud_data:
        # ── SGPA trend graph ──────────────────────────────
        st.caption("SGPA Trend")
        df_plot = pd.DataFrame(
            [{"Sem": k, "SGPA": v['sgpa']} for k, v in cloud_data.items()]
        ).set_index("Sem")
        st.line_chart(df_plot, height=190, color="#FF4B4B")

        # ── Per-semester score badges ─────────────────────
        st.caption("Semester Scores")
        for sem, d in cloud_data.items():
            c1, c2 = st.columns([1, 1])
            c1.markdown(f"**{sem}**")
            c2.markdown(sgpa_badge(d['sgpa']), unsafe_allow_html=True)

        st.write("---")

        # ── CSV export ───────────────────────────────────
        csv_rows = [
            {
                "Semester": s,
                "SGPA":     f"{d['sgpa']:.2f}",
                "Credits":  d['credits'],
                "Points":   d['points'],
                "Branch":   CURRENT_BRANCH
            }
            for s, d in cloud_data.items()
        ]
        csv_buf = pd.DataFrame(csv_rows).to_csv(index=False)
        st.download_button(
            "⬇️ Export CSV Report",
            data=csv_buf,
            file_name=f"RTU_{CURRENT_BRANCH}_Report.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.write("---")
        if st.button("🗑️ Reset Dashboard", use_container_width=True):
            supabase.table("rtu_data").delete().eq("profile_id", CURRENT_USER).execute()
            st.rerun()
    else:
        st.info("Upload results to see analytics.")


# ═══════════════════════════════════════════════════════════
# MAIN PAGE  ─  Header + Metrics
# ═══════════════════════════════════════════════════════════
st.title("🎓 RTU Performance Dashboard")
st.caption(f"Branch: **{CURRENT_BRANCH}** · {USER_EMAIL}")

if IS_GUEST:
    st.warning(
        "👀 **You're browsing as a Guest.** Results are calculated live but "
        "not saved — they'll be lost when you close the tab. "
        "[Sign up](#) to save your data permanently.",
        icon=None
    )

if cloud_data:
    cgpa  = compute_cgpa(cloud_data)
    best  = max(cloud_data.values(), key=lambda x: x['sgpa'])
    worst = min(cloud_data.values(), key=lambda x: x['sgpa'])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🌟 Predicted CGPA",   f"{cgpa:.2f}")
    m2.metric("📚 Semesters Sync'd", f"{len(cloud_data)} / 4")
    m3.metric("🏆 Best Semester",    f"{best['semester']}  ·  {best['sgpa']:.2f}")
    m4.metric("📉 Needs Attention",  f"{worst['semester']}  ·  {worst['sgpa']:.2f}")
else:
    m1, m2 = st.columns(2)
    m1.metric("🌟 Predicted CGPA",   "–")
    m2.metric("📚 Semesters Sync'd", "0 / 4")

# Progress bar
synced = len(cloud_data)
st.progress(synced / 4, text=f"Semester progress: {synced} / 4 synced")

st.write("---")


# ═══════════════════════════════════════════════════════════
# 2×2 UPLOAD GRID  (collapses to 1-col in mobile view)
# ═══════════════════════════════════════════════════════════
mobile = st.session_state.get("mobile_view", False)

if mobile:
    sem_layout = [(s, st) for s in SEMESTERS]
else:
    col1, col2 = st.columns(2)
    sem_layout = [
        ("Sem 1", col1), ("Sem 2", col2),
        ("Sem 3", col1), ("Sem 4", col2)
    ]

for sem_name, col in sem_layout:
    with col:
        with st.container(border=True):
            h1, h2 = st.columns([2, 1])
            h1.subheader(f"📄 {sem_name}")
            if sem_name in cloud_data:
                h2.markdown(sgpa_badge(cloud_data[sem_name]['sgpa']), unsafe_allow_html=True)

            up = st.file_uploader(
                "Upload", type="pdf",
                key=f"up_{sem_name}",
                label_visibility="collapsed"
            )

            if up:
                file_bytes  = up.getvalue()
                COURSE_INFO = UNIVERSITY_DATA[CURRENT_BRANCH][sem_name]
                extracted   = extract_grades_from_pdf(file_bytes, COURSE_INFO)

                if extracted:
                    sem_pts, sem_creds, seen, rows = 0.0, 0.0, set(), []
                    fail_subjects = []   # track F-grade subjects

                    for item in extracted:
                        if item['Subject Name'] in seen:
                            continue
                        seen.add(item['Subject Name'])

                        code, grade = item['Course Code'], item['Grade']
                        cred = COURSE_INFO[code]['credits']
                        pts  = 4.0 if grade == 'F' else GRADE_POINTS[grade]
                        sem_pts   += cred * pts
                        sem_creds += cred

                        if grade == 'F':
                            fail_subjects.append(item['Subject Name'])

                        rows.append({
                            "Subject": item['Subject Name'],
                            "Credits": cred,
                            "Grade":   'F ➔ E' if grade == 'F' else grade
                        })

                    if sem_creds > 0:
                        sgpa   = sem_pts / sem_creds
                        df_sub = pd.DataFrame(rows)

                        # ── Pending backlogs warning ──────────────────
                        if fail_subjects:
                            backs_list = "\n".join(f"• {s}" for s in fail_subjects)
                            st.warning(
                                f"⚠️ **{len(fail_subjects)} Pending Back(s) Detected**\n\n"
                                f"{backs_list}\n\n"
                                f"📌 *Note: F grades have been treated as E (4.0 pts) "
                                f"for SGPA/CGPA prediction. Clear your backs to improve your actual score.*",
                                icon=None
                            )

                        with st.expander(f"✅ {sgpa:.2f} SGPA — View Subjects & Grade Chart"):
                            styled = df_sub.style.apply(highlight_fail_rows, axis=1)
                            st.dataframe(styled, use_container_width=True, hide_index=True)

                            # F → E calculation note
                            if fail_subjects:
                                st.info(
                                    "ℹ️ **F → E Conversion Applied:** Subjects with F grade are "
                                    "assigned 4.0 grade points (equivalent to E) solely for "
                                    "SGPA/CGPA estimation. This does **not** reflect clearance "
                                    "of the backlog.",
                                    icon=None
                                )

                            # Grade distribution bar chart
                            st.caption("Grade Distribution")
                            grade_counts = (
                                df_sub['Grade']
                                .value_counts()
                                .reindex([g if g != 'F' else 'F ➔ E' for g in ALL_GRADES], fill_value=0)
                                .loc[lambda s: s > 0]
                            )
                            st.bar_chart(grade_counts, height=160)

                        # Auto-upsert if data changed (skip for guests)
                        if not IS_GUEST and (
                            sem_name not in cloud_data or
                            abs(cloud_data[sem_name]['sgpa'] - sgpa) > 0.001
                        ):
                            supabase.table("rtu_data").upsert({
                                "profile_id": CURRENT_USER,
                                "semester":   sem_name,
                                "sgpa":       sgpa,
                                "points":     sem_pts,
                                "credits":    sem_creds,
                                "branch":     CURRENT_BRANCH
                            }).execute()
                            st.rerun()
                else:
                    st.error("No valid RTU subject codes detected in this PDF.")


# ═══════════════════════════════════════════════════════════
# CGPA TARGET CALCULATOR
# ═══════════════════════════════════════════════════════════
st.write("---")
st.subheader("🎯 CGPA Target Calculator")
st.caption("Find out what SGPA you need in remaining semesters to hit your target CGPA.")

remaining_sems = [s for s in SEMESTERS if s not in cloud_data]

if not remaining_sems:
    # All 4 semesters synced — just show final CGPA
    st.success(
        f"✅ All semesters are synced. Your final predicted CGPA is "
        f"**{compute_cgpa(cloud_data):.2f}**.",
        icon=None
    )
elif not cloud_data:
    st.info("Upload at least one semester result to use the target calculator.")
else:
    current_pts   = sum(v['points']  for v in cloud_data.values())
    current_creds = sum(v['credits'] for v in cloud_data.values())
    remaining_creds = sum(sem_total_credits(s) for s in remaining_sems)
    total_creds     = current_creds + remaining_creds

    tc1, tc2 = st.columns([1, 2])

    with tc1:
        target = st.number_input(
            "Target CGPA",
            min_value=4.0, max_value=10.0,
            value=8.0, step=0.1,
            format="%.1f",
            key="target_cgpa"
        )

    # Needed points from remaining sems
    needed_pts   = (target * total_creds) - current_pts
    needed_sgpa  = needed_pts / remaining_creds if remaining_creds > 0 else 0.0

    with tc2:
        if needed_sgpa > 10.0:
            st.error(
                f"❌ **Not achievable.** Even scoring A++ (10.0) in all "
                f"{len(remaining_sems)} remaining semester(s) won't reach a CGPA of {target:.1f}. "
                f"Maximum possible CGPA from here is "
                f"**{(current_pts + 10.0 * remaining_creds) / total_creds:.2f}**.",
                icon=None
            )
        elif needed_sgpa < 4.0:
            st.success(
                f"🎉 **Already on track!** Your current performance guarantees "
                f"a CGPA above {target:.1f} even with minimum passing grades in remaining semesters.",
                icon=None
            )
        else:
            # Colour the metric based on difficulty
            if needed_sgpa >= 9.0:   diff, diff_color = "Very Hard",  "🔴"
            elif needed_sgpa >= 8.0: diff, diff_color = "Hard",       "🟠"
            elif needed_sgpa >= 7.0: diff, diff_color = "Moderate",   "🟡"
            else:                    diff, diff_color = "Achievable",  "🟢"

            r1, r2, r3 = st.columns(3)
            r1.metric("📐 Needed SGPA",      f"{needed_sgpa:.2f}")
            r2.metric("📅 Sems Remaining",   str(len(remaining_sems)))
            r3.metric("📊 Difficulty",       f"{diff_color} {diff}")

            st.caption(
                f"You need an average SGPA of **{needed_sgpa:.2f}** across "
                f"**{', '.join(remaining_sems)}** to achieve a CGPA of **{target:.1f}**."
            )
