"""
Tests the section groups: under the word limit, every clause in exactly one group, no group across documents.
"""

import pytest

from evals.golden_answer_chunks import CHUNKS_FILE, load_chunks
from retrieval.section_groups import GROUP_WORD_LIMIT, build_section_groups


# ===== Build the groups once from the real chunks =====

@pytest.fixture(scope="module")
def chunks_and_groups():
    """The real clause chunks and the section groups built from them."""
    if not CHUNKS_FILE.exists():
        pytest.skip("data/rule_chunks.json is missing: run scripts.build_rule_chunks first")
    chunks = load_chunks()
    return chunks, build_section_groups(chunks)


# ===== Tests =====

def test_only_a_single_clause_may_pass_the_word_limit(chunks_and_groups):
    _, groups = chunks_and_groups
    too_long = []
    for group in groups:
        is_over_limit = len(group["text"].split()) > GROUP_WORD_LIMIT
        if is_over_limit and len(group["covers"]) > 1:
            too_long.append(group["id"])
    assert too_long == []


def test_every_clause_sits_in_exactly_one_group(chunks_and_groups):
    chunks, groups = chunks_and_groups
    covered_ids = []
    for group in groups:
        covered_ids.extend(group["covers"])
    assert sorted(covered_ids) == sorted(chunk["id"] for chunk in chunks)


def test_a_group_holds_one_document_and_one_format(chunks_and_groups):
    chunks, groups = chunks_and_groups
    source_by_id = {chunk["id"]: (chunk["document"], chunk["alternative_format"]) for chunk in chunks}
    mixed = []
    for group in groups:
        sources = {source_by_id[clause_id] for clause_id in group["covers"]}
        if len(sources) > 1:
            mixed.append(group["id"])
    assert mixed == []


def test_group_ids_are_unique(chunks_and_groups):
    _, groups = chunks_and_groups
    group_ids = [group["id"] for group in groups]
    assert len(group_ids) == len(set(group_ids))


def test_a_clause_stays_with_its_children(chunks_and_groups):
    """Law 9.1.6 (serve height) keeps its wheelchair and standing-class children in one group."""
    _, groups = chunks_and_groups
    groups_with_serve_height = [group for group in groups if "laws-9.1.6" in group["covers"]]
    assert groups_with_serve_height[0]["covers"] == ["laws-9.1.6", "laws-9.1.6.1", "laws-9.1.6.2"]
    assert groups_with_serve_height[0]["search_text"].startswith("Laws of Badminton · 9. SERVICE · Clause 9.1.6")
