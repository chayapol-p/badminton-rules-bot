"""
Tests for the rule map (scripts/build_rule_links.py) and for following it (retrieval/expand_with_rule_links.py).

They read data/rule_chunks.json, which is never committed, so they are skipped when
the chunks have not been built yet. They make no API calls.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from retrieval.expand_with_rule_links import expand_with_links, index_links
from scripts.build_rule_links import build_rule_links


# Constants
## Path to each resource
CHUNKS_FILE = Path(__file__).resolve().parent.parent / "data" / "rule_chunks.json"

## Dates on both sides of the Alternative Laws' in-force date (4 January 2027)
BEFORE_ALTERNATIVES = date(2026, 11, 3)
AFTER_ALTERNATIVES = date(2027, 2, 1)


# ===== Build the map once for every test =====

@pytest.fixture(scope="module")
def corpus():
    if not CHUNKS_FILE.exists():
        pytest.skip("data/rule_chunks.json is missing: run scripts.build_rule_chunks first")
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    rule_map = build_rule_links(chunks)
    link_keys = {(link["from_id"], link["to_id"], link["relation"]) for link in rule_map["links"]}
    return {
        "chunks_by_id": {chunk["id"]: chunk for chunk in chunks},
        "rule_map": rule_map,
        "link_keys": link_keys,
        "indexed_map": index_links(rule_map["links"], rule_map["outside_corpus"]),
    }


# ===== Every level of a list =====

def context_ids(hit_ids, corpus, question_is_para=False):
    """The ids expand_with_links returns for these hits, without the clauses around each hit."""
    context = expand_with_links(hit_ids, corpus["chunks_by_id"], corpus["indexed_map"], question_is_para=question_is_para,
                                include_nearby=False)
    return [item["chunk"]["id"] for item in context]


def test_an_item_that_is_a_heading_brings_its_own_items(corpus):
    """11 Nov: 14.2 ("It shall be a let, if:") brought 14.2.3 ("the shuttle is:") but not its two cases."""
    assert {"laws-14.2.3", "laws-14.2.3.1", "laws-14.2.3.2"}.issubset(context_ids(["laws-14.2"], corpus))


def test_a_cited_heading_brings_every_level_of_its_items(corpus):
    """11 Nov: sweat-on-court got Law 16.7.1 ("... by:") through a citation, without its three steps."""
    assert {"laws-16.7.1.1", "laws-16.7.1.2", "laws-16.7.1.3"}.issubset(context_ids(["itto-5.9.1.6"], corpus))


def test_an_alternative_laws_heading_brings_its_items(corpus):
    """13 Nov: items were found by an "alt-16.2." prefix, but the ids hold the format ("alt-best-of-3-games-21:16.2.1")."""
    assert "alt-best-of-3-games-21:16.2.1" in context_ids(["alt-best-of-3-games-21:16.2"], corpus)


def test_a_regular_rule_shown_as_context_stays_one_line(corpus):
    """13 Nov: the wheelchair rule 13.3.10 pulled in Law 13.3 as context, and with it nine regular faults."""
    found_ids = context_ids(["laws-13.3.10"], corpus)
    assert "laws-13.3" in found_ids
    assert "laws-13.3.1" not in found_ids
    assert "laws-13.3.10.1" in found_ids, "the para rule search found still brings its own items"


def test_a_found_heading_keeps_its_para_items_and_a_cited_one_drops_them(corpus):
    """Law 13.3's item 13.3.10 is Wheelchair Badminton only: it comes when search found 13.3 itself."""
    assert "laws-13.3.10" in context_ids(["laws-13.3"], corpus)


def labels_by_id(context):
    """The label each clause got, keyed by chunk id."""
    return {item["chunk"]["id"]: item["label"] for item in context}


# ===== The map finds each kind of link =====

def test_alternative_service_law_overrides_law_9_1_6(corpus):
    assert ("alt-alternative-service:9.1.6", "laws-9.1.6", "overrides") in corpus["link_keys"]


def test_the_service_judges_law_links_to_their_itto_instructions(corpus):
    """8 Nov: service-fault-officials never got ITTO 7.2, the "call 'Fault' loudly" clause."""
    assert ("laws-17.3", "itto-7.2", "instructions_for") in corpus["link_keys"]


def test_override_falls_back_to_parent_when_law_has_no_such_clause(corpus):
    # The Laws have no 8.1.5, so the fifth-game rule overrides Law 8.1 (change of ends)
    assert ("alt-best-of-5-games-11:8.1.5", "laws-8.1", "overrides") in corpus["link_keys"]


def test_itto_reference_links_to_both_cited_laws(corpus):
    assert ("itto-5.15.1", "laws-16.6.4", "cites") in corpus["link_keys"]
    assert ("itto-5.15.1", "laws-16.7", "cites") in corpus["link_keys"]


def test_range_reference_includes_same_depth_clauses_only(corpus):
    # "Law 9.1.2 to Law 9.1.8" covers 9.1.5, but not the Wheelchair sub-clause 9.1.6.1
    cited_by_itto_7_2 = {to_id for from_id, to_id, relation in corpus["link_keys"] if from_id == "itto-7.2"}
    assert "laws-9.1.5" in cited_by_itto_7_2
    assert "laws-9.1.6.1" not in cited_by_itto_7_2


