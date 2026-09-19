"""
Prompts the AI agent to mark answers and to write new questions.
"""

import json
import random
import re

from integrations.antigravity_cli import run_antigravity

def _extract_json(text: str):
    """Pull a JSON value out of a reply that may have extra text around it."""
    text = (text or "").strip()

    # 1. The reply might be clean JSON already.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. It might be wrapped in a Markdown code fence.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1).strip())

    # 3. Otherwise, find the first { ... } or [ ... ] in the text.
    match = re.search(r"[\{\[].*[\}\]]", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"No JSON found in the agent's reply: {text[:200]!r}")
    
def evaluate_answer(question: str, correct_answer: str, user_answer: str) -> tuple:
    """
    Ask the agent to mark an answer, allowing typos and synonyms.

    Returns (is_correct, feedback).
    """
    prompt = (
        f"Trivia question: {question}\n"
        f"Official correct answer: {correct_answer}\n"
        f"Player's answer: {user_answer}\n\n"
        "Decide whether the player's answer is correct. Allow minor spelling "
        "mistakes, differences in capitalisation, synonyms, and clearly "
        "correct partial answers.\n\n"
        "Respond with ONLY raw JSON, no code fences and no extra commentary, "
        "in exactly this shape:\n"
        '{"correct": true, "feedback": "2-3 short, friendly sentences"}'
    )

    # If the agent fails, fall back to a plain text comparison so the app survives.
    matches = user_answer.strip().lower() == correct_answer.strip().lower()

    try:
        data = _extract_json(run_antigravity(prompt, timeout_seconds=60))
    except Exception as error:
        return matches, f"(Antigravity error: {error})"

    return bool(data.get("correct", False)), str(data.get("feedback", "")).strip()

def fetch_web_questions(topic: str, amount: int = 5) -> list:
    """Ask the agent to research a topic and write questions about it."""
    prompt = (
        f"Search the web for interesting, verifiable facts about: {topic}\n\n"
        f"Then write exactly {amount} multiple-choice questions from what you "
        "found. Each needs one correct answer and exactly three plausible but "
        "incorrect answers.\n\n"
        "Respond with ONLY a raw JSON array, no code fences and no extra "
        "commentary, where each item has exactly this shape:\n"
        '{"question": "...", "correct_answer": "...", '
        '"incorrect_answers": ["...", "...", "..."], "difficulty": "easy"}'
    )

    items = _extract_json(run_antigravity(prompt, timeout_seconds=180))

    questions = []
    for item in items:
        correct = item["correct_answer"]
        choices = item["incorrect_answers"] + [correct]
        random.shuffle(choices)

        questions.append(
            {
                "question": item["question"],
                "correct_answer": correct,
                "choices": choices,
                "category": topic,
                "difficulty": item.get("difficulty", "medium"),
            }
        )

    return questions

def ask_anything(question: str, context: str = "") -> str:
    """Answer a free-form question, using the documents in rag/ if they help."""
    documents = ""
    if context.strip():
        documents = (
            "Here are the user's own documents:\n\n"
            f"<documents>\n{context.strip()}\n</documents>\n\n"
            "If the documents answer the question, answer from them and say "
            "which one you used. If they are not relevant, ignore them "
            "completely -- do not mention them at all.\n\n"
        )

    prompt = (
        f"{documents}"
        f"Answer this question: {question.strip()}\n\n"
        "Search the web if the answer depends on recent or specific facts. "
        "Answer in a few short paragraphs of plain markdown. Reply in the "
        "same language as the question."
    )
    return run_antigravity(prompt, timeout_seconds=120)
