import json
import random
import re
from pathlib import Path
from typing import Optional

from integrations.antigravity_cli import AntigravityError, run_antigravity

WEB_QUESTIONS_TIMEOUT_SECONDS = 180
JUDGE_TIMEOUT_SECONDS = 60
ASK_TIMEOUT_SECONDS = 120


def _extract_json(text: str):
    """Best-effort extraction of a JSON value from a free-form agent response."""
    text = (text or "").strip()

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = fence.group(1).strip() if fence else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Fall back to the first balanced object or array in the text. Whichever
    # delimiter appears first wins, so an array of objects wrapped in prose
    # yields the array rather than its first element.
    delimiters = [(candidate.find(o), o, c) for o, c in (("{", "}"), ("[", "]"))]

    for start, open_ch, close_ch in sorted(d for d in delimiters if d[0] != -1):
        depth = 0
        for i in range(start, len(candidate)):
            if candidate[i] == open_ch:
                depth += 1
            elif candidate[i] == close_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(candidate[start : i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"Could not find valid JSON in Antigravity's response: {text[:300]!r}")


def _build_question(question: str, correct: str, incorrect: list, category: str, difficulty: str) -> dict:
    """Assemble one question with its choices shuffled."""
    choices = list(incorrect) + [correct]
    random.shuffle(choices)

    return {
        "question": question,
        "correct_answer": correct,
        "choices": choices,
        "category": category,
        "difficulty": difficulty,
    }


JSON_FORMAT = (
    "Respond with ONLY a raw JSON array (no markdown fences, no extra commentary "
    "before or after it), where each item has exactly this shape:\n"
    '{"question": "...", "correct_answer": "...", '
    '"incorrect_answers": ["...", "...", "..."], "difficulty": "easy"}'
)


def _questions_from_prompt(prompt: str, category: str, workspace: Optional[Path]) -> list:
    """Run one question-writing prompt and turn the reply into question dicts."""
    try:
        response = run_antigravity(prompt, workspace, WEB_QUESTIONS_TIMEOUT_SECONDS)
    except AntigravityError as exc:
        raise RuntimeError(f"Antigravity couldn't write questions about '{category}': {exc}")

    items = _extract_json(response)
    if not isinstance(items, list):
        raise RuntimeError("Antigravity didn't return a JSON array of questions.")

    return [
        _build_question(
            item["question"],
            item["correct_answer"],
            item.get("incorrect_answers", []),
            category=category,
            difficulty=item.get("difficulty", "medium"),
        )
        for item in items
    ]


def fetch_web_questions(topic: str, amount: int = 5, workspace: Optional[Path] = None) -> list:
    """Ask agy to research `topic` on the web and write `amount` questions."""
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("A topic is required for web-search questions.")

    prompt = (
        f"Search the web for interesting, verifiable facts about: {topic}\n\n"
        f"Then write exactly {amount} multiple-choice trivia questions based on what "
        "you found. Each question needs one correct answer and exactly three "
        "plausible but incorrect answers. Keep questions factual, unambiguous, and "
        f"specific enough to have one clearly correct answer.\n\n{JSON_FORMAT}"
    )

    return _questions_from_prompt(prompt, topic, workspace)


def ask_anything(
    question: str,
    workspace: Optional[Path] = None,
    context: str = "",
) -> str:
    if not question or not question.strip():
        raise ValueError("A question is required.")

    documents = ""
    if context.strip():
        documents = (
            "Here are the user's own documents:\n\n"
            "<documents>\n"
            f"{context.strip()}\n"
            "</documents>\n\n"
            "If the documents answer the question, answer from them and say which "
            "one you used. If they are not relevant to the question, ignore them "
            "completely and answer normally — do not mention them, and do not "
            "explain that they were unhelpful.\n\n"
        )

    prompt = (
        f"{documents}"
        f"Answer this question: {question.strip()}\n\n"
        "Search the web if the answer depends on recent information, specific "
        "facts, or anything you're unsure about. Answer in a few short "
        "paragraphs of plain markdown — no code blocks, no JSON. Reply in the "
        "same language as the question."
    )

    try:
        return run_antigravity(prompt, workspace, ASK_TIMEOUT_SECONDS)
    except AntigravityError as exc:
        raise RuntimeError(f"Antigravity couldn't answer that: {exc}")


def evaluate_answer(
    question: str,
    correct_answer: str,
    user_answer: str,
    workspace: Optional[Path] = None,
) -> tuple:
    prompt = (
        f"Trivia question: {question}\n"
        f"Official correct answer: {correct_answer}\n"
        f"Player's answer: {user_answer}\n\n"
        "Judge whether the player's answer is correct. Allow for minor spelling "
        "differences, case differences, synonyms, or clearly-correct partial answers.\n\n"
        "Respond with ONLY raw JSON (no markdown fences, no extra commentary before "
        "or after it) in exactly this shape:\n"
        '{"correct": true, "feedback": "2-3 short, friendly sentences about the answer"}'
    )

    matches = user_answer.strip().lower() == correct_answer.strip().lower()

    try:
        response = run_antigravity(prompt, workspace, JUDGE_TIMEOUT_SECONDS)
    except AntigravityError as exc:
        note = "That's right!" if matches else f"The correct answer was {correct_answer}."
        return matches, f"(Antigravity error: {exc}) {note}"

    try:
        data = _extract_json(response)
    except ValueError:
        return matches, response

    return bool(data.get("correct", False)), str(data.get("feedback", "")).strip() or "Thanks for playing!"