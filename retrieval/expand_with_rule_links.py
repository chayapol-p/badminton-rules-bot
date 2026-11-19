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
- LIST ITEM      an item under a list heading the context holds, at every level (16.7.1 -> 16.7.1.1)

The rule map gives the first six. LIST ITEM comes from where a clause sits in its document.

A clause is either a rule to apply or context. Context is the regular rule shown beside the
alternative or para exception that search found, or an alternative reached through a cited Law
(the one second hop): it comes as one line, without its items.

The order is fixed in code: the default comes before its alternatives and exceptions.
The labels go into the prompt (retrieval/build_bundle.py writes them on each source block), so the
model never has to guess which rule is the default.

Use:
    rule_map = load_rule_map()
    context = expand_with_links(hit_ids, chunks_by_id, rule_map, question_is_para=False)
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

## A clause this short, or ending in a colon, only introduces the clauses below it
LIST_HEADING_MAX_WORDS = 5


# ===== Loading the map into two lookups =====

def load_rule_map(links_file=LINKS_FILE):
    """Reads rule_links.json and indexes the links by where they start and where they end."""
    saved_map = json.loads(Path(links_file).read_text(encoding="utf-8"))
    return index_links(saved_map["links"])


def index_links(links):
    """Returns {"outgoing": {from_id: [links]}, "incoming": {to_id: [links]}}."""
    outgoing, incoming = {}, {}
    for link in links:
        outgoing.setdefault(link["from_id"], []).append(link)
        incoming.setdefault(link["to_id"], []).append(link)
    return {"outgoing": outgoing, "incoming": incoming}


def linked_ids(rule_map, chunk_id, relation, direction):
    """Ids linked to this chunk by one relation, either "outgoing" (from it) or "incoming" (to it)."""
    end = "to_id" if direction == "outgoing" else "from_id"
    return [link[end] for link in rule_map[direction].get(chunk_id, []) if link["relation"] == relation]


# ===== Finding the clauses below a list heading =====

def is_list_heading(chunk):
    """True for a clause that only introduces its sub-clauses, such as "Intervals:" or "Administration of breach"."""
    text = chunk["text"].strip()
    return text.endswith(":") or len(text.split()) <= LIST_HEADING_MAX_WORDS


def direct_sub_clauses(chunks_by_id: dict[str, dict], parent_id: str) -> list[str]:
    """Ids of the clauses one level below a clause id (laws-16.7 -> laws-16.7.1, laws-16.7.2), in document order."""
    # Matched on the id, not on the document and clause number: an Alternative Laws id holds its format
    # ("alt-best-of-3-games-21:16.2.1"), so the old "alt-16.2." prefix never matched (7 headings lost their items)
    prefix = f"{parent_id}."
    sub_clause_ids = []
    for chunk_id in chunks_by_id:
        is_one_level_below = chunk_id.startswith(prefix) and "." not in chunk_id.removeprefix(prefix)
        if is_one_level_below:
            sub_clause_ids.append(chunk_id)
    return sub_clause_ids


# ===== Bringing every level of a list =====

def brings_its_items(chunk: dict, is_hit: bool, is_context: bool, question_is_para: bool) -> bool:
    """True for a list heading whose items should come: one that is a rule to apply, not context for another clause."""
    # Context (the kinds are listed at the top of this file) comes as one line: wheelchair-shuttle-on-net
    # got Law 13.3's nine regular faults only because the wheelchair rule 13.3.10 is its para exception
    if not is_list_heading(chunk) or is_context:
        return False

    # A para heading reached through a link stays bare for a regular question; one search found comes whole
    return is_hit or question_is_para or not chunk["para_only"]


