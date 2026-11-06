"""
Builds the rule map: the links between clause chunks that similarity search cannot see.

Search finds clauses by their words. Some clauses that answer a question share almost no
words with it: the alternative rule that replaces a Law, a Law that an ITTO clause cites,
the regular rule behind a Wheelchair exception. This script reads those links straight
from the rule books and stores them, so retrieval can follow them after search.

It finds four kinds of link (the "relation" field):
- overrides:          an Alternative Laws clause -> the Law it replaces (alt 9.1.6 -> Law 9.1.6)
- cites:              a clause -> a clause it names ("dealt with under Law 16.7")
- para_exception_of:  a Para Badminton clause -> the regular rule it changes
- shows_diagram:      a clause -> the diagram it names ("as shown in Diagram A")

It also lists references to BWF documents that are not in the corpus (such as Section
4.1.5, Vocabulary), so the bot can say where an answer lives instead of guessing it.

  Input:  data/rule_chunks.json (from scripts.ingest_rules)
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


# ===== Patterns that find a reference in clause text =====

# One clause number, such as "16.7" or "9.1.6"
NUMBER = r"\d+(?:\.\d+)*"

# What joins numbers in one reference: "2.2.2, 2.2.3 and 2.2.6", "9.1.2 to Law 9.1.8", "3.6.1.2 - 3.6.1.4"
JOINER = r"\s*(?:,|and|or|to|-|–)\s*"

# "Law 16.7" or "Laws 16.6.3 and 16.6.4" point into the Laws of Badminton
LAW_REFERENCE = re.compile(rf"\bLaws?\s+({NUMBER}(?:{JOINER}(?:Laws?\s+)?{NUMBER})*)")

# "Instructions 2.2 and 2.3" point to other clauses of the ITTO
INSTRUCTION_REFERENCE = re.compile(rf"\bInstructions?\s+({NUMBER}(?:{JOINER}(?:Instructions?\s+)?{NUMBER})*)")

# "Diagram A" or "Diagrams D and E" point to the court and racket diagrams in the Laws
DIAGRAM_REFERENCE = re.compile(r"\bDiagrams?\s+([A-F](?:\s*(?:,|and|or)\s*[A-F])*)\b")

# "Section 4.1.5" names a BWF Statutes document
STATUTE_SECTION_REFERENCE = re.compile(r"\bSection\s+(4\.1(?:\.\d+)*)")

# The Statutes sections this corpus holds. Any other Section 4.1.x is outside the corpus
SECTIONS_IN_CORPUS = {"4.1", "4.1.1", "4.1.4"}


# ===== Looking up chunks by document and clause number =====

def is_heading_only(chunk):
    """True for a chunk that holds only a Law heading, such as "9. SERVICE"."""
    return chunk["text"] == chunk["heading"]


def parent_number(clause_number):
    """Returns the clause one level up ("9.1.6" -> "9.1"), or None at the top."""
    parts = clause_number.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else None


def find_clause(chunks_by_id, document, clause_number):
    """Returns the chunk for this clause, or for its nearest parent when the exact one does not exist."""
    while clause_number:
        chunk = chunks_by_id.get(f"{document}-{clause_number}")
        if chunk:
            return chunk
        clause_number = parent_number(clause_number)
    return None


def expand_reference(reference_text, document, clause_order):
    """
    Turns one reference into clause numbers: "2.2.2, 2.2.3 and 2.2.6" gives three numbers,
    and a range "9.1.2 to 9.1.8" gives every clause between them at the same depth
    (so 9.1.4 is included, but its sub-clause 9.1.4.1 is not).
    """
    numbers = re.findall(NUMBER, reference_text)
    pieces = re.split(rf"(?:Laws?|Instructions?)?\s*{NUMBER}", reference_text)
    joiners = [piece.strip(" ,") for piece in pieces[1:-1]]

    clause_numbers = [numbers[0]]
    for i, joiner in enumerate(joiners):
        next_number = numbers[i + 1]
        is_range = joiner in ("to", "-", "–")
        if is_range and clause_numbers[-1] in clause_order[document] and next_number in clause_order[document]:
            order = clause_order[document]
            start, end = order.index(clause_numbers[-1]), order.index(next_number)
            depth = clause_numbers[-1].count(".")
            clause_numbers += [number for number in order[start + 1:end + 1] if number.count(".") == depth]
        else:
            clause_numbers.append(next_number)
    return clause_numbers


# ===== Finding each kind of link =====

def find_override_links(chunks, chunks_by_id):
    """Each Alternative Laws clause replaces the Law with the same number (or its nearest parent)."""
    links = []
    for chunk in chunks:
        has_clause_number = re.fullmatch(NUMBER, chunk["clause"])
        if chunk["document"] != "alt" or not has_clause_number or is_heading_only(chunk):
            continue
        replaced_law = find_clause(chunks_by_id, "laws", chunk["clause"])
        if replaced_law:
            links.append(make_link(chunk, replaced_law, "overrides", f"same number, option {chunk['variant']}"))
    return links


def find_citation_links(chunks, chunks_by_id, clause_order):
    """Each "Law 16.7" or "Instructions 2.2" in a clause's text links to the clause it names."""
    links = []
    for chunk in chunks:
        patterns = [(LAW_REFERENCE, "laws"), (INSTRUCTION_REFERENCE, "itto")]
        for pattern, target_document in patterns:
            for match in pattern.finditer(chunk["text"]):
                for clause_number in expand_reference(match.group(1), target_document, clause_order):
                    cited_chunk = find_clause(chunks_by_id, target_document, clause_number)
                    if cited_chunk and cited_chunk["id"] != chunk["id"]:
                        links.append(make_link(chunk, cited_chunk, "cites", match.group(0)))
    return links


