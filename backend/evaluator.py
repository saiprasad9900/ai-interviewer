"""
evaluator.py — Evaluates candidate answers using Groq (Llama).
Returns structured scores and feedback in JSON.
"""

import os
import json
import re
import groq
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.prompts import INTERVIEWER_SYSTEM_PROMPT, evaluation_prompt, final_report_prompt


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


# ─────────────────────────────────────────────
# Scoring constants
# ─────────────────────────────────────────────
SCORE_WEIGHTS = {
    "technical_accuracy": 0.50,
    "depth":              0.30,
    "clarity":            0.20,
}


def evaluate_answer(question: str, answer: str, role: str) -> dict:
    """
    Send question + answer to Llama for evaluation.

    Returns a dict:
    {
        "technical_accuracy": int (1-10),
        "depth":              int (1-10),
        "clarity":            int (1-10),
        "feedback":           str,
        "suggested_difficulty": "easy"|"medium"|"hard",
        "composite_score":    float   # weighted average
    }
    """
    # Edge case: empty / very short answer
    if not answer or len(answer.strip()) < 5:
        return {
            "technical_accuracy": 1,
            "depth": 1,
            "clarity": 1,
            "feedback": "No substantial answer was provided.",
            "suggested_difficulty": "easy",
            "composite_score": 1.0,
        }

    if use_mock_mode():
        from backend import mock_llm
        return mock_llm.evaluate_answer(question, answer, role)

    prompt = evaluation_prompt(question, answer, role)

    client = get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": INTERVIEWER_SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.2,
        max_tokens=300,
    )

    raw = response.choices[0].message.content.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON block manually
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(match.group()) if match else {}

    # Ensure all keys are present with safe defaults
    result.setdefault("technical_accuracy", 5)
    result.setdefault("depth", 5)
    result.setdefault("clarity", 5)
    result.setdefault("feedback", "")
    result.setdefault("suggested_difficulty", "medium")

    # Clamp scores to 1–10
    for key in ("technical_accuracy", "depth", "clarity"):
        result[key] = max(1, min(10, int(result[key])))

    # Compute weighted composite
    result["composite_score"] = round(
        sum(result[k] * w for k, w in SCORE_WEIGHTS.items()), 2
    )

    return result


def generate_final_report(role: str, qa_pairs: list[dict]) -> dict:
    """
    Given all Q&A pairs with scores, ask Llama to produce a final report.

    qa_pairs items must have keys: question, answer, scores (dict)

    Returns:
    {
        "overall_score":   float,
        "skill_level":     str,
        "strengths":       list[str],
        "weaknesses":      list[str],
        "recommendation":  str,
        "summary":         str
    }
    """
    if use_mock_mode():
        from backend import mock_llm
        return mock_llm.generate_final_report(role, qa_pairs)

    prompt = final_report_prompt(role, qa_pairs)

    client = get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are an expert technical recruiter generating a candidate assessment report."},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.3,
        max_tokens=600,
    )

    raw = response.choices[0].message.content.strip()

    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        report = json.loads(match.group()) if match else {}

    # Safe defaults
    report.setdefault("overall_score", 0.0)
    report.setdefault("skill_level", "Unknown")
    report.setdefault("strengths", [])
    report.setdefault("weaknesses", [])
    report.setdefault("recommendation", "Maybe")
    report.setdefault("summary", "Insufficient data to generate summary.")

    return report


def composite_score_label(score: float) -> str:
    """Return a human-readable label for a composite score."""
    if score >= 8.5:
        return "Outstanding"
    elif score >= 7.0:
        return "Strong"
    elif score >= 5.5:
        return "Satisfactory"
    elif score >= 4.0:
        return "Needs Improvement"
    else:
        return "Weak"
