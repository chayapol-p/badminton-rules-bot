"""
Checks every citation in an answer: was the cited chunk among the ones the model saw, and are the quoted words really in it?

A chunk the model never saw means the citation was invented. A quote that isn't in the clause
means made-up support. Both texts are normalised first (lower case, straight quote marks and
dashes, single spaces), so a curly apostrophe can't fail a true quote. Anything looser would let
a paraphrase pass as a quote.

Use:
    problems = find_citation_problems(rules_answer, retrieved_chunks)
    citations_pass = not problems
"""

import re

from answer.answer_shape import Citation, RulesAnswer


# Constants
## Curly quote marks and long dashes, and the plain characters they become
## 8 Nov: red-card quoted "..." where ITTO 5.17.4 prints the one-character ellipsis "…"
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


# ===== Checking a whole answer =====

def find_citation_problems(rules_answer: RulesAnswer, retrieved_chunks: list[dict]) -> list[dict]:
    """Returns one problem per failed citation, with its quote and, for a mismatch, the clause text; plus one when an answer that isn't a refusal cites nothing."""
    chunk_by_id = {chunk["id"]: chunk for chunk in retrieved_chunks}
    problems = []
    for citation in rules_answer.citations:
        problem = find_citation_problem(citation, retrieved_chunks)
        if problem is None:
            continue

        # Keep what's needed to debug it: the quote, and for a mismatch, the clause it was checked against
        details = {"chunk_id": citation.chunk_id, "problem": problem, "quote": citation.quote}
        if problem == "quote not in clause":
            details["clause_text"] = chunk_by_id[citation.chunk_id]["text"]
        problems.append(details)

    # An answer must rest on at least one source; a refusal may cite nothing
    cites_nothing = not rules_answer.citations
    if cites_nothing and not rules_answer.refused:
        problems.append({"chunk_id": None, "problem": "no citation"})
    return problems
