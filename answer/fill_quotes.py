"""
Turns the model's answer into the checked answer: each citation's sentence number becomes the sentence itself, copied by code.

The model cites a chunk id and a sentence number (answer/answer_shape.py ModelAnswer). Code looks the
sentence up in the clauses the model was shown and copies it in as the quote, so a quote can never be
misquoted or joined from pieces. A citation that can't be filled keeps a quote that says why ("not
shown", "no sentence 4"), so the citation check (answer/check_citations.py) fails it by name instead
of the run losing it.

Use:
    rules_answer = fill_quotes(model_answer, shown_chunk_by_id)
"""

from answer.answer_shape import Citation, ModelAnswer, RulesAnswer
from retrieval.build_bundle import split_sentences


# ===== One citation =====

def quote_for(chunk_id: str, sentence_number: int, shown_chunk_by_id: dict[str, dict]) -> str:
    """Returns the cited sentence, or a note saying why there is none, which the citation check then fails."""

    # A clause the model never saw in full can't be quoted: the citation check names it as not shown
    if chunk_id not in shown_chunk_by_id:
        return f"(not shown: {chunk_id})"

    # Sentence numbers start at 1, as the source blocks print them
    sentences = split_sentences(shown_chunk_by_id[chunk_id]["text"])
    is_real_sentence = 1 <= sentence_number <= len(sentences)
    if not is_real_sentence:
        return f"(no sentence {sentence_number} in {chunk_id})"
    return sentences[sentence_number - 1]


# ===== The whole answer =====

def fill_quotes(model_answer: ModelAnswer, shown_chunk_by_id: dict[str, dict]) -> RulesAnswer:
    """Returns the model's answer with every citation's quote copied in from the sentence it names."""
    citations = []
    for sentence_citation in model_answer.citations:
        quote = quote_for(sentence_citation.chunk_id, sentence_citation.sentence, shown_chunk_by_id)
        citations.append(Citation(chunk_id=sentence_citation.chunk_id, quote=quote))
    return RulesAnswer(
        reasoning=model_answer.reasoning,
        refused=model_answer.refused,
        answer=model_answer.answer,
        citations=citations,
    )
