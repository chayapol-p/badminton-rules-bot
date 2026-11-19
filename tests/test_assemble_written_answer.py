"""Tests slice 5's code between and after the two calls: checking picks, the refusal gate, the write call's input and the answer."""

from answer_flows.gather_then_write.answer_shape import GatheredAnswer, GatheredPart, WrittenAnswer
from answer_flows.shared.answer_shape import AnswerSentence, SentenceCitation
from answer_flows.shared.cite_sentences import NO_PARTS_ANSWER
from answer_flows.gather_then_write.assemble_written_answer import (NO_SOURCE_MARK, RELATED_HEADING,
                                                                    assemble_written_answer,
                                                                    build_refusal, check_gathered_picks,
                                                                    format_parts_for_writer, is_refusal)
from evals.checks.check_citations import find_citation_problems
from retrieval.load_rule_chunks import load_chunks


# ===== Real clauses: Law 1.4 (one sentence) and Law 4.2.2 (two sentences, its subject in 4.2's heading) =====

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


def written(*sentences: tuple[bool, str]) -> WrittenAnswer:
    """Returns the write call's sentences, as (is gap, text) pairs."""
    return WrittenAnswer(sentences=[AnswerSentence(is_gap=is_gap, text=text) for is_gap, text in sentences])


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
    """Job's pick, 13 Nov: a bad pick counts as no sentence, so it can't pass the gate."""
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
    """Job's pick, 13 Nov: the related text is a code-quoted sentence, not a model-written note."""
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
    assert part_blocks[0].endswith(f"[1] {POST_HEIGHT_SENTENCE}")
    assert part_blocks[1] == f"Part 2 · the highest string tension allowed\n{NO_SOURCE_MARK}"


def test_a_picked_sentence_keeps_its_subject_from_the_under_line():
    answer = gathered([GatheredPart(asks="the largest stringed area", sentences=picks(("laws-4.2.2", 1)))])
    parts_text = format_parts_for_writer(answer, SHOWN_CHUNK_BY_ID, LABEL_BY_ID)
    assert "[laws-4.2.2] LIST ITEM · " in parts_text
    assert "Under: 4.2 The stringed area:\n[1] shall not exceed 280 mm" in parts_text
    assert "However, the strings" not in parts_text, "only the picked sentence goes to the writer, not sentence 2"


def test_the_writer_sees_related_sentences_numbered_after_the_parts_but_never_the_reasoning():
    """17 Nov: a key fact the gather call filed as related (toss-choices, Law 6.2) never reached the writer."""
    answer = GatheredAnswer(reasoning="SECRET REASONING", parts=TWO_PARTS.parts, related_sentences=picks(("laws-4.2.2", 1)))
    writer_input = format_parts_for_writer(answer, SHOWN_CHUNK_BY_ID, LABEL_BY_ID)
    assert "SECRET REASONING" not in writer_input
    related_block = writer_input.split("\n\n")[-1]
    assert related_block.startswith(RELATED_HEADING)
    assert related_block.endswith(f"[2] {STRINGED_AREA_SENTENCE}")


def test_a_related_sentence_a_part_already_picked_is_not_shown_twice():
    answer = gathered(TWO_PARTS.parts, related=[("laws-1.4", 1)])
    writer_input = format_parts_for_writer(answer, SHOWN_CHUNK_BY_ID, LABEL_BY_ID)
    assert RELATED_HEADING not in writer_input
    assert writer_input.count(POST_HEIGHT_SENTENCE) == 1


def test_picked_sentences_are_numbered_once_in_part_order():
    """Record 0027: the writer sees each picked sentence as [n]; a sentence two parts pick keeps one number."""
    answer = gathered([GatheredPart(asks="the largest stringed area", sentences=picks(("laws-4.2.2", 1))),
                       GatheredPart(asks="how tall the posts are", sentences=picks(("laws-1.4", 1), ("laws-4.2.2", 1)))])
    parts_text = format_parts_for_writer(answer, SHOWN_CHUNK_BY_ID, LABEL_BY_ID)
    assert f"[1] {STRINGED_AREA_SENTENCE}" in parts_text
    assert f"[2] {POST_HEIGHT_SENTENCE}" in parts_text
    assert parts_text.count(f"[1] {STRINGED_AREA_SENTENCE}") == 2, "part 2 shows the shared sentence with its first number"


