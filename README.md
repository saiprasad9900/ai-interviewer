# 🤖 ARIA — AI Interview Agent

> An adaptive, voice-powered technical interview system built with GPT-4, Whisper, and FastAPI.

---

## 📁 Project Structure

```
ai_interviewer/
├── backend/
│   ├── main.py                 # FastAPI REST API (all endpoints)
│   ├── interview_controller.py # State machine: START→ASK→LISTEN→EVALUATE→DECIDE→END
│   ├── evaluator.py            # GPT-based answer scoring + final report generation
│   ├── question_generator.py   # Adaptive question generation + difficulty control
│   ├── voice.py                # gTTS (TTS) + Whisper (STT) + microphone recording
│   └── database.py             # SQLite persistence (sessions, exchanges, reports)
├── frontend/
│   └── app.py                  # Streamlit UI
├── models/
│   └── prompts.py              # All LLM prompt templates (centralised)
├── data/
│   └── interviews.db           # SQLite database (auto-created)
└── requirements.txt
```

---

## ⚙️ Prerequisites

- Python 3.11+
- An **OpenAI API key** with access to `gpt-4o-mini` and `whisper-1`
- `ffmpeg` installed (required by pydub for audio):
  - macOS: `brew install ffmpeg`
  - Ubuntu: `sudo apt install ffmpeg`
  - Windows: Download from https://ffmpeg.org/download.html

---

## ☁️ Deploy via GitHub

Host the app free with **GitHub + Render (API) + Streamlit Cloud (UI)**.

See **[DEPLOY.md](DEPLOY.md)** for step-by-step instructions.

Quick push (after creating an empty GitHub repo):

```powershell
.\push_to_github.ps1 -GitHubUsername YOUR_GITHUB_USERNAME
```

---

## 🚀 Quick Start

### 1. Clone / unzip the project

```bash
cd ai_interviewer
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set your OpenAI API key

```bash
export OPENAI_API_KEY="sk-..."   # macOS / Linux
set    OPENAI_API_KEY="sk-..."   # Windows CMD
$env:OPENAI_API_KEY="sk-..."     # Windows PowerShell
```

### 5. Start the FastAPI backend

```bash
# From the ai_interviewer/ root
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000/docs to see the interactive API documentation.

### 6. Start the Streamlit frontend (new terminal)

```bash
# From the ai_interviewer/ root
streamlit run frontend/app.py
```

Open http://localhost:8501 in your browser.

---

## 🧠 How It Works

### Interview State Machine

```
START ──► ASK ──► LISTEN ──► EVALUATE ──► DECIDE ──► (back to ASK or END)
```

| Stage      | What happens                                              |
|------------|-----------------------------------------------------------|
| START      | Create DB session, generate warm greeting via GPT         |
| ASK        | Generate role-appropriate question at current difficulty  |
| LISTEN     | Wait for candidate's typed/spoken answer                  |
| EVALUATE   | GPT scores technical accuracy, depth, clarity (1–10 each)|
| DECIDE     | Adaptive difficulty: harder if score high, easier if low  |
| END        | Generate comprehensive final report + recommendation      |

### Adaptive Difficulty

- Each evaluation returns a `suggested_difficulty` (easy/medium/hard)
- The controller clamps changes to ±1 level per question to avoid wild swings
- Topics already covered are tracked and excluded from future questions

### Voice Pipeline

```
Candidate speaks → records audio → uploads WAV/MP3
→ POST /transcribe → Whisper API → text transcript
→ POST /session/{id}/answer → GPT evaluation

ARIA response text → POST /tts → gTTS → MP3 bytes
→ Streamlit st.audio() → plays in browser
```

---

## 🌐 API Endpoints

| Method | Path                          | Description                        |
|--------|-------------------------------|------------------------------------|
| POST   | `/session/start`              | Begin interview, get first question|
| POST   | `/session/{id}/answer`        | Submit answer, get next question   |
| GET    | `/session/{id}/report`        | Fetch final report                 |
| GET    | `/session/{id}/exchanges`     | Full Q&A transcript                |
| GET    | `/sessions`                   | List all past sessions             |
| POST   | `/tts`                        | Text → MP3 bytes                   |
| POST   | `/transcribe`                 | Audio file → text (Whisper)        |
| GET    | `/health`                     | Health check                       |

### Example: Start a session

```bash
curl -X POST http://localhost:8000/session/start \
  -H "Content-Type: application/json" \
  -d '{"candidate_name":"Alice","role":"Python Backend Developer","max_questions":5}'
```

### Example: Submit an answer

```bash
curl -X POST http://localhost:8000/session/1/answer \
  -H "Content-Type: application/json" \
  -d '{"answer":"A generator is a function that uses yield instead of return..."}'
```

---

## 📊 Evaluation Schema

Each answer is scored by GPT and returns:

```json
{
  "technical_accuracy": 8,
  "depth": 7,
  "clarity": 9,
  "feedback": "Solid understanding. Consider mentioning memory efficiency benefits.",
  "suggested_difficulty": "hard",
  "composite_score": 7.9
}
```

Composite score weights: Technical 50% · Depth 30% · Clarity 20%

---

## 📋 Final Report Schema

```json
{
  "overall_score": 7.4,
  "skill_level": "Intermediate",
  "strengths": ["Strong core Python", "Clear communication style"],
  "weaknesses": ["Async/await depth", "System design gaps"],
  "recommendation": "Hire",
  "summary": "Alice demonstrated solid foundational Python knowledge..."
}
```

Recommendation tiers: `Strong Hire` · `Hire` · `Maybe` · `No Hire`

---

## 🔧 Configuration

| Environment Variable | Default                    | Description              |
|----------------------|----------------------------|--------------------------|
| `OPENAI_API_KEY`     | *(required)*               | OpenAI API key           |
| `API_BASE`           | `http://localhost:8000`    | Backend URL for frontend |

---

## 🧩 Extending the System

**Add a new job role**: Edit the `selectbox` list in `frontend/app.py` — no other changes needed. The question generator uses the role string directly.

**Change question count**: Adjust the slider in the UI or pass `max_questions` to the API.

**Use ElevenLabs instead of gTTS**: Replace `speak_text()` and `text_to_mp3_file()` in `voice.py` with ElevenLabs API calls.

**Add a new evaluation dimension**: Update `evaluation_prompt()` in `models/prompts.py` and `SCORE_WEIGHTS` in `evaluator.py`.

**Persistent in-memory store**: Replace the `_sessions` dict in `main.py` with Redis using `aioredis`.

---

## 🐛 Troubleshooting

| Problem | Fix |
|---------|-----|
| `Cannot reach backend` | Start uvicorn first; check port 8000 is free |
| `TTS failed` | Install gTTS: `pip install gtts` |
| `Transcription empty` | Check OPENAI_API_KEY; ensure audio has speech |
| `pydub: ffmpeg not found` | Install ffmpeg (see Prerequisites) |
| `sounddevice OSError` | Normal in headless environments; recording still works via file upload |

---

## 📄 License

MIT — free to use, modify, and distribute.
