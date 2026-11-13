"""
Tests the bundle: one source block format for setup A and both tools, role labels on every block, and
previews and "shown above" lines in place of text the model doesn't need again.
"""

import json

import pytest

from evals.golden_answer_chunks import CHUNKS_FILE, load_chunks
from retrieval.build_bundle import (FULL, PREVIEW, SHOWN, build_bundle, describe_source, format_bundle,
                                    format_preview, format_source, full_chunks, parent_headings)
from retrieval.expand_with_rule_links import load_rule_map
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


# ===== The sample stays a true copy of the real data =====

def test_alternative_laws_sample_matches_the_real_file():
    if not CHUNKS_FILE.exists():
        pytest.skip("data/rule_chunks.json is missing: run scripts.build_rule_chunks first")
    real_chunks_by_id = {chunk["id"]: chunk for chunk in json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))}
    assert ONE_GAME_CHANGE_OF_ENDS_CHUNK == real_chunks_by_id["alt-one-game-21:8.1"]


# ===== The heading above a clause =====

def test_only_parents_that_name_a_subject_are_shown():
    """A full parent rule gets quoted as if it were the clause, so only headings are shown."""
    chunk = {"text": "shall not exceed 280 mm.",
             "search_text_with_parents": "Laws · 4. RACKET · Clause 4.2.2\n4.1 The racket shall be a frame not exceeding 680 mm · 4.2 The stringed area:\nshall not exceed 280 mm."}
    assert parent_headings(chunk) == "4.2 The stringed area:"


# ===== The bundle over the real clauses =====

@pytest.fixture(scope="module")
def corpus():
    if not CHUNKS_FILE.exists():
        pytest.skip("data/rule_chunks.json is missing: run scripts.build_rule_chunks first")
    return {"chunks_by_id": {chunk["id"]: chunk for chunk in load_chunks()}, "rule_map": load_rule_map()}


def detail_by_id(items):
    """The level of detail each clause got, by chunk id."""
    return {item["chunk"]["id"]: item["detail"] for item in items}


def test_setup_a_gets_every_clause_in_full_with_its_label(corpus):
    """13 Nov: the labels were made but dropped before the prompt, so the model never saw which rule was the default."""
    items = build_bundle(["alt-best-of-5-games-11:8.1.3"], corpus["chunks_by_id"], corpus["rule_map"], related_in_full=True)
    assert set(detail_by_id(items).values()) == {FULL}
    assert "[laws-8.1.3] DEFAULT · Laws of Badminton" in format_bundle(items)


def test_a_tool_shows_the_hit_in_full_and_its_links_as_previews(corpus):
    """Law 8.1.3 has alternatives in two formats: the tool previews them, and the model reads the one it needs."""
    items = build_bundle(["laws-8.1.3"], corpus["chunks_by_id"], corpus["rule_map"], related_in_full=False)
    details = detail_by_id(items)
    assert details["laws-8.1.3"] == FULL
    assert details["alt-best-of-5-games-11:8.1.3"] == PREVIEW
    assert "[alt-best-of-5-games-11:8.1.3] ALTERNATIVE · " in format_bundle(items)


def test_a_tool_shows_every_level_of_the_hits_own_list_in_full(corpus):
    """Law 16.7.1 ends with "by:": its three steps are part of the clause, not links to preview."""
    items = build_bundle(["laws-16.7.1"], corpus["chunks_by_id"], corpus["rule_map"], related_in_full=False)
    assert [chunk["id"] for chunk in full_chunks(items)] == ["laws-16.7.1", "laws-16.7.1.1", "laws-16.7.1.2",
                                                            "laws-16.7.1.3"]


def test_a_cited_heading_brings_its_items_as_previews_in_a_tool(corpus):
    """ITTO 5.9.1.6 cites Law 16.7.1: the citation and its steps are previews, so the result stays short."""
    items = build_bundle(["itto-5.9.1.6"], corpus["chunks_by_id"], corpus["rule_map"], related_in_full=False)
    details = detail_by_id(items)
    assert details["itto-5.9.1.6"] == FULL
    assert details["laws-16.7.1.1"] == PREVIEW


def test_a_clause_shown_before_is_one_line_and_not_citable_again(corpus):
    items = build_bundle(["laws-8.1.3"], corpus["chunks_by_id"], corpus["rule_map"], related_in_full=False,
                         shown_ids={"laws-8.1.3"})
    assert detail_by_id(items)["laws-8.1.3"] == SHOWN
    assert "[laws-8.1.3] DEFAULT · shown above" in format_bundle(items)
    assert "laws-8.1.3" not in [chunk["id"] for chunk in full_chunks(items)]


def test_a_source_block_shows_the_heading_above_a_fragment_clause(corpus):
    """8 Nov: clause 4.2.2 reads "shall not exceed 280 mm…"; its subject is in 4.2 ("The stringed area:")."""
    assert "Under: 4.2 The stringed area:" in format_source(corpus["chunks_by_id"]["laws-4.2.2"])


def test_a_preview_holds_the_opening_words_only():
    chunk = {"id": "laws-x", "text": " ".join(f"word{i}" for i in range(1, 21))}
    preview = format_preview(chunk, "CITED")
    assert preview == "[laws-x] CITED · preview: word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 " \
                      "word12 word13 word14 word15 …"
