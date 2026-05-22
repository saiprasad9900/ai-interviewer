"""
database.py — SQLite persistence layer.
Stores interview sessions, Q&A pairs, and evaluation scores.
"""

import sqlite3
import json
import os
from datetime import datetime

# Resolve DB path (DATA_DIR env for cloud hosts e.g. Render /tmp)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DATA_DIR, "interviews.db")


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory for dict-like access."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    conn = get_connection()
    cur = conn.cursor()

    # One row per interview session
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate   TEXT    NOT NULL,
            role        TEXT    NOT NULL,
            started_at  TEXT    NOT NULL,
            ended_at    TEXT,
            status      TEXT    DEFAULT 'active'   -- active | completed
        )
    """)

    # One row per Q&A exchange
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exchanges (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER NOT NULL,
            question_num    INTEGER NOT NULL,
            question        TEXT    NOT NULL,
            answer          TEXT,
            difficulty      TEXT,
            tech_score      REAL,
            depth_score     REAL,
            clarity_score   REAL,
            feedback        TEXT,
            created_at      TEXT    NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    # Final report — one row per session
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      INTEGER UNIQUE NOT NULL,
            overall_score   REAL,
            skill_level     TEXT,
            strengths       TEXT,   -- JSON array
            weaknesses      TEXT,   -- JSON array
            recommendation  TEXT,
            summary         TEXT,
            created_at      TEXT    NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# Session helpers
# ─────────────────────────────────────────────

def create_session(candidate: str, role: str) -> int:
    """Insert a new interview session; return its ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sessions (candidate, role, started_at) VALUES (?, ?, ?)",
        (candidate, role, datetime.utcnow().isoformat())
    )
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def close_session(session_id: int):
    """Mark a session as completed."""
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET status='completed', ended_at=? WHERE id=?",
        (datetime.utcnow().isoformat(), session_id)
    )
    conn.commit()
    conn.close()


def get_session(session_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# Exchange helpers
# ─────────────────────────────────────────────

def save_exchange(
    session_id: int,
    question_num: int,
    question: str,
    answer: str,
    difficulty: str,
    scores: dict
) -> int:
    """Persist a single Q&A exchange with its evaluation scores."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO exchanges
            (session_id, question_num, question, answer, difficulty,
             tech_score, depth_score, clarity_score, feedback, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, question_num, question, answer, difficulty,
        scores.get("technical_accuracy", 0),
        scores.get("depth", 0),
        scores.get("clarity", 0),
        scores.get("feedback", ""),
        datetime.utcnow().isoformat()
    ))
    exchange_id = cur.lastrowid
    conn.commit()
    conn.close()
    return exchange_id


def get_exchanges(session_id: int) -> list[dict]:
    """Fetch all exchanges for a session, ordered by question number."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM exchanges WHERE session_id=? ORDER BY question_num",
        (session_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# Report helpers
# ─────────────────────────────────────────────

def save_report(session_id: int, report: dict):
    """Store the final interview report."""
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO reports
            (session_id, overall_score, skill_level, strengths, weaknesses,
             recommendation, summary, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        report.get("overall_score"),
        report.get("skill_level"),
        json.dumps(report.get("strengths", [])),
        json.dumps(report.get("weaknesses", [])),
        report.get("recommendation"),
        report.get("summary"),
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()


def get_report(session_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM reports WHERE session_id=?", (session_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    r = dict(row)
    r["strengths"] = json.loads(r["strengths"] or "[]")
    r["weaknesses"] = json.loads(r["weaknesses"] or "[]")
    return r


def list_sessions() -> list[dict]:
    """Return all sessions for the history view."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY started_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
