"""
Slice 5 tests for POST /chat: a refusal streams as a normal "answer" event with refused true and no citations
(spec criterion 4). The stub refuses one fixed question with a real refusal from the 17 Nov run.
Nothing here runs a paid API.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.stub_rules_bot import SAMPLE_REFUSAL_ANSWER, STUB_REFUSED_QUESTION
from tests.test_chat_endpoint import placeholder_keys, read_events  # placeholder_keys runs for every test here too


# Constants
## The run the sample refusal was copied from, and the question it answers there
REFUSAL_RUN_FILE = Path("evals/answer_runs/20261117T0753-hybrid-natural-format-fix-phase2-run2-answers.jsonl")
REFUSAL_QUESTION_ID = "net-cord-tension"


# ===== The stub's refusal =====

def test_the_stub_refuses_its_fixed_question_with_no_citations():
    with TestClient(app) as client:
        response = client.post("/chat", json={"question": STUB_REFUSED_QUESTION})

    events = read_events(response.text)
    assert events[-1][0] == "answer"
    answer = json.loads(events[-1][1])
    assert answer["refused"] is True
    assert answer["citations"] == []
    assert answer["answer"].startswith("The sources do not say the force in newtons")


# ===== The sample is real =====

def test_the_sample_refusal_is_the_real_one_from_the_run():
    for line in REFUSAL_RUN_FILE.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["id"] == REFUSAL_QUESTION_ID:
            assert row["question"] == STUB_REFUSED_QUESTION
            assert row["answer"] == SAMPLE_REFUSAL_ANSWER.model_dump()
            return
    raise AssertionError(f"{REFUSAL_QUESTION_ID} is missing from {REFUSAL_RUN_FILE}")
