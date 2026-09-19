"""
Fetches trivia questions from the Open Trivia DB API (https://opentdb.com).
"""

import html
import random

import requests


def fetch_questions(amount: int = 10) -> list:
    response = requests.get(
        "https://opentdb.com/api.php",
        params={"amount": amount, "type": "multiple"},
        timeout=10,
    )
    data = response.json()

    questions = []
    for item in data["results"]:
        correct = html.unescape(item["correct_answer"])
        choices = [html.unescape(a) for a in item["incorrect_answers"]] + [correct]
        random.shuffle(choices)

        questions.append(
            {
                "question": html.unescape(item["question"]),
                "correct_answer": correct,
                "choices": choices,
                "category": html.unescape(item["category"]),
                "difficulty": item["difficulty"],
            }
        )

    return questions
