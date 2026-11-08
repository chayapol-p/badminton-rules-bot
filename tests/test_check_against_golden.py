"""
Tests the checks against the golden set: the cited clause, and the golden answer's numbers.
"""

from evals.check_against_golden import cites_expected_clause, find_missing_golden_numbers
from tests.sample_data import SAMPLE_CHUNKS, SAMPLE_QUESTIONS


# ===== The cited clause =====

def test_citing_one_of_the_answer_clauses_is_enough():
    deuce_question = SAMPLE_QUESTIONS[0]
    assert cites_expected_clause({"laws-7.5"}, deuce_question, SAMPLE_CHUNKS)


def test_citing_only_other_clauses_fails():
    posts_question = SAMPLE_QUESTIONS[1]
    assert not cites_expected_clause({"laws-7.4"}, posts_question, SAMPLE_CHUNKS)


# ===== The golden answer's numbers =====

def test_every_golden_number_present_gives_no_warning():
    golden_answer = SAMPLE_QUESTIONS[1]["answer"]
    assert find_missing_golden_numbers("The posts are 1.55 metres tall.", golden_answer) == []


def test_a_missing_golden_number_is_listed():
    golden_answer = SAMPLE_QUESTIONS[0]["answer"]
    assert find_missing_golden_numbers("A two-point lead wins.", golden_answer) == ["29", "30"]