def find_para_exception_links(chunks, chunks_by_id):
    """Each Para Badminton clause links to the nearest regular clause above it."""
    links = []
    for chunk in chunks:
        if not chunk["para_only"]:
            continue
        # Walk up the clause numbers until a regular, non-heading clause is found
        clause_number = parent_number(chunk["clause"])
        while clause_number:
            parent = chunks_by_id.get(f"laws-{clause_number}")
            if parent and not parent["para_only"] and not is_heading_only(parent):
                links.append(make_link(chunk, parent, "para_exception_of", "nearest regular clause above"))
                break
            clause_number = parent_number(clause_number)
    return links


def find_diagram_links(chunks, chunks_by_id):
    """Each "Diagram A" in a clause's text links to that diagram's caption chunk."""
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


def find_outside_references(chunks):
    """Lists each reference to a BWF Statutes section that is not in the corpus."""
    references = []
    for chunk in chunks:
        for section in set(STATUTE_SECTION_REFERENCE.findall(chunk["text"])):
            if section not in SECTIONS_IN_CORPUS:
                references.append({"from_id": chunk["id"], "section": f"BWF Statutes Section {section}"})
    return references


def make_link(from_chunk, to_chunk, relation, evidence):
    """One link record. The evidence is the text or rule that created it, so a wrong link can be traced."""
    return {"from_id": from_chunk["id"], "to_id": to_chunk["id"], "relation": relation, "evidence": evidence}


# ===== Building the whole map =====

def build_rule_links(chunks):
    """Returns every link (without duplicates) and the references outside the corpus."""
    chunks_by_id = {chunk["id"]: chunk for chunk in chunks}
    clause_order = {
        document: [chunk["clause"] for chunk in chunks if chunk["document"] == document]
        for document in ("laws", "itto", "alt")
    }

    all_links = (
        find_override_links(chunks, chunks_by_id)
        + find_citation_links(chunks, chunks_by_id, clause_order)
        + find_para_exception_links(chunks, chunks_by_id)
        + find_diagram_links(chunks, chunks_by_id)
    )

    # A clause can name the same Law twice; keep the first link of each kind
    unique_links = {}
    for link in all_links:
        unique_links.setdefault((link["from_id"], link["to_id"], link["relation"]), link)

    return {"links": list(unique_links.values()), "outside_corpus": find_outside_references(chunks)}


def main() -> None:
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    rule_map = build_rule_links(chunks)

    for relation in ("overrides", "cites", "para_exception_of", "shows_diagram"):
        count = sum(1 for link in rule_map["links"] if link["relation"] == relation)
        print(f"{relation}: {count} links")
    print(f"outside the corpus: {len(rule_map['outside_corpus'])} references")

    LINKS_FILE.write_text(json.dumps(rule_map, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved to {LINKS_FILE.relative_to(PROJECT_FOLDER)}")


if __name__ == "__main__":
    main()
