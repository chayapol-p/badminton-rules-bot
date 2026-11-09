"""Tests the agent's two tools on the real clauses and rule map, with a stub search, so no test calls the API."""

from agent.rule_tools import LARGEST_TOP_K, RuleTools
from evals.golden_answer_chunks import load_chunks
from retrieval.expand_with_rule_links import load_rule_map


# ===== The tools over the real clauses =====

CHUNKS = load_chunks()


def first_chunks_search(query: str, top_k: int) -> list[dict]:
    """Stub: returns the first top_k clauses, whatever the query."""
    return CHUNKS[:top_k]


RULE_TOOLS = RuleTools(CHUNKS, first_chunks_search, load_rule_map())


# ===== search_rules =====

def test_a_search_returns_top_k_source_blocks():
    result = RULE_TOOLS.search_rules("posts", 3)
    assert result.error is None
    assert len(result.shown_chunks) == 3
    assert result.text.startswith(f"[{CHUNKS[0]['id']}]")


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


def test_reading_a_clause_lists_the_ids_it_links_to_without_their_text():
    """ITTO 5.12.2 says "(Law 16.2)": the result names laws-16.2 but doesn't show it."""
    result = RULE_TOOLS.read_clause("itto-5.12.2")
    assert "cites: laws-16.2" in result.text
    assert [chunk["id"] for chunk in result.shown_chunks] == ["itto-5.12.2"]


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
