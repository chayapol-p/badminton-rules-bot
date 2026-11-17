"""
Turns the three BWF rule PDFs into one chunk per clause and saves them as JSON.

What it does, in order:
1. Reads each PDF line by line with PyMuPDF, keeping each line's position and font.
2. Starts a new chunk at every clause number (9.1.6, 5.4.13, ...).
3. Rebuilds the numbers the Laws PDF hides: its two-level numbers (1.4., 7.5.)
   are small pictures, not text, so each picture starts the next clause in order.
4. Tags every chunk with its document, version, in-force date and Law heading,
   and marks Para Badminton clauses (printed in italics in the Laws).
5. Writes a search text for every chunk: a short context header, then the clause text.
   A clause alone often lacks its context ("…reaches 8 points" never says which format),
   so search reads the header too. This follows Anthropic's Contextual Retrieval, with a
   header built from the tags instead of written by a model.
6. Writes a second search text that also names the parent clauses ("2.2 Feathered Shuttle"
   for 2.2.6), so Stage 1 can measure what the parents add on top of the header.

  Input:  the three PDFs in data/bwf/ (downloaded by hand, never committed)
  Output: data/rule_chunks.json, one record per clause

Run from the project root:
    uv run python -m scripts.build_rule_chunks
"""

import json
import re
from pathlib import Path

import pymupdf


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
PDF_FOLDER = PROJECT_FOLDER / "data" / "bwf"
CHUNKS_FILE = PROJECT_FOLDER / "data" / "rule_chunks.json"

## The three documents and their versions
DOCUMENTS = [
    {
        "document": "laws",
        "file_name": "bwf-laws-of-badminton-2025-v5.0.pdf",
        "title": "Laws of Badminton",
        "version": "5.0 (2)",
        "in_force": "2025-04-26",
    },
    {
        "document": "itto",
        "file_name": "bwf-itto-2025-v7.0.pdf",
        "title": "Instructions to Technical Officials",
        "version": "7.0 (5)",
        "in_force": "2025-04-26",
    },
    {
        "document": "alt",
        "file_name": "bwf-alternative-laws-2027-v2.0.pdf",
        "title": "Alternative Laws of Badminton",
        "version": "2.0",
        "in_force": "2027-01-04",
    },
]

## Patterns that recognise each kind of line
# A clause number on its own, such as "9.1.6." or "16.2" (the final dot is optional)
CLAUSE_NUMBER_ONLY = re.compile(r"^(\d+(?:\.\d+)+)\.?$")

# A clause number followed by text on the same line. The Alternative Laws often drop the
# final dot; the Laws keep it (for example the deepest clauses, "14.2.3.1.1. except in ...")
CLAUSE_NUMBER_WITH_TEXT_ANY_DOT = re.compile(r"^(\d+(?:\.\d+)+)\.?\s+(\S.*)$")
CLAUSE_NUMBER_WITH_TEXT_FINAL_DOT = re.compile(r"^(\d+(?:\.\d+)+)\.\s+(\S.*)$")

# In the ITTO, a clause number and its text can share one PDF span ("5.2.2.     Get into the chair").
# A real start has a final dot or two or more spaces; a wrapped reference ("16.7 applied") has neither
CLAUSE_NUMBER_WITH_TEXT_ITTO = re.compile(r"^(\d+(?:\.\d+)+)(?:\.\s+|\s{2,})(\S.*)$")

# Each document marks a clause start differently. Wrapped lines in the ITTO can start
# with a reference such as "16.7 applied", so the ITTO needs a final dot or a wide gap
CLAUSE_NUMBER_WITH_TEXT_BY_DOCUMENT = {
    "alt": CLAUSE_NUMBER_WITH_TEXT_ANY_DOT,
    "laws": CLAUSE_NUMBER_WITH_TEXT_FINAL_DOT,
    "itto": CLAUSE_NUMBER_WITH_TEXT_ITTO,
}

# A Law or section heading, such as "9. SERVICE" or "5. INSTRUCTIONS TO UMPIRES"
SECTION_HEADING = re.compile(r"^(\d+)\.\s+([A-Z][A-Z ,&’'()/–-]+)$")

# A diagram title, such as "DIAGRAM A"
DIAGRAM_TITLE = re.compile(r"^DIAGRAM ([A-Z])$")

# The running header and footer on every page
PAGE_FURNITURE = re.compile(r"^(BWF Statutes, Section|Page \d+ of \d+)")

