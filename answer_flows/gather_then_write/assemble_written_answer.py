"""
Slice 5's code between and after the two calls: checks the gather call's picks, decides the refusal,
builds the write call's input, and builds the checked answer from both calls.

The flow (answer_flows/gather_then_write/gather_then_write.py runs it):
1. The gather call (tools) sends GatheredAnswer: the sentences that answer each part, no answer text.
2. Code checks each pick. A bad pick (a clause never shown in full, or no such sentence) is dropped, so its part
   counts as unanswered, and it is recorded by name in bad_picks, so the run counts it apart from
   false refusals (Job's pick, 13 Nov).
3. The gate: when no part has a sentence left, code refuses and the write call never runs. The refusal says
   what the sources don't say, and quotes the related sentences word for word (Job's pick, 13 Nov:
   code-quoted, not a model-written note).
4. Otherwise the write call (no tools) gets a clean input: the question and every part, an unanswered part
   marked NO SOURCE, an answered part with its sentences under their label and Under: line.
5. Code builds the answer: each answered part's written answer, then a line per NO SOURCE part, then
   the related sentences, quoted. Every quote is copied by code, as in slice 4.

Use:
    checked_answer, bad_picks = check_gathered_picks(gathered_answer, shown_chunk_by_id)
    if is_refusal(checked_answer):
        rules_answer = build_refusal(checked_answer, shown_chunk_by_id)
    else:
        writer_input = format_parts_for_writer(checked_answer, shown_chunk_by_id, label_by_id)
        rules_answer, error_message = assemble_written_answer(checked_answer, written_answer, shown_chunk_by_id)
"""

from collections import Counter

from answer_flows.gather_then_write.answer_shape import GatheredAnswer, GatheredPart, WrittenAnswer
from answer_flows.shared.answer_shape import RulesAnswer, SentenceCitation
from answer_flows.shared.cite_sentences import NO_PARTS_ANSWER, add_citations, find_pick_problem, quote_for
from retrieval.build_bundle import first_line, parent_headings, split_sentences


# Constants
## The mark the write call sees on a part no sentence answers
NO_SOURCE_MARK = "NO SOURCE"


# ===== Checking the gather call's picks =====

def keep_valid_picks(sentence_citations: list[SentenceCitation], shown_chunk_by_id: dict[str, dict], where: str,
                     bad_picks: list[dict]) -> list[SentenceCitation]:
    """Returns the picks code can quote; adds every other pick to bad_picks with where it was and why it is bad."""
    valid_picks = []
    for sentence_citation in sentence_citations:
        problem = find_pick_problem(sentence_citation.chunk_id, sentence_citation.sentence, shown_chunk_by_id)
        if problem is None:
            valid_picks.append(sentence_citation)
        else:
            bad_picks.append({"where": where, "chunk_id": sentence_citation.chunk_id,
                              "sentence": sentence_citation.sentence, "problem": problem})
    return valid_picks


def check_gathered_picks(gathered_answer: GatheredAnswer,
                         shown_chunk_by_id: dict[str, dict]) -> tuple[GatheredAnswer, list[dict]]:
    """Returns the gathered answer with only the picks code can quote, and the bad picks it dropped."""
    bad_picks = []

    # Each part keeps its valid picks; a part left with none counts as unanswered
    checked_parts = []
    for part_number, part in enumerate(gathered_answer.parts, start=1):
        valid_picks = keep_valid_picks(part.sentences, shown_chunk_by_id, f"part {part_number}", bad_picks)
        checked_parts.append(GatheredPart(asks=part.asks, sentences=valid_picks))

    # Related sentences are checked the same way
    related_picks = keep_valid_picks(gathered_answer.related_sentences, shown_chunk_by_id, "related", bad_picks)
    checked_answer = GatheredAnswer(reasoning=gathered_answer.reasoning, parts=checked_parts,
                                    related_sentences=related_picks)
    return checked_answer, bad_picks


# ===== The gate =====

def is_refusal(checked_answer: GatheredAnswer) -> bool:
    """True when no part has a sentence that answers it: code refuses, and the write call never runs."""
    return not any(part.sentences for part in checked_answer.parts)


# ===== The lines code writes =====

def build_not_covered_lines(checked_answer: GatheredAnswer) -> list[str]:
    """Returns one "The sources do not say …" line per unanswered part, or one line when the model named no part."""
    if not checked_answer.parts:
        return [NO_PARTS_ANSWER]
    lines = []
    for part in checked_answer.parts:
        if not part.sentences:
            lines.append(f"The sources do not say {part.asks}.")
    return lines


def build_related_lines(checked_answer: GatheredAnswer, shown_chunk_by_id: dict[str, dict]) -> list[str]:
    """Returns one line per related sentence, quoted word for word by code, with the document and clause it comes from."""
    lines = []
    for sentence_citation in checked_answer.related_sentences:
        chunk = shown_chunk_by_id[sentence_citation.chunk_id]
        source_name = f"{chunk['document_title']} {chunk['version']}, Clause {chunk['clause']}"
        quote = quote_for(sentence_citation.chunk_id, sentence_citation.sentence, shown_chunk_by_id)
        lines.append(f"Related ({source_name}): \"{quote}\"")
    return lines


