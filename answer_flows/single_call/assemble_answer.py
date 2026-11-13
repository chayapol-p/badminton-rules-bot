"""
Builds the checked answer from the model's parts: the answer text, the quotes and the refusal are all decided by code.

The model makes one decision per part of the question: which sentences answer it (answer_flows/single_call/answer_shape.py
ModelAnswer). From those picks, code:

- copies each cited sentence in as its quote, so a quote can never be misquoted or joined from pieces;
- writes "The sources do not say <part>." for every part with no sentences;
- refuses when no part has a sentence that answers it. Related sentences never count as an answer:
  9-10 Nov, prompt version 2 left this call to the model, which counted nearby rules as an answer and
  missed 4 refusals.

A citation code can't fill keeps a quote that says why ("not shown", "no sentence 4"), so the citation
check (evals/checks/check_citations.py) fails it by name instead of the run losing it.

Use:
    rules_answer = assemble_answer(model_answer, shown_chunk_by_id)
"""

from answer_flows.shared.answer_shape import RulesAnswer
from answer_flows.shared.cite_sentences import NO_PARTS_ANSWER, add_citations
from answer_flows.single_call.answer_shape import ModelAnswer


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
