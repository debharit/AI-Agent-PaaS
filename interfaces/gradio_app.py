"""
The web interface, built with gradio.
"""

from pathlib import Path

import gradio as gr

from integrations.agy_questions import (
    ask_anything,
    evaluate_answer,
    fetch_web_questions,
)
from integrations.trivia_api import fetch_questions

RAG_FOLDER = Path("rag")
MAX_CONTEXT_CHARS = 30_000
DEFAULT_QUESTIONS = 5


def new_state() -> dict:
    """The state of a session with no quiz running."""
    return {"questions": [], "index": 0, "score": 0}


def read_documents() -> str:
    """Read every .txt file in rag/ into one string."""
    parts = []
    for path in sorted(RAG_FOLDER.glob("*.txt")):
        parts.append(f"--- {path.name} ---\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)[:MAX_CONTEXT_CHARS]

API_SOURCE = "Open Trivia DB"
WEB_SOURCE = "Web Search (agy)"


def show_question(state: dict) -> str:
    """Format the current question as markdown."""
    question = state["questions"][state["index"]]
    choices = "\n".join(f"- {choice}" for choice in question["choices"])
    return (
        f"**Question {state['index'] + 1}/{len(state['questions'])}** "
        f"--- {question['category']} ({question['difficulty']})\n\n"
        f"{question['question']}\n\n{choices}"
    )


def start_quiz(source: str, topic: str, amount: float, history: list, state: dict):
    """Start a quiz from the chosen source."""
    amount = int(amount)
    topic = topic.strip()

    if source == WEB_SOURCE:
        if not topic:
            note = "Type a topic first, then press Start Quiz."
            history = history + [{"role": "assistant", "content": note}]
            return topic, history, state

        questions = fetch_web_questions(topic, amount)
        described = f"the web, on {topic}"
    else:
        questions = fetch_questions(amount)
        described = API_SOURCE

    state = {"questions": questions, "index": 0, "score": 0}
    intro = (
        f"Let's play! I'll ask you {amount} questions from {described} "
        "--- just type your answer in the box below."
    )
    history = history + [
        {"role": "assistant", "content": f"{intro}\n\n{show_question(state)}"}
    ]
    return "", history, state

def respond(message: str, history: list, state: dict):
    """Handle one message from the player."""
    if not message.strip():
        return "", history, state

    history = history + [{"role": "user", "content": message}]

    if state["questions"]:
        question = state["questions"][state["index"]]
        correct, feedback = evaluate_answer(
            question["question"], question["correct_answer"], message
        )
        if correct:
            state["score"] += 1

        reply = ("Correct. " if correct else "Not quite. ") + feedback
        state["index"] += 1

        if state["index"] < len(state["questions"]):
            reply += "\n\n---\n\n" + show_question(state)
        else:
            total = len(state["questions"])
            reply += f"\n\n---\n\n**Final score: {state['score']} / {total}**"
            state = new_state()
    else:
        reply = ask_anything(message, context=read_documents())

    history = history + [{"role": "assistant", "content": reply}]
    return "", history, state

def build_interface():
    with gr.Blocks(title="Antigravity Trivia") as demo:
        gr.Markdown("# Antigravity Trivia\nAsk anything, or start a quiz.")

        state = gr.State(new_state())

        source = gr.Radio(
            [API_SOURCE, WEB_SOURCE],
            value=API_SOURCE,
            label="Question source",
        )

        with gr.Row():
            topic = gr.Textbox(
                placeholder="Topic (used for Web Search only)...",
                show_label=False,
                scale=3,
            )
            amount = gr.Slider(
                minimum=1,
                maximum=15,
                value=DEFAULT_QUESTIONS,
                step=1,
                label="Questions",
                scale=1,
            )

        start = gr.Button("Start Quiz", variant="primary")

        chatbot = gr.Chatbot(label="Trivia Chat", height=420)
        box = gr.Textbox(label="Chat", placeholder="Type a question, or your answer...")

        box.submit(respond, [box, chatbot, state], [box, chatbot, state])
        start.click(
            start_quiz,
            [source, topic, amount, chatbot, state],
            [topic, chatbot, state],
        )

    return demo
