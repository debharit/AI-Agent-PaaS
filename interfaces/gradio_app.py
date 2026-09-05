import logging
from pathlib import Path

import gradio as gr

from integrations import trivia_api
from integrations.agy_questions import ask_anything, evaluate_answer, fetch_web_questions

PROJECT_ROOT = Path(__file__).resolve().parents[1]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("antigravity_interface")

STATE_QUESTIONS = "questions"
STATE_INDEX = "index"
STATE_SCORE = "score"

SOURCE_OPENTDB = "Open Trivia DB"
SOURCE_WEB = "Web Search (agy)"
RAG_DIR = PROJECT_ROOT / "rag"

# Long documents make the agent slow, so send it a generous but bounded slice.
MAX_CONTEXT_CHARS = 30_000


def read_documents() -> str:
    """The text of every .txt file in rag/, labelled by filename."""
    parts = []

    for path in sorted(RAG_DIR.glob("*.txt")):
        parts.append(f"--- {path.name} ---\n{path.read_text(encoding='utf-8', errors='replace')}")

    return "\n\n".join(parts)[:MAX_CONTEXT_CHARS]


def format_question(q: dict, index: int, total: int) -> str:
    lines = [f"**Question {index + 1}/{total}** — {q['category']} ({q['difficulty']})", "", q["question"], ""]
    lines += [f"- {choice}" for choice in q["choices"]]
    return "\n".join(lines)


def toggle_topic_box(source):
    return gr.update(visible=(source == SOURCE_WEB))


def start_quiz(source, topic, amount, history):
    """Fetch a fresh batch of questions (from the chosen source) and post the first one to the chat."""
    if source == SOURCE_WEB:
        if not topic or not topic.strip():
            history = [
                {
                    "role": "assistant",
                    "content": "⚠️ Please enter a topic to search the web for, then click **Start Quiz** again.",
                }
            ]
            return history, {}, gr.update()

        logger.info("Requesting web-search questions from agy for topic=%r", topic)
        try:
            questions = fetch_web_questions(topic.strip(), amount=int(amount), workspace=PROJECT_ROOT)
        except Exception as e:
            logger.error("agy failed to generate web questions: %s", e)
            history = [{"role": "assistant", "content": f"⚠️ Couldn't generate questions from the web: {e}"}]
            return history, {}, gr.update()

        intro = (
            f"Let's play! I asked Antigravity to research **{topic.strip()}** and put together "
            f"{len(questions)} questions — just type your answer in the box below.\n\n"
        )
    else:
        questions = trivia_api.fetch_questions(amount=int(amount))
        intro = f"Let's play! I'll ask you {len(questions)} questions from Open Trivia DB — just type your answer in the box below.\n\n"

    state = {STATE_QUESTIONS: questions, STATE_INDEX: 0, STATE_SCORE: 0}
    first_question = format_question(questions[0], 0, len(questions))

    history = [{"role": "assistant", "content": intro + first_question}]
    return history, state, gr.update(value="", interactive=True)


def answer_question(message: str) -> str:
    """Research a free-form question with agy and format the reply for the chat."""
    logger.info("Answering free-form question via agy: %r", message)
    try:
        answer = ask_anything(message, workspace=PROJECT_ROOT, context=read_documents())
    except Exception as e:
        logger.error("agy failed to answer the question: %s", e)
        return f"⚠️ {e}\n\nOr click **Start Quiz** above to play instead."

    return f"{answer}\n\n<sub>Ask me anything else, or click **Start Quiz** above to play.</sub>"


def respond(message, history, state):
    """Handle one chat turn: judge the answer via agy, give feedback, ask the next question."""
    history = history + [{"role": "user", "content": message}]

    quiz_running = state and state.get(STATE_QUESTIONS) and state[STATE_INDEX] < len(state[STATE_QUESTIONS])

    if not quiz_running:
        # No quiz in progress — treat the message as a question to research.
        history.append({"role": "assistant", "content": answer_question(message)})
        return history, state, ""

    questions = state[STATE_QUESTIONS]
    q = questions[state[STATE_INDEX]]

    logger.info("Judging answer via agy for question index=%d", state[STATE_INDEX])
    is_correct, feedback = evaluate_answer(q["question"], q["correct_answer"], message, workspace=PROJECT_ROOT)

    if is_correct:
        state[STATE_SCORE] += 1
        prefix = "✅ **Correct!**"
    else:
        prefix = f"❌ **Not quite** — the correct answer was **{q['correct_answer']}**."

    state[STATE_INDEX] += 1
    reply = f"{prefix}\n\n{feedback}"

    if state[STATE_INDEX] < len(questions):
        next_question = format_question(questions[state[STATE_INDEX]], state[STATE_INDEX], len(questions))
        reply += f"\n\n---\n\n{next_question}"
    else:
        reply += f"\n\n---\n\n🎉 **Quiz complete!** Final score: **{state[STATE_SCORE]} / {len(questions)}**"

    history.append({"role": "assistant", "content": reply})
    return history, state, ""


def build_interface() -> gr.Blocks:
    with gr.Blocks(title="Antigravity Trivia") as demo:
        gr.Markdown(
            "# 🧠 Antigravity Trivia\n"
            "**Ask me anything** in the chat below — I'll answer from the documents in "
            "`rag/` when they cover it, and search the web when they don't. "
            "Or click **Start Quiz** to play."
        )

        with gr.Row():
            source = gr.Radio(
                choices=[SOURCE_OPENTDB, SOURCE_WEB],
                value=SOURCE_OPENTDB,
                label="Question source",
            )
            amount = gr.Slider(minimum=3, maximum=20, value=5, step=1, label="Number of questions")

        topic = gr.Textbox(
            label="Topic to search the web for",
            placeholder="e.g. Ancient Rome, Formula 1, the James Webb Space Telescope",
            visible=False,
        )

        start_btn = gr.Button("Start Quiz", variant="primary")

        chatbot = gr.Chatbot(height=450, label="Trivia Chat")
        msg = gr.Textbox(
            label="Chat",
            placeholder="Ask me anything, or type your answer when a quiz is running...",
        )

        state = gr.State({})

        source.change(fn=toggle_topic_box, inputs=[source], outputs=[topic])

        start_btn.click(
            fn=start_quiz,
            inputs=[source, topic, amount, chatbot],
            outputs=[chatbot, state, msg],
        )

        msg.submit(
            fn=respond,
            inputs=[msg, chatbot, state],
            outputs=[chatbot, state, msg],
        )

    return demo


if __name__ == "__main__":
    build_interface().launch(share=True)
