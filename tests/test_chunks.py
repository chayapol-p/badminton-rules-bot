"""
Tests the ingest output, data/rule_chunks.json: is every clause its own chunk, with the right tags?

What it checks, in groups:
1. Every chunk has the full set of fields, a unique id in the agreed format, and real text.
2. The chunk counts per document match the last checked ingest (update them only on purpose).
3. Clause numbers: the Laws' hidden two-level numbers run without gaps, known clauses hold
   their known text, and no clause number is left buried inside another chunk's text.
4. Tags: version and in-force date per document, the Alternative Laws option, the Law heading,
   and the para-only flag.
5. Coverage: every golden answer location has a chunk with that clause, and the source PDFs
   still match their frozen hashes.

A known ingest bug gets a test marked xfail(strict=True): pytest flags it the day the bug
is fixed, and the marker comes off. None are open now.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

from scripts.ingest_rules import DOCUMENTS


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
CHUNKS_FILE = PROJECT_FOLDER / "data" / "rule_chunks.json"
QUESTIONS_FILE = PROJECT_FOLDER / "evals" / "golden_questions.json"
PDF_FOLDER = PROJECT_FOLDER / "data" / "bwf"

## Expected shape of the ingest, checked by hand against the PDFs on 2-3 Nov (ITTO recount 7 Nov)
EXPECTED_CHUNKS_PER_DOCUMENT = {"laws": 225, "itto": 499, "alt": 30}
EXPECTED_PARA_ONLY_COUNT = 22
LAWS_SUB_CLAUSE_COUNTS = {1: 11, 2: 4, 3: 2, 4: 3, 5: 2, 6: 2, 7: 6, 8: 2, 9: 5, 10: 3,
                          11: 6, 12: 2, 13: 5, 14: 3, 15: 3, 16: 7, 17: 6}
ALTERNATIVE_OPTIONS = {"one-game-21", "best-of-3-games-21", "best-of-5-games-11", "alternative-service"}
REQUIRED_FIELDS = {"id", "document", "document_title", "version", "in_force", "clause",
                   "variant", "heading", "para_only", "page", "text"}

## Known clauses and a phrase each must hold, one per kind of ingest risk
KNOWN_CLAUSE_TEXT = {
    "laws-1.4": "1.55 metres",                        # a hidden two-level number, rebuilt
    "laws-7.6": "serve first in the next game",       # the last clause before a new Law
    "laws-14.2.3.1.1": "except in Wheelchair Badminton",  # a five-level number on its text's line
    "alt-best-of-5-games-11:8.1.5": "6 points",       # a clause number repeated per option
    "laws-Diagram A": "Diagonal length of full court",  # a diagram caption as its own chunk
}

## Para flag: clauses printed in italics in the Laws, and regular clauses right next to them
KNOWN_PARA_ONLY = ["laws-9.1.6.1", "laws-9.1.6.2", "laws-13.4.6.2", "laws-16.5.3",
                   "laws-14.2.3.1.1"]  # 14.2.3.1.1 ends with a plain "or", which once switched the flag off
KNOWN_REGULAR = ["laws-9.1.6", "laws-14.2.3.1", "laws-16.5.2"]

## A clause number that starts a new clause in the middle of another chunk's text: a final dot
## then a capital or a quote ("fines. 3.5.15.4. The Referee"), or a wide gap after the number
BURIED_CLAUSE_NUMBER = re.compile(r"(?<![\d.])(\d+(?:\.\d+){1,4})(?:\.\s+[A-Z“\"]|\.?\s{2,}\S)")
## Text just before a number that makes it a reference ("Laws 2.2.2, 2.2.3 and"), not a clause start
REFERENCE_BEFORE = re.compile(r"\b(?:Laws?|Instructions?|Sections?|Regulations?|Clauses?)\s+(?:\d+(?:\.\d+)*\s*(?:,|and|or|to|-|–)\s*)*$")
CLAUSE_NUMBER = re.compile(r"^\d+(?:\.\d+)*$")


# ===== Load the data once =====

CHUNKS = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
CHUNKS_BY_ID = {chunk["id"]: chunk for chunk in CHUNKS}
GOLDEN_SET = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
DOCUMENT_INFO = {document["document"]: document for document in DOCUMENTS}


# ===== Helpers that name each check =====

def expected_chunk_id(chunk):
    """The id a chunk should have: document, then option (if any), then clause."""
    if chunk["variant"]:
        return f"{chunk['document']}-{chunk['variant']}:{chunk['clause']}"
    return f"{chunk['document']}-{chunk['clause']}"


def has_valid_page(chunk):
    """True when the page is a whole number above zero."""
    return isinstance(chunk["page"], int) and chunk["page"] > 0


def has_numbered_clause(chunk):
    """True for a clause such as 9.1.6; false for intros, headings like Introduction, and diagrams."""
    return CLAUSE_NUMBER.match(chunk["clause"]) is not None


def heading_matches_clause_number(chunk):
    """True when the heading starts with the clause's Law number: clause 9.1.6 sits under "9. ..."."""
    law_number = chunk["clause"].split(".")[0]
    heading = chunk["heading"] or ""
    return heading.startswith(law_number + ".")