## The Alternative Laws formats
# The line that opens each format, and the format's name.
# Each format (a scoring system, or the alternative service rule) repeats clause numbers
ALTERNATIVE_FORMAT_MARKERS = {
    "In case of 1 above": "one-game-21",
    "In case of 2 above": "best-of-3-games-21",
    "In the case of 3 above": "best-of-5-games-11",
    "ALTERNATIVE SERVICE LAWS": "alternative-service",
}

# Readable names for the formats, for the search text and the prompt labels
ALTERNATIVE_FORMAT_NAMES = {
    "one-game-21": "one game to 21",
    "best-of-3-games-21": "best of 3 games to 21",
    "best-of-5-games-11": "best of 5 games to 11",
    "alternative-service": "alternative service law",
}

## Search text
# A parent clause in the search text keeps only its first words, so a long parent can't drown the clause
PARENT_WORD_LIMIT = 15

## PDF layout
# A small picture at the left margin is a hidden two-level clause number in the Laws
NUMBER_PICTURE_MAX_WIDTH = 25
NUMBER_PICTURE_MAX_HEIGHT = 15

# PyMuPDF stores a span's font styles as bits in one number; this bit means italic
ITALIC_FONT_FLAG = 2

# A line this short is a joining word such as "or", which sits between clauses in plain type
JOINING_WORD_MAX_LENGTH = 3


# ===== Reading a PDF into simple line records =====

def is_italic_span(span: dict) -> bool:
    """True when PyMuPDF marks the span's font as italic. Bit flags have no word form, so the & stays here."""
    return (span["flags"] & ITALIC_FONT_FLAG) != 0


def is_number_picture(block: dict) -> bool:
    """True for a picture block small enough to be a hidden clause number."""
    left, top, right, bottom = block["bbox"]
    if right - left >= NUMBER_PICTURE_MAX_WIDTH:
        return False
    return bottom - top < NUMBER_PICTURE_MAX_HEIGHT


def has_visible_text(span: dict) -> bool:
    """True for a span with more than white space."""
    return bool(span["text"].strip())


def read_lines(pdf_path: Path) -> list[dict]:
    """Returns every text line and small picture in reading order, as dictionaries."""
    lines = []
    for page_number, page in enumerate(pymupdf.open(pdf_path), start=1):
        for block in page.get_text("dict")["blocks"]:

            # A picture block: keep it only if it is small enough to be a clause number
            is_text_block = block["type"] == 0
            if not is_text_block:
                if is_number_picture(block):
                    lines.append({"kind": "number_picture", "page": page_number})
                continue

            # A text block: one record per line, with its first span kept separately
            for line in block["lines"]:
                spans = [span for span in line["spans"] if has_visible_text(span)]
                if not spans:
                    continue
                lines.append({
                    "kind": "text",
                    "page": page_number,
                    "text": " ".join(span["text"].strip() for span in spans),
                    "first_span": spans[0]["text"].strip(),
                    "is_italic": all(is_italic_span(span) for span in spans),
                })
    return lines


# ===== Turning lines into clause chunks =====

def find_format_opened_by(text: str) -> str | None:
    """Returns the Alternative Laws format this line opens, or None for any other line."""
    for marker, format_name in ALTERNATIVE_FORMAT_MARKERS.items():
        if text.startswith(marker):
            return format_name
    return None


