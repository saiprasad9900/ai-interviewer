"""
interview_controller.py — State-machine orchestrator for the AI interview.

States:
    START  → ASK → LISTEN → EVALUATE → DECIDE → NEXT → END

The controller is stateless between calls (all state lives in the
InterviewState dataclass so it can be serialised into Streamlit session_state).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.question_generator import (
    generate_greeting,
    generate_question,
    extract_topic,
    next_difficulty,
)
from backend.evaluator import evaluate_answer, generate_final_report
from backend.database import (
    init_db,
    create_session,
    close_session,
    save_exchange,
    save_report,
    get_exchanges,
)


# ─────────────────────────────────────────────
# State enum
# ─────────────────────────────────────────────

class Stage(str, Enum):
    START    = "START"
    ASK      = "ASK"
    LISTEN   = "LISTEN"
    EVALUATE = "EVALUATE"
    DECIDE   = "DECIDE"
    END      = "END"


# ─────────────────────────────────────────────
# Interview state (serialisable)
# ─────────────────────────────────────────────

@dataclass
class InterviewState:
    # Identity
    candidate_name: str = ""
    role:           str = ""
    session_id:     Optional[int] = None

    # Progress
    stage:            Stage      = Stage.START
    question_index:   int        = 0
    max_questions:    int        = 6
    current_difficulty: str      = "easy"

    # Current turn
    current_question: str        = ""
    current_answer:   str        = ""
    current_scores:   dict       = field(default_factory=dict)

    # History
    topics_covered:   list[str]  = field(default_factory=list)
    qa_history:       list[dict] = field(default_factory=list)  # [{question, answer, scores, difficulty}]
    score_history:    list[float]= field(default_factory=list)  # composite scores per question

    # Output
    greeting:         str        = ""
    final_report:     dict       = field(default_factory=dict)
    error:            str        = ""


# ─────────────────────────────────────────────
# Controller
# ─────────────────────────────────────────────

class InterviewController:
    """
    Drives the interview from START → END.
    All methods mutate and return the passed-in InterviewState.
    """

    def __init__(self):
        init_db()  # Ensure tables exist on first use

    # ── Stage: START ──────────────────────────────────────────────────────

    def start(self, state: InterviewState) -> InterviewState:
        """
        Initialise a session, generate greeting.
        Transition: START → ASK
        """
        try:
            state.session_id = create_session(state.candidate_name, state.role)
            state.greeting   = generate_greeting(state.candidate_name, state.role)
            state.stage      = Stage.ASK
        except Exception as e:
            state.error = f"Failed to start interview: {e}"
        return state

    # ── Stage: ASK ───────────────────────────────────────────────────────

    def ask(self, state: InterviewState) -> InterviewState:
        """
        Generate the next question.
        Transition: ASK → LISTEN
        """
        try:
            state.current_question = generate_question(
                role=state.role,
                difficulty=state.current_difficulty,
                topics_covered=state.topics_covered,
            )
            state.current_answer  = ""
            state.current_scores  = {}
            state.stage           = Stage.LISTEN
        except Exception as e:
            state.error = f"Failed to generate question: {e}"
        return state

    # ── Stage: LISTEN ─────────────────────────────────────────────────────
    # (The actual listening/recording happens externally in the frontend;
    #  the frontend calls submit_answer() when audio/text is ready.)

    def submit_answer(self, state: InterviewState, answer: str) -> InterviewState:
        """
        Accept the candidate's answer text and move to EVALUATE.
        Transition: LISTEN → EVALUATE
        """
        state.current_answer = answer.strip()
        state.stage          = Stage.EVALUATE
        return state

    # ── Stage: EVALUATE ───────────────────────────────────────────────────

    def evaluate(self, state: InterviewState) -> InterviewState:
        """
        Score the answer, persist the exchange, then move to DECIDE.
        Transition: EVALUATE → DECIDE
        """
        try:
            scores = evaluate_answer(
                question=state.current_question,
                answer=state.current_answer,
                role=state.role,
            )
            state.current_scores = scores

            # Track for adaptive logic
            state.score_history.append(scores["composite_score"])

            # Save to DB
            save_exchange(
                session_id   = state.session_id,
                question_num = state.question_index + 1,
                question     = state.current_question,
                answer       = state.current_answer,
                difficulty   = state.current_difficulty,
                scores       = scores,
            )

            # Accumulate history for final report
            state.qa_history.append({
                "question":   state.current_question,
                "answer":     state.current_answer,
                "scores":     scores,
                "difficulty": state.current_difficulty,
            })

            # Track topic to avoid repetition
            topic = extract_topic(state.current_question)
            state.topics_covered.append(topic)

            state.question_index += 1
            state.stage = Stage.DECIDE

        except Exception as e:
            state.error = f"Evaluation error: {e}"

        return state

    # ── Stage: DECIDE ─────────────────────────────────────────────────────

    def decide(self, state: InterviewState) -> InterviewState:
        """
        Determine whether to ask another question or end the interview.
        Adjusts difficulty for the next question.
        Transition: DECIDE → ASK  OR  DECIDE → END
        """
        if state.question_index >= state.max_questions:
            state.stage = Stage.END
            return state

        # Adaptive difficulty: use the evaluator's suggestion
        suggested = state.current_scores.get("suggested_difficulty", "medium")
        state.current_difficulty = next_difficulty(state.current_difficulty, suggested)
        state.stage = Stage.ASK
        return state

    # ── Stage: END ────────────────────────────────────────────────────────

    def end(self, state: InterviewState) -> InterviewState:
        """
        Generate and persist the final report; close the session.
        """
        try:
            report = generate_final_report(
                role=state.role,
                qa_pairs=state.qa_history,
            )
            state.final_report = report
            save_report(state.session_id, report)
            close_session(state.session_id)
        except Exception as e:
            state.error = f"Report generation error: {e}"
        return state

    # ── Convenience: full automatic step ─────────────────────────────────

    def step(self, state: InterviewState, answer: str | None = None) -> InterviewState:
        """
        Advance the state machine by one logical step.

        - If stage is LISTEN and `answer` is provided → submit + evaluate + decide
        - Otherwise advance the current stage automatically.
        """
        if state.stage == Stage.START:
            return self.start(state)

        if state.stage == Stage.ASK:
            return self.ask(state)

        if state.stage == Stage.LISTEN:
            if answer is not None:
                state = self.submit_answer(state, answer)
                state = self.evaluate(state)
                return self.decide(state)
            return state  # Waiting for answer

        if state.stage == Stage.DECIDE:
            return self.decide(state)

        if state.stage == Stage.END:
            return self.end(state)

        return state
