"""
The gather-then-write code between and after the two calls: checks the gather call's picks, decides the refusal,
builds the write call's input, and builds the checked answer from both calls.

The flow (answer_flows/gather_then_write/gather_then_write.py runs it):
1. The gather call (tools) sends GatheredAnswer: the sentences that answer each part, no answer text.
2. Code checks each pick. A bad pick (a clause never shown in full, or no such sentence) is dropped, so its part
   counts as unanswered, and it is recorded by name in bad_picks, so the run counts it apart from
   false refusals.
3. The gate: when no part has a sentence left, code refuses and the write call never runs. The refusal says
   what the sources don't say, and quotes the related sentences word for word
   (quoted by code, not a note the model writes).
4. Otherwise the write call (no tools) gets a clean input: the question and every part, an unanswered part
   marked NO SOURCE, an answered part with its sentences under their label and Under: line, then the
   related sentences under their own heading. Every sentence is numbered [1]…[n] once: the parts' sentences
   in part order, then the related ones (record 0027; related sentences were added after runs where a key fact
   sat in related and never reached the writer).
5. Code builds the answer: the write call's sentences joined into one paragraph with their [n] markers, the
   numbered source list (marker [n] is citations[n - 1]) and the related sentences in their own list. A related
   sentence the writer cited joins the source list after the parts' sentences, and its markers are renumbered;
   one it didn't cite stays related. Every quote is copied by code. The model writes the gaps
   itself; the citation check (evals/checks/check_citations.py) checks every marker.

Use:
    checked_answer, bad_picks = check_gathered_picks(gathered_answer, shown_chunk_by_id)
    if is_refusal(checked_answer):
        rules_answer = build_refusal(checked_answer, shown_chunk_by_id)
    else:
        writer_input = format_parts_for_writer(checked_answer, shown_chunk_by_id, label_by_id)
        rules_answer, error_message = assemble_written_answer(checked_answer, written_answer, shown_chunk_by_id)
"""

from answer_flows.gather_then_write.answer_shape import GatheredAnswer, GatheredPart, WrittenAnswer
from answer_flows.shared.answer_shape import AnswerSentence, Citation, RulesAnswer, SentenceCitation
from answer_flows.shared.cite_sentences import (NO_PARTS_ANSWER, add_citations, build_named_citation, find_pick_problem,
                                                name_source, quote_for)
from answer_flows.shared.inline_markers import find_marker_numbers, renumber_markers
from retrieval.build_bundle import first_line, parent_headings, split_sentences


# Constants
## The mark the write call sees on a part no sentence answers
NO_SOURCE_MARK = "NO SOURCE"

## The heading above the related sentences in the write call's input
RELATED_HEADING = "Related · sentences that bear on the question without answering a part"


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
        source_name = name_source(shown_chunk_by_id[sentence_citation.chunk_id])
        quote = quote_for(sentence_citation.chunk_id, sentence_citation.sentence, shown_chunk_by_id)
        lines.append(f"Related ({source_name}): \"{quote}\"")
    return lines


# ===== A refusal =====

def build_refusal(checked_answer: GatheredAnswer, shown_chunk_by_id: dict[str, dict]) -> RulesAnswer:
    """Returns the refusal code writes: what the sources don't say, then the related sentences, quoted."""
    related_citations = []
    add_citations(related_citations, checked_answer.related_sentences, shown_chunk_by_id)
    answer_lines = build_not_covered_lines(checked_answer) + build_related_lines(checked_answer, shown_chunk_by_id)
    return RulesAnswer(reasoning=checked_answer.reasoning, refused=True, refusal_kind="not_covered",
                       answer="\n".join(answer_lines), citations=[], related_citations=related_citations)


# ===== Numbering the sentences the writer sees =====

def number_picked_sentences(checked_answer: GatheredAnswer) -> dict[tuple[str, int], int]:
    """Returns each picked sentence's marker number, from 1, in part order; a sentence two parts pick keeps one number."""
    number_by_pick = {}
    for part in checked_answer.parts:
        for sentence_citation in part.sentences:
            pick = (sentence_citation.chunk_id, sentence_citation.sentence)
            if pick not in number_by_pick:
                number_by_pick[pick] = len(number_by_pick) + 1
    return number_by_pick


def find_related_only(checked_answer: GatheredAnswer) -> list[SentenceCitation]:
    """Returns the related sentences no part picked, once each, in the gather call's order."""
    part_number_by_pick = number_picked_sentences(checked_answer)
    related_only = []
    seen_picks = set()
    for sentence_citation in checked_answer.related_sentences:
        pick = (sentence_citation.chunk_id, sentence_citation.sentence)
        if pick in part_number_by_pick or pick in seen_picks:
            continue
        seen_picks.add(pick)
        related_only.append(sentence_citation)
    return related_only