# ===== The whole answer =====

def test_the_answer_is_one_paragraph_with_a_numbered_source_list_and_related_in_their_own_list():
    answer = gathered(TWO_PARTS.parts, related=[("laws-4.2.2", 1)])
    rules_answer, error_message = assemble_written_answer(
        answer, written((False, "The posts are 1.55 m tall [1]."), (True, "The rules don't say the highest string tension.")),
        SHOWN_CHUNK_BY_ID)
    assert error_message is None
    assert not rules_answer.refused
    assert rules_answer.answer == "The posts are 1.55 m tall [1]. The rules don't say the highest string tension."
    assert [(citation.quote, citation.source_name) for citation in rules_answer.citations] == [
        (POST_HEIGHT_SENTENCE, "Laws of Badminton 5.0 (2), Clause 1.4")]
    assert [citation.quote for citation in rules_answer.related_citations] == [STRINGED_AREA_SENTENCE]
    assert "Related" not in rules_answer.answer, "related rules stay out of the answer text (record 0027)"
    assert [sentence.is_gap for sentence in rules_answer.answer_sentences] == [False, True]
    assert find_citation_problems(rules_answer, list(SHOWN_CHUNK_BY_ID.values())) == []


def test_marker_n_is_the_nth_source_even_when_two_sentences_share_a_clause():
    answer = gathered([GatheredPart(asks="the stringed area and the strings", sentences=picks(("laws-4.2.2", 2), ("laws-4.2.2", 1)))])
    rules_answer, _ = assemble_written_answer(answer, written((False, "Some area [2], some strings [1].")), SHOWN_CHUNK_BY_ID)
    assert rules_answer.citations[1].quote == STRINGED_AREA_SENTENCE
    assert rules_answer.citations[0].quote.startswith("However, the strings")


def test_a_write_reply_with_no_sentence_is_a_format_error():
    rules_answer, error_message = assemble_written_answer(TWO_PARTS, written(), SHOWN_CHUNK_BY_ID)
    assert rules_answer is None
    assert error_message == "write call: no sentences"


def test_a_cited_related_sentence_joins_the_sources_and_an_uncited_one_stays_related():
    """The writer saw [1] Law 1.4 (part), [2] Law 4.2.2 (1) and [3] Law 4.2.2 (2) (related); it cited [1] and [3]."""
    answer = gathered(TWO_PARTS.parts, related=[("laws-4.2.2", 1), ("laws-4.2.2", 2)])
    rules_answer, _ = assemble_written_answer(answer, written((False, "Posts are 1.55 m [1]; strings may run on [3].")),
                                              SHOWN_CHUNK_BY_ID)
    assert rules_answer.answer == "Posts are 1.55 m [1]; strings may run on [2]."
    assert [citation.chunk_id for citation in rules_answer.citations] == ["laws-1.4", "laws-4.2.2"]
    assert rules_answer.citations[1].quote.startswith("However, the strings")
    assert [citation.quote for citation in rules_answer.related_citations] == [STRINGED_AREA_SENTENCE]
    assert find_citation_problems(rules_answer, list(SHOWN_CHUNK_BY_ID.values())) == []


def test_a_marker_past_the_writers_list_stays_past_the_source_list():
    answer = gathered(TWO_PARTS.parts, related=[("laws-4.2.2", 1)])
    rules_answer, _ = assemble_written_answer(answer, written((False, "Posts are 1.55 m [1][9].")), SHOWN_CHUNK_BY_ID)
    problems = find_citation_problems(rules_answer, list(SHOWN_CHUNK_BY_ID.values()))
    assert [problem["problem"] for problem in problems] == ["marker [9] points to no source"]