def add_list_items(context: list[dict], hit_ids: set[str], context_ids: set[str], chunks_by_id: dict[str, dict],
                   question_is_para: bool) -> list[dict]:
    """Returns the context with each list heading's items added after it, down every level (16.7.1 -> 16.7.1.1)."""
    # Before this, only a heading search found brought its items, so sweat-on-court got Law 16.7.1 ("... by:")
    # without its three steps, and every-let-situation got 14.2.3 ("the shuttle is:") without its two cases
    expanded_context = list(context)
    seen_ids = {item["chunk"]["id"] for item in context}

    # A for loop over a list that grows: an item that is itself a heading is reached later in the same loop,
    # so every level is covered without a separate recursive call
    for item in expanded_context:
        chunk = item["chunk"]
        is_hit = chunk["id"] in hit_ids
        if not brings_its_items(chunk, is_hit, chunk["id"] in context_ids, question_is_para):
            continue

        # A heading search found brings every item; one reached another way skips para-only items for a regular question
        for item_id in direct_sub_clauses(chunks_by_id, chunk["id"]):
            is_unwanted_para_item = chunks_by_id[item_id]["para_only"] and not (is_hit or question_is_para)
            if item_id in seen_ids or is_unwanted_para_item:
                continue
            expanded_context.append({"chunk": chunks_by_id[item_id], "label": "LIST ITEM", "reached_from": chunk["id"]})
            seen_ids.add(item_id)
    return expanded_context


# ===== Labelling a clause =====

def alternative_label(chunk, today):
    """ALTERNATIVE label with the format and whether it is in force on this date."""
    format_name = ALTERNATIVE_FORMAT_NAMES[chunk["alternative_format"]]
    in_force = today >= date.fromisoformat(chunk["in_force"])
    status = f"in force from {chunk['in_force']}" if in_force else f"not in force until {chunk['in_force']}"
    return f"ALTERNATIVE · {format_name} · only by prior arrangement · {status}"


# ===== Expanding search hits through the map =====

def expand_with_links(hit_ids, chunks_by_id, rule_map, question_is_para=False, today=None):
    """
    Returns the hits plus their linked clauses and their list items, in prompt order, as
    [{"chunk": ..., "label": ..., "reached_from": hit id or None}].
    Each clause appears once, under the first label it was given.
    """
    today = today or date.today()
    context = []
    seen_ids = set()

    # Clauses added only as context: the regular rule beside the alternative or para exception search
    # found, and a cited Law's alternatives
    context_ids = set()

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
            if linked_from is not None:
                context_ids.add(regular_id)
            for alternative_id in alternative_ids:
                add(alternative_id, alternative_label(chunks_by_id[alternative_id], today), regular_id)
            for para_id in shown_para_ids:
                add(para_id, "PARA EXCEPTION", regular_id)

        # A hit with no regular rule (such as a format's intro) still goes in
        add(hit_id, "RULE")

        # Then what the hit names: cited clauses (not bare headings) and diagrams
        cited_ids = [
            cited_id for cited_id in linked_ids(rule_map, hit_id, "cites", "outgoing")
            if chunks_by_id[cited_id]["text"] != chunks_by_id[cited_id]["heading"]
        ]
        for cited_id in cited_ids[:MAX_CITED_PER_HIT]:
            add(cited_id, "CITED", hit_id)

            # A cited Law brings its alternatives too (ITTO 7.4.1 -> Law 9.1.6 -> the waist rule). This second hop
            # is context: Law 16.2's alternatives brought other formats' interval rules to card questions
            for alternative_id in linked_ids(rule_map, cited_id, "overrides", "incoming"):
                add(alternative_id, alternative_label(chunks_by_id[alternative_id], today), cited_id)
                context_ids.add(alternative_id)

        for instruction_id in linked_ids(rule_map, hit_id, "instructions_for", "outgoing"):
            add(instruction_id, "INSTRUCTIONS", hit_id)
        for diagram_id in linked_ids(rule_map, hit_id, "shows_diagram", "outgoing"):
            add(diagram_id, "DIAGRAM", hit_id)

    # Then the items of every list heading that is a rule to apply; a clause search found is never context
    return add_list_items(context, set(hit_ids), context_ids.difference(hit_ids), chunks_by_id, question_is_para)
