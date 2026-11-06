"""
Turns the three BWF rule PDFs into one chunk per clause and saves them as JSON.

What it does, in order:
1. Reads each PDF line by line with PyMuPDF, keeping each line's position and font.
2. Starts a new chunk at every clause number (9.1.6, 5.4.13, ...).
3. Rebuilds the numbers the Laws PDF hides: its two-level numbers (1.4., 7.5.)
   are small pictures, not text, so each picture starts the next clause in order.
4. Tags every chunk with its document, version, in-force date and Law heading,
   and marks Para Badminton clauses (printed in italics in the Laws).

  Input:  the three PDFs in data/bwf/ (downloaded by hand, never committed)
  Output: data/rule_chunks.json, one record per clause

Run from the project root:
    uv run python -m scripts.ingest_rules
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


# ===== The three documents and their versions =====

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


# ===== Patterns that recognise each kind of line =====

# A clause number on its own, such as "9.1.6." or "16.2" (the final dot is optional)
CLAUSE_NUMBER_ONLY = re.compile(r"^(\d+(?:\.\d+)+)\.?$")

# A clause number followed by text on the same line. The Alternative Laws often drop the
# final dot; the Laws keep it (for example the deepest clauses, "14.2.3.1.1. except in ...")
CLAUSE_NUMBER_WITH_TEXT_ANY_DOT = re.compile(r"^(\d+(?:\.\d+)+)\.?\s+(\S.*)$")
CLAUSE_NUMBER_WITH_TEXT_FINAL_DOT = re.compile(r"^(\d+(?:\.\d+)+)\.\s+(\S.*)$")

# In the ITTO, a clause number and its text can share one PDF span ("5.2.2.     Get into the chair").
# A real start has a final dot or two or more spaces; a wrapped reference ("16.7 applied") has neither
CLAUSE_NUMBER_WITH_TEXT_ITTO = re.compile(r"^(\d+(?:\.\d+)+)(?:\.\s+|\s{2,})(\S.*)$")

# A Law or section heading, such as "9. SERVICE" or "5. INSTRUCTIONS TO UMPIRES"
SECTION_HEADING = re.compile(r"^(\d+)\.\s+([A-Z][A-Z ,&’'()/–-]+)$")

# A diagram title, such as "DIAGRAM A"
DIAGRAM_TITLE = re.compile(r"^DIAGRAM ([A-Z])$")

# The running header and footer on every page
PAGE_FURNITURE = re.compile(r"^(BWF Statutes, Section|Page \d+ of \d+)")

# In the Alternative Laws, which scoring option or service rule a clause belongs to
ALTERNATIVE_VARIANTS = {
    "In case of 1 above": "one-game-21",
    "In case of 2 above": "best-of-3-games-21",
    "In the case of 3 above": "best-of-5-games-11",
    "ALTERNATIVE SERVICE LAWS": "alternative-service",
}

# A small picture at the left margin is a hidden two-level clause number in the Laws
NUMBER_PICTURE_MAX_WIDTH = 25
NUMBER_PICTURE_MAX_HEIGHT = 15


# ===== Reading a PDF into simple line records =====

def read_lines(pdf_path):
    """Returns every text line and small picture in reading order, as dictionaries."""
    lines = []
    for page_index, page in enumerate(pymupdf.open(pdf_path)):
        for block in page.get_text("dict")["blocks"]:
            left, top, right, bottom = block["bbox"]

            # A picture block: keep it only if it is small enough to be a clause number
            if block["type"] != 0:
                is_number_picture = (right - left) < NUMBER_PICTURE_MAX_WIDTH and (bottom - top) < NUMBER_PICTURE_MAX_HEIGHT
                if is_number_picture:
                    lines.append({"kind": "number_picture", "page": page_index + 1})
                continue

            # A text block: one record per line, with its first span kept separately
            for line in block["lines"]:
                spans = [span for span in line["spans"] if span["text"].strip()]
                if not spans:
                    continue
                lines.append({
                    "kind": "text",
                    "page": page_index + 1,
                    "text": " ".join(span["text"].strip() for span in spans),
                    "first_span": spans[0]["text"].strip(),
                    "is_italic": all(span["flags"] & 2 for span in spans),
                })
    return lines


# ===== Turning lines into clause chunks =====

def build_chunks(document_info, lines):
    """Groups the lines of one document into one chunk per clause."""
    chunks = []
    current_chunk = None
    current_heading = None
    current_section_number = None
    hidden_number_count = 0
    current_variant = None

    def start_chunk(clause, page, is_italic=None):
        nonlocal current_chunk
        current_chunk = {
            "clause": clause,
            "heading": current_heading,
            "variant": current_variant,
            "page": page,
            "lines": [],
            "italic_flags": [] if is_italic is None else [is_italic],
        }
        chunks.append(current_chunk)

    for line in lines:

        # A hidden two-level number: the next clause under the current Law
        if line["kind"] == "number_picture":
            if current_section_number is not None:
                hidden_number_count += 1
                start_chunk(f"{current_section_number}.{hidden_number_count}", line["page"])
            continue

        text = line["text"]
        if PAGE_FURNITURE.match(text):
            continue

        # The Alternative Laws: a marker line opens a new option, with its own short intro chunk
        variant_marker = next((variant for marker, variant in ALTERNATIVE_VARIANTS.items() if text.startswith(marker)), None)
        if variant_marker:
            current_variant = variant_marker

            # A new option starts with no heading, so the previous option's heading can't carry over
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

        # A clause number, either alone in its span or (Alternative Laws only) followed by text
        number_match = CLAUSE_NUMBER_ONLY.match(line["first_span"])
        if number_match:
            start_chunk(number_match.group(1), line["page"], line["is_italic"])
            remaining_text = text[len(line["first_span"]):].strip()
            if remaining_text:
                current_chunk["lines"].append(remaining_text)
            continue
        # Each document marks a clause start differently. Wrapped lines in the ITTO can start
        # with a reference such as "16.7 applied", so the ITTO needs a final dot or a wide gap
        if document_info["document"] == "alt":
            number_with_text_match = CLAUSE_NUMBER_WITH_TEXT_ANY_DOT.match(text)
        elif document_info["document"] == "laws":
            number_with_text_match = CLAUSE_NUMBER_WITH_TEXT_FINAL_DOT.match(text)
        else:
            number_with_text_match = CLAUSE_NUMBER_WITH_TEXT_ITTO.match(text)
        if number_with_text_match:
            start_chunk(number_with_text_match.group(1), line["page"], line["is_italic"])
            current_chunk["lines"].append(number_with_text_match.group(2))
            continue

        # Any other line belongs to the clause already open (or to the opening text)
        if current_chunk is None:
            start_chunk("Introduction", line["page"])
        current_chunk["lines"].append(text)

        # Joining words such as "or" sit between clauses in plain type, so they don't count
        is_joining_word = len(text) <= 3
        if not is_joining_word:
            current_chunk["italic_flags"].append(line["is_italic"])

    return chunks


# ===== Shaping the final records =====

def to_records(document_info, chunks):
    """Adds document details, joins the lines, and drops empty chunks."""
    records = []
    for chunk in chunks:
        text = " ".join(chunk["lines"]).strip()
        if not text:
            continue

        # The Alternative Laws repeat clause numbers per option, so the option goes in the id
        clause_id = f"{chunk['variant']}:{chunk['clause']}" if chunk["variant"] else chunk["clause"]

        # Para Badminton clauses are printed in italics, but only the Laws follow that rule.
        # A heading or diagram title has no font flags, and all([]) is True, so it needs at least one flag
        has_font_flags = bool(chunk["italic_flags"])
        is_para_only = document_info["document"] == "laws" and has_font_flags and all(chunk["italic_flags"])

        records.append({
            "id": f"{document_info['document']}-{clause_id}",
            "document": document_info["document"],
            "document_title": document_info["title"],
            "version": document_info["version"],
            "in_force": document_info["in_force"],
            "clause": chunk["clause"],
            "variant": chunk["variant"],
            "heading": chunk["heading"],
            "para_only": is_para_only,
            "page": chunk["page"],
            "text": text,
        })
    return records


def fill_headings_from_laws(alternative_records, law_records):
    """Gives a numbered Alternative Laws clause with no heading the heading of the Law it changes."""
    law_heading_by_number = {record["clause"]: record["heading"] for record in law_records if record["clause"].isdigit()}
    for record in alternative_records:
        section_number = record["clause"].split(".")[0]
        if record["heading"] is None and section_number.isdigit():
            record["heading"] = law_heading_by_number.get(section_number)


# ===== Running all three documents =====

def main() -> None:
    all_records = []
    records_by_document = {}
    for document_info in DOCUMENTS:
        lines = read_lines(PDF_FOLDER / document_info["file_name"])
        chunks = build_chunks(document_info, lines)
        records = to_records(document_info, chunks)
        records_by_document[document_info["document"]] = records
        print(f"{document_info['document']}: {len(records)} chunks")
        all_records.extend(records)

    # The alternative service law sits under no heading of its own, so it borrows the Law's
    fill_headings_from_laws(records_by_document["alt"], records_by_document["laws"])

    CHUNKS_FILE.write_text(json.dumps(all_records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved {len(all_records)} chunks to {CHUNKS_FILE.relative_to(PROJECT_FOLDER)}")


if __name__ == "__main__":
    main()
