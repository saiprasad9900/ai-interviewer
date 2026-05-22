"""
question_generator.py — Generates adaptive interview questions via Groq (Llama).
Difficulty adjusts dynamically based on candidate performance.
"""

import os
import json
import groq
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.prompts import (
    INTERVIEWER_SYSTEM_PROMPT,
    question_generation_prompt,
    greeting_prompt,
)

from backend.mock_llm import use_mock_mode

# Lazy initialization of Groq client
def get_groq_client():
    """Get or create Groq client with current environment variable."""
    from backend.secrets_config import bootstrap_groq_api_key
    api_key = bootstrap_groq_api_key()
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not set. Add it to .env locally or Streamlit Cloud Secrets."
        )
    return groq.Groq(api_key=api_key)

# Default difficulty ramp for a fresh interview
DIFFICULTY_ORDER = ["easy", "medium", "hard"]


def generate_greeting(candidate_name: str, role: str) -> str:
    """Ask Llama to produce a warm, professional opening greeting."""
    if use_mock_mode():
        from backend import mock_llm
        return mock_llm.generate_greeting(candidate_name, role)
    client = get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": INTERVIEWER_SYSTEM_PROMPT},
            {"role": "user",   "content": greeting_prompt(candidate_name, role)},
        ],
        temperature=0.7,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()


def generate_question(
    role: str,
    difficulty: str,
    topics_covered: list[str],
) -> str:
    """
    Generate a single interview question.

    Args:
        role:            Job role, e.g. "Python Backend Developer"
        difficulty:      "easy" | "medium" | "hard"
        topics_covered:  List of topic strings already asked about

    Returns:
        The question as a plain string.
    """
    if use_mock_mode():
        from backend import mock_llm
        return mock_llm.generate_question(role, difficulty, topics_covered)

    prompt = question_generation_prompt(role, difficulty, topics_covered)

    client = get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": INTERVIEWER_SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.8,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


def extract_topic(question: str) -> str:
    """
    Use a lightweight Llama call to extract the core topic of a question.
    Returns a short label like "list comprehensions" or "async/await".
    """
    if use_mock_mode():
        from backend import mock_llm
        return mock_llm.extract_topic(question)
    client = get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "user",
                "content": (
                    f"In 2–4 words, what is the main technical topic of this question?\n"
                    f'"{question}"\n'
                    "Return ONLY the topic label, nothing else."
                ),
            }
        ],
        temperature=0,
        max_tokens=20,
    )
    return response.choices[0].message.content.strip().lower()


def next_difficulty(current: str, suggested: str) -> str:
    """
    Merge the current plan with the evaluator's suggestion.
    Uses the evaluator suggestion if it differs from current by at most one step.
    """
    idx_current   = DIFFICULTY_ORDER.index(current)   if current   in DIFFICULTY_ORDER else 1
    idx_suggested = DIFFICULTY_ORDER.index(suggested) if suggested in DIFFICULTY_ORDER else 1

    # Clamp: never jump more than one level at a time
    delta = max(-1, min(1, idx_suggested - idx_current))
    new_idx = max(0, min(len(DIFFICULTY_ORDER) - 1, idx_current + delta))
    return DIFFICULTY_ORDER[new_idx]
