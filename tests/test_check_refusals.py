"""
Tests the four refusal outcomes on real golden questions from the sample data.
"""

import json

from evals.checks.check_refusals import (ANSWERED, CATEGORIES_TO_REFUSE, CORRECT_REFUSAL, FALSE_REFUSAL,
                                         MISSED_REFUSAL, refusal_outcome, should_refuse)
from evals.golden_answer_chunks import QUESTIONS_FILE
from evals.probes import load_probes
from tests.sample_data import SAMPLE_QUESTIONS


# ===== Sample questions: one with an answer, one without =====

POSTS_QUESTION = SAMPLE_QUESTIONS[1]
CEILING_QUESTION = SAMPLE_QUESTIONS[2]


# ===== Tests =====

def test_only_the_refuse_categories_should_be_refused():
    assert should_refuse(CEILING_QUESTION)
    assert not should_refuse(POSTS_QUESTION)


def test_refusing_a_question_without_an_answer_is_correct():
    assert refusal_outcome(CEILING_QUESTION, refused=True) == CORRECT_REFUSAL


def test_answering_a_question_without_an_answer_is_a_missed_refusal():
    assert refusal_outcome(CEILING_QUESTION, refused=False) == MISSED_REFUSAL


def test_refusing_a_question_with_an_answer_is_a_false_refusal():
    assert refusal_outcome(POSTS_QUESTION, refused=True) == FALSE_REFUSAL


def test_answering_a_question_with_an_answer_goes_to_the_judge():
    assert refusal_outcome(POSTS_QUESTION, refused=False) == ANSWERED


# ===== The categories stay in step with the data =====

def test_exactly_the_questions_without_an_answer_are_in_the_refuse_categories():
    """A new category, or a misspelt one, would silently change what gets refused, so check every question."""
    golden_questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]
    for question in golden_questions + load_probes():
        has_no_answer = question["answer"] is None
        assert (question["category"] in CATEGORIES_TO_REFUSE) == has_no_answer, question["id"]
