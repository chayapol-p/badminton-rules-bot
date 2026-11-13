"""
Tests the answer run's scores, the cost of one call, the retrieve step, and the code-checks-then-judge step.
"""

import pytest

from evals.golden_answer_chunks import load_chunks
from evals.judge_answers import JUDGE_VOTES
from evals.token_costs import call_cost
from experiments.compare_answer_setups import (build_clause_vector_search, build_retrieve_function, check_and_grade,
                                               summarise_answer_run)
from retrieval.build_bundle import full_chunks
from retrieval.expand_with_rule_links import load_rule_map
from tests.sample_data import SAMPLE_CHUNKS, SAMPLE_QUESTIONS, full_items
from tests.test_judge_answers import POSTS_REPLY, StubJudgeClient

CHUNK_BY_ID = {chunk["id"]: chunk for chunk in SAMPLE_CHUNKS}


# ===== Sample answer lines =====

## The two outcomes where the bot refused
REFUSED_OUTCOMES = {"correct refusal", "false refusal"}


def answer_line(question_id: str, split: str, category: str, should_refuse: bool, refusal_outcome: str | None,
                citation_problems: list[dict], code_failures: list[str]) -> dict:
    """Returns one answer line in the run's shape; a None outcome means the reply didn't fit the shape."""
    answer = None
    if refusal_outcome is not None:
        answer = {"answer": "sample", "citations": [], "refused": refusal_outcome in REFUSED_OUTCOMES}
    return {
        "id": question_id,
        "split": split,
        "category": category,
        "should_refuse": should_refuse,
        "words_returned": 100,
        "answer": answer,
        "is_format_error": answer is None,
        "citation_problems": citation_problems,
        "refusal_outcome": refusal_outcome,
        "code_failures": code_failures,
        "answer_cost": 0.003,
        "judge_cost": 0.009,
    }


ANSWER_LINES = [
    answer_line("post-height", "dev", "direct_lookup", False, "answered", [], []),
    answer_line("deuce-end", "dev", "direct_lookup", False, "false refusal", [], ["false refusal"]),
    answer_line("red-card", "dev", "cross_reference", False, None, [], ["format error"]),
    answer_line("doubles-court-size", "dev", "diagram", False, "answered", [{"chunk_id": "x", "problem": "not retrieved"}],
                ["citation [x] not retrieved"]),
    answer_line("service-judge-height-signal", "dev", "diagram", False, "false refusal", [], ["false refusal"]),
    answer_line("ceiling-height", "dev", "unanswerable", True, "correct refusal", [], []),
    answer_line("spin-serve-ban-date", "dev", "unanswerable", True, "missed refusal", [], ["missed refusal"]),
    answer_line("string-tension", "probe", "refusal_probe", True, "correct refusal", [], []),
    answer_line("game-ends-at-25", "probe", "false_premise", False, "answered", [], []),
]

PASSED_BY_ID = {
    "post-height": True,
    "deuce-end": False,
    "red-card": False,
    "doubles-court-size": False,
    "service-judge-height-signal": False,
    "ceiling-height": True,
    "spin-serve-ban-date": False,
    "string-tension": True,
    "game-ends-at-25": True,
}


# ===== Tests =====

def test_answers_are_scored_without_the_image_only_questions():
    scores = summarise_answer_run(ANSWER_LINES, PASSED_BY_ID)
    assert scores["answers_passed"] == 1
    assert scores["answers_scored"] == 3
    assert scores["image_only_scored"] == 2
    assert scores["by_category"]["direct_lookup"] == {"passed": 1, "questions": 2}


def test_false_premise_probes_are_scored_apart_from_the_answers():
    scores = summarise_answer_run(ANSWER_LINES, PASSED_BY_ID)
    assert scores["false_premise_passed"] == 1
    assert scores["false_premise_probes"] == 1
    assert "false_premise" not in scores["by_category"]


def test_refusals_are_counted_both_ways_and_probes_apart():
    scores = summarise_answer_run(ANSWER_LINES, PASSED_BY_ID)
    assert scores["refusals_correct"] == 1
    assert scores["refusals_needed"] == 2
    assert scores["probe_refusals_correct"] == 1
    assert scores["probes"] == 1
    assert scores["false_refusals"] == 1, "the image-only false refusal is left out"
    assert scores["no_answer_passed"] == 2


def test_code_failures_are_counted_by_check_and_only_clean_answers_reach_the_judge():
    scores = summarise_answer_run(ANSWER_LINES, PASSED_BY_ID)
    assert scores["code_failed"] == 5
    assert scores["code_failures_by_check"] == {"format error": 1, "wrong refusal": 3, "citation problem": 1,
                                                "wrong clause": 0}
    assert scores["judge_calls"] == 4


def test_citations_are_scored_only_on_replies_that_fit_the_shape():
    scores = summarise_answer_run(ANSWER_LINES, PASSED_BY_ID)
    assert scores["format_errors"] == 1
    assert scores["citation_pass_rate"] == round(7 / 8, 3)


def test_cost_adds_the_answer_and_the_judge():
    scores = summarise_answer_run(ANSWER_LINES, PASSED_BY_ID)
    assert scores["cost_per_question"] == 0.012
    assert scores["total_cost"] == round(9 * 0.012, 3)


