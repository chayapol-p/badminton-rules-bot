"""Tests the progress lines the flow builds, for every form a tool call's arguments arrive in, and the "still writing"
updates sent while a long call runs."""

import time

import pytest

from answer_flows.shared.answer_shape import Citation
from answer_flows.shared.progress_updates import (READING, SEARCHING, STILL_WRITING, ProgressUpdate,
                                                  call_with_still_writing_updates, describe_checking,
                                                  describe_found_rules, describe_question_parts,
                                                  describe_sources_picked, describe_tool_call)
from retrieval.load_rule_chunks import load_chunks


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



def test_the_question_parts_read_as_one_line():
    assert describe_question_parts(["the net height in the middle"]).message == (
        "Your question asks about the net height in the middle")
    assert describe_question_parts(["the net height in the middle", "the net height at the sides"]).message == (
        "Your question has 2 parts: the net height in the middle · the net height at the sides")


# ===== Updates while a long call runs =====

## Short waits, so the tests run in a fraction of a second
SECONDS_BETWEEN_TEST_UPDATES = 0.05


def test_a_slow_call_sends_still_writing_updates_and_returns_its_result():
    updates: list[ProgressUpdate] = []

    def slow_call() -> str:
        """Stub: takes about four update waits, then returns a fixed result."""
        time.sleep(SECONDS_BETWEEN_TEST_UPDATES * 4.5)
        return "the reply"

    result = call_with_still_writing_updates(slow_call, updates.append, SECONDS_BETWEEN_TEST_UPDATES)
    assert result == "the reply"
    assert len(updates) >= 2
    assert all(update.step == STILL_WRITING for update in updates)
    assert updates[0].message.startswith("Still writing the answer · ")


def test_a_fast_call_sends_no_update_and_none_come_after_it_ends():
    updates: list[ProgressUpdate] = []
    call_with_still_writing_updates(lambda: "the reply", updates.append, SECONDS_BETWEEN_TEST_UPDATES)
    time.sleep(SECONDS_BETWEEN_TEST_UPDATES * 3)
    assert updates == []


def test_a_call_that_raises_stops_the_updates_and_passes_the_error_on():
    updates: list[ProgressUpdate] = []

    def failing_call() -> str:
        """Stub: waits two update waits, then fails as a server error would."""
        time.sleep(SECONDS_BETWEEN_TEST_UPDATES * 2.5)
        raise RuntimeError("server error")

    with pytest.raises(RuntimeError, match="server error"):
        call_with_still_writing_updates(failing_call, updates.append, SECONDS_BETWEEN_TEST_UPDATES)
    count_when_it_failed = len(updates)
    time.sleep(SECONDS_BETWEEN_TEST_UPDATES * 3)
    assert len(updates) == count_when_it_failed
