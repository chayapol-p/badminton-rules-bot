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


# ===== 1. Every chunk is well formed =====

def test_every_chunk_has_every_field():
    incomplete = [chunk.get("id") for chunk in CHUNKS if set(chunk) != REQUIRED_FIELDS]
    assert incomplete == []

def test_chunk_ids_are_unique():
    assert len(CHUNKS_BY_ID) == len(CHUNKS)

def test_chunk_id_is_document_option_and_clause():
    def expected_id(chunk):
        clause_part = f"{chunk['variant']}:{chunk['clause']}" if chunk["variant"] else chunk["clause"]
        return f"{chunk['document']}-{clause_part}"
    assert [chunk["id"] for chunk in CHUNKS if chunk["id"] != expected_id(chunk)] == []

def test_every_chunk_has_text_and_a_page():
    assert [chunk["id"] for chunk in CHUNKS if not chunk["text"].strip()] == []
    assert [chunk["id"] for chunk in CHUNKS if not (isinstance(chunk["page"], int) and chunk["page"] > 0)] == []

def test_no_page_footer_left_in_text():
    assert [chunk["id"] for chunk in CHUNKS if re.search(r"Page \d+ of \d+", chunk["text"])] == []


# ===== 2. Counts match the last checked ingest =====

def test_chunk_count_per_document():
    counts = {document: sum(1 for chunk in CHUNKS if chunk["document"] == document) for document in EXPECTED_CHUNKS_PER_DOCUMENT}
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
    buried = [(chunk["id"], match.group(1)) for chunk in CHUNKS for match in BURIED_CLAUSE_NUMBER.finditer(chunk["text"])
              if not REFERENCE_BEFORE.search(chunk["text"][:match.start()])]
    assert buried == []


# ===== 4. Tags =====

def test_version_and_in_force_date_match_the_document():
    wrong = [chunk["id"] for chunk in CHUNKS
             if (chunk["version"], chunk["in_force"]) != (DOCUMENT_INFO[chunk["document"]]["version"], DOCUMENT_INFO[chunk["document"]]["in_force"])]
    assert wrong == []

def test_only_alternative_laws_chunks_carry_an_option():
    assert [chunk["id"] for chunk in CHUNKS if chunk["document"] != "alt" and chunk["variant"] is not None] == []
    options_used = {chunk["variant"] for chunk in CHUNKS if chunk["document"] == "alt" and chunk["clause"] != "Introduction"}
    assert options_used == ALTERNATIVE_OPTIONS

def test_option_markers_stay_in_their_intro_chunk():
    markers = ["In case of 1 above", "In case of 2 above", "In the case of 3 above", "ALTERNATIVE SERVICE LAWS"]
    leaked = [chunk["id"] for chunk in CHUNKS if chunk["clause"] != "intro" and any(marker in chunk["text"] for marker in markers)]
    assert leaked == []

def test_laws_and_itto_heading_matches_the_clause_number():
    numbered = [chunk for chunk in CHUNKS if chunk["document"] in ("laws", "itto") and CLAUSE_NUMBER.match(chunk["clause"])]
    mismatched = [chunk["id"] for chunk in numbered if not (chunk["heading"] or "").startswith(chunk["clause"].split(".")[0] + ".")]
    assert mismatched == []

def test_alternative_laws_heading_belongs_to_its_own_option():
    wrong = [chunk["id"] for chunk in CHUNKS if chunk["document"] == "alt" and chunk["clause"] == "intro" and chunk["heading"] is not None]
    wrong += [chunk["id"] for chunk in CHUNKS if chunk["document"] == "alt" and CLAUSE_NUMBER.match(chunk["clause"])
              and not (chunk["heading"] or "").startswith(chunk["clause"].split(".")[0] + ".")]
    assert wrong == []

def test_para_only_count_and_document():
    para_chunks = [chunk for chunk in CHUNKS if chunk["para_only"]]
    assert len(para_chunks) == EXPECTED_PARA_ONLY_COUNT
    assert {chunk["document"] for chunk in para_chunks} == {"laws"}

def test_headings_and_diagrams_are_never_para_only():
    # An empty list of font flags once counted as "all italic" and flagged these
    flagged = [chunk["id"] for chunk in CHUNKS if chunk["para_only"]
               and (re.match(r"^\d+$", chunk["clause"]) or chunk["clause"].startswith("Diagram"))]
    assert flagged == []

@pytest.mark.parametrize("chunk_id", KNOWN_PARA_ONLY)
def test_known_para_clause_is_flagged(chunk_id):
    assert CHUNKS_BY_ID[chunk_id]["para_only"] is True

@pytest.mark.parametrize("chunk_id", KNOWN_REGULAR)
def test_known_regular_clause_is_not_flagged(chunk_id):
    assert CHUNKS_BY_ID[chunk_id]["para_only"] is False


# ===== 5. Coverage =====

def test_diagrams_a_to_f_are_each_one_chunk():
    assert {f"laws-Diagram {letter}" for letter in "ABCDEF"} <= set(CHUNKS_BY_ID)

def test_every_numbered_golden_location_has_its_own_chunk():
    clause_keys = {(chunk["document"], chunk["clause"]) for chunk in CHUNKS}
    missing = [(question["id"], location["doc"], location["clause"])
               for question in GOLDEN_SET["questions"] for location in question["answer_locations"]
               if CLAUSE_NUMBER.match(location["clause"]) and (location["doc"], location["clause"]) not in clause_keys]
    assert missing == []

def test_label_locations_map_to_one_chunk_each():
    # A label must not match every chunk that mentions it ("as shown in Diagram A")
    from evals.golden import expected_chunk_ids
    labels = {(location["doc"], location["clause"]) for question in GOLDEN_SET["questions"]
              for location in question["answer_locations"] if not CLAUSE_NUMBER.match(location["clause"])}
    too_wide = {label: expected_chunk_ids({"doc": label[0], "clause": label[1]}, CHUNKS) for label in labels}
    assert {label: ids for label, ids in too_wide.items() if len(ids) != 1} == {}

def test_source_pdfs_match_their_frozen_hashes():
    for document, frozen in GOLDEN_SET["corpus_frozen"].items():
        pdf_path = PDF_FOLDER / frozen["file"]
        if not pdf_path.exists():
            pytest.skip("PDFs are not in this clone; run scripts.ingest_rules after fetching them")
        assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == frozen["sha256"], f"{document} PDF changed"
