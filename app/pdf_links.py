"""
Links each citation to its page in the frozen rule-book PDF, so the page can open the clause where it is printed
(slice 3 of docs/specs/ask-a-rules-question.md, records 0029 and 0034).

A link is the PDF's address under /rule-books, then #page=N: the physical page counted from 1 (RFC 8118), which is
how the chunks store "page". The file names come from the frozen corpus list in evals/golden_questions.json, the one
place that names each document's PDF and its hash. FastAPI serves the PDFs from RULE_BOOKS_FOLDER (app/main.py).

Use:
    link_to_pdf_page("itto-7.2")          # "/rule-books/bwf-itto-2025-v7.0.pdf#page=37"
    linked_answer = add_pdf_links(rules_answer)
"""

import json
from functools import cache

from answer_flows.shared.answer_shape import Citation, RulesAnswer
from evals.golden_answer_chunks import PROJECT_FOLDER, QUESTIONS_FILE, load_chunks


# Constants
## Where the rule-book PDFs live on disk (downloaded by hand, never committed), and the address the app serves them at
RULE_BOOKS_FOLDER = PROJECT_FOLDER / "data" / "bwf"
RULE_BOOKS_ADDRESS = "/rule-books"


# ===== The answer the page gets =====

class LinkedCitation(Citation):
    """A citation with the link that opens its PDF at the clause's page."""

    pdf_link: str


class LinkedRulesAnswer(RulesAnswer):
    """The bot's answer, with a PDF link on each citation the answer cites."""

    citations: list[LinkedCitation]


# ===== The links =====

# Returns every clause's PDF link by its chunk id; read once, because the corpus is frozen
@cache
def load_pdf_link_by_chunk_id() -> dict[str, str]:
    frozen_corpus = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["corpus_frozen"]
    file_name_by_document = {document: entry["file"] for document, entry in frozen_corpus.items()}

    pdf_link_by_chunk_id = {}
    for chunk in load_chunks():
        file_name = file_name_by_document[chunk["document"]]
        pdf_link_by_chunk_id[chunk["id"]] = f"{RULE_BOOKS_ADDRESS}/{file_name}#page={chunk['page']}"
    return pdf_link_by_chunk_id


# Returns the link that opens a clause's PDF at its page; an unknown id stops with its name, because a citation the
# bot wrote must point to a real clause
def link_to_pdf_page(chunk_id: str) -> str:
    pdf_link_by_chunk_id = load_pdf_link_by_chunk_id()
    if chunk_id not in pdf_link_by_chunk_id:
        raise ValueError(f"No clause has the id {chunk_id}, so there is no PDF page to link to")
    return pdf_link_by_chunk_id[chunk_id]


# Returns the answer with a PDF link added to each citation; the related citations stay as they are, because the
# page doesn't show them
def add_pdf_links(rules_answer: RulesAnswer) -> LinkedRulesAnswer:
    linked_citations = []
    for citation in rules_answer.citations:
        linked_citations.append(LinkedCitation(**citation.model_dump(), pdf_link=link_to_pdf_page(citation.chunk_id)))
    return LinkedRulesAnswer(**rules_answer.model_dump(exclude={"citations"}), citations=linked_citations)