def test_wheelchair_net_rule_is_an_exception_of_the_let_rule(corpus):
    assert ("laws-14.2.3.1.1", "laws-14.2.3.1", "para_exception_of") in corpus["link_keys"]


def test_court_clause_shows_diagram_a(corpus):
    assert ("laws-1.1", "laws-Diagram A", "shows_diagram") in corpus["link_keys"]


def test_vocabulary_section_is_listed_as_outside_the_corpus(corpus):
    sections = {reference["section"] for reference in corpus["rule_map"]["outside_corpus"]}
    assert "BWF Statutes Section 4.1.5" in sections


# ===== Following the map labels and orders the clauses =====

def test_default_law_brings_its_alternative_before_the_date(corpus):
    context = expand_with_links(["laws-9.1.6"], corpus["chunks_by_id"], corpus["indexed_map"], today=BEFORE_ALTERNATIVES)
    labels = labels_by_id(context)

    assert context[0]["chunk"]["id"] == "laws-9.1.6"
    assert labels["laws-9.1.6"] == "DEFAULT"
    assert "not in force until 2027-01-04" in labels["alt-alternative-service:9.1.6"]


def test_alternative_label_changes_after_the_in_force_date(corpus):
    context = expand_with_links(["laws-9.1.6"], corpus["chunks_by_id"], corpus["indexed_map"], today=AFTER_ALTERNATIVES)
    assert "in force from 2027-01-04" in labels_by_id(context)["alt-alternative-service:9.1.6"]


def test_alternative_hit_puts_its_default_law_first(corpus):
    context = expand_with_links(["alt-alternative-service:9.1.6"], corpus["chunks_by_id"], corpus["indexed_map"])
    assert [item["chunk"]["id"] for item in context][:2] == ["laws-9.1.6", "alt-alternative-service:9.1.6"]


def test_one_hit_brings_every_alternative_of_its_law(corpus):
    # Law 8.1 has alternatives in two scoring options
    context = expand_with_links(["laws-8.1"], corpus["chunks_by_id"], corpus["indexed_map"])
    reached_ids = {item["chunk"]["id"] for item in context}
    assert {"alt-one-game-21:8.1", "alt-best-of-5-games-11:8.1.5"} <= reached_ids


def test_para_exceptions_appear_only_for_para_questions(corpus):
    regular = expand_with_links(["laws-9.1.6"], corpus["chunks_by_id"], corpus["indexed_map"], question_is_para=False)
    para = expand_with_links(["laws-9.1.6"], corpus["chunks_by_id"], corpus["indexed_map"], question_is_para=True)

    assert "laws-9.1.6.1" not in labels_by_id(regular)
    assert labels_by_id(para)["laws-9.1.6.1"] == "PARA EXCEPTION"


def test_cited_list_heading_brings_its_sub_clauses(corpus):
    # ITTO 5.15.1 (phone rings) cites Law 16.7, a heading; the warning-and-fault rule is 16.7.1
    context = expand_with_links(["itto-5.15.1"], corpus["chunks_by_id"], corpus["indexed_map"])
    labels = labels_by_id(context)
    assert labels["laws-16.7"] == "CITED"
    assert labels["laws-16.7.1"] == "LIST ITEM"


def test_list_item_brings_its_intro_and_the_other_items(corpus):
    # "When is a shuttle not in play?" needs all of 15.1, 15.2 and 15.3
    context = expand_with_links(["laws-15.2"], corpus["chunks_by_id"], corpus["indexed_map"])
    labels = labels_by_id(context)

    assert labels["laws-15"] == "LIST INTRO"
    assert labels["laws-15.1"] == labels["laws-15.3"] == "SAME LIST"


def test_clause_brings_the_clause_after_it(corpus):
    # 20-all (7.4) runs on into 29-all (7.5)
    context = expand_with_links(["laws-7.4"], corpus["chunks_by_id"], corpus["indexed_map"])
    assert labels_by_id(context)["laws-7.5"] == "NEIGHBOUR"


def test_long_list_keeps_the_items_closest_to_the_hit(corpus):
    # ITTO 5.4 (the umpire's duties) has more items than MAX_LIST_ITEMS; 5.4.12 sits next to 5.4.13
    context = expand_with_links(["itto-5.4.13"], corpus["chunks_by_id"], corpus["indexed_map"])
    reached_ids = labels_by_id(context)

    assert "itto-5.4.12" in reached_ids
    assert "itto-5.4.1" not in reached_ids


def test_nearby_clauses_skip_para_items_for_regular_questions(corpus):
    # 13.3.10 (Wheelchair net faults) is an item of the same fault list as 13.3.9
    regular = expand_with_links(["laws-13.3.9"], corpus["chunks_by_id"], corpus["indexed_map"], question_is_para=False)
    para = expand_with_links(["laws-13.3.9"], corpus["chunks_by_id"], corpus["indexed_map"], question_is_para=True)

    assert "laws-13.3.10" not in labels_by_id(regular)
    assert labels_by_id(para)["laws-13.3.10"] == "SAME LIST"


def test_a_cited_laws_alternative_stays_one_line(corpus):
    """13 Nov: ITTO 5.17.3 cites Law 16.2, whose alternatives brought other formats' interval rules to card questions."""
    found_ids = context_ids(["itto-5.17.3"], corpus)
    assert "alt-best-of-3-games-21:16.2" in found_ids
    assert "alt-best-of-3-games-21:16.2.1" not in found_ids
