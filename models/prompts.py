"""
prompts.py — Centralized prompt engineering for the AI Interview Agent.
All LLM prompts are defined here for easy tuning and reuse.
"""

# ─────────────────────────────────────────────
# SYSTEM / PERSONA PROMPT
# ─────────────────────────────────────────────

INTERVIEWER_SYSTEM_PROMPT = """
You are ARIA — an Advanced Recruiting Intelligence Agent.
You conduct professional, friendly, and rigorous technical interviews.

Guidelines:
- Ask ONE question at a time. Never stack multiple questions.
- Keep questions clear, focused, and role-relevant.
- Be encouraging but objective.
- Adapt difficulty based on candidate performance.
- If a candidate seems confused, you may offer a small clarifying hint.
- Never reveal the evaluation scores to the candidate mid-interview.
""".strip()


# ─────────────────────────────────────────────
# QUESTION GENERATION PROMPT
# ─────────────────────────────────────────────

def question_generation_prompt(role: str, difficulty: str, topics_covered: list[str]) -> str:
    covered = ", ".join(topics_covered) if topics_covered else "none yet"
    return f"""
Generate a single technical interview question for a {role} position.

Difficulty level: {difficulty}  (easy | medium | hard)
Topics already covered: {covered}

Rules:
- Do NOT repeat topics already covered.
- The question must be practical and relevant to real-world {role} work.
- For "easy": basic concepts, definitions, simple usage.
- For "medium": implementation, trade-offs, debugging scenarios.
- For "hard": architecture, optimization, edge cases, system design.
- Return ONLY the question text — no preamble, no numbering, no explanation.
""".strip()


# ─────────────────────────────────────────────
# ANSWER EVALUATION PROMPT
# ─────────────────────────────────────────────

def evaluation_prompt(question: str, answer: str, role: str) -> str:
    return f"""
You are evaluating a candidate's response during a {role} technical interview.

Question asked:
{question}

Candidate's answer:
{answer}

Evaluate the answer across three dimensions (score each 1–10):
1. technical_accuracy — Is the information correct and precise?
2. depth           — Does the answer show deep understanding or is it superficial?
3. clarity         — Is the answer well-structured and easy to follow?

Also provide:
- feedback: 1–2 sentences of constructive feedback (what was good, what was missing).
- suggested_difficulty: Based on this answer, what difficulty should the NEXT question be?
  Options: "easy", "medium", "hard"

Respond ONLY with valid JSON. No extra text. Example:
{{
  "technical_accuracy": 7,
  "depth": 6,
  "clarity": 8,
  "feedback": "Good understanding of the basics, but missed discussing time complexity.",
  "suggested_difficulty": "medium"
}}
""".strip()


# ─────────────────────────────────────────────
# FINAL REPORT PROMPT
# ─────────────────────────────────────────────

def final_report_prompt(role: str, qa_pairs: list[dict]) -> str:
    formatted = ""
    for i, pair in enumerate(qa_pairs, 1):
        formatted += f"""
Q{i}: {pair['question']}
Answer: {pair['answer']}
Scores — Technical: {pair['scores'].get('technical_accuracy')}, Depth: {pair['scores'].get('depth')}, Clarity: {pair['scores'].get('clarity')}
Feedback: {pair['scores'].get('feedback', '')}
"""
    return f"""
You are generating a final interview assessment report for a {role} candidate.

Interview transcript with scores:
{formatted}

Generate a comprehensive report with:
1. overall_score: Weighted average out of 10 (round to 1 decimal).
2. skill_level: One of "Beginner", "Intermediate", "Advanced", or "Expert".
3. strengths: List of 2–4 specific strengths observed.
4. weaknesses: List of 2–4 areas needing improvement.
5. recommendation: "Strong Hire", "Hire", "Maybe", or "No Hire".
6. summary: 2–3 sentence narrative summary of the candidate's performance.

Respond ONLY with valid JSON. No extra text. Example structure:
{{
  "overall_score": 7.4,
  "skill_level": "Intermediate",
  "strengths": ["Strong grasp of core Python", "Clear communication"],
  "weaknesses": ["Needs more depth on async patterns", "System design gaps"],
  "recommendation": "Hire",
  "summary": "The candidate demonstrated solid foundational knowledge..."
}}
""".strip()


# ─────────────────────────────────────────────
# INTRO / GREETING PROMPT
# ─────────────────────────────────────────────

def greeting_prompt(candidate_name: str, role: str) -> str:
    return f"""
You are ARIA, an AI technical interviewer. 
Greet {candidate_name} warmly and professionally.
Explain that you'll be conducting a technical interview for the {role} position.
Mention that the interview will have about 5–7 questions.
Keep the greeting to 2–3 sentences max. Be warm but professional.
""".strip()
