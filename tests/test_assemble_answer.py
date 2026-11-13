"""Tests building the answer from the model's parts: quotes copied by code, a line for each part the sources don't answer, and the refusal."""

from answer_flows.shared.answer_shape import SentenceCitation
from answer_flows.single_call.answer_shape import ModelAnswer, QuestionPart
from answer_flows.shared.cite_sentences import NO_PARTS_ANSWER
from answer_flows.single_call.assemble_answer import assemble_answer
from evals.checks.check_citations import find_citation_problems
from retrieval.build_bundle import format_source, split_sentences


# ===== A clause with two sentences, copied from the real data (ITTO 5.4.13, 13 Nov 2026) =====

COACHES_CHUNK = {
    "id": "itto-5.4.13",
    "text": "In all these intervals (Law 16.2.1) each side may be joined on the court by no more than two accredited "
            "Coaches. They must leave the court when the Umpire calls “20 seconds”.",
}
SHOWN_CHUNK_BY_ID = {COACHES_CHUNK["id"]: COACHES_CHUNK}


def sentences(*citations: tuple[str, int]) -> list[SentenceCitation]:
    """Returns the (chunk id, sentence number) pairs as the model cites them."""
    return [SentenceCitation(chunk_id=chunk_id, sentence=number) for chunk_id, number in citations]


def part(asks: str, answer: str = "", *citations: tuple[str, int]) -> QuestionPart:
    """Returns one part of a question; with no citations, a part the sources don't answer."""
    return QuestionPart(asks=asks, sentences=sentences(*citations), answer=answer)


def model_answer(parts: list[QuestionPart], related: list[tuple[str, int]] = (), related_note: str = "") -> ModelAnswer:
    """Returns a model answer with these parts and related sentences."""
    return ModelAnswer(reasoning="", parts=parts, related_sentences=sentences(*related), related_note=related_note)


def answer_citing(*citations: tuple[str, int]) -> ModelAnswer:
    """Returns a model answer with one part, answered by these sentences."""
    return model_answer([part("how many coaches may join a side", "Two coaches.", *citations)])


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


# ===== Quotes copied by code =====

def test_a_sentence_number_becomes_that_sentence():
    rules_answer = assemble_answer(answer_citing(("itto-5.4.13", 2)), SHOWN_CHUNK_BY_ID)
    assert rules_answer.citations[0].quote == "They must leave the court when the Umpire calls “20 seconds”."
    assert find_citation_problems(rules_answer, [COACHES_CHUNK]) == []


def test_a_sentence_number_out_of_range_fails_the_citation_check():
    rules_answer = assemble_answer(answer_citing(("itto-5.4.13", 3)), SHOWN_CHUNK_BY_ID)
    assert rules_answer.citations[0].quote == "(no sentence 3 in itto-5.4.13)"
    assert find_citation_problems(rules_answer, [COACHES_CHUNK])[0]["problem"] == "quote not in clause"


def test_a_clause_never_shown_fails_the_citation_check():
    rules_answer = assemble_answer(answer_citing(("laws-16.2.1", 1)), SHOWN_CHUNK_BY_ID)
    assert find_citation_problems(rules_answer, [COACHES_CHUNK])[0]["problem"] == "not retrieved"


def test_a_sentence_two_parts_cite_is_one_citation():
    two_parts = model_answer([part("how many coaches", "Two.", ("itto-5.4.13", 1)),
                              part("which interval", "Every interval.", ("itto-5.4.13", 1))])
    assert len(assemble_answer(two_parts, SHOWN_CHUNK_BY_ID).citations) == 1


# ===== The refusal, decided by code =====

def test_an_answered_part_is_an_answer():
    rules_answer = assemble_answer(answer_citing(("itto-5.4.13", 1)), SHOWN_CHUNK_BY_ID)
    assert not rules_answer.refused
    assert rules_answer.answer == "Two coaches."


def test_a_part_with_no_sentences_gets_a_line_saying_the_sources_do_not_say_it():
    """A partial answer stays an answer: one part answered, one not."""
    rules_answer = assemble_answer(model_answer([part("how many coaches", "Two.", ("itto-5.4.13", 1)),
                                                 part("how long the interval lasts")]), SHOWN_CHUNK_BY_ID)
    assert not rules_answer.refused
    assert rules_answer.answer == "Two.\nThe sources do not say how long the interval lasts."


def test_no_answered_part_is_a_refusal_even_with_related_sentences():
    """10 Nov: version 2's model counted nearby rules as an answer and missed 4 refusals; related sentences never count."""
    rules_answer = assemble_answer(model_answer([part("how many coaches a side may have at an exhibition match")],
                                                related=[("itto-5.4.13", 1)],
                                                related_note="In match intervals, at most two coaches may join a side."),
                                   SHOWN_CHUNK_BY_ID)
    assert rules_answer.refused
    assert rules_answer.answer == ("The sources do not say how many coaches a side may have at an exhibition match.\n"
                                   "In match intervals, at most two coaches may join a side.")
    assert rules_answer.citations[0].quote.startswith("In all these intervals")


def test_an_answer_with_no_parts_is_a_refusal_that_says_so():
    rules_answer = assemble_answer(model_answer([]), SHOWN_CHUNK_BY_ID)
    assert rules_answer.refused
    assert rules_answer.answer == NO_PARTS_ANSWER
