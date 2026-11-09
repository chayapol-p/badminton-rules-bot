"""Checks the unseen questions (Stage 3): their shape, their tags, and that every answer location has its chunk."""

from evals.golden_answer_chunks import expected_chunk_ids, load_chunks, load_questions
from evals.probes import load_probes, load_unseen_questions


# Constants
## What reaching the full answer takes, and how many questions need each
EXPECTED_NEEDS_COUNTS = {"map": 1, "tool": 3, "map and tool": 2, "search only": 4, "no answer": 1}

## The difficulty labels a question may carry
DIFFICULTY_LABELS = {"easy", "medium", "hard"}


def test_the_needs_tags_are_spread_as_planned():
    needs_counts = {}
    for question in load_unseen_questions():
        needs_counts[question["needs"]] = needs_counts.get(question["needs"], 0) + 1
    assert needs_counts == EXPECTED_NEEDS_COUNTS


def test_every_question_has_a_difficulty_and_the_unseen_split():
    for question in load_unseen_questions():
        assert question["difficulty"] in DIFFICULTY_LABELS, question["id"]
        assert question["split"] == "unseen", question["id"]


def test_only_the_unanswerable_question_has_no_answer():
    for question in load_unseen_questions():
        has_no_answer = question["answer"] is None
        assert has_no_answer == (question["needs"] == "no answer"), question["id"]
        assert has_no_answer == (question["answer_locations"] == []), question["id"]


def test_every_answer_location_has_its_chunk():
    chunks = load_chunks()
    for question in load_unseen_questions():
        for location in question["answer_locations"]:
            assert expected_chunk_ids(location, chunks), f"{question['id']}: {location}"


def test_no_id_or_question_repeats_another_set():
    other_questions = load_questions("dev") + load_questions("held_out") + load_probes()
    other_ids = {question["id"] for question in other_questions}
    other_texts = {question["question"] for question in other_questions}
    for question in load_unseen_questions():
        assert question["id"] not in other_ids
        assert question["question"] not in other_texts