def build_chunks(document_info: dict, lines: list[dict]) -> list[dict]:
    """Groups the lines of one document into one chunk per clause."""
    chunks = []
    current_chunk = None
    current_heading = None
    current_section_number = None
    hidden_number_count = 0
    current_format = None
    clause_number_with_text = CLAUSE_NUMBER_WITH_TEXT_BY_DOCUMENT[document_info["document"]]

    def start_chunk(clause: str, page: int, is_italic: bool | None = None) -> None:
        """Opens a new chunk under the current heading and format; is_italic is the font of its number line."""
        nonlocal current_chunk

        # A chunk opened by a heading, a diagram or a hidden number has no font flag yet
        if is_italic is None:
            italic_flags = []
        else:
            italic_flags = [is_italic]

        current_chunk = {
            "clause": clause,
            "heading": current_heading,
            "alternative_format": current_format,
            "page": page,
            "lines": [],
            "italic_flags": italic_flags,
        }
        chunks.append(current_chunk)

    for line in lines:

        # A hidden two-level number: the next clause under the current Law
        if line["kind"] == "number_picture":
            if current_section_number is not None:
                hidden_number_count += 1
                start_chunk(f"{current_section_number}.{hidden_number_count}", line["page"])
            continue

        # The running header and footer belong to no clause
        text = line["text"]
        if PAGE_FURNITURE.match(text):
            continue

        # The Alternative Laws: a marker line opens a new format, with its own short intro chunk
        opened_format = find_format_opened_by(text)
        if opened_format:
            current_format = opened_format

            # A new format starts with no heading, so the previous format's heading can't carry over
            current_heading = None
            current_section_number = None
            hidden_number_count = 0
            start_chunk("intro", line["page"])
            current_chunk["lines"].append(text)
            continue

        # A Law or section heading: remember it, and restart the hidden-number count
        heading_match = SECTION_HEADING.match(text)
        if heading_match:
            current_section_number = heading_match.group(1)
            current_heading = f"{heading_match.group(1)}. {heading_match.group(2).strip()}"
            hidden_number_count = 0
            start_chunk(current_section_number, line["page"])
            current_chunk["lines"].append(current_heading)
            continue

        # A diagram title: its caption lines become their own chunk
        diagram_match = DIAGRAM_TITLE.match(text)
        if diagram_match:
            start_chunk(f"Diagram {diagram_match.group(1)}", line["page"])
            current_chunk["lines"].append(text)
            continue

        # A clause number alone in its first span, perhaps with text after it in later spans
        number_match = CLAUSE_NUMBER_ONLY.match(line["first_span"])
        if number_match:
            start_chunk(number_match.group(1), line["page"], line["is_italic"])
            remaining_text = text[len(line["first_span"]):].strip()
            if remaining_text:
                current_chunk["lines"].append(remaining_text)
            continue

        # A clause number and its text in one span, with the document's own pattern
        number_with_text_match = clause_number_with_text.match(text)
        if number_with_text_match:
            start_chunk(number_with_text_match.group(1), line["page"], line["is_italic"])
            current_chunk["lines"].append(number_with_text_match.group(2))
            continue

        # Any other line belongs to the clause already open (or to the opening text)
        if current_chunk is None:
            start_chunk("Introduction", line["page"])
        current_chunk["lines"].append(text)

        # Joining words such as "or" sit between clauses in plain type, so they don't count
        is_joining_word = len(text) <= JOINING_WORD_MAX_LENGTH
        if not is_joining_word:
            current_chunk["italic_flags"].append(line["is_italic"])

    return chunks


# ===== Shaping the final records =====

def is_para_only_chunk(document_info: dict, chunk: dict) -> bool:
    """True for a Laws clause printed wholly in italics, the Laws' mark for a Para Badminton clause."""

    # Only the Laws follow the italics rule
    if document_info["document"] != "laws":
        return False

    # A heading or diagram title has no font flags, and all([]) is True, so it needs at least one flag
    if not chunk["italic_flags"]:
        return False
    return all(chunk["italic_flags"])


def build_clause_records(document_info: dict, chunks: list[dict]) -> list[dict]:
    """Returns one record per chunk, with the document details and the joined text; empty chunks are dropped."""
    records = []
    for chunk in chunks:
        text = " ".join(chunk["lines"]).strip()
        if not text:
            continue

        # The Alternative Laws repeat clause numbers per format, so the format goes in the id
        if chunk["alternative_format"]:
            clause_id = f"{chunk['alternative_format']}:{chunk['clause']}"
        else:
            clause_id = chunk["clause"]

        records.append({
            "id": f"{document_info['document']}-{clause_id}",
            "document": document_info["document"],
            "document_title": document_info["title"],
            "version": document_info["version"],
            "in_force": document_info["in_force"],
            "clause": chunk["clause"],
            "alternative_format": chunk["alternative_format"],
            "heading": chunk["heading"],
            "para_only": is_para_only_chunk(document_info, chunk),
            "page": chunk["page"],
            "text": text,
        })
    return records


def fill_headings_from_laws(alternative_records: list[dict], law_records: list[dict]) -> None:
    """Gives a numbered Alternative Laws clause with no heading the heading of the Law it changes."""

    # Each Law's heading, by its one-level number ("9" -> "9. SERVICE")
    law_heading_by_number = {}
    for record in law_records:
        if record["clause"].isdigit():
            law_heading_by_number[record["clause"]] = record["heading"]

    # Fill only the gaps, and only under a numbered Law
    for record in alternative_records:
        if record["heading"] is not None:
            continue
        section_number = record["clause"].split(".")[0]
        if section_number.isdigit():
            record["heading"] = law_heading_by_number.get(section_number)


