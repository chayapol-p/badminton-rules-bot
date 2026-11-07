"""
Tests that every refusal probe has the shape the answer run reads, and stays apart from the golden set.
"""

import json

from evals.golden_answer_chunks import QUESTIONS_FILE
from evals.refusal_probes import load_refusal_probes


# ===== Tests =====

def test_every_probe_has_no_answer_a_reason_and_a_pass_rule():
    for probe in load_refusal_probes():
        assert probe["answer"] is None
        assert probe["answer_locations"] == []
        assert probe["why_unanswerable"]
        assert probe["pass_rule"]
        assert probe["split"] == "probe"


def test_probe_ids_are_unique_and_not_golden_ids():
    probe_ids = [probe["id"] for probe in load_refusal_probes()]
    golden_ids = {question["id"] for question in json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]}
    assert len(probe_ids) == len(set(probe_ids))
    assert golden_ids.isdisjoint(probe_ids)
