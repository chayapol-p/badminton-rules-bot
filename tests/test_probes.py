"""
Tests that every probe has the shape the answer run reads, points at real clauses, and stays apart from the golden set.
"""

import json

import pytest

from evals.golden_answer_chunks import QUESTIONS_FILE, expected_chunk_ids
from evals.probes import load_false_premise_probes, load_probes, load_refusal_probes
from retrieval.load_rule_chunks import load_chunks


# ===== Refusal probes =====

def test_every_refusal_probe_has_no_answer_a_reason_and_a_pass_rule():
    for probe in load_refusal_probes():
        assert probe["category"] == "refusal_probe"
        assert probe["answer"] is None
        assert probe["answer_locations"] == []
        assert probe["why_unanswerable"]
        assert probe["pass_rule"]
        assert probe["split"] == "probe"


# ===== False-premise probes =====

def test_every_false_premise_probe_has_an_answer_its_clauses_and_a_pass_rule():
    for probe in load_false_premise_probes():
        assert probe["category"] == "false_premise"
        assert probe["answer"]
        assert probe["answer_locations"]
        assert probe["pass_rule"]
        assert probe["split"] == "probe"


def test_every_false_premise_answer_location_is_a_real_clause():
    try:
        chunks = load_chunks()
    except FileNotFoundError:
        pytest.skip("data/rule_chunks.json is missing: run scripts.build_rule_chunks first")
    for probe in load_false_premise_probes():
        for location in probe["answer_locations"]:
            assert expected_chunk_ids(location, chunks), (probe["id"], location)


# ===== Apart from the golden set =====

def test_probe_ids_are_unique_and_not_golden_ids():
    probe_ids = [probe["id"] for probe in load_probes()]
    golden_ids = {question["id"] for question in json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]}
    assert len(probe_ids) == len(set(probe_ids))
    assert golden_ids.isdisjoint(probe_ids)
