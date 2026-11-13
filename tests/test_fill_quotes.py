"""Tests filling quotes: a sentence number becomes the sentence, and a citation code can't fill fails the citation check by name."""

from answer.answer_shape import ModelAnswer, SentenceCitation
from answer.check_citations import find_citation_problems
from answer.fill_quotes import fill_quotes
from retrieval.build_bundle import format_source, split_sentences


# ===== A clause with two sentences, copied from the real data (ITTO 5.4.13, 13 Nov 2026) =====

COACHES_CHUNK = {
    "id": "itto-5.4.13",
    "text": "In all these intervals (Law 16.2.1) each side may be joined on the court by no more than two accredited "
            "Coaches. They must leave the court when the Umpire calls “20 seconds”.",
}
SHOWN_CHUNK_BY_ID = {COACHES_CHUNK["id"]: COACHES_CHUNK}


def answer_citing(*citations: tuple[str, int]) -> ModelAnswer:
    """Returns a model answer that cites these (chunk id, sentence number) pairs."""
    return ModelAnswer(reasoning="", refused=False, answer="Two coaches.",
                       citations=[SentenceCitation(chunk_id=chunk_id, sentence=number) for chunk_id, number in citations])


# ===== Sentences =====

def test_a_clause_splits_into_its_sentences():
    assert split_sentences(COACHES_CHUNK["text"])[1] == "They must leave the court when the Umpire calls “20 seconds”."


def test_list_items_ending_in_a_semicolon_are_sentences_of_their_own():
    assert split_sentences("the server serves; the receiver waits; and play starts.") == [
        "the server serves;", "the receiver waits;", "and play starts."]


def test_a_source_block_numbers_each_sentence_on_its_own_line():
    chunk = {**COACHES_CHUNK, "document_title": "Instructions to Technical Officials", "version": "7.0 (5)",
             "in_force": "2025-04-26", "alternative_format": None, "para_only": False, "heading": "", "clause": "5.4.13",
             "search_text_with_parents": "header\n" + COACHES_CHUNK["text"]}
    assert format_source(chunk).endswith("\n(1) In all these intervals (Law 16.2.1) each side may be joined on the court "
                                         "by no more than two accredited Coaches.\n(2) They must leave the court when the "
                                         "Umpire calls “20 seconds”.")


# ===== Filling quotes =====

def test_a_sentence_number_becomes_that_sentence():
    rules_answer = fill_quotes(answer_citing(("itto-5.4.13", 2)), SHOWN_CHUNK_BY_ID)
    assert rules_answer.citations[0].quote == "They must leave the court when the Umpire calls “20 seconds”."
    assert find_citation_problems(rules_answer, [COACHES_CHUNK]) == []


def test_a_sentence_number_out_of_range_fails_the_citation_check():
    rules_answer = fill_quotes(answer_citing(("itto-5.4.13", 3)), SHOWN_CHUNK_BY_ID)
    assert rules_answer.citations[0].quote == "(no sentence 3 in itto-5.4.13)"
    assert find_citation_problems(rules_answer, [COACHES_CHUNK])[0]["problem"] == "quote not in clause"


def test_a_clause_never_shown_fails_the_citation_check():
    rules_answer = fill_quotes(answer_citing(("laws-16.2.1", 1)), SHOWN_CHUNK_BY_ID)
    assert find_citation_problems(rules_answer, [COACHES_CHUNK])[0]["problem"] == "not retrieved"
