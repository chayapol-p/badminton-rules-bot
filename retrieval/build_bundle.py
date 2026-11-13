"""
Builds what the model sees for a set of clauses: the bundle. Setup A's sources, search_rules and
read_clause all call build_bundle, so every source block has one format, wherever it comes from.

A bundle is the clauses the rule map brings for the hits (retrieval/expand_with_rule_links.py), each
with its role label and one of three levels of detail:

  full      a source block: the chunk id, the label, where the clause comes from, then its text,
            one numbered sentence per line. The model cites a clause by chunk id and sentence
            number, and code copies the sentence in as the quote, so a quote can never be
            misquoted. The model may cite only what it saw in full.
  preview   one line: the chunk id, the label and the clause's opening words. The model reads the
            whole clause with read_clause when it needs it.
  shown     one line saying the clause was shown earlier for this question, so a tool never sends
            the same text twice.

Setup A sends every clause in full: it has one call and no tools. The tools send the hits and their
list items in full, and every other clause the map brings as a preview, so a tool result stays short
and the model decides which links are worth a read.

Use:
    items = build_bundle(hit_ids, chunks_by_id, rule_map, related_in_full=True)
    sources_text = format_bundle(items)
    citable_chunks = full_chunks(items)
"""

import re

from retrieval.expand_with_rule_links import expand_with_links


# Constants
## The three levels of detail a clause can have in a bundle
FULL = "full"
PREVIEW = "preview"
SHOWN = "shown"

## Where one sentence ends and the next begins: after ".", ";", ":", "!" or "?" and a space. Clauses list
## their items with ";", so each item is a sentence the model can cite alone
SENTENCE_BREAK_PATTERN = re.compile(r"(?<=[.;:!?])\s+")

## How many opening words a preview line holds
PREVIEW_WORD_COUNT = 15

## A parent clause this short, or ending in a colon, only names the subject of the clauses below it
PARENT_HEADING_MAX_WORDS = 5


# ===== Where a clause comes from =====

def describe_source(chunk: dict) -> str:
    """Returns where a clause comes from: document, version and in-force date, format, heading and clause number."""
    parts = [f"{chunk['document_title']} {chunk['version']}, in force {chunk['in_force']}"]

    # Only Alternative Laws clauses have a format, only some clauses are para-only, and introductions have no heading
    if chunk["alternative_format"] is not None:
        parts.append(f"format: {chunk['alternative_format']}")
    if chunk["para_only"]:
        parts.append("Para Badminton only")
    if chunk["heading"]:
        parts.append(chunk["heading"])

    parts.append(f"Clause {chunk['clause']}")
    return " · ".join(parts)


def is_parent_heading(parent_text: str) -> bool:
    """True for a parent clause that only names a subject ("4.2 The stringed area:"), not a rule of its own."""
    return parent_text.endswith(":") or len(parent_text.split()) <= PARENT_HEADING_MAX_WORDS


def parent_headings(chunk: dict) -> str:
    """Returns the headings above this clause, as search_text_with_parents holds them ("4.2 The stringed area:"), or "".

    8 Nov: a full parent rule shown here got quoted as if it were the clause (string-tension quoted Law 4.1
    under 4.1.2), so only parents that name a subject are kept.
    """
    lines_after_header = chunk["search_text_with_parents"].split("\n", 1)[1]
    parents_text = lines_after_header.removesuffix(chunk["text"]).strip()
    headings = []
    for parent_text in parents_text.split(" · "):
        if parent_text and is_parent_heading(parent_text):
            headings.append(parent_text)
    return " · ".join(headings)


# ===== The numbered sentences of a clause =====

def split_sentences(text: str) -> list[str]:
    """Returns a clause's sentences in order; sentence n is item n - 1."""
    return SENTENCE_BREAK_PATTERN.split(text.strip())


def numbered_sentences(text: str) -> str:
    """Returns a clause's sentences one per line, each after its number in brackets: "(1) …"."""
    lines = []
    for sentence_number, sentence in enumerate(split_sentences(text), start=1):
        lines.append(f"({sentence_number}) {sentence}")
    return "\n".join(lines)


# ===== One clause at each level of detail =====

def first_line(chunk_id: str, label: str | None, chunk: dict) -> str:
    """Returns a source block's first line: the chunk id in square brackets, the label if any, and where the clause comes from."""
    label_part = f"{label} · " if label else ""
    return f"[{chunk_id}] {label_part}{describe_source(chunk)}"


def format_source(chunk: dict, label: str | None = None) -> str:
    """Returns one source block: the first line, the headings above the clause, then its numbered sentences."""
    # 8 Nov: clause 4.2.2 reads "shall not exceed 280 mm…"; its subject is in 4.2 ("The stringed area:"), record 0017
    under_line = ""
    headings = parent_headings(chunk)
    if headings:
        under_line = f"Under: {headings}\n"
    return f"{first_line(chunk['id'], label, chunk)}\n{under_line}{numbered_sentences(chunk['text'])}"


def format_preview(chunk: dict, label: str) -> str:
    """Returns one preview line: the chunk id, the label and the clause's opening words."""
    words = chunk["text"].split()
    opening_words = " ".join(words[:PREVIEW_WORD_COUNT])
    if len(words) > PREVIEW_WORD_COUNT:
        opening_words += " …"
    return f"[{chunk['id']}] {label} · preview: {opening_words}"


def format_shown(chunk: dict, label: str) -> str:
    """Returns the line for a clause the model already saw in full for this question."""
    return f"[{chunk['id']}] {label} · shown above"


# ===== The bundle =====

def build_bundle(hit_ids: list[str], chunks_by_id: dict[str, dict], rule_map: dict, related_in_full: bool,
                 shown_ids: set[str] | frozenset[str] = frozenset(), question_is_para: bool = False) -> list[dict]:
    """
    Returns the hits and every clause the rule map brings for them, in prompt order, as
    [{"chunk", "label", "reached_from", "detail"}]. The hits and their list items are always full;
    the other clauses are full when related_in_full, otherwise previews. A clause in shown_ids is "shown".
    """
    items = expand_with_links(hit_ids, chunks_by_id, rule_map, question_is_para=question_is_para)

    # The hits' own list items, at every level: the map adds each item after the heading it hangs from
    hit_and_item_ids = set(hit_ids)
    for item in items:
        is_item_of_a_hit = item["label"] == "LIST ITEM" and item["reached_from"] in hit_and_item_ids
        if is_item_of_a_hit:
            hit_and_item_ids.add(item["chunk"]["id"])

    # Give each clause its level of detail
    for item in items:
        chunk_id = item["chunk"]["id"]
        if chunk_id in shown_ids:
            item["detail"] = SHOWN
        elif related_in_full or chunk_id in hit_and_item_ids:
            item["detail"] = FULL
        else:
            item["detail"] = PREVIEW
    return items


def format_bundle(items: list[dict]) -> str:
    """Returns the bundle as the model reads it: source blocks for full clauses, one line for the others."""
    blocks = []
    for item in items:
        if item["detail"] == FULL:
            blocks.append(format_source(item["chunk"], item["label"]))
        elif item["detail"] == PREVIEW:
            blocks.append(format_preview(item["chunk"], item["label"]))
        else:
            blocks.append(format_shown(item["chunk"], item["label"]))
    return "\n\n".join(blocks)


def full_chunks(items: list[dict]) -> list[dict]:
    """Returns the clauses the bundle shows in full: the only ones the model may cite."""
    return [item["chunk"] for item in items if item["detail"] == FULL]
