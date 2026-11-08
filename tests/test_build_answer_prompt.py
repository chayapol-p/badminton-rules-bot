"""
Tests the answer prompt: every source block names its chunk id and where it comes from, and the question is fenced off.
"""

import json

import pytest

from answer.answer_shape import RulesAnswer
from answer.build_answer_prompt import ANSWER_RULES, EXTRA_ANSWER_RULES, build_answer_prompt, build_answer_rules, describe_source, format_source
from evals.golden_answer_chunks import CHUNKS_FILE
from tests.sample_data import SAMPLE_CHUNKS


# ===== A sample of the real data: an Alternative Laws clause =====

## Alternative Laws, one game to 21, Law 8.1, copied as it is (7 Nov 2026): it has a format and a 2027 in-force date
ONE_GAME_CHANGE_OF_ENDS_CHUNK = {
    "id": "alt-one-game-21:8.1",
    "document": "alt",
    "document_title": "Alternative Laws of Badminton",
    "version": "2.0",
    "in_force": "2027-01-04",
    "clause": "8.1",
    "alternative_format": "one-game-21",
    "heading": "8. CHANGE OF ENDS",
    "para_only": False,
    "page": 1,
    "text": "In a one game match, players shall change ends when a side first scores 11 points.",
    "search_text": "Alternative Laws of Badminton · one game to 21 · 8. CHANGE OF ENDS · Clause 8.1\nIn a one game match, players shall change ends when a side first scores 11 points.",
    "search_text_with_parents": "Alternative Laws of Badminton · one game to 21 · 8. CHANGE OF ENDS · Clause 8.1\nIn a one game match, players shall change ends when a side first scores 11 points."
}


# ===== One source block =====

def test_a_source_block_starts_with_the_chunk_id_and_ends_with_the_clause_text():
    source_block = format_source(SAMPLE_CHUNKS[2])
    assert source_block.startswith("[laws-1.4] ")
    assert source_block.endswith(SAMPLE_CHUNKS[2]["text"])


def test_a_laws_clause_names_its_version_heading_and_number():
    description = describe_source(SAMPLE_CHUNKS[0])
    assert description == "Laws of Badminton 5.0 (2), in force 2025-04-26 · 7. SCORING SYSTEM · Clause 7.4"


def test_an_alternative_laws_clause_names_its_format_and_in_force_date():
    description = describe_source(ONE_GAME_CHANGE_OF_ENDS_CHUNK)
    assert "in force 2027-01-04" in description
    assert "format: one-game-21" in description


# ===== The messages =====

def test_a_false_premise_is_corrected_and_answered_not_refused():
    """FreshQA credits a false-premise reply only when it points the premise out; refusing would be a false refusal."""
    assert "Correcting an assumption is an answer, not a refusal" in ANSWER_RULES


def test_the_rules_go_in_the_system_message_and_the_question_in_its_tags():
    messages = build_answer_prompt(ANSWER_RULES, "How tall are the posts?", SAMPLE_CHUNKS)
    assert messages[0] == {"role": "system", "content": ANSWER_RULES}
    assert messages[1]["role"] == "user"
    assert "<question>\nHow tall are the posts?\n</question>" in messages[1]["content"]


def test_every_retrieved_chunk_is_in_the_sources():
    user_message = build_answer_prompt(ANSWER_RULES, "any question", SAMPLE_CHUNKS)[1]["content"]
    for chunk in SAMPLE_CHUNKS:
        assert format_source(chunk) in user_message


# ===== The extra sample stays a true copy of the real data =====

def test_alternative_laws_sample_matches_the_real_file():
    if not CHUNKS_FILE.exists():
        pytest.skip("data/rule_chunks.json is missing: run scripts.build_rule_chunks first")
    real_chunks_by_id = {chunk["id"]: chunk for chunk in json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))}
    assert ONE_GAME_CHANGE_OF_ENDS_CHUNK == real_chunks_by_id["alt-one-game-21:8.1"]


# ===== The answer shape =====

def test_the_model_writes_its_reasoning_before_it_decides():
    """The model writes fields in schema order, so reasoning must come before refused and the answer."""
    field_names = list(RulesAnswer.model_json_schema()["properties"])
    assert field_names == ["reasoning", "refused", "answer", "citations"]


# ===== Extra rules under test =====

def test_no_extra_rules_leaves_the_standing_rules_unchanged():
    assert build_answer_rules([]) == ANSWER_RULES


def test_extra_rules_are_numbered_on_after_the_standing_rules():
    rules_text = build_answer_rules(["complete-answers"])
    assert rules_text.startswith(ANSWER_RULES)
    assert rules_text.endswith(f"\n11. {EXTRA_ANSWER_RULES['complete-answers']}")
    assert "\n10. " in ANSWER_RULES and "\n11. " not in ANSWER_RULES
