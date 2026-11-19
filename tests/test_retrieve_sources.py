"""
Tests the retrieve step: the search hits in full, and the clauses the rule map brings for them.
"""

import pytest

from retrieval.build_bundle import full_chunks
from retrieval.expand_with_rule_links import load_rule_map
from retrieval.load_rule_chunks import load_chunks
from retrieval.retrieve_sources import build_clause_vector_search, build_retrieve_function
from tests.sample_data import SAMPLE_CHUNKS, full_items

CHUNK_BY_ID = {chunk["id"]: chunk for chunk in SAMPLE_CHUNKS}


# ===== The retrieve step =====

def test_retrieve_brings_the_items_of_an_item_that_is_a_heading():
    """Every-let-situation got 14.2.3 ("the shuttle is:") without its two cases."""
    try:
        chunk_by_id = {chunk["id"]: chunk for chunk in load_chunks()}
        retrieve = build_retrieve_function(lambda question_text, top_k: [chunk_by_id["laws-14.2"]], 1, chunk_by_id,
                                           load_rule_map())
    except FileNotFoundError:
        pytest.skip("data/ is missing: run scripts.build_rule_chunks and scripts.build_rule_links first")
    retrieved_ids = [chunk["id"] for chunk in full_chunks(retrieve("When is it a let?"))]
    assert {"laws-14.2.3.1", "laws-14.2.3.2"}.issubset(retrieved_ids)


def test_with_no_links_retrieve_hands_on_the_search_hits_in_full():
    empty_rule_map = {"outgoing": {}, "incoming": {}}
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
    """Wheelchair-shuttle-on-net got the heading "in Wheelchair Badminton if the shuttle is:" but not its items."""
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