def is_heading_or_diagram(chunk):
    """True for a Law heading chunk (clause "9") or a diagram chunk (clause "Diagram A")."""
    is_heading = re.match(r"^\d+$", chunk["clause"]) is not None
    is_diagram = chunk["clause"].startswith("Diagram")
    return is_heading or is_diagram


def contains_option_marker(text):
    """True when the text holds a line that opens an Alternative Laws option."""
    markers = ["In case of 1 above", "In case of 2 above", "In the case of 3 above", "ALTERNATIVE SERVICE LAWS"]
    return any(marker in text for marker in markers)


def every_golden_location():
    """Yields (question id, location) for every answer location in the golden set."""
    for question in GOLDEN_SET["questions"]:
        for location in question["answer_locations"]:
            yield question["id"], location


# ===== 1. Every chunk is well formed =====

def test_every_chunk_has_every_field():
    incomplete = [chunk.get("id") for chunk in CHUNKS if set(chunk) != REQUIRED_FIELDS]
    assert incomplete == []

def test_chunk_ids_are_unique():
    assert len(CHUNKS_BY_ID) == len(CHUNKS)

def test_chunk_id_is_document_option_and_clause():
    wrong_ids = [chunk["id"] for chunk in CHUNKS if chunk["id"] != expected_chunk_id(chunk)]
    assert wrong_ids == []

def test_every_chunk_has_text_and_a_page():
    assert [chunk["id"] for chunk in CHUNKS if not chunk["text"].strip()] == []
    assert [chunk["id"] for chunk in CHUNKS if not has_valid_page(chunk)] == []

def test_no_page_footer_left_in_text():
    assert [chunk["id"] for chunk in CHUNKS if re.search(r"Page \d+ of \d+", chunk["text"])] == []


# ===== 2. Counts match the last checked ingest =====

def test_chunk_count_per_document():
    counts = {document: 0 for document in EXPECTED_CHUNKS_PER_DOCUMENT}
    for chunk in CHUNKS:
        counts[chunk["document"]] += 1
    assert counts == EXPECTED_CHUNKS_PER_DOCUMENT


# ===== 3. Clause numbers =====

def test_laws_hidden_two_level_numbers_run_without_gaps():
    for law_number, sub_clause_count in LAWS_SUB_CLAUSE_COUNTS.items():
        for sub_number in range(1, sub_clause_count + 1):
            assert f"laws-{law_number}.{sub_number}" in CHUNKS_BY_ID, f"Law {law_number}.{sub_number} is missing"

@pytest.mark.parametrize("chunk_id, phrase", KNOWN_CLAUSE_TEXT.items())
def test_known_clause_holds_its_text(chunk_id, phrase):
    assert phrase in CHUNKS_BY_ID[chunk_id]["text"]

def test_no_chunk_text_starts_with_a_clause_number():
    assert [chunk["id"] for chunk in CHUNKS if re.match(r"^\d+(?:\.\d+)+\.?\s", chunk["text"])] == []

def test_no_clause_number_buried_inside_another_chunk():
    buried = []
    for chunk in CHUNKS:
        for match in BURIED_CLAUSE_NUMBER.finditer(chunk["text"]):
            text_before_number = chunk["text"][:match.start()]
            is_reference = REFERENCE_BEFORE.search(text_before_number) is not None
            if not is_reference:
                buried.append((chunk["id"], match.group(1)))
    assert buried == []


# ===== 4. Tags =====

def test_version_and_in_force_date_match_the_document():
    wrong = []
    for chunk in CHUNKS:
        document_info = DOCUMENT_INFO[chunk["document"]]
        if chunk["version"] != document_info["version"] or chunk["in_force"] != document_info["in_force"]:
            wrong.append(chunk["id"])
    assert wrong == []

