"""Asks the product entry point one question with no saved vector, and prints the answer and its sources. Run: uv run python -m workshop.rules_bot_live_check"""

import time

from answer_flows.rules_bot import load_rules_bot


# Ask one new question and time it
started = time.perf_counter()
rules_answer = load_rules_bot().answer("Can I serve while my partner is still walking to the court?")
print(f"seconds: {time.perf_counter() - started:.1f}, refused: {rules_answer.refused}")

# Print the answer sentences, then the numbered sources
for sentence in rules_answer.answer_sentences:
    print(" ", sentence.text)
for number, citation in enumerate(rules_answer.citations, start=1):
    print(f"[{number}] {citation.source_name}")
