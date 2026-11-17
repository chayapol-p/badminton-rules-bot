"""
Builds the rule map: the links between clause chunks that similarity search cannot see.

Search finds clauses by their words. Some clauses that answer a question share almost no
words with it: the alternative rule that replaces a Law, a Law that an ITTO clause cites,
the regular rule behind a Wheelchair exception. This script reads those links straight
from the rule books and stores them, so retrieval can follow them after search.

It finds five kinds of link (the "relation" field):
- overrides:          an Alternative Laws clause -> the Law it replaces (alt 9.1.6 -> Law 9.1.6)
- cites:              a clause -> a clause it names ("dealt with under Law 16.7")
- para_exception_of:  a Para Badminton clause -> the regular rule it changes
- shows_diagram:      a clause -> the diagram it names ("as shown in Diagram A")
- instructions_for:   an official's duty in the Laws -> that official's instructions in the ITTO
                      (Law 17.3, the service judge -> ITTO 7.2). Listed by hand: the books never cite them

It also lists references to BWF documents that are not in the corpus (such as Section
4.1.5, Vocabulary), so the bot can say where an answer lives instead of guessing it.

  Input:  data/rule_chunks.json (from scripts.build_rule_chunks)
  Output: data/rule_links.json

Run from the project root:
    uv run python -m scripts.build_rule_links
"""

import json
import re
from pathlib import Path


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
CHUNKS_FILE = PROJECT_FOLDER / "data" / "rule_chunks.json"
LINKS_FILE = PROJECT_FOLDER / "data" / "rule_links.json"

## The documents in the corpus, as rule_chunks.json names them
DOCUMENT_NAMES = ("laws", "itto", "alt")

## The kinds of link, in the order main prints their counts
RELATIONS = ("overrides", "cites", "para_exception_of", "shows_diagram", "instructions_for")

## Patterns that find a reference in clause text
# One clause number, such as "16.7" or "9.1.6"
CLAUSE_NUMBER_PATTERN = r"\d+(?:\.\d+)*"

# What joins numbers in one reference: "2.2.2, 2.2.3 and 2.2.6", "9.1.2 to Law 9.1.8", "3.6.1.2 - 3.6.1.4"
REFERENCE_JOINER_PATTERN = r"\s*(?:,|and|or|to|-|–)\s*"

# The joiners that mean a range ("9.1.2 to 9.1.8"), not a list
RANGE_JOINERS = ("to", "-", "–")

# "Law 16.7" or "Laws 16.6.3 and 16.6.4" point into the Laws of Badminton
LAW_REFERENCE = re.compile(
    rf"\bLaws?\s+({CLAUSE_NUMBER_PATTERN}(?:{REFERENCE_JOINER_PATTERN}(?:Laws?\s+)?{CLAUSE_NUMBER_PATTERN})*)"
)

# "Instructions 2.2 and 2.3" point to other clauses of the ITTO
INSTRUCTION_REFERENCE = re.compile(
    rf"\bInstructions?\s+({CLAUSE_NUMBER_PATTERN}(?:{REFERENCE_JOINER_PATTERN}(?:Instructions?\s+)?{CLAUSE_NUMBER_PATTERN})*)"
)

# Each reference pattern, with the document its numbers point into
REFERENCE_PATTERNS = [(LAW_REFERENCE, "laws"), (INSTRUCTION_REFERENCE, "itto")]

# "Diagram A" or "Diagrams D and E" point to the court and racket diagrams in the Laws
DIAGRAM_REFERENCE = re.compile(r"\bDiagrams?\s+([A-F](?:\s*(?:,|and|or)\s*[A-F])*)\b")

# "Section 4.1.5" names a BWF Statutes document
STATUTE_SECTION_REFERENCE = re.compile(r"\bSection\s+(4\.1(?:\.\d+)*)")

## The Statutes sections this corpus holds. Any other Section 4.1.x is outside the corpus
SECTIONS_IN_CORPUS = {"4.1", "4.1.1", "4.1.4"}

## Each official's duty in the Laws, and the ITTO clause that instructs that official in it
# 8 Nov: service-fault-officials never got ITTO 7.2 ("call 'Fault' loudly"); it ranked 13th in vector search
OFFICIAL_INSTRUCTIONS = [
    ("laws-17.3", "itto-7.2", "the service judge"),
    ("laws-17.4", "itto-8.2", "a line judge"),
    ("laws-17.5.1", "itto-8.2", "the umpire overruling a line judge"),
]


# ===== Making one link record =====

def make_link(from_chunk: dict, to_chunk: dict, relation: str, evidence: str) -> dict:
    """Returns one link record. The evidence is the text or rule that created it, so a wrong link can be traced."""
    return {"from_id": from_chunk["id"], "to_id": to_chunk["id"], "relation": relation, "evidence": evidence}