# ===== Adding the context header that search reads =====

def is_numbered_clause(record: dict) -> bool:
    """True for a real clause number, not a label such as "Diagram A", "intro" or "Introduction"."""
    return record["clause"][0].isdigit()


def build_context_header(record: dict) -> str:
    """Returns the context a clause needs to be found: document, format, para flag, heading, number."""
    parts = [record["document_title"]]
    if record["alternative_format"]:
        parts.append(ALTERNATIVE_FORMAT_NAMES[record["alternative_format"]])
    if record["para_only"]:
        parts.append("Para Badminton only")
    if record["heading"]:
        parts.append(record["heading"])

    # Only real clause numbers, so labels such as "Diagram A" or "intro" don't turn into "Clause intro"
    if is_numbered_clause(record):
        parts.append(f"Clause {record['clause']}")
    return " · ".join(parts)


def add_search_text(records: list[dict]) -> None:
    """Gives every record a search_text: its context header, a new line, then its clause text."""
    for record in records:
        record["search_text"] = f"{build_context_header(record)}\n{record['text']}"


def list_parent_clause_numbers(clause: str) -> list[str]:
    """Returns the numbered parents below the Law heading, outermost first: "2.2.6" gives ["2.2"]."""
    parts = clause.split(".")
    parents = []
    for depth in range(2, len(parts)):
        parents.append(".".join(parts[:depth]))
    return parents


def find_parent_record(record: dict, parent_clause: str, record_by_place: dict[tuple, dict]) -> dict | None:
    """Returns the parent clause's record from the same document and format, or the Law it changes."""
    same_place = (record["document"], record["alternative_format"], parent_clause)
    if same_place in record_by_place:
        return record_by_place[same_place]

    # An Alternative Laws clause can sit under a Law the Alternative Laws never repeat (8.1.3 under 8.1)
    if record["document"] == "alt":
        return record_by_place.get(("laws", None, parent_clause))
    return None


def build_parents_line(record: dict, record_by_place: dict[tuple, dict]) -> str:
    """Returns the parent clauses as one line ("2.2 Feathered Shuttle"), each cut to its first words."""
    if not is_numbered_clause(record):
        return ""
    parent_texts = []
    for parent_clause in list_parent_clause_numbers(record["clause"]):
        parent = find_parent_record(record, parent_clause, record_by_place)
        if parent is None:
            continue
        first_words = " ".join(parent["text"].split()[:PARENT_WORD_LIMIT])
        parent_texts.append(f"{parent_clause} {first_words}")
    return " · ".join(parent_texts)


def add_search_text_with_parents(records: list[dict]) -> None:
    """Gives every record a search_text_with_parents: the header, the parent clauses, then the clause text."""

    # Index the records by where they sit: document, format and clause number
    record_by_place = {}
    for record in records:
        record_by_place[(record["document"], record["alternative_format"], record["clause"])] = record

    # A clause with no parents keeps the plain search text
    for record in records:
        parents_line = build_parents_line(record, record_by_place)
        if parents_line:
            record["search_text_with_parents"] = f"{build_context_header(record)}\n{parents_line}\n{record['text']}"
        else:
            record["search_text_with_parents"] = record["search_text"]


# ===== Running all three documents =====

def main() -> None:
    """Chunks every document, adds both search texts, and saves the records."""
    all_records = []
    records_by_document = {}
    for document_info in DOCUMENTS:
        lines = read_lines(PDF_FOLDER / document_info["file_name"])
        chunks = build_chunks(document_info, lines)
        records = build_clause_records(document_info, chunks)
        records_by_document[document_info["document"]] = records
        print(f"{document_info['document']}: {len(records)} chunks")
        all_records.extend(records)

    # The alternative service law sits under no heading of its own, so it borrows the Law's
    fill_headings_from_laws(records_by_document["alt"], records_by_document["laws"])

    # Last, once every tag is final: the header reads the headings filled in just above
    add_search_text(all_records)
    add_search_text_with_parents(all_records)

    # Save the records
    CHUNKS_FILE.write_text(json.dumps(all_records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved {len(all_records)} chunks to {CHUNKS_FILE.relative_to(PROJECT_FOLDER)}")


if __name__ == "__main__":
    main()