# ===== A refusal =====

def build_refusal(checked_answer: GatheredAnswer, shown_chunk_by_id: dict[str, dict]) -> RulesAnswer:
    """Returns the refusal code writes: what the sources don't say, then the related sentences, quoted."""
    citations = []
    add_citations(citations, checked_answer.related_sentences, shown_chunk_by_id)
    answer_lines = build_not_covered_lines(checked_answer) + build_related_lines(checked_answer, shown_chunk_by_id)
    return RulesAnswer(reasoning=checked_answer.reasoning, refused=True, answer="\n".join(answer_lines),
                       citations=citations)


# ===== The write call's input =====

def format_picked_sentences(sentence_citations: list[SentenceCitation], shown_chunk_by_id: dict[str, dict],
                            label_by_id: dict[str, str]) -> str:
    """Returns one part's sentences, grouped by clause: the clause's first line, its Under: line, then each sentence."""
    blocks = []
    sentences_by_chunk_id = {}
    for sentence_citation in sentence_citations:
        sentences_by_chunk_id.setdefault(sentence_citation.chunk_id, []).append(sentence_citation.sentence)

    # One block per clause, so a sentence like "shall not exceed 280 mm" keeps its subject from the Under: line
    for chunk_id, sentence_numbers in sentences_by_chunk_id.items():
        chunk = shown_chunk_by_id[chunk_id]
        block_lines = [first_line(chunk_id, label_by_id.get(chunk_id), chunk)]
        headings = parent_headings(chunk)
        if headings:
            block_lines.append(f"Under: {headings}")
        sentences = split_sentences(chunk["text"])
        for sentence_number in sentence_numbers:
            block_lines.append(f"({sentence_number}) {sentences[sentence_number - 1]}")
        blocks.append("\n".join(block_lines))
    return "\n\n".join(blocks)


def format_parts_for_writer(checked_answer: GatheredAnswer, shown_chunk_by_id: dict[str, dict],
                            label_by_id: dict[str, str]) -> str:
    """Returns every part as the write call reads it: numbered, then its sentences or NO SOURCE."""
    part_blocks = []
    for part_number, part in enumerate(checked_answer.parts, start=1):
        part_text = NO_SOURCE_MARK
        if part.sentences:
            part_text = format_picked_sentences(part.sentences, shown_chunk_by_id, label_by_id)
        part_blocks.append(f"Part {part_number} · {part.asks}\n{part_text}")
    return "\n\n".join(part_blocks)


# ===== The whole answer =====

def find_written_answer_problem(answered_part_numbers: list[int], written_answer: WrittenAnswer) -> str | None:
    """Returns why the written answers don't match the answered parts one to one, or None when they do."""
    written_part_numbers = [part_answer.part_number for part_answer in written_answer.answers]
    missing = [number for number in answered_part_numbers if number not in written_part_numbers]
    not_answerable = [number for number in written_part_numbers if number not in answered_part_numbers]
    answer_count_by_part_number = Counter(written_part_numbers)
    repeated = sorted(number for number, answer_count in answer_count_by_part_number.items() if answer_count > 1)
    problems = []
    if missing:
        problems.append(f"no answer for parts {missing}")
    if not_answerable:
        problems.append(f"answers for parts with no source or no such part {not_answerable}")
    if repeated:
        problems.append(f"more than one answer for parts {repeated}")
    if problems:
        return "write call: " + "; ".join(problems)
    return None


def assemble_written_answer(checked_answer: GatheredAnswer, written_answer: WrittenAnswer,
                            shown_chunk_by_id: dict[str, dict]) -> tuple[RulesAnswer | None, str | None]:
    """Returns the checked answer built from both calls, or None and the reason when the written answers don't match the parts."""
    answered_part_numbers = []
    for part_number, part in enumerate(checked_answer.parts, start=1):
        if part.sentences:
            answered_part_numbers.append(part_number)

    # Every answered part needs exactly one written answer, and a NO SOURCE part none: anything else is a format error
    problem = find_written_answer_problem(answered_part_numbers, written_answer)
    if problem is not None:
        return None, problem

    # Answered parts in part order, each with its sentences cited and quoted by code
    answer_by_part_number = {part_answer.part_number: part_answer.answer for part_answer in written_answer.answers}
    answer_lines = []
    citations = []
    for part_number in answered_part_numbers:
        answer_lines.append(answer_by_part_number[part_number])
        add_citations(citations, checked_answer.parts[part_number - 1].sentences, shown_chunk_by_id)

    # Then the lines code writes: what the sources don't say, and the related sentences, quoted
    add_citations(citations, checked_answer.related_sentences, shown_chunk_by_id)
    answer_lines += build_not_covered_lines(checked_answer) + build_related_lines(checked_answer, shown_chunk_by_id)
    rules_answer = RulesAnswer(reasoning=checked_answer.reasoning, refused=False, answer="\n".join(answer_lines),
                               citations=citations)
    return rules_answer, None
