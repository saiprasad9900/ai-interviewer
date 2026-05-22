"""
mock_llm.py — Offline demo mode when no GROQ_API_KEY is configured.

Provides canned greetings, questions, heuristic scoring, and reports
so the full interview flow works without any external LLM API.
"""

import re
import statistics

DIFFICULTY_ORDER = ["easy", "medium", "hard"]

_QUESTION_BANK: dict[str, dict[str, list[str]]] = {
    "default": {
        "easy": [
            "What is the difference between a list and a tuple in Python?",
            "Explain what a REST API is in simple terms.",
            "What does version control (e.g. Git) help a team accomplish?",
        ],
        "medium": [
            "How would you design a simple caching layer for a read-heavy API?",
            "Describe how you would debug a slow database query in production.",
            "What trade-offs exist between SQL and NoSQL databases?",
        ],
        "hard": [
            "How would you handle idempotency and retries in a distributed payment service?",
            "Explain eventual consistency and when it is acceptable in system design.",
            "Walk through how you would scale a WebSocket-based chat backend to 100k concurrent users.",
        ],
    },
    "python": {
        "easy": [
            "What is a Python generator and when would you use one?",
            "Explain the difference between `==` and `is` in Python.",
        ],
        "medium": [
            "How does the GIL affect CPU-bound vs I/O-bound Python workloads?",
            "Compare `asyncio` coroutines with threading for concurrent I/O.",
        ],
        "hard": [
            "Design a plugin architecture for a Python CLI tool with lazy loading.",
        ],
    },
}


_PLACEHOLDER_KEYS = {
    "",
    "your-groq-api-key",
    "your-groq-api-key-here",
    "sk-your-key-here",
    "changeme",
    "xxx",
}


def use_mock_mode() -> bool:
    import os
    from backend.secrets_config import bootstrap_groq_api_key, groq_configured

    if os.getenv("USE_MOCK_LLM", "").lower() in ("1", "true", "yes"):
        return True
    bootstrap_groq_api_key()
    return not groq_configured()


def generate_greeting(candidate_name: str, role: str) -> str:
    name = candidate_name.strip() or "there"
    return (
        f"Hello {name}, welcome to your {role} interview. "
        "I'm ARIA running in demo mode (no API key required). "
        "Answer each question thoughtfully; you'll receive scores and a summary at the end."
    )


def _bank_for_role(role: str) -> dict[str, list[str]]:
    role_lower = role.lower()
    if "python" in role_lower:
        bank = {k: list(v) for k, v in _QUESTION_BANK["python"].items()}
        for diff, qs in _QUESTION_BANK["default"].items():
            bank.setdefault(diff, []).extend(qs)
        return bank
    return _QUESTION_BANK["default"]


def generate_question(role: str, difficulty: str, topics_covered: list[str]) -> str:
    bank = _bank_for_role(role)
    pool = list(bank.get(difficulty, bank.get("medium", [])))
    if not pool:
        pool = _QUESTION_BANK["default"]["medium"]
    covered = {t.lower() for t in topics_covered}
    for q in pool:
        topic = extract_topic(q)
        if topic not in covered:
            return q
    return pool[len(topics_covered) % len(pool)]


def extract_topic(question: str) -> str:
    q = question.lower()
    for label, pattern in (
        ("generators", r"generator"),
        ("rest api", r"rest"),
        ("git", r"git|version control"),
        ("caching", r"cache"),
        ("databases", r"database|sql|nosql"),
        ("async", r"async|asyncio|gil"),
        ("distributed systems", r"distributed|idempotency|consistency|scale"),
        ("data structures", r"list|tuple"),
    ):
        if re.search(pattern, q):
            return label
    words = re.findall(r"[a-z]{4,}", q)
    return " ".join(words[:3]) if words else "general"


def next_difficulty(current: str, suggested: str) -> str:
    idx_current = DIFFICULTY_ORDER.index(current) if current in DIFFICULTY_ORDER else 1
    idx_suggested = DIFFICULTY_ORDER.index(suggested) if suggested in DIFFICULTY_ORDER else 1
    delta = max(-1, min(1, idx_suggested - idx_current))
    new_idx = max(0, min(len(DIFFICULTY_ORDER) - 1, idx_current + delta))
    return DIFFICULTY_ORDER[new_idx]


def evaluate_answer(question: str, answer: str, role: str) -> dict:
    if not answer or len(answer.strip()) < 5:
        return _score_result(1, 1, 1, "No substantial answer was provided.", "easy")

    text = answer.strip()
    words = len(text.split())
    technical = min(10, 3 + words // 8)
    if re.search(r"\b(because|therefore|trade-?off|example|implement|design)\b", text, re.I):
        technical = min(10, technical + 2)
    depth = min(10, 2 + words // 12)
    if len(text) > 200:
        depth = min(10, depth + 2)
    clarity = 8 if words >= 15 else 6 if words >= 8 else 4

    composite = round(technical * 0.5 + depth * 0.3 + clarity * 0.2, 2)
    if composite >= 7.5:
        suggested = "hard"
    elif composite >= 5.5:
        suggested = "medium"
    else:
        suggested = "easy"

    feedback = (
        "Demo scoring: longer, structured answers score higher. "
        f"You wrote ~{words} words. Add examples and trade-offs for stronger scores."
    )
    return _score_result(technical, depth, clarity, feedback, suggested, composite)


def _score_result(
    technical: int,
    depth: int,
    clarity: int,
    feedback: str,
    suggested: str,
    composite: float | None = None,
) -> dict:
    if composite is None:
        composite = round(technical * 0.5 + depth * 0.3 + clarity * 0.2, 2)
    return {
        "technical_accuracy": technical,
        "depth": depth,
        "clarity": clarity,
        "feedback": feedback,
        "suggested_difficulty": suggested,
        "composite_score": composite,
    }


def generate_final_report(role: str, qa_pairs: list[dict]) -> dict:
    scores = [
        p["scores"]["composite_score"]
        for p in qa_pairs
        if p.get("scores", {}).get("composite_score") is not None
    ]
    overall = round(statistics.mean(scores), 2) if scores else 0.0

    if overall >= 8.0:
        recommendation, skill = "Strong Hire", "Advanced"
    elif overall >= 6.5:
        recommendation, skill = "Hire", "Intermediate"
    elif overall >= 5.0:
        recommendation, skill = "Maybe", "Junior"
    else:
        recommendation, skill = "No Hire", "Needs Development"

    strengths = []
    weaknesses = []
    if overall >= 7:
        strengths.append("Consistent answers across the interview (demo mode).")
    else:
        weaknesses.append("Room to add more depth and concrete examples.")
    if len(qa_pairs) >= 3:
        strengths.append(f"Completed {len(qa_pairs)} questions for {role}.")

    return {
        "overall_score": overall,
        "skill_level": skill,
        "strengths": strengths or ["Participated in the full demo interview flow."],
        "weaknesses": weaknesses or ["Run with a GROQ_API_KEY for AI-powered evaluation."],
        "recommendation": recommendation,
        "summary": (
            f"Demo report for {role}: average composite score {overall}/10 "
            f"over {len(qa_pairs)} question(s). Enable GROQ_API_KEY for real LLM scoring."
        ),
    }
