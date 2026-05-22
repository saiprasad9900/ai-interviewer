"""
app.py — Streamlit frontend for the AI Interview Agent (ARIA).

Run with:  streamlit run frontend/app.py
Expects FastAPI backend at http://localhost:8000  (set API_BASE env var to override)
"""

import os
import sys
import time
import requests
import streamlit as st

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from avatar_ui import render_interviewer_avatar, render_interviewer_preview
from backend.secrets_config import bootstrap_groq_api_key, groq_configured

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
bootstrap_groq_api_key()
API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(
    page_title="ARIA – AI Interview Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Re-load after Streamlit secrets are available (Streamlit Cloud)
bootstrap_groq_api_key()

# ─────────────────────────────────────────────
# Styling
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
.stApp { background: #0d0f17; color: #e8eaf0; }
[data-testid="stSidebar"] { background: #13151f !important; border-right: 1px solid #1e2230; }

.card {
    background: #13151f; border: 1px solid #1e2230;
    border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem;
}
.question-box {
    background: linear-gradient(135deg, #1a1d2e, #151824);
    border-left: 4px solid #6c63ff; border-radius: 8px;
    padding: 1.5rem 2rem; font-size: 1.15rem; font-weight: 500;
    color: #ffffff; margin: 1.5rem 0;
    box-shadow: 0 4px 20px rgba(108,99,255,0.15);
}
.score-badge { display:inline-block; padding:4px 14px; border-radius:20px; font-size:0.85rem; font-weight:700; font-family:'JetBrains Mono',monospace; }
.score-high { background:#1a3a2a; color:#4ade80; border:1px solid #22c55e; }
.score-mid  { background:#3a2e1a; color:#fbbf24; border:1px solid #f59e0b; }
.score-low  { background:#3a1a1a; color:#f87171; border:1px solid #ef4444; }
.pill-easy   { background:#1a3a2a; color:#4ade80;  padding:3px 10px; border-radius:12px; font-size:0.78rem; font-weight:600; }
.pill-medium { background:#3a2e1a; color:#fbbf24;  padding:3px 10px; border-radius:12px; font-size:0.78rem; font-weight:600; }
.pill-hard   { background:#3a1a1a; color:#f87171;  padding:3px 10px; border-radius:12px; font-size:0.78rem; font-weight:600; }
.rec-strong { background:#162a1e; border:1px solid #22c55e; color:#4ade80; }
.rec-hire   { background:#1a2a38; border:1px solid #60a5fa; color:#93c5fd; }
.rec-maybe  { background:#2a2a16; border:1px solid #fbbf24; color:#fcd34d; }
.rec-no     { background:#2a1616; border:1px solid #ef4444; color:#fca5a5; }
.rec-banner { padding:1rem 1.5rem; border-radius:10px; font-weight:700; font-size:1.1rem; text-align:center; margin:1rem 0; }
.prog-track { background:#1e2230; border-radius:8px; height:8px; margin:8px 0; }
.prog-fill  { border-radius:8px; height:8px; background:linear-gradient(90deg,#6c63ff,#a78bfa); }
.stButton > button {
    background: linear-gradient(135deg,#6c63ff,#8b5cf6) !important;
    color: white !important; border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; padding: 0.6rem 1.8rem !important;
    font-family: 'Space Grotesk', sans-serif !important;
}
.stButton > button:hover { opacity: 0.85 !important; }
textarea { background:#1a1d2e !important; color:#e8eaf0 !important; border-color:#2a2d40 !important; border-radius:8px !important; }
h1,h2,h3 { font-family: 'Space Grotesk', sans-serif !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Session state defaults
# ─────────────────────────────────────────────
_DEFAULTS = {
    "phase":            "setup",
    "session_id":       None,
    "candidate_name":   "",
    "role":             "",
    "max_q":            6,
    "greeting":         "",
    "current_question": "",
    "question_number":  1,
    "difficulty":       "easy",
    "last_eval":        None,
    "qa_log":           [],
    "final_report":     None,
    "tts_audio":        None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def reset_state():
    for _k, _v in _DEFAULTS.items():
        st.session_state[_k] = _v


# ─────────────────────────────────────────────
# API helpers
# ─────────────────────────────────────────────

def api_call(method: str, path: str, **kwargs):
    try:
        r = getattr(requests, method)(f"{API_BASE}{path}", timeout=60, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("⚡ Cannot reach backend. Run: `uvicorn backend.main:app --reload` from project root.")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def fetch_tts_audio(text: str):
    try:
        r = requests.post(f"{API_BASE}/tts", json={"text": text}, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def transcribe_uploaded_file(uploaded_file) -> str:
    try:
        file_bytes = uploaded_file.read()
        r = requests.post(
            f"{API_BASE}/transcribe",
            files={"file": (uploaded_file.name, file_bytes, uploaded_file.type)},
            timeout=60,
        )
        r.raise_for_status()
        return r.json().get("transcript", "")
    except Exception as e:
        st.error(f"Transcription error: {e}")
        return ""


# ─────────────────────────────────────────────
# UI helpers
# ─────────────────────────────────────────────

def score_class(s) -> str:
    s = float(s)
    return "score-high" if s >= 7.5 else ("score-mid" if s >= 5.0 else "score-low")


def difficulty_pill(d: str) -> str:
    cls = {"easy": "pill-easy", "medium": "pill-medium", "hard": "pill-hard"}.get(d, "pill-medium")
    return f'<span class="{cls}">{d.upper()}</span>'


def progress_bar_html(value, max_val: float = 10.0) -> str:
    pct = min(100, int(float(value) / max_val * 100))
    return f'<div class="prog-track"><div class="prog-fill" style="width:{pct}%"></div></div>'


def recommendation_banner_html(rec: str) -> str:
    mapping = {
        "Strong Hire": ("rec-strong", "🚀 STRONG HIRE"),
        "Hire":        ("rec-hire",   "✅ HIRE"),
        "Maybe":       ("rec-maybe",  "🤔 MAYBE"),
        "No Hire":     ("rec-no",     "❌ NO HIRE"),
    }
    cls, label = mapping.get(rec, ("rec-maybe", rec.upper()))
    return f'<div class="rec-banner {cls}">{label}</div>'


# ─────────────────────────────────────────────
# Answer submission (defined before usage)
# ─────────────────────────────────────────────

def submit_answer(answer: str):
    """Send answer to API and advance state."""
    with st.spinner("Evaluating your answer …"):
        data = api_call(
            "post",
            f"/session/{st.session_state.session_id}/answer",
            json={"answer": answer},
        )
    if not data:
        return

    st.session_state.qa_log.append({
        "question":   st.session_state.current_question,
        "answer":     answer,
        "scores":     data.get("evaluation", {}),
        "difficulty": st.session_state.difficulty,
    })
    st.session_state.last_eval = data.get("evaluation", {})
    st.session_state.greeting  = ""

    if data.get("stage") == "END":
        st.session_state.final_report = data.get("final_report", {})
        st.session_state.phase        = "report"
        st.rerun()
    else:
        nq = data.get("next_question", "")
        st.session_state.current_question = nq
        st.session_state.question_number += 1
        st.session_state.difficulty       = data.get("difficulty", "medium")
        st.session_state.tts_audio        = fetch_tts_audio(nq) if nq else None
        st.rerun()


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🤖 ARIA")
    st.markdown("*Advanced Recruiting Intelligence Agent*")

    _health = api_call("get", "/health")
    if _health is not None:
        if _health.get("demo_mode"):
            st.error(
                "**Demo mode** — Groq API key missing. "
                "In Streamlit Cloud → App settings → Secrets, add:\n\n"
                "`GROQ_API_KEY = \"gsk_...\"`\n\n"
                "Remove `USE_MOCK_LLM` if present, then **Reboot app**."
            )
        elif _health.get("groq_configured"):
            st.success("Groq AI active")

    st.divider()

    if st.button("＋ New Interview"):
        reset_state()
        st.rerun()

    st.markdown("### 📁 Past Sessions")
    hist_data = api_call("get", "/sessions")
    if hist_data and hist_data.get("sessions"):
        for sess in hist_data["sessions"][:8]:
            icon = "✅" if sess["status"] == "completed" else "🔄"
            with st.expander(f"{icon} {sess['candidate']} · {sess['role']}", expanded=False):
                st.caption(f"ID: {sess['id']} | {sess['started_at'][:10]}")
                if sess["status"] == "completed":
                    past_rep = api_call("get", f"/session/{sess['id']}/report")
                    if past_rep:
                        st.metric("Score", f"{past_rep['overall_score']}/10")
                        st.caption(f"{past_rep['skill_level']} · {past_rep['recommendation']}")
    else:
        st.caption("No sessions yet.")

    st.divider()
    st.caption(f"Backend: `{API_BASE}`")


# ═════════════════════════════════════════════
# PHASE: SETUP
# ═════════════════════════════════════════════

if st.session_state.phase == "setup":
    st.markdown("# 🤖 AI Interview Agent")
    st.markdown("##### Powered by GPT-4 · Whisper · gTTS")
    st.divider()

    col_avatar, col_left, col_right = st.columns([1, 1.1, 1.1], gap="large")

    with col_avatar:
        st.markdown("### 🎥 Your interviewer")
        render_interviewer_preview()

    with col_left:
        st.markdown("### 👤 Candidate Details")
        cand_name = st.text_input("Full Name", placeholder="e.g. Priya Sharma")
        cand_role = st.selectbox("Job Role", [
            "Python Backend Developer",
            "Frontend React Developer",
            "Full-Stack Engineer",
            "Data Scientist",
            "Machine Learning Engineer",
            "DevOps Engineer",
            "Cloud Architect",
            "Mobile Developer (Flutter)",
            "SQL / Data Analyst",
            "System Design Architect",
        ])
        cand_maxq = st.slider("Number of Questions", 3, 10, 6)

    with col_right:
        st.markdown("### ℹ️ How it works")
        st.markdown("""
<div class="card"><ol style="line-height:2.2">
<li>🎯 ARIA asks adaptive technical questions for your role</li>
<li>🎥 <b>ARIA</b> asks questions face-to-face with lip-synced voice</li>
<li>✍️ Answer by <b>typing</b> or uploading a <b>voice recording</b></li>
<li>🧠 GPT evaluates <b>accuracy</b>, <b>depth</b> &amp; <b>clarity</b> live</li>
<li>📈 Difficulty adjusts based on your performance</li>
<li>📋 Get a full <b>report</b> with scores &amp; recommendation</li>
</ol></div>
""", unsafe_allow_html=True)

    st.divider()
    if st.button("🚀  Start Interview", use_container_width=True):
        if not cand_name.strip():
            st.error("Please enter your name.")
        else:
            with st.spinner("Initialising session …"):
                init_data = api_call("post", "/session/start", json={
                    "candidate_name": cand_name.strip(),
                    "role":           cand_role,
                    "max_questions":  cand_maxq,
                })
            if init_data:
                st.session_state.update({
                    "phase":            "interview",
                    "session_id":       init_data["session_id"],
                    "candidate_name":   cand_name.strip(),
                    "role":             cand_role,
                    "max_q":            cand_maxq,
                    "greeting":         init_data["greeting"],
                    "current_question": init_data["question"],
                    "question_number":  1,
                    "difficulty":       init_data["difficulty"],
                    "tts_audio":        fetch_tts_audio(
                        init_data["greeting"] + " " + init_data["question"]
                    ),
                })
                st.rerun()


# ═════════════════════════════════════════════
# PHASE: INTERVIEW
# ═════════════════════════════════════════════

elif st.session_state.phase == "interview":
    max_questions = st.session_state.max_q

    speech_parts = []
    if st.session_state.greeting:
        speech_parts.append(st.session_state.greeting)
    if st.session_state.current_question:
        speech_parts.append(st.session_state.current_question)
    speech_text = " ".join(speech_parts)

    col_avatar, col_main = st.columns([1, 1.55], gap="large")

    with col_avatar:
        render_interviewer_avatar(
            audio_bytes=st.session_state.tts_audio,
            speech_text=speech_text,
            interviewer_name="ARIA",
            height=600,
            instance_id=f"{st.session_state.session_id}_{st.session_state.question_number}",
        )

    with col_main:
        # Header
        hc1, hc2, hc3 = st.columns([3, 1, 1])
        with hc1:
            st.markdown(f"### 👤 {st.session_state.candidate_name} — {st.session_state.role}")
        with hc2:
            st.markdown(f"**Q {st.session_state.question_number} / {max_questions}**")
        with hc3:
            st.markdown(difficulty_pill(st.session_state.difficulty), unsafe_allow_html=True)

        # Progress
        done_pct = int((st.session_state.question_number - 1) / max_questions * 100)
        st.markdown(
            f'<div class="prog-track"><div class="prog-fill" style="width:{done_pct}%"></div></div>',
            unsafe_allow_html=True,
        )
        st.divider()

        # Question
        st.markdown(
            f'<div class="question-box">🎯 {st.session_state.current_question}</div>',
            unsafe_allow_html=True,
        )
        st.caption("Listen to ARIA on the left, then type or upload your answer below.")

        if st.session_state.last_eval:
            ev = st.session_state.last_eval
            st.markdown("#### 📊 Previous Answer Scores")
            ev_cols = st.columns(4)
            for ev_col, (ev_label, ev_key) in zip(ev_cols, [
                ("Technical",  "technical_accuracy"),
                ("Depth",      "depth"),
                ("Clarity",    "clarity"),
                ("Composite",  "composite_score"),
            ]):
                ev_val = ev.get(ev_key, 0)
                with ev_col:
                    ev_cls = score_class(ev_val)
                    st.markdown(
                        f'<div class="card" style="text-align:center">'
                        f'<div style="font-size:0.75rem;color:#888;margin-bottom:4px">{ev_label}</div>'
                        f'<span class="score-badge {ev_cls}">{ev_val}</span>'
                        f'{progress_bar_html(ev_val)}</div>',
                        unsafe_allow_html=True,
                    )
            if ev.get("feedback"):
                st.markdown(f"> 💬 **Feedback:** {ev['feedback']}")
            st.divider()

        ans_tab_text, ans_tab_voice = st.tabs(["✍️  Type Answer", "🎙️  Upload Voice Recording"])

        with ans_tab_text:
            typed_text = st.text_area(
                "Your answer",
                height=180,
                placeholder="Write your answer here…",
                key=f"typed_{st.session_state.question_number}",
            )
            if st.button("Submit Answer  ➤", key="btn_submit_text", use_container_width=True):
                if not typed_text.strip():
                    st.error("Please write an answer before submitting.")
                else:
                    submit_answer(typed_text.strip())

        with ans_tab_voice:
            st.info("Record with your phone/Audacity, then upload. Supported: WAV · MP3 · M4A · WEBM · OGG")
            voice_file = st.file_uploader(
                "Upload audio",
                type=["wav", "mp3", "m4a", "webm", "ogg"],
                key=f"upload_{st.session_state.question_number}",
            )
            if voice_file:
                st.audio(voice_file)
                if st.button("Transcribe & Submit  🔊➤", key="btn_submit_voice", use_container_width=True):
                    with st.spinner("Transcribing with Whisper …"):
                        voice_transcript = transcribe_uploaded_file(voice_file)
                    if voice_transcript:
                        st.success(f"📝 Transcript: *{voice_transcript}*")
                        time.sleep(0.8)
                        submit_answer(voice_transcript)
                    else:
                        st.error("Transcription failed. Try a clearer audio file.")


# ═════════════════════════════════════════════
# PHASE: REPORT
# ═════════════════════════════════════════════

elif st.session_state.phase == "report":
    rpt   = st.session_state.final_report or {}
    qa_lg = st.session_state.qa_log

    st.markdown("# 📋 Final Interview Report")
    st.caption(
        f"Candidate: **{st.session_state.candidate_name}**  |  "
        f"Role: **{st.session_state.role}**"
    )
    st.divider()

    # Metrics row
    rpt_c1, rpt_c2, rpt_c3, rpt_c4 = st.columns(4)
    composites = [q["scores"].get("composite_score", 0) for q in qa_lg]
    avg_composite = round(sum(composites) / max(len(composites), 1), 1)

    with rpt_c1: st.metric("Overall Score",   f"{rpt.get('overall_score','–')}/10")
    with rpt_c2: st.metric("Skill Level",     rpt.get("skill_level", "–"))
    with rpt_c3: st.metric("Questions Asked", len(qa_lg))
    with rpt_c4: st.metric("Avg Composite",   f"{avg_composite}/10")

    # Recommendation
    st.markdown(recommendation_banner_html(rpt.get("recommendation", "–")), unsafe_allow_html=True)

    # Summary
    st.markdown("### 📝 Summary")
    st.markdown(f'<div class="card">{rpt.get("summary","No summary available.")}</div>', unsafe_allow_html=True)

    # Strengths & weaknesses
    sw_left, sw_right = st.columns(2)
    with sw_left:
        st.markdown("### ✅ Strengths")
        for s_item in rpt.get("strengths", []):
            st.markdown(f"- {s_item}")
    with sw_right:
        st.markdown("### ⚠️ Areas to Improve")
        for w_item in rpt.get("weaknesses", []):
            st.markdown(f"- {w_item}")

    st.divider()

    # Average score bars
    st.markdown("### 📈 Average Score by Dimension")
    dim_data = {
        "Technical Accuracy": sum(q["scores"].get("technical_accuracy", 0) for q in qa_lg) / max(len(qa_lg), 1),
        "Depth":              sum(q["scores"].get("depth", 0)               for q in qa_lg) / max(len(qa_lg), 1),
        "Clarity":            sum(q["scores"].get("clarity", 0)             for q in qa_lg) / max(len(qa_lg), 1),
    }
    for dim_label, dim_val in dim_data.items():
        dim_val = round(dim_val, 1)
        st.markdown(
            f'<div style="margin:8px 0">'
            f'<span style="display:inline-block;width:190px;font-size:0.85rem">{dim_label}</span>'
            f'<span class="score-badge {score_class(dim_val)}" style="margin-right:12px">{dim_val}/10</span>'
            f'{progress_bar_html(dim_val)}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # Q&A breakdown
    st.markdown("### 🔍 Question-by-Question Breakdown")
    for qi, qa_item in enumerate(qa_lg, 1):
        sc_item = qa_item["scores"]
        comp    = sc_item.get("composite_score", "–")
        q_short = qa_item["question"][:75] + ("…" if len(qa_item["question"]) > 75 else "")
        with st.expander(f"Q{qi} · {q_short}  |  Composite: {comp}", expanded=False):
            st.markdown(
                f"**Difficulty:** {difficulty_pill(qa_item.get('difficulty','?'))}",
                unsafe_allow_html=True,
            )
            st.markdown(f"**Answer:** {qa_item['answer']}")
            qa_cols = st.columns(3)
            for qa_col, (qa_key, qa_lbl) in zip(qa_cols, [
                ("technical_accuracy", "Technical"),
                ("depth",              "Depth"),
                ("clarity",            "Clarity"),
            ]):
                qa_val = sc_item.get(qa_key, 0)
                with qa_col:
                    st.markdown(
                        f'<div class="card" style="text-align:center">'
                        f'<div style="font-size:0.75rem;color:#888">{qa_lbl}</div>'
                        f'<span class="score-badge {score_class(qa_val)}">{qa_val}/10</span>'
                        f'{progress_bar_html(qa_val)}</div>',
                        unsafe_allow_html=True,
                    )
            if sc_item.get("feedback"):
                st.info(f"💬 {sc_item['feedback']}")

    st.divider()
    if st.button("🔄 Start New Interview", use_container_width=True):
        reset_state()
        st.rerun()