def test_one_call_costs_its_tokens_at_the_model_price():
    assert call_cost("claude-sonnet-5-5", 1_000_000, 100_000) == 2.00 + 1.00


# ===== Code checks first, then the judge =====

def answer_line_to_check(rules_answer) -> dict:
    """Returns the posts answer line as the run builds it, before the checks."""
    return {"id": "post-height", "question": SAMPLE_QUESTIONS[1]["question"], "retrieved_ids": ["laws-1.4"],
            "is_format_error": False, "answer": rules_answer.model_dump()}


def test_an_answer_that_fails_the_code_checks_never_reaches_the_judge():
    client = StubJudgeClient()
    refused_reply = POSTS_REPLY.model_copy(update={"refused": True})
    line = answer_line_to_check(refused_reply)
    grade_line = check_and_grade(line, refused_reply, SAMPLE_QUESTIONS[1], [SAMPLE_CHUNKS[2]], SAMPLE_CHUNKS,
                                 CHUNK_BY_ID, client, "claude-sonnet-5-5")
    assert grade_line == {"id": "post-height", "passed": False, "judged": False, "grade": None}
    assert line["code_failures"] == ["false refusal"]
    assert client.requests == []


def test_a_clean_answer_is_judged_and_its_cost_counted():
    client = StubJudgeClient()
    line = answer_line_to_check(POSTS_REPLY)
    grade_line = check_and_grade(line, POSTS_REPLY, SAMPLE_QUESTIONS[1], [SAMPLE_CHUNKS[2]], SAMPLE_CHUNKS,
                                 CHUNK_BY_ID, client, "claude-sonnet-5-5")
    assert grade_line["judged"]
    assert grade_line["passed"]
    assert line["judge_cost"] > 0
    assert len(client.requests) == JUDGE_VOTES


# ===== The retrieve step =====

def test_retrieve_brings_the_items_of_an_item_that_is_a_heading():
    """11 Nov: every-let-situation got 14.2.3 ("the shuttle is:") without its two cases."""
    try:
        chunk_by_id = {chunk["id"]: chunk for chunk in load_chunks()}
        retrieve = build_retrieve_function(lambda question_text, top_k: [chunk_by_id["laws-14.2"]], 1, chunk_by_id,
                                           load_rule_map())
    except FileNotFoundError:
        pytest.skip("data/ is missing: run scripts.build_rule_chunks and scripts.build_rule_links first")
    retrieved_ids = [chunk["id"] for chunk in full_chunks(retrieve("When is it a let?"))]
    assert {"laws-14.2.3.1", "laws-14.2.3.2"}.issubset(retrieved_ids)


def test_with_no_links_retrieve_hands_on_the_search_hits_in_full():
    empty_rule_map = {"outgoing": {}, "incoming": {}, "outside": {}}
    retrieve = build_retrieve_function(lambda question_text, top_k: SAMPLE_CHUNKS[:top_k], 2, CHUNK_BY_ID, empty_rule_map)
    assert retrieve("any question") == full_items(SAMPLE_CHUNKS[:2])


def test_rule_links_bring_the_clause_a_hit_cites():
    """Run 1: ITTO 5.4.13 says "(Law 16.2.1)", but Law 16.2.1 never reached the model."""
    try:
        chunk_by_id = {chunk["id"]: chunk for chunk in load_chunks()}
        retrieve = build_retrieve_function(lambda question_text, top_k: [chunk_by_id["itto-5.4.13"]], 1, chunk_by_id,
                                           load_rule_map())
    except FileNotFoundError:
        pytest.skip("data/ is missing: run scripts.build_rule_chunks and scripts.build_rule_links first")
    retrieved_ids = [chunk["id"] for chunk in full_chunks(retrieve("How many coaches at the 11-point break?"))]
    assert retrieved_ids[0] == "itto-5.4.13"
    assert "laws-16.2.1" in retrieved_ids


def test_a_found_list_heading_brings_its_items():
    """8 Nov: wheelchair-shuttle-on-net got the heading "in Wheelchair Badminton if the shuttle is:" but not its items."""
    try:
        chunk_by_id = {chunk["id"]: chunk for chunk in load_chunks()}
        retrieve = build_retrieve_function(lambda question_text, top_k: [chunk_by_id["laws-13.3.10"]], 1, chunk_by_id,
                                           load_rule_map())
    except FileNotFoundError:
        pytest.skip("data/ is missing: run scripts.build_rule_chunks and scripts.build_rule_links first")
    retrieved_ids = [chunk["id"] for chunk in full_chunks(retrieve("Shuttle stuck on the net in Wheelchair Badminton?"))]
    assert "laws-13.3.10.1" in retrieved_ids


def test_a_question_with_no_saved_vector_stops_the_run_with_how_to_fix_it():
    """Every question needs its vector, so the run fails fast, before any paid call (coding style rule 14)."""
    question_without_vector = {"id": "not-embedded-yet", "question": "A question nobody embedded?"}
    with pytest.raises(KeyError, match="run scripts.build_embeddings first"):
        build_clause_vector_search(load_chunks(), [question_without_vector], "mistral-embed-2312")
