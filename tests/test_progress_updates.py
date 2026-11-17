"""Tests the progress lines the flow builds, for every form a tool call's arguments arrive in."""

from answer_flows.shared.answer_shape import Citation
from answer_flows.shared.progress_updates import (READING, SEARCHING, describe_checking, describe_found_rules,
                                                  describe_sources_picked, describe_tool_call)
from evals.golden_answer_chunks import load_chunks


# Constants
## The real clauses, so the names are the ones the app will show
CHUNK_BY_ID = {chunk["id"]: chunk for chunk in load_chunks()}
LAW_1_4_NAME = "Laws of Badminton 5.0 (2), Clause 1.4"


# ===== Tool calls =====

def test_a_search_shows_its_words_whether_arguments_come_as_text_or_a_dict():
    for arguments in ['{"query": "post height", "top_k": 5}', {"query": "post height", "top_k": 5}]:
        update = describe_tool_call("search_rules", arguments, CHUNK_BY_ID)
        assert update.step == SEARCHING
        assert update.message == 'Searching the rules: "post height"'


def test_a_read_shows_the_clause_name():
    update = describe_tool_call("read_clause", '{"chunk_id": "laws-1.4"}', CHUNK_BY_ID)
    assert update.step == READING
    assert update.message == f"Reading {LAW_1_4_NAME}"
    assert update.source_names == [LAW_1_4_NAME]


def test_broken_arguments_still_get_a_plain_line():
    """The tool records the error for the run file; the app only needs a line that doesn't break."""
    assert describe_tool_call("search_rules", '{"query": cut off', CHUNK_BY_ID).message == "Searching the rules"
    assert describe_tool_call("read_clause", '{"chunk_id": "laws-99.9"}', CHUNK_BY_ID).message == "Reading a clause"


# ===== The other steps =====

def test_the_first_check_and_later_checks_read_differently():
    assert describe_checking(0).message == "Checking which rules answer your question"
    assert describe_checking(2).message == "Checking what the search found"


def test_found_rules_counts_and_names_them():
    update = describe_found_rules([CHUNK_BY_ID["laws-1.4"], CHUNK_BY_ID["laws-1.1"]])
    assert update.message == "Found 2 rules to check"
    assert update.source_names[0] == LAW_1_4_NAME


def test_one_picked_sentence_reads_as_singular():
    source = Citation(chunk_id="laws-1.4", quote="The posts shall be 1.55 m in height.", source_name=LAW_1_4_NAME)
    assert describe_sources_picked([source]).message == "Found 1 sentence that answers it"
    assert describe_sources_picked([source, source]).message == "Found 2 sentences that answer it"