# ===== Looking up chunks by document and clause number =====

def is_heading_only(chunk: dict) -> bool:
    """True for a chunk that holds only a Law heading, such as "9. SERVICE"."""
    return chunk["text"] == chunk["heading"]


def list_clause_and_its_parents(clause_number: str) -> list[str]:
    """Returns the clause, then each level above it: "9.1.6" gives ["9.1.6", "9.1", "9"]."""
    parts = clause_number.split(".")
    clause_and_parents = []
    for depth in range(len(parts), 0, -1):
        clause_and_parents.append(".".join(parts[:depth]))
    return clause_and_parents


def find_clause(chunks_by_id: dict[str, dict], document: str, clause_number: str) -> dict | None:
    """Returns the chunk for this clause, or for its nearest parent when the exact one does not exist."""
    for candidate_number in list_clause_and_its_parents(clause_number):
        chunk = chunks_by_id.get(f"{document}-{candidate_number}")
        if chunk:
            return chunk
    return None


def list_clauses_in_range(first_number: str, last_number: str, clause_numbers_in_order: list[str]) -> list[str]:
    """Returns the clauses after first_number, up to and including last_number, at first_number's depth."""
    start_position = clause_numbers_in_order.index(first_number)
    end_position = clause_numbers_in_order.index(last_number)
    depth = first_number.count(".")

    # Same depth only, so "9.1.2 to 9.1.8" brings 9.1.4 but not its sub-clause 9.1.4.1
    clauses_in_range = []
    for number in clause_numbers_in_order[start_position + 1:end_position + 1]:
        is_same_depth = number.count(".") == depth
        if is_same_depth:
            clauses_in_range.append(number)
    return clauses_in_range


def expand_reference(reference_text: str, document: str, clause_order: dict[str, list[str]]) -> list[str]:
    """
    Turns one reference into clause numbers: "2.2.2, 2.2.3 and 2.2.6" gives three numbers,
    and a range "9.1.2 to 9.1.8" gives every clause between them at the same depth
    (so 9.1.4 is included, but its sub-clause 9.1.4.1 is not).
    """

    # Split the reference into its numbers and the words between them
    numbers = re.findall(CLAUSE_NUMBER_PATTERN, reference_text)
    pieces = re.split(rf"(?:Laws?|Instructions?)?\s*{CLAUSE_NUMBER_PATTERN}", reference_text)
    joiners = [piece.strip(" ,") for piece in pieces[1:-1]]
    clause_numbers_in_order = clause_order[document]

    # Each joiner sits before the next number; a range brings every clause in between
    clause_numbers = [numbers[0]]
    for joiner, next_number in zip(joiners, numbers[1:]):
        previous_number = clause_numbers[-1]
        is_range = joiner in RANGE_JOINERS
        is_known_range = previous_number in clause_numbers_in_order and next_number in clause_numbers_in_order
        if is_range and is_known_range:
            clause_numbers.extend(list_clauses_in_range(previous_number, next_number, clause_numbers_in_order))
        else:
            clause_numbers.append(next_number)
    return clause_numbers


# ===== Finding each kind of link =====

def is_numbered_alternative_clause(chunk: dict) -> bool:
    """True for an Alternative Laws chunk with a clause number and text of its own (not only a heading)."""
    if chunk["document"] != "alt":
        return False
    if not re.fullmatch(CLAUSE_NUMBER_PATTERN, chunk["clause"]):
        return False
    return not is_heading_only(chunk)


def find_override_links(chunks: list[dict], chunks_by_id: dict[str, dict]) -> list[dict]:
    """Returns an overrides link from each Alternative Laws clause to the Law with its number (or nearest parent)."""
    links = []
    for chunk in chunks:
        if not is_numbered_alternative_clause(chunk):
            continue
        replaced_law = find_clause(chunks_by_id, "laws", chunk["clause"])
        if replaced_law:
            links.append(make_link(chunk, replaced_law, "overrides", f"same number, format {chunk['alternative_format']}"))
    return links


def find_cited_clauses(text: str, clause_order: dict[str, list[str]]) -> list[tuple[str, str, str]]:
    """Returns each clause a text cites, as (document, clause number, the reference as written)."""
    cited_clauses = []
    for pattern, target_document in REFERENCE_PATTERNS:
        for match in pattern.finditer(text):
            for clause_number in expand_reference(match.group(1), target_document, clause_order):
                cited_clauses.append((target_document, clause_number, match.group(0)))
    return cited_clauses


