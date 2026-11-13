"""
Builds the checked answer from the model's parts: the answer text, the quotes and the refusal are all decided by code.

The model makes one decision per part of the question: which sentences answer it (answer/answer_shape.py
ModelAnswer). From those picks, code:

- copies each cited sentence in as its quote, so a quote can never be misquoted or joined from pieces;
- writes "The sources do not say <part>." for every part with no sentences;
- refuses when no part has a sentence that answers it. Related sentences never count as an answer:
  9-10 Nov, prompt version 2 left this call to the model, which counted nearby rules as an answer and
  missed 4 refusals.

A citation code can't fill keeps a quote that says why ("not shown", "no sentence 4"), so the citation
check (answer/check_citations.py) fails it by name instead of the run losing it.

Use:
    rules_answer = assemble_answer(model_answer, shown_chunk_by_id)
"""

from answer.answer_shape import Citation, ModelAnswer, RulesAnswer, SentenceCitation
from retrieval.build_bundle import split_sentences


# Constants
## The answer when the model names no part at all, so a refusal still says what is missing
NO_PARTS_ANSWER = "The sources do not answer this question."


# ===== One citation =====

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


def add_citations(citations: list[Citation], sentence_citations: list[SentenceCitation],
                  shown_chunk_by_id: dict[str, dict]) -> None:
    """Adds each sentence as a citation with its quote filled in, once, however many parts cite it."""
    for sentence_citation in sentence_citations:
        citation = Citation(chunk_id=sentence_citation.chunk_id,
                            quote=quote_for(sentence_citation.chunk_id, sentence_citation.sentence, shown_chunk_by_id))
        if citation not in citations:
            citations.append(citation)


# ===== The whole answer =====

def assemble_answer(model_answer: ModelAnswer, shown_chunk_by_id: dict[str, dict]) -> RulesAnswer:
    """Returns the checked answer: answered parts first, then a line per part the sources don't answer, then related sentences."""
    answer_lines = []
    not_covered_lines = []
    citations = []

    # Each part: its answer and its sentences, or one line saying the sources don't cover it
    for part in model_answer.parts:
        if part.sentences:
            answer_lines.append(part.answer)
            add_citations(citations, part.sentences, shown_chunk_by_id)
        else:
            not_covered_lines.append(f"The sources do not say {part.asks}.")

    # Refuse when no part is answered; related sentences are context, never an answer
    refused = not answer_lines
    if not model_answer.parts:
        not_covered_lines.append(NO_PARTS_ANSWER)

    # Related sentences come last, cited like the rest
    related_lines = []
    if model_answer.related_sentences:
        related_lines.append(model_answer.related_note)
        add_citations(citations, model_answer.related_sentences, shown_chunk_by_id)

    return RulesAnswer(
        reasoning=model_answer.reasoning,
        refused=refused,
        answer="\n".join(answer_lines + not_covered_lines + related_lines),
        citations=citations,
    )
