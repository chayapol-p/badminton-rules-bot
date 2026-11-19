"""Tests the Phase 2 question set loads with the shape every answer run reads."""

from evals.checks.check_refusals import should_refuse
from evals.probes import load_phase2_questions


def test_the_phase2_set_has_41_dev_questions_and_14_to_refuse():
    questions = load_phase2_questions()
    assert len(questions) == 41
    assert {question["split"] for question in questions} == {"dev"}
    assert sum(should_refuse(question) for question in questions) == 14


def test_every_question_to_refuse_has_a_pass_rule_and_no_answer_location():
    for question in load_phase2_questions():
        if should_refuse(question):
            assert question["pass_rule"], question["id"]
            assert question["answer_locations"] == [], question["id"]