def find_citation_links(chunks: list[dict], chunks_by_id: dict[str, dict],
                        clause_order: dict[str, list[str]]) -> list[dict]:
    """Returns a cites link for each "Law 16.7" or "Instructions 2.2" in a clause's text."""
    links = []
    for chunk in chunks:
        for target_document, clause_number, reference in find_cited_clauses(chunk["text"], clause_order):
            cited_chunk = find_clause(chunks_by_id, target_document, clause_number)
            if cited_chunk is None:
                continue

            # A clause that names itself, or falls back to itself as the nearest parent, is no link
            is_self_citation = cited_chunk["id"] == chunk["id"]
            if not is_self_citation:
                links.append(make_link(chunk, cited_chunk, "cites", reference))
    return links


def is_regular_clause(chunk: dict | None) -> bool:
    """True for a Laws chunk that exists, applies to regular play, and holds more than a heading."""
    if chunk is None:
        return False
    if chunk["para_only"]:
        return False
    return not is_heading_only(chunk)


def find_para_exception_links(chunks: list[dict], chunks_by_id: dict[str, dict]) -> list[dict]:
    """Returns a para_exception_of link from each Para Badminton clause to the nearest regular clause above it."""
    links = []
    for chunk in chunks:
        if not chunk["para_only"]:
            continue

        # Go up the clause numbers until a regular, non-heading clause is found
        parent_numbers = list_clause_and_its_parents(chunk["clause"])[1:]
        for parent_number in parent_numbers:
            parent = chunks_by_id.get(f"laws-{parent_number}")
            if is_regular_clause(parent):
                links.append(make_link(chunk, parent, "para_exception_of", "nearest regular clause above"))
                break
    return links


def find_diagram_links(chunks: list[dict], chunks_by_id: dict[str, dict]) -> list[dict]:
    """Returns a shows_diagram link for each "Diagram A" in a clause's text, to that diagram's caption chunk."""
    links = []
    for chunk in chunks:
        if chunk["clause"].startswith("Diagram"):
            continue
        for match in DIAGRAM_REFERENCE.finditer(chunk["text"]):
            for letter in re.findall(r"[A-F]", match.group(1)):
                diagram = chunks_by_id.get(f"laws-Diagram {letter}")
                if diagram:
                    links.append(make_link(chunk, diagram, "shows_diagram", match.group(0)))
    return links


def find_instruction_links(chunks_by_id: dict[str, dict]) -> list[dict]:
    """Returns an instructions_for link from each official's duty in the Laws to the ITTO clause that instructs them."""
    links = []
    for law_id, instruction_id, official in OFFICIAL_INSTRUCTIONS:
        links.append(make_link(chunks_by_id[law_id], chunks_by_id[instruction_id], "instructions_for",
                               f"listed by hand: {official}"))
    return links


def find_outside_references(chunks: list[dict]) -> list[dict]:
    """Returns each reference to a BWF Statutes section that is not in the corpus."""
    references = []
    for chunk in chunks:
        for section in set(STATUTE_SECTION_REFERENCE.findall(chunk["text"])):
            if section not in SECTIONS_IN_CORPUS:
                references.append({"from_id": chunk["id"], "section": f"BWF Statutes Section {section}"})
    return references


# ===== Building the whole map =====

def list_clause_order_by_document(chunks: list[dict]) -> dict[str, list[str]]:
    """Returns each document's clause numbers in document order, so a range can be expanded."""
    clause_order = {}
    for document in DOCUMENT_NAMES:
        clause_order[document] = []
    for chunk in chunks:
        clause_order[chunk["document"]].append(chunk["clause"])
    return clause_order


def build_rule_links(chunks: list[dict]) -> dict:
    """Returns every link (without duplicates) and the references outside the corpus."""
    chunks_by_id = {chunk["id"]: chunk for chunk in chunks}
    clause_order = list_clause_order_by_document(chunks)

    # Find every kind of link
    all_links = (
        find_override_links(chunks, chunks_by_id)
        + find_citation_links(chunks, chunks_by_id, clause_order)
        + find_para_exception_links(chunks, chunks_by_id)
        + find_diagram_links(chunks, chunks_by_id)
        + find_instruction_links(chunks_by_id)
    )

    # A clause can name the same Law twice; keep the first link of each kind
    unique_links = {}
    for link in all_links:
        unique_links.setdefault((link["from_id"], link["to_id"], link["relation"]), link)

    return {"links": list(unique_links.values()), "outside_corpus": find_outside_references(chunks)}


# ===== Running =====

def main() -> None:
    """Builds the rule map from the saved chunks, prints a count per relation, and saves it."""
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    rule_map = build_rule_links(chunks)

    # Print how many links of each kind were found
    for relation in RELATIONS:
        count = sum(1 for link in rule_map["links"] if link["relation"] == relation)
        print(f"{relation}: {count} links")
    print(f"outside the corpus: {len(rule_map['outside_corpus'])} references")

    # Save the map
    LINKS_FILE.write_text(json.dumps(rule_map, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved to {LINKS_FILE.relative_to(PROJECT_FOLDER)}")


if __name__ == "__main__":
    main()
