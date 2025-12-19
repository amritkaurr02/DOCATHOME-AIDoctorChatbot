import streamlit as st
from PIL import Image
from datetime import datetime
import os
from PyPDF2 import PdfReader
import docx2txt

# Case chat system (your existing module)
from chat_system import (
    get_available_rooms,
    get_messages,
    add_message,
    create_chat_room,
    get_response
)

# Report Q&A system (Gemini + offline)
from report_qa_chat import ReportQASystem


# -----------------------------
# Streamlit Page Setup
# -----------------------------
st.set_page_config(
    page_title="🩺 DOCATHOME – AI Medical Assistant",
    layout="wide"
)

st.sidebar.title("🧭 Navigation")
page = st.sidebar.radio(
    "Choose a section:",
    ["🏠 Dashboard", "💬 Case Chat", "📄 Report Q&A"]
)

# =====================================================
# 🏠 Dashboard
# =====================================================
if page == "🏠 Dashboard":
    st.title("🩺 DOCATHOME")
    st.markdown("""
    **AI-powered medical assistant**  
    - Case-based discussions  
    - Medical report analysis  
    - Doctor-style Q&A using Gemini AI  
    """)

# =====================================================
# 💬 Case Chat
# =====================================================
elif page == "💬 Case Chat":
    st.title("💬 Medical Case Discussion")

    uploaded_file = st.file_uploader(
        "Upload medical image",
        ["jpg", "png", "jpeg"]
    )

    if uploaded_file:
        st.image(Image.open(uploaded_file), use_column_width=True)

    rooms = get_available_rooms()
    if rooms:
        room_map = {
            f"{r['id']} – {r['description']}": r["id"]
            for r in rooms
        }
        selected = st.selectbox("Join Case", room_map.keys())
        if st.button("Join"):
            st.session_state.case_id = room_map[selected]

    desc = st.text_input("New Case Description")
    if st.button("Create Case"):
        st.session_state.case_id = create_chat_room(
            f"CASE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "Radiologist",
            desc or "General Case"
        )

    if "case_id" in st.session_state:
        cid = st.session_state.case_id

        for msg in get_messages(cid):
            role = "assistant" if msg["user"] == "Dr. AI Assistant" else "user"
            with st.chat_message(role):
                st.markdown(msg["content"])

        if user_msg := st.chat_input("Type message"):
            add_message(cid, "Radiologist", user_msg)
            reply = get_response(user_msg, cid)

            with st.chat_message("assistant"):
                st.markdown(reply)

# =====================================================
# 📄 Report Q&A
# =====================================================
elif page == "📄 Report Q&A":
    st.title("📄 Medical Report Q&A")

    # -------------------------------------------------
    # 🔑 Gemini Configuration
    # -------------------------------------------------
    st.subheader("🔑 Gemini Configuration (Optional)")

    env_key = os.getenv("GEMINI_API_KEY")

    gemini_key = st.text_input(
        "Gemini API Key (leave blank for environment variable or offline mode)",
        value=env_key if env_key else "",
        type="password"
    )

    # Initialize / reinitialize QA system only if key changes
    if (
        "qa_system" not in st.session_state
        or st.session_state.get("current_gemini_key") != gemini_key
    ):
        st.session_state.qa_system = ReportQASystem(
            gemini_api_key=gemini_key if gemini_key else None
        )
        st.session_state.current_gemini_key = gemini_key

    if gemini_key:
        st.success("✅ Gemini AI Enabled")
    else:
        st.warning("⚠ Offline analysis mode (no Gemini key)")

    # -------------------------------------------------
    # Upload Report
    # -------------------------------------------------
    st.markdown("---")
    st.subheader("📤 Upload Medical Report")

    uploaded_report = st.file_uploader(
        "Upload report (PDF, TXT, DOCX)",
        type=["pdf", "txt", "docx"]
    )

    if uploaded_report:
        report_content = ""

        if uploaded_report.type == "application/pdf":
            reader = PdfReader(uploaded_report)
            report_content = "\n".join(
                [page.extract_text() or "" for page in reader.pages]
            )

        elif uploaded_report.type == "text/plain":
            report_content = uploaded_report.read().decode(
                "utf-8", errors="ignore"
            )

        elif uploaded_report.type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword"
        ):
            temp_path = f"temp_{uploaded_report.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_report.read())

            report_content = docx2txt.process(temp_path)
            os.remove(temp_path)

        st.success(f"Report **{uploaded_report.name}** uploaded successfully ✅")

        with st.expander("📄 Report Preview"):
            st.text_area(
                "Extracted Report Text",
                report_content,
                height=250
            )

        # -------------------------------------------------
        # Analyze Report
        # -------------------------------------------------
        with st.spinner("Analyzing report like a doctor..."):
            summary = st.session_state.qa_system.analyze_report(
                uploaded_report.name,
                report_content
            )

        st.subheader("🩺 Analysis Summary")
        st.markdown(summary)

    # -------------------------------------------------
    # Ask Questions
    # -------------------------------------------------
    st.markdown("---")
    st.subheader("💬 Ask Questions About Reports")

    if question := st.chat_input("Ask a question based on the uploaded reports"):
        with st.spinner("Thinking..."):
            answer = st.session_state.qa_system.answer_question(question)

        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            st.write(answer)
