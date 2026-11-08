"""
Follows the rule map after search, so each answer gets the clauses its hits are linked to.

Search returns the clauses whose words match the question. This step adds, for each hit,
the clauses the rule books link it to (one hop only), and gives every clause a label the
answer model must respect:

- DEFAULT        the standard Law, when an alternative or a para exception exists for it
- RULE           a matched clause with nothing attached
- ALTERNATIVE    an Alternative Laws clause, with its format and in-force status
- PARA EXCEPTION a Para Badminton clause, added only when the question is about para play
- CITED          a clause that another clause names ("dealt with under Law 16.7")
- INSTRUCTIONS   the ITTO clause that instructs the official a Law names (Law 17.3 -> ITTO 7.2)
- DIAGRAM        the caption of a diagram that a clause names
- LIST INTRO     the opening line of a list the hit belongs to ("A shuttle is not in play when:")
- SAME LIST      another item of that list (15.1, 15.2 and 15.3 answer one question together)
- NEIGHBOUR      the clause just before or after the hit (20-all in 7.4, then 29-all in 7.5)

The rule map gives the first six. The last three come from where a clause sits in its
document: the rule books never say "see the next clause", but answers often run on into it.

The order is fixed in code: the default comes before its alternatives and exceptions.
The labels go into the prompt, so the model never has to guess which rule is the default.

Use:
    rule_map = load_rule_map()
    context = expand_with_links(hit_ids, chunks_by_id, rule_map, question_is_para=False)
    prompt_text = format_for_prompt(context)
"""

import json
from datetime import date
from pathlib import Path

from scripts.build_rule_chunks import ALTERNATIVE_FORMAT_NAMES


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
LINKS_FILE = PROJECT_FOLDER / "data" / "rule_links.json"

## How many CITED clauses one hit may bring, so a clause that names ten Laws doesn't flood the prompt
MAX_CITED_PER_HIT = 4

## How many sub-clauses a cited list heading may bring ("Law 16.7" -> 16.7.1, 16.7.2)
MAX_SUB_CLAUSES_PER_CITED = 4

## A clause this short, or ending in a colon, only introduces the clauses below it
LIST_HEADING_MAX_WORDS = 5

## How many items of the hit's list may come along, so a long list doesn't flood the prompt
MAX_LIST_ITEMS = 6

## Short document names for citations
DOCUMENT_NAMES = {"laws": "Laws", "itto": "ITTO", "alt": "Alternative Laws"}


# ===== Loading the map into two lookups =====

def load_rule_map(links_file=LINKS_FILE):
    """Reads rule_links.json and indexes the links by where they start and where they end."""
    saved_map = json.loads(Path(links_file).read_text(encoding="utf-8"))
    return index_links(saved_map["links"], saved_map["outside_corpus"])


def index_links(links, outside_corpus=()):
    """
    Returns {"outgoing": {from_id: [links]}, "incoming": {to_id: [links]},
    "outside": {from_id: [section names]}}.
    """
    outgoing, incoming, outside = {}, {}, {}
    for link in links:
        outgoing.setdefault(link["from_id"], []).append(link)
        incoming.setdefault(link["to_id"], []).append(link)
    for reference in outside_corpus:
        outside.setdefault(reference["from_id"], []).append(reference["section"])
    return {"outgoing": outgoing, "incoming": incoming, "outside": outside}


def linked_ids(rule_map, chunk_id, relation, direction):
    """Ids linked to this chunk by one relation, either "outgoing" (from it) or "incoming" (to it)."""
    end = "to_id" if direction == "outgoing" else "from_id"
    return [link[end] for link in rule_map[direction].get(chunk_id, []) if link["relation"] == relation]


# ===== Finding the clauses below a list heading =====

def is_list_heading(chunk):
    """True for a clause that only introduces its sub-clauses, such as "Intervals:" or "Administration of breach"."""
    text = chunk["text"].strip()
    return text.endswith(":") or len(text.split()) <= LIST_HEADING_MAX_WORDS


