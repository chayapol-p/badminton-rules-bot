"""
Turns the model's sentence picks into quotes and citations, for every flow: code copies each cited sentence
in, so a quote can never be misquoted or joined from pieces. A pick code can't quote (a clause not shown
in full, or no such sentence) gets a note saying why, which the citation check then fails by name.

Use:
    problem = find_pick_problem(chunk_id, sentence_number, shown_chunk_by_id)
    add_citations(citations, sentence_citations, shown_chunk_by_id)
    citation = build_named_citation(sentence_citation, shown_chunk_by_id)
    source_name = name_source(chunk)
"""

from answer_flows.shared.answer_shape import Citation, SentenceCitation
from retrieval.build_bundle import split_sentences


# Constants
## The answer when the model names no part at all, so a refusal still says what is missing
NO_PARTS_ANSWER = "The sources do not answer this question."


# ===== One citation =====

def name_source(chunk: dict) -> str:
    """Returns the document, version and clause a chunk comes from, such as "Laws of Badminton 5.0 (2), Clause 1.4"."""
    return f"{chunk['document_title']} {chunk['version']}, Clause {chunk['clause']}"


def find_pick_problem(chunk_id: str, sentence_number: int, shown_chunk_by_id: dict[str, dict]) -> str | None:
    """Returns why a cited sentence can't be quoted ("not shown: …", "no sentence 4 in …"), or None when it can."""

    # A clause the model never saw in full can't be quoted
    if chunk_id not in shown_chunk_by_id:
        return f"not shown: {chunk_id}"

    # Sentence numbers start at 1, as the source blocks print them
    sentence_count = len(split_sentences(shown_chunk_by_id[chunk_id]["text"]))
    is_real_sentence = 1 <= sentence_number <= sentence_count
    if not is_real_sentence:
        return f"no sentence {sentence_number} in {chunk_id}"
    return None


def quote_for(chunk_id: str, sentence_number: int, shown_chunk_by_id: dict[str, dict]) -> str:
    """Returns the cited sentence, or a note saying why there is none, which the citation check then fails."""
    problem = find_pick_problem(chunk_id, sentence_number, shown_chunk_by_id)
    if problem is not None:
        return f"({problem})"
    return split_sentences(shown_chunk_by_id[chunk_id]["text"])[sentence_number - 1]


def build_named_citation(sentence_citation: SentenceCitation, shown_chunk_by_id: dict[str, dict]) -> Citation:
    """Returns one picked sentence as a citation with its quote copied in and the name of its source (record 0027).
    Only for picks code already checked, so the chunk was shown."""
    chunk = shown_chunk_by_id[sentence_citation.chunk_id]
    quote = quote_for(sentence_citation.chunk_id, sentence_citation.sentence, shown_chunk_by_id)
    return Citation(chunk_id=sentence_citation.chunk_id, quote=quote, source_name=name_source(chunk))


def add_citations(citations: list[Citation], sentence_citations: list[SentenceCitation],
                  shown_chunk_by_id: dict[str, dict]) -> None:
    """Adds each sentence as a citation with its quote filled in, once, however many parts cite it."""
    for sentence_citation in sentence_citations:
        citation = Citation(chunk_id=sentence_citation.chunk_id,
                            quote=quote_for(sentence_citation.chunk_id, sentence_citation.sentence, shown_chunk_by_id))
        if citation not in citations:
            citations.append(citation)
