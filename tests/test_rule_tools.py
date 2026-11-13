"""Tests the agent's two tools on the real clauses and rule map, with a stub search, so no test calls the API."""

import copy
import json

import pytest

from agent.rule_tools import (LARGEST_TOP_K, SEARCH_QUERY_DESCRIPTION_VERSION_2, TOOL_DEFINITIONS, RuleTools,
                              build_tool_definitions)
from evals.golden_answer_chunks import load_chunks
from retrieval.expand_with_rule_links import load_rule_map


# ===== The tools over the real clauses =====

CHUNKS = load_chunks()
CHUNK_BY_ID = {chunk["id"]: chunk for chunk in CHUNKS}
RULE_MAP = load_rule_map()


def first_chunks_search(query: str, top_k: int) -> list[dict]:
    """Stub: returns the first top_k clauses, whatever the query."""
    return CHUNKS[:top_k]


RULE_TOOLS = RuleTools(CHUNKS, first_chunks_search, RULE_MAP)


@pytest.fixture(autouse=True)
def new_question():
    """Each test is a new question: nothing shown yet."""
    RULE_TOOLS.start_question(set())


# ===== The tool definitions of each prompt version =====

def test_version_2_changes_only_the_query_description_and_leaves_version_1_untouched():
    expected_definitions = copy.deepcopy(TOOL_DEFINITIONS)
    expected_definitions[0]["function"]["parameters"]["properties"]["query"]["description"] = SEARCH_QUERY_DESCRIPTION_VERSION_2
    assert build_tool_definitions(2) == expected_definitions
    assert "in your own words" in json.dumps(build_tool_definitions(1)), "building version 2 must not change version 1"


# ===== search_rules =====

## Clauses with no list items, so a search for them shows exactly the hits in full
LEAF_IDS = ["laws-1.4", "laws-1.5", "laws-7.4"]


def leaf_search(query: str, top_k: int) -> list[dict]:
    """Stub: returns the first top_k of LEAF_IDS, whatever the query."""
    return [CHUNK_BY_ID[chunk_id] for chunk_id in LEAF_IDS[:top_k]]


def test_a_search_returns_top_k_source_blocks_with_their_labels():
    rule_tools = RuleTools(CHUNKS, leaf_search, RULE_MAP)
    result = rule_tools.search_rules("posts", 3)
    assert result.error is None
    assert [chunk["id"] for chunk in result.shown_chunks] == LEAF_IDS
    assert result.text.startswith("[laws-1.4] RULE · ")


def test_a_second_search_leaves_out_the_text_it_already_showed():
    rule_tools = RuleTools(CHUNKS, leaf_search, RULE_MAP)
    rule_tools.search_rules("posts", 2)
    result = rule_tools.search_rules("posts", 3)
    assert [chunk["id"] for chunk in result.shown_chunks] == ["laws-7.4"]
    assert "[laws-1.4] RULE · shown above" in result.text


def test_a_new_question_starts_from_its_own_starting_sources():
    rule_tools = RuleTools(CHUNKS, leaf_search, RULE_MAP)
    rule_tools.search_rules("posts", 2)
    rule_tools.start_question({"laws-1.5"})
    result = rule_tools.search_rules("posts", 2)
    assert [chunk["id"] for chunk in result.shown_chunks] == ["laws-1.4"]


def test_top_k_outside_1_to_100_or_not_a_whole_number_is_an_error_not_a_clamp():
    for bad_top_k in [0, LARGEST_TOP_K + 1, "5", 2.5, True]:
        result = RULE_TOOLS.search_rules("posts", bad_top_k)
        assert result.error is not None, bad_top_k
        assert result.shown_chunks == []
    assert RULE_TOOLS.search_rules("posts", LARGEST_TOP_K).error is None


# ===== read_clause =====

def test_reading_a_list_heading_brings_its_items():
    """Law 16.7.1 ends with "by:"; its three steps are the clauses under it (sweat-on-court's gap)."""
    result = RULE_TOOLS.read_clause("laws-16.7.1")
    shown_ids = [chunk["id"] for chunk in result.shown_chunks]
    assert shown_ids == ["laws-16.7.1", "laws-16.7.1.1", "laws-16.7.1.2", "laws-16.7.1.3"]


def test_reading_a_clause_previews_the_clauses_it_links_to():
    """ITTO 5.12.2 says "(Law 16.2)": the result previews laws-16.2 but doesn't show it in full."""
    result = RULE_TOOLS.read_clause("itto-5.12.2")
    assert "[laws-16.2] CITED · preview: " in result.text
    assert [chunk["id"] for chunk in result.shown_chunks] == ["itto-5.12.2"]


def test_reading_a_standard_law_previews_its_alternatives():
    """The best-of-five 8.1.3 names the Law it replaces; Law 8.1.3 never names it, so the link points back."""
    result = RULE_TOOLS.read_clause("laws-8.1.3")
    assert "[alt-best-of-5-games-11:8.1.3] ALTERNATIVE · " in result.text
    assert "[alt-best-of-3-games-21:8.1.3] ALTERNATIVE · " in result.text


def test_reading_a_clause_shows_it_in_full_even_when_shown_before():
    RULE_TOOLS.start_question({"laws-1.4"})
    result = RULE_TOOLS.read_clause("laws-1.4")
    assert [chunk["id"] for chunk in result.shown_chunks] == ["laws-1.4"]


def test_an_unknown_id_is_an_error_that_suggests_close_ids():
    result = RULE_TOOLS.read_clause("laws-16.71")
    assert result.error is not None
    assert "laws-16.7.1" in result.error
    assert result.shown_chunks == []


# ===== run_tool_call =====

def test_arguments_arrive_as_json_text_or_as_a_dict():
    from_text = RULE_TOOLS.run_tool_call("read_clause", '{"chunk_id": "laws-1.4"}')
    from_dict = RULE_TOOLS.run_tool_call("read_clause", {"chunk_id": "laws-1.4"})
    assert from_text.text == from_dict.text
    assert from_text.error is None


def test_bad_calls_return_an_error_the_model_can_read():
    bad_calls = [
        ("read_clause", "{not json"),
        ("read_clause", "{}"),
        ("search_rules", '{"query": "posts"}'),
        ("look_up", '{"chunk_id": "laws-1.4"}'),
    ]
    for tool_name, arguments in bad_calls:
        result = RULE_TOOLS.run_tool_call(tool_name, arguments)
        assert result.error is not None, (tool_name, arguments)
        assert result.text.startswith("Error: ")
