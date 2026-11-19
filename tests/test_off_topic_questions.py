"""
Checks the off-topic question set (evals/off_topic_questions.json) before any run scores it: its shape, its counts
(6 off topic; 18 that must reach the flow, badminton-wide since Job's relabel of 18 Nov;
docs/specs/refuse-off-topic-questions-fast.md), unique ids
across every question set, and that each rule location exists in the chunks.
"""

import json
from collections import Counter

from evals.golden_answer_chunks import PROJECT_FOLDER, load_chunks


# Constants
## The set, and the other sets its ids must not repeat
OFF_TOPIC_QUESTIONS_FILE = PROJECT_FOLDER / "evals" / "off_topic_questions.json"
OTHER_QUESTION_FILES = ["golden_questions", "phase2_questions", "unseen_questions", "refusal_probes", "false_premise_probes"]
FIELDS = {"id", "category", "kind", "question", "expected_screen", "rule_locations", "why", "pass_rule", "split"}


# Returns the questions in one set file
def load_question_set(file_name: str) -> list[dict]:
    data = json.loads((PROJECT_FOLDER / "evals" / f"{file_name}.json").read_text(encoding="utf-8"))
    return data["questions"]


OFF_TOPIC_QUESTIONS = load_question_set("off_topic_questions")


def test_every_question_has_the_same_fields_and_a_known_screen_result():
    for question in OFF_TOPIC_QUESTIONS:
        assert set(question) == FIELDS, question["id"]
        assert question["expected_screen"] in {"off_topic", "on_topic"}, question["id"]


def test_the_set_holds_6_off_topic_questions_and_18_badminton_questions():
    assert Counter(question["expected_screen"] for question in OFF_TOPIC_QUESTIONS) == {"off_topic": 6, "on_topic": 18}


def test_ids_are_unique_here_and_across_every_question_set():
    ids = [question["id"] for question in OFF_TOPIC_QUESTIONS]
    other_ids = set()
    for file_name in OTHER_QUESTION_FILES:
        other_ids.update(question["id"] for question in load_question_set(file_name))

    assert len(ids) == len(set(ids))
    assert set(ids).isdisjoint(other_ids)


def test_off_topic_questions_name_no_rule_and_every_named_rule_exists():
    chunk_ids = {chunk["id"] for chunk in load_chunks()}
    for question in OFF_TOPIC_QUESTIONS:
        if question["expected_screen"] == "off_topic":
            assert question["rule_locations"] == [], question["id"]
        assert set(question["rule_locations"]).issubset(chunk_ids), question["id"]