def number_writer_sentences(checked_answer: GatheredAnswer) -> dict[tuple[str, int], int]:
    """Returns the marker number of every sentence the writer sees: the parts' sentences first, then the related ones."""
    number_by_pick = number_picked_sentences(checked_answer)
    for sentence_citation in find_related_only(checked_answer):
        number_by_pick[(sentence_citation.chunk_id, sentence_citation.sentence)] = len(number_by_pick) + 1
    return number_by_pick


# ===== The write call's input =====

def format_picked_sentences(sentence_citations: list[SentenceCitation], shown_chunk_by_id: dict[str, dict],
                            label_by_id: dict[str, str], number_by_pick: dict[tuple[str, int], int]) -> str:
    """Returns sentences grouped by clause: the clause's first line, its Under: line, then each sentence with its [n]."""
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
            marker_number = number_by_pick[(chunk_id, sentence_number)]
            block_lines.append(f"[{marker_number}] {sentences[sentence_number - 1]}")
        blocks.append("\n".join(block_lines))
    return "\n\n".join(blocks)


def format_parts_for_writer(checked_answer: GatheredAnswer, shown_chunk_by_id: dict[str, dict],
                            label_by_id: dict[str, str]) -> str:
    """Returns what the write call reads: every part with its numbered sentences or NO SOURCE, then the related sentences."""
    number_by_pick = number_writer_sentences(checked_answer)
    blocks = []
    for part_number, part in enumerate(checked_answer.parts, start=1):
        part_text = NO_SOURCE_MARK
        if part.sentences:
            part_text = format_picked_sentences(part.sentences, shown_chunk_by_id, label_by_id, number_by_pick)
        blocks.append(f"Part {part_number} · {part.asks}\n{part_text}")

    # The related sentences come last, so a key fact the gather call filed there still reaches the writer
    related_only = find_related_only(checked_answer)
    if related_only:
        related_text = format_picked_sentences(related_only, shown_chunk_by_id, label_by_id, number_by_pick)
        blocks.append(f"{RELATED_HEADING}\n{related_text}")
    return "\n\n".join(blocks)


# ===== The whole answer =====

def find_cited_numbers(written_answer: WrittenAnswer) -> set[int]:
    """Returns every marker number the write call used."""
    cited_numbers = set()
    for answer_sentence in written_answer.sentences:
        cited_numbers.update(find_marker_numbers(answer_sentence.text))
    return cited_numbers


def build_named_citations(picks: list[tuple[str, int]], shown_chunk_by_id: dict[str, dict]) -> list[Citation]:
    """Returns one citation per (chunk id, sentence number), in order and never merged, so positions match the markers."""
    citations = []
    for chunk_id, sentence_number in picks:
        sentence_citation = SentenceCitation(chunk_id=chunk_id, sentence=sentence_number)
        citations.append(build_named_citation(sentence_citation, shown_chunk_by_id))
    return citations


def assemble_written_answer(checked_answer: GatheredAnswer, written_answer: WrittenAnswer,
                            shown_chunk_by_id: dict[str, dict]) -> tuple[RulesAnswer | None, str | None]:
    """Returns the answer built from both calls with its numbered source list, or None and the reason when the write call wrote no sentence."""

    # A reply with no sentence has nothing to show or check: a format error
    if not written_answer.sentences:
        return None, "write call: no sentences"

    # The source list: every part sentence keeps its number; a related sentence joins after them only when cited
    writer_number_by_pick = number_writer_sentences(checked_answer)
    source_picks = list(number_picked_sentences(checked_answer))
    part_sentence_count = len(source_picks)
    cited_numbers = find_cited_numbers(written_answer)
    new_number_by_old = {}
    uncited_related_picks = []
    for pick, writer_number in writer_number_by_pick.items():
        is_part_sentence = writer_number <= part_sentence_count
        if is_part_sentence:
            continue
        if writer_number in cited_numbers:
            source_picks.append(pick)
            new_number_by_old[writer_number] = len(source_picks)
        else:
            uncited_related_picks.append(pick)

    # Markers follow their sentence into the source list; a marker past the list stays past it, so the check fails it
    answer_sentences = []
    for answer_sentence in written_answer.sentences:
        answer_sentences.append(AnswerSentence(is_gap=answer_sentence.is_gap,
                                               text=renumber_markers(answer_sentence.text, new_number_by_old)))
    answer_text = " ".join(answer_sentence.text for answer_sentence in answer_sentences)

    # Every quote copied by code: the numbered sources, then the related sentences the writer didn't cite
    citations = build_named_citations(source_picks, shown_chunk_by_id)
    related_citations = build_named_citations(uncited_related_picks, shown_chunk_by_id)
    rules_answer = RulesAnswer(reasoning=checked_answer.reasoning, refused=False, answer=answer_text,
                               citations=citations, related_citations=related_citations,
                               answer_sentences=answer_sentences)
    return rules_answer, None
