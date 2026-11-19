"""Tests the retired per-part flow's code between and after the two calls: checking picks, the refusal gate, the write call's input and the answer."""

from experiments.retired_flows.gather_then_write_per_part.answer_shape import GatheredAnswer, GatheredPart, PartAnswer, WrittenAnswer
from answer_flows.shared.answer_shape import SentenceCitation
from answer_flows.shared.cite_sentences import NO_PARTS_ANSWER
from experiments.retired_flows.gather_then_write_per_part.assemble_written_answer import (NO_SOURCE_MARK, assemble_written_answer,
                                                                    build_refusal, check_gathered_picks,
                                                                    format_parts_for_writer, is_refusal)
from evals.checks.check_citations import find_citation_problems
from retrieval.load_rule_chunks import load_chunks
from tests.rule_data import skip_without_rule_data


# ===== Real clauses: Law 1.4 (one sentence) and Law 4.2.2 (two sentences, its subject in 4.2's heading) =====

# Every test here reads the real clauses, built from the rule books and never committed
skip_without_rule_data()

CHUNK_BY_ID = {chunk["id"]: chunk for chunk in load_chunks()}
SHOWN_CHUNK_BY_ID = {chunk_id: CHUNK_BY_ID[chunk_id] for chunk_id in ["laws-1.4", "laws-4.2.2"]}
LABEL_BY_ID = {"laws-1.4": "RULE", "laws-4.2.2": "LIST ITEM"}
POST_HEIGHT_SENTENCE = CHUNK_BY_ID["laws-1.4"]["text"]
STRINGED_AREA_SENTENCE = "shall not exceed 280 mm in overall length and 220 mm in overall width."


def picks(*citations: tuple[str, int]) -> list[SentenceCitation]:
    """Returns the (chunk id, sentence number) pairs as the gather call sends them."""
    return [SentenceCitation(chunk_id=chunk_id, sentence=number) for chunk_id, number in citations]


def gathered(parts: list[GatheredPart], related: list[tuple[str, int]] = ()) -> GatheredAnswer:
    """Returns a gathered answer with these parts and related sentences."""
    return GatheredAnswer(reasoning="", parts=parts, related_sentences=picks(*related))


def written(*answers: tuple[int, str]) -> WrittenAnswer:
    """Returns the write call's answers, as (part number, answer) pairs."""
    return WrittenAnswer(answers=[PartAnswer(part_number=number, answer=text) for number, text in answers])


## Two parts: the post height is answered, the string tension is not
TWO_PARTS = gathered([GatheredPart(asks="how tall the posts are", sentences=picks(("laws-1.4", 1))),
                      GatheredPart(asks="the highest string tension allowed", sentences=[])])


# ===== Checking the picks =====

def test_a_pick_never_shown_or_past_the_last_sentence_is_dropped_and_recorded():
    answer = gathered([GatheredPart(asks="how tall the posts are",
                                    sentences=picks(("laws-1.4", 1), ("laws-1.4", 2), ("laws-7.4", 1)))])
    checked_answer, bad_picks = check_gathered_picks(answer, SHOWN_CHUNK_BY_ID)
    assert checked_answer.parts[0].sentences == picks(("laws-1.4", 1))
    assert bad_picks == [
        {"where": "part 1", "chunk_id": "laws-1.4", "sentence": 2, "problem": "no sentence 2 in laws-1.4"},
        {"where": "part 1", "chunk_id": "laws-7.4", "sentence": 1, "problem": "not shown: laws-7.4"},
    ]


def test_a_part_whose_only_pick_is_bad_counts_as_unanswered_and_the_gate_refuses():
    """a bad pick counts as no sentence, so it can't pass the gate."""
    answer = gathered([GatheredPart(asks="how tall the posts are", sentences=picks(("laws-7.4", 1)))])
    checked_answer, bad_picks = check_gathered_picks(answer, SHOWN_CHUNK_BY_ID)
    assert is_refusal(checked_answer)
    assert len(bad_picks) == 1


def test_a_bad_related_pick_is_recorded_as_related():
    answer = gathered([GatheredPart(asks="the highest string tension allowed", sentences=[])], related=[("laws-9.9", 1)])
    checked_answer, bad_picks = check_gathered_picks(answer, SHOWN_CHUNK_BY_ID)
    assert checked_answer.related_sentences == []
    assert bad_picks[0]["where"] == "related"


# ===== The gate =====

def test_one_answered_part_passes_the_gate():
    assert not is_refusal(TWO_PARTS)


def test_no_parts_at_all_is_a_refusal_that_says_so():
    refusal = build_refusal(gathered([]), SHOWN_CHUNK_BY_ID)
    assert refusal.refused
    assert refusal.answer == NO_PARTS_ANSWER