def direct_sub_clauses(chunks_by_id, chunk):
    """Ids of the clauses one level below this one (16.7 -> 16.7.1, 16.7.2), in document order."""
    return clauses_below(chunks_by_id, chunk["document"], chunk["clause"])


def clauses_below(chunks_by_id, document, clause_number):
    """Ids of the clauses one level below a clause number, such as "15" -> 15.1, 15.2, 15.3."""
    prefix = f"{document}-{clause_number}."
    depth = clause_number.count(".") + 1
    return [
        chunk_id for chunk_id, other in chunks_by_id.items()
        if chunk_id.startswith(prefix) and other["clause"].count(".") == depth
    ]


# ===== Finding the clauses around a hit =====

def is_list_item(chunk, parent):
    """True when the hit is one item of a list: its parent ends in a colon, or it ends in ";", "or" or "and"."""
    text = chunk["text"].rstrip()
    ends_like_an_item = text.endswith(";") or text.endswith(" or") or text.endswith(" and")
    parent_opens_a_list = parent is not None and parent["text"].rstrip().endswith(":")
    return ends_like_an_item or parent_opens_a_list


def nearby_clauses(chunks_by_id, hit, question_is_para):
    """
    Returns [(chunk id, label)] for the clauses around a hit, in document order:
    for a list item, the list's opening line and the other items; otherwise the clause
    just before and just after it. Alternative Laws and headings get none.
    """
    has_parent = "." in hit["clause"] and hit["document"] != "alt"
    if not has_parent:
        return []

    parent_clause = hit["clause"].rsplit(".", 1)[0]
    parent = chunks_by_id.get(f"{hit['document']}-{parent_clause}")
    sibling_ids = [
        sibling_id for sibling_id in clauses_below(chunks_by_id, hit["document"], parent_clause)
        if question_is_para or not chunks_by_id[sibling_id]["para_only"]
    ]
    if hit["id"] not in sibling_ids:
        return []

    position = sibling_ids.index(hit["id"])

    # A long list (ITTO 5.4 has 15 items) keeps only the items closest to the hit
    if is_list_item(hit, parent):
        list_intro = [(parent["id"], "LIST INTRO")] if parent else []
        first = max(position - MAX_LIST_ITEMS // 2, 0)
        items = [(sibling_id, "SAME LIST") for sibling_id in sibling_ids[first:first + MAX_LIST_ITEMS]]
        return list_intro + items

    neighbour_ids = sibling_ids[max(position - 1, 0):position] + sibling_ids[position + 1:position + 2]
    return [(neighbour_id, "NEIGHBOUR") for neighbour_id in neighbour_ids]


# ===== Labelling a clause =====

def alternative_label(chunk, today):
    """ALTERNATIVE label with the format and whether it is in force on this date."""
    format_name = ALTERNATIVE_FORMAT_NAMES[chunk["alternative_format"]]
    in_force = today >= date.fromisoformat(chunk["in_force"])
    status = f"in force from {chunk['in_force']}" if in_force else f"not in force until {chunk['in_force']}"
    return f"ALTERNATIVE · {format_name} · only by prior arrangement · {status}"


# ===== Expanding search hits through the map =====

def expand_with_links(hit_ids, chunks_by_id, rule_map, question_is_para=False, today=None, include_nearby=True):
    """
    Returns the hits plus their linked clauses, in prompt order, as
    [{"chunk": ..., "label": ..., "reached_from": hit id or None}].
    Each clause appears once, under the first label it was given.
    """
    today = today or date.today()
    context = []
    seen_ids = set()

    def add(chunk_id, label, reached_from=None):
        if chunk_id in seen_ids or chunk_id not in chunks_by_id:
            return
        seen_ids.add(chunk_id)
        context.append({"chunk": chunks_by_id[chunk_id], "label": label, "reached_from": reached_from})

    for hit_id in hit_ids:
        hit = chunks_by_id[hit_id]

        # Find the regular rule this hit belongs to: itself, the Law an alternative replaces,
        # or the regular clause a para exception changes
        if hit["document"] == "alt":
            regular_ids = linked_ids(rule_map, hit_id, "overrides", "outgoing")
        elif hit["para_only"]:
            regular_ids = linked_ids(rule_map, hit_id, "para_exception_of", "outgoing")
        else:
            regular_ids = [hit_id]

        # The regular rule first, then every alternative of it, then its para exceptions
        for regular_id in regular_ids:
            alternative_ids = linked_ids(rule_map, regular_id, "overrides", "incoming")
            para_ids = linked_ids(rule_map, regular_id, "para_exception_of", "incoming")
            shown_para_ids = para_ids if question_is_para else []
            # A para hit is shown even for a regular question: search already chose it
            if hit["para_only"] and hit_id not in shown_para_ids:
                shown_para_ids = [hit_id] + shown_para_ids

            # The regular rule is the DEFAULT when an alternative or a para exception sits beside it
            has_alternative_or_exception = bool(alternative_ids or shown_para_ids)
            regular_label = "DEFAULT" if has_alternative_or_exception else "RULE"
            linked_from = None if regular_id == hit_id else hit_id
            add(regular_id, regular_label, linked_from)
            for alternative_id in alternative_ids:
                add(alternative_id, alternative_label(chunks_by_id[alternative_id], today), regular_id)
            for para_id in shown_para_ids:
                add(para_id, "PARA EXCEPTION", regular_id)

        # A hit with no regular rule (such as a format's intro) still goes in
        add(hit_id, "RULE")

        # The clauses around the hit: the rest of its list, or the clause before and after
        if include_nearby:
            for nearby_id, label in nearby_clauses(chunks_by_id, hit, question_is_para):
                add(nearby_id, label, hit_id)

        # Then what the hit names: cited clauses (not bare headings) and diagrams
        cited_ids = [
            cited_id for cited_id in linked_ids(rule_map, hit_id, "cites", "outgoing")
            if chunks_by_id[cited_id]["text"] != chunks_by_id[cited_id]["heading"]
        ]
        for cited_id in cited_ids[:MAX_CITED_PER_HIT]:
            add(cited_id, "CITED", hit_id)

            # A cited Law brings its alternatives too (ITTO 7.4.1 -> Law 9.1.6 -> the waist rule)
            for alternative_id in linked_ids(rule_map, cited_id, "overrides", "incoming"):
                add(alternative_id, alternative_label(chunks_by_id[alternative_id], today), cited_id)

            # A cited list heading brings the regular clauses below it, where the actual rule is
            cited_chunk = chunks_by_id[cited_id]
            if is_list_heading(cited_chunk):
                sub_clause_ids = [
                    sub_id for sub_id in direct_sub_clauses(chunks_by_id, cited_chunk)
                    if question_is_para or not chunks_by_id[sub_id]["para_only"]
                ]
                for sub_id in sub_clause_ids[:MAX_SUB_CLAUSES_PER_CITED]:
                    add(sub_id, "CITED", cited_id)
        for instruction_id in linked_ids(rule_map, hit_id, "instructions_for", "outgoing"):
            add(instruction_id, "INSTRUCTIONS", hit_id)
        for diagram_id in linked_ids(rule_map, hit_id, "shows_diagram", "outgoing"):
            add(diagram_id, "DIAGRAM", hit_id)

    return context


# ===== Writing the context for the answer model =====

def format_for_prompt(context, rule_map=None):
    """
    One block per clause: a label line with the citation and version, then the clause text.
    With the rule map, it ends with the BWF documents these clauses name but the corpus
    does not hold, so the model can point there instead of guessing (such as Section 4.1.5).
    """
    blocks = []
    for item in context:
        chunk = item["chunk"]
        citation = f"{DOCUMENT_NAMES[chunk['document']]} {chunk['clause']} · V{chunk['version']}"
        blocks.append(f"[{item['label']} · {citation}]\n{chunk['text']}")

    if rule_map:
        outside_sections = sorted({
            section for item in context for section in rule_map["outside"].get(item["chunk"]["id"], [])
        })
        for section in outside_sections:
            blocks.append(f"[NOT IN CORPUS · {section}]\nNamed by the clauses above. Its text is not available.")

    return "\n\n".join(blocks)
