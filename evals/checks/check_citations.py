"""
Checks every citation in an answer: was the cited chunk among the ones the model saw, and are the quoted words really in it?

A chunk the model never saw means the citation was invented. A quote that isn't in the clause
means made-up support. Both texts are normalised first (lower case, straight quote marks and
dashes, single spaces), so a curly apostrophe can't fail a true quote. Anything looser would let
a paraphrase pass as a quote.

Since Phase 2 the model cites sentence numbers and code copies each quote in (answer_flows/gather_then_write/assemble_written_answer.py;
experiments/retired_flows/single_call/assemble_answer.py for the retired flows),
so a new answer's quote is always a real sentence. This check still fails the citations code couldn't
fill (a clause not shown, a sentence number out of range), and it re-checks older run files.

A natural answer (record 0027) also has its inline markers checked, sentence by sentence: every marker must be
a source's number in the list, every answer sentence needs at least one, and a gap sentence none. A bad
one fails by name. Bracketed text the rule books print themselves, such as "[name of player(s)]" in a quoted
call, is not a marker (black-card once failed on it).

Use:
    problems = find_citation_problems(rules_answer, retrieved_chunks)
    citations_pass = not problems
    answer_text_for_numbers = remove_markers(rules_answer.answer)
"""

import re

from answer_flows.shared.answer_shape import Citation, RulesAnswer
from answer_flows.shared.inline_markers import MARKER_PATTERN


# Constants
## Curly quote marks and long dashes, and the plain characters they become
## Red-card quoted "..." where ITTO 5.17.4 prints the one-character ellipsis "…"
TYPOGRAPHIC_REPLACEMENTS = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."}

## Any run of spaces, tabs and line breaks
WHITESPACE_PATTERN = re.compile(r"\s+")


# ===== Normalising text before comparing =====

def normalise_text(text: str) -> str:
    """Returns the text in lower case, with straight quote marks and dashes, three dots for "…", and single spaces."""
    for typographic_character, plain_character in TYPOGRAPHIC_REPLACEMENTS.items():
        text = text.replace(typographic_character, plain_character)
    return WHITESPACE_PATTERN.sub(" ", text).strip().lower()


# ===== Checking one citation =====

def find_citation_problem(citation: Citation, retrieved_chunks: list[dict]) -> str | None:
    """Returns what is wrong with one citation, or None when it holds up."""

    # An empty quote is "in" every clause, so it proves nothing
    quote = normalise_text(citation.quote)
    if not quote:
        return "empty quote"

    # Find the cited chunk among the chunks the model was shown
    chunk_by_id = {chunk["id"]: chunk for chunk in retrieved_chunks}
    cited_chunk = chunk_by_id.get(citation.chunk_id)
    if cited_chunk is None:
        return "not retrieved"

    # The quote must be the clause's own words
    quote_is_in_clause = quote in normalise_text(cited_chunk["text"])
    if not quote_is_in_clause:
        return "quote not in clause"
    return None


# ===== Checking the inline markers =====

def remove_markers(text: str) -> str:
    """Returns the text without its inline markers, so a marker's number is never read as a number in the answer."""
    return MARKER_PATTERN.sub("", text)


def is_source_number(marker: str, source_count: int) -> bool:
    """True when a marker's text is the number of a source in the list: 1 up to source_count."""
    if not marker.isdigit():
        return False
    return 1 <= int(marker) <= source_count


def is_quoted_from_sources(marker: str, rules_answer: RulesAnswer) -> bool:
    """True when the bracketed text appears, brackets and all, in one of the answer's quoted sources."""
    bracketed_text = normalise_text(f"[{marker}]")
    for citation in rules_answer.citations + rules_answer.related_citations:
        if bracketed_text in normalise_text(citation.quote):
            return True
    return False


def find_markers(text: str, rules_answer: RulesAnswer) -> list[str]:
    """Returns the inline markers in a sentence, leaving out bracketed text the sources print themselves."""
    markers = []
    for bracketed_text in MARKER_PATTERN.findall(text):
        if not is_quoted_from_sources(bracketed_text, rules_answer):
            markers.append(bracketed_text)
    return markers


def find_marker_problems(rules_answer: RulesAnswer) -> list[dict]:
    """Returns one problem per bad marker and per sentence with the wrong markers: an answer sentence needs one, a gap none."""
    problems = []
    source_count = len(rules_answer.citations)
    for sentence_number, answer_sentence in enumerate(rules_answer.answer_sentences, start=1):
        markers = find_markers(answer_sentence.text, rules_answer)

        # A gap says what the rules don't cover, so no source backs it; every other sentence rests on one
        if answer_sentence.is_gap and markers:
            problems.append({"chunk_id": None, "problem": f"gap sentence {sentence_number} has a marker",
                             "sentence": answer_sentence.text})
        if not answer_sentence.is_gap and not markers:
            problems.append({"chunk_id": None, "problem": f"sentence {sentence_number} has no marker",
                             "sentence": answer_sentence.text})

        # Each marker must point to a source in the numbered list
        for marker in markers:
            if not is_source_number(marker, source_count):
                problems.append({"chunk_id": None, "problem": f"marker [{marker}] points to no source",
                                 "sentence": answer_sentence.text})
    return problems


# ===== Checking a whole answer =====

def find_citation_problems(rules_answer: RulesAnswer, retrieved_chunks: list[dict]) -> list[dict]:
    """Returns one problem per failed citation, with its quote and, for a mismatch, the clause text; plus one when an answer that isn't a refusal cites nothing."""
    chunk_by_id = {chunk["id"]: chunk for chunk in retrieved_chunks}
    problems = []
    # Related sentences are quoted by code too, so their quotes are checked the same way
    for citation in rules_answer.citations + rules_answer.related_citations:
        problem = find_citation_problem(citation, retrieved_chunks)
        if problem is None:
            continue

        # Keep what's needed to debug it: the quote, and for a mismatch, the clause it was checked against
        details = {"chunk_id": citation.chunk_id, "problem": problem, "quote": citation.quote}
        if problem == "quote not in clause":
            details["clause_text"] = chunk_by_id[citation.chunk_id]["text"]
        problems.append(details)

    # An answer must rest on at least one source of its own (related sentences don't count); a refusal may cite nothing
    cites_nothing = not rules_answer.citations
    if cites_nothing and not rules_answer.refused:
        problems.append({"chunk_id": None, "problem": "no citation"})

    # A natural answer's markers; answers without kept sentences (refusals, older flows) have none to check
    problems.extend(find_marker_problems(rules_answer))
    return problems
