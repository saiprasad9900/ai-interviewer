"""
main.py — FastAPI REST backend for the AI Interview Agent.

Endpoints:
    POST /session/start          — Begin a new interview session
    POST /session/{id}/answer    — Submit an answer + get next question
    GET  /session/{id}/report    — Fetch the final report
    GET  /sessions               — List all past sessions
    GET  /session/{id}/exchanges — Get all Q&A for a session
    POST /tts                    — Text → speech (returns MP3 bytes)
    POST /transcribe             — Audio file → transcript (Whisper)
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database       import init_db, list_sessions, get_session, get_exchanges, get_report
from backend.interview_controller import InterviewController, InterviewState, Stage
from backend.voice          import speak_text, transcribe_bytes

# ─────────────────────────────────────────────
# App lifecycle
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.secrets_config import bootstrap_groq_api_key
    bootstrap_groq_api_key()
    init_db()
    yield

app = FastAPI(
    title="AI Interview Agent API",
    description="Voice-powered technical interview system backed by GPT + Whisper.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store (maps session_id → InterviewState)
# For production replace with Redis / DB-backed store.
_sessions: dict[int, InterviewState] = {}
_controller = InterviewController()


# ─────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────

class StartRequest(BaseModel):
    candidate_name: str
    role: str
    max_questions: int = 6


class AnswerRequest(BaseModel):
    answer: str


class TTSRequest(BaseModel):
    text: str


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    from backend.mock_llm import use_mock_mode
    from backend.secrets_config import groq_configured
    return {
        "status": "ok",
        "demo_mode": use_mock_mode(),
        "groq_configured": groq_configured(),
    }


@app.post("/session/start")
def start_session(req: StartRequest):
    """
    Initialise a new interview session.
    Returns greeting text and the first question.
    """
    state = InterviewState(
        candidate_name=req.candidate_name,
        role=req.role,
        max_questions=req.max_questions,
    )

    # START → ASK
    state = _controller.start(state)
    if state.error:
        raise HTTPException(500, f"Failed to start interview: {state.error}")

    # ASK → LISTEN (generates first question)
    state = _controller.ask(state)
    if state.error:
        raise HTTPException(500, f"Failed to generate question: {state.error}")

    _sessions[state.session_id] = state

    return {
        "session_id":       state.session_id,
        "greeting":         state.greeting,
        "question":         state.current_question,
        "question_number":  state.question_index,   # 0-based pre-increment; first Q is 0 → displayed as 1
        "difficulty":       state.current_difficulty,
        "stage":            state.stage,
    }


@app.post("/session/{session_id}/answer")
def submit_answer(session_id: int, req: AnswerRequest):
    """
    Submit a candidate answer.
    Returns evaluation scores, feedback, and the next question (or signals END).
    """
    state = _sessions.get(session_id)
    if not state:
        raise HTTPException(404, "Session not found or expired.")

    if state.stage != Stage.LISTEN:
        raise HTTPException(400, f"Cannot submit answer in stage: {state.stage}")

    # LISTEN → EVALUATE → DECIDE
    state = _controller.submit_answer(state, req.answer)
    state = _controller.evaluate(state)
    state = _controller.decide(state)
    _sessions[session_id] = state

    response = {
        "evaluation":      state.current_scores,
        "question_number": state.question_index,
        "stage":           state.stage,
        "difficulty":      state.current_difficulty,
    }

    if state.stage == Stage.END:
        # Generate final report
        state = _controller.end(state)
        _sessions[session_id] = state
        response["final_report"] = state.final_report
        response["stage"]        = state.stage
    elif state.stage == Stage.ASK:
        # Generate next question immediately
        state = _controller.ask(state)
        _sessions[session_id] = state
        response["next_question"] = state.current_question

    return response


@app.get("/session/{session_id}/report")
def get_final_report(session_id: int):
    """Return the stored final report for a session."""
    report = get_report(session_id)
    if not report:
        raise HTTPException(404, "Report not found. Interview may still be in progress.")
    return report


@app.get("/session/{session_id}/exchanges")
def get_session_exchanges(session_id: int):
    """Return all Q&A exchanges for a session."""
    exchanges = get_exchanges(session_id)
    return {"session_id": session_id, "exchanges": exchanges}


@app.get("/sessions")
def get_all_sessions():
    """List all past interview sessions."""
    return {"sessions": list_sessions()}


@app.post("/tts")
def text_to_speech(req: TTSRequest):
    """Convert text to speech and return MP3 bytes."""
    mp3_bytes = speak_text(req.text)
    if mp3_bytes is None:
        raise HTTPException(500, "TTS failed. Check gTTS installation.")
    return Response(content=mp3_bytes, media_type="audio/mpeg")


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Accept an audio file and return Whisper transcription."""
    audio_bytes = await file.read()
    transcript  = transcribe_bytes(audio_bytes, filename=file.filename or "audio.wav")
    if not transcript:
        raise HTTPException(500, "Transcription failed or produced empty result.")
    return {"transcript": transcript}