def test_a_refusal_quotes_the_related_sentence_word_for_word():
    """the related text is a code-quoted sentence, not a model-written note."""
    answer = gathered([GatheredPart(asks="the highest string tension allowed", sentences=[])], related=[("laws-4.2.2", 1)])
    refusal = build_refusal(answer, SHOWN_CHUNK_BY_ID)
    assert refusal.refused
    assert refusal.answer.split("\n") == [
        "The sources do not say the highest string tension allowed.",
        f'Related (Laws of Badminton 5.0 (2), Clause 4.2.2): "{STRINGED_AREA_SENTENCE}"',
    ]
    assert refusal.citations == [], "a related sentence is never the answer's source (record 0025)"
    assert refusal.related_citations[0].quote == STRINGED_AREA_SENTENCE
    assert find_citation_problems(refusal, list(SHOWN_CHUNK_BY_ID.values())) == []


# ===== The write call's input =====

def test_the_writer_sees_every_part_with_no_source_marked():
    parts_text = format_parts_for_writer(TWO_PARTS, SHOWN_CHUNK_BY_ID, LABEL_BY_ID)
    part_blocks = parts_text.split("\n\n")
    assert part_blocks[0].startswith("Part 1 · how tall the posts are\n[laws-1.4] RULE · Laws of Badminton")
    assert part_blocks[0].endswith(f"(1) {POST_HEIGHT_SENTENCE}")
    assert part_blocks[1] == f"Part 2 · the highest string tension allowed\n{NO_SOURCE_MARK}"


def test_a_picked_sentence_keeps_its_subject_from_the_under_line():
    answer = gathered([GatheredPart(asks="the largest stringed area", sentences=picks(("laws-4.2.2", 1)))])
    parts_text = format_parts_for_writer(answer, SHOWN_CHUNK_BY_ID, LABEL_BY_ID)
    assert "[laws-4.2.2] LIST ITEM · " in parts_text
    assert "Under: 4.2 The stringed area:\n(1) shall not exceed 280 mm" in parts_text
    assert "However, the strings" not in parts_text, "only the picked sentence goes to the writer, not sentence 2"


def test_the_writer_never_sees_the_reasoning_or_the_related_sentences():
    answer = GatheredAnswer(reasoning="SECRET REASONING", parts=TWO_PARTS.parts, related_sentences=picks(("laws-4.2.2", 1)))
    parts_text = format_parts_for_writer(answer, SHOWN_CHUNK_BY_ID, LABEL_BY_ID)
    assert "SECRET REASONING" not in parts_text
    assert "laws-4.2.2" not in parts_text


# ===== The whole answer =====

def test_the_answer_is_the_written_parts_then_the_gap_lines_then_related_quotes():
    answer = gathered(TWO_PARTS.parts, related=[("laws-4.2.2", 1)])
    rules_answer, error_message = assemble_written_answer(answer, written((1, "1.55 metres.")), SHOWN_CHUNK_BY_ID)
    assert error_message is None
    assert not rules_answer.refused
    assert rules_answer.answer.split("\n") == [
        "1.55 metres.",
        "The sources do not say the highest string tension allowed.",
        f'Related (Laws of Badminton 5.0 (2), Clause 4.2.2): "{STRINGED_AREA_SENTENCE}"',
    ]
    assert [citation.quote for citation in rules_answer.citations] == [POST_HEIGHT_SENTENCE]
    assert [citation.quote for citation in rules_answer.related_citations] == [STRINGED_AREA_SENTENCE]


def test_a_missing_answer_for_an_answered_part_is_a_format_error():
    rules_answer, error_message = assemble_written_answer(TWO_PARTS, written(), SHOWN_CHUNK_BY_ID)
    assert rules_answer is None
    assert error_message == "write call: no answer for parts [1]"


def test_an_answer_for_a_no_source_part_is_a_format_error():
    """The writer must not answer a NO SOURCE part: that answer would have no sentence behind it."""
    rules_answer, error_message = assemble_written_answer(TWO_PARTS, written((1, "1.55 metres."), (2, "About 30 lbs.")),
                                                          SHOWN_CHUNK_BY_ID)
    assert rules_answer is None
    assert error_message == "write call: answers for parts with no source or no such part [2]"


def test_two_answers_for_one_part_is_a_format_error():
    rules_answer, error_message = assemble_written_answer(TWO_PARTS, written((1, "1.55 m."), (1, "1.55 metres.")),
                                                          SHOWN_CHUNK_BY_ID)
    assert rules_answer is None
    assert error_message == "write call: more than one answer for parts [1]"