def test_only_alternative_laws_chunks_carry_an_option():
    other_chunks = [chunk for chunk in CHUNKS if chunk["document"] != "alt"]
    assert [chunk["id"] for chunk in other_chunks if chunk["variant"] is not None] == []

    option_chunks = [chunk for chunk in CHUNKS if chunk["document"] == "alt" and chunk["clause"] != "Introduction"]
    assert {chunk["variant"] for chunk in option_chunks} == ALTERNATIVE_OPTIONS

def test_option_markers_stay_in_their_intro_chunk():
    non_intro_chunks = [chunk for chunk in CHUNKS if chunk["clause"] != "intro"]
    leaked = [chunk["id"] for chunk in non_intro_chunks if contains_option_marker(chunk["text"])]
    assert leaked == []

def test_laws_and_itto_heading_matches_the_clause_number():
    numbered = [chunk for chunk in CHUNKS if chunk["document"] in ("laws", "itto") and has_numbered_clause(chunk)]
    mismatched = [chunk["id"] for chunk in numbered if not heading_matches_clause_number(chunk)]
    assert mismatched == []

def test_alternative_laws_heading_belongs_to_its_own_option():
    alternative_chunks = [chunk for chunk in CHUNKS if chunk["document"] == "alt"]

    # An option's intro chunk carries no heading; a numbered clause carries its Law's heading
    intro_with_heading = [chunk["id"] for chunk in alternative_chunks if chunk["clause"] == "intro" and chunk["heading"] is not None]
    numbered = [chunk for chunk in alternative_chunks if has_numbered_clause(chunk)]
    wrong_heading = [chunk["id"] for chunk in numbered if not heading_matches_clause_number(chunk)]
    assert intro_with_heading + wrong_heading == []

def test_para_only_count_and_document():
    para_chunks = [chunk for chunk in CHUNKS if chunk["para_only"]]
    assert len(para_chunks) == EXPECTED_PARA_ONLY_COUNT
    assert {chunk["document"] for chunk in para_chunks} == {"laws"}

def test_headings_and_diagrams_are_never_para_only():
    # An empty list of font flags once counted as "all italic" and flagged these
    para_chunks = [chunk for chunk in CHUNKS if chunk["para_only"]]
    assert [chunk["id"] for chunk in para_chunks if is_heading_or_diagram(chunk)] == []

@pytest.mark.parametrize("chunk_id", KNOWN_PARA_ONLY)
def test_known_para_clause_is_flagged(chunk_id):
    assert CHUNKS_BY_ID[chunk_id]["para_only"] is True

@pytest.mark.parametrize("chunk_id", KNOWN_REGULAR)
def test_known_regular_clause_is_not_flagged(chunk_id):
    assert CHUNKS_BY_ID[chunk_id]["para_only"] is False


# ===== 5. Coverage =====

def test_diagrams_a_to_f_are_each_one_chunk():
    diagram_ids = {f"laws-Diagram {letter}" for letter in "ABCDEF"}
    assert diagram_ids.issubset(CHUNKS_BY_ID)

def test_every_numbered_golden_location_has_its_own_chunk():
    clause_keys = {(chunk["document"], chunk["clause"]) for chunk in CHUNKS}
    missing = []
    for question_id, location in every_golden_location():
        is_numbered = CLAUSE_NUMBER.match(location["clause"]) is not None
        if is_numbered and (location["doc"], location["clause"]) not in clause_keys:
            missing.append((question_id, location["doc"], location["clause"]))
    assert missing == []

def test_every_golden_location_maps_to_exactly_one_chunk():
    # A label must not match every chunk that mentions it ("as shown in Diagram A"), and an
    # Alternative Laws clause repeated across formats must name its format
    from evals.golden import expected_chunk_ids
    not_single = []
    for question_id, location in every_golden_location():
        if len(expected_chunk_ids(location, CHUNKS)) != 1:
            not_single.append((question_id, location))
    assert not_single == []

def test_source_pdfs_match_their_frozen_hashes():
    for document, frozen in GOLDEN_SET["corpus_frozen"].items():
        pdf_path = PDF_FOLDER / frozen["file"]
        if not pdf_path.exists():
            pytest.skip("PDFs are not in this clone; run scripts.ingest_rules after fetching them")
        assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == frozen["sha256"], f"{document} PDF changed"
