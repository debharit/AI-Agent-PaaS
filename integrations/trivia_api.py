import html
import random
from typing import List, Optional

import requests

OPENTDB_URL = "https://opentdb.com/api.php"


def fetch_questions(
    amount: int = 10,
    category: Optional[int] = None,
    difficulty: Optional[str] = None,
    q_type: str = "multiple",
) -> List[dict]:
    params = {"amount": amount, "type": q_type}
    if category:
        params["category"] = category
    if difficulty:
        params["difficulty"] = difficulty

    response = requests.get(OPENTDB_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    if data.get("response_code") != 0:
        raise RuntimeError(
            f"Open Trivia DB returned an error (response_code={data.get('response_code')}). "
            "Try a smaller 'amount' or different category/difficulty."
        )

    questions = []
    for item in data["results"]:
        question_text = html.unescape(item["question"])
        correct_answer = html.unescape(item["correct_answer"])
        incorrect_answers = [html.unescape(a) for a in item["incorrect_answers"]]

        choices = incorrect_answers + [correct_answer]
        random.shuffle(choices)

        questions.append(
            {
                "question": question_text,
                "correct_answer": correct_answer,
                "choices": choices,
                "category": html.unescape(item["category"]),
                "difficulty": item["difficulty"],
            }
        )

    return questions
