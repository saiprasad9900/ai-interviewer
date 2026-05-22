"""
Streamlit Cloud entry point.
Deploy with main file: streamlit_app.py (at repo root).

When API_BASE is not set, starts the FastAPI backend in-process so one
Streamlit Cloud app runs the full stack (no separate Render service needed).
"""

from __future__ import annotations

import os
import sys
import time
import threading

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if os.path.join(_ROOT, "frontend") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "frontend"))

API_PORT = int(os.getenv("API_PORT", "8000"))
DEFAULT_API_BASE = f"http://127.0.0.1:{API_PORT}"


def _load_local_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_ROOT, ".env"))
    except ImportError:
        pass


def _bootstrap_secrets() -> None:
    from backend.secrets_config import bootstrap_groq_api_key
    key = bootstrap_groq_api_key()
    if key:
        print("[ARIA] Groq API key loaded.")
    else:
        print("[ARIA] No Groq API key — demo mode. Set GROQ_API_KEY in Streamlit Secrets.")


def _start_embedded_api() -> None:
    _bootstrap_secrets()
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=API_PORT,
        log_level="warning",
    )


def _ensure_embedded_api() -> None:
    """Start FastAPI in a background thread unless an external API_BASE is set."""
    if os.getenv("API_BASE", "").strip():
        return

    os.environ.setdefault("API_BASE", DEFAULT_API_BASE)

    try:
        import requests
        r = requests.get(f"{DEFAULT_API_BASE}/health", timeout=1.5)
        if r.status_code == 200:
            return
    except Exception:
        pass

    thread = threading.Thread(target=_start_embedded_api, daemon=True)
    thread.start()

    import requests
    for _ in range(40):
        try:
            r = requests.get(f"{DEFAULT_API_BASE}/health", timeout=1.5)
            if r.status_code == 200:
                return
        except Exception:
            time.sleep(0.25)

    print("[ARIA] Warning: embedded API did not respond on /health yet.")


_load_local_env()
_bootstrap_secrets()
_ensure_embedded_api()

import runpy

runpy.run_path(os.path.join(_ROOT, "frontend", "app.py"), run_name="__main__")
