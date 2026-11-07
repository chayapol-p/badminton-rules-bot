"""
Cuts each rule book into fixed-size windows, the usual chunking baseline, to compare with one chunk per clause.

Each document's clauses are joined back into one text, with their clause numbers, then
LangChain's RecursiveCharacterTextSplitter cuts it into windows of about 500 tokens with
about 50 overlapping. Every window records the clause chunks it covers, so the scorer can
count a location as found when a retrieved window covers its clause.

Windows never cross from one document into another.

Use:
    windows = build_windows(load_chunks())
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter


# Constants
## Window size in characters. English runs at roughly 4 characters per token,
## so this is about 500 tokens with about 50 overlapping.
WINDOW_CHARACTERS = 2000
OVERLAP_CHARACTERS = 200

## Clauses are joined with a blank line, so the splitter cuts between clauses when it can
CLAUSE_SEPARATOR = "\n\n"


# ===== Joining a document's clauses back into one text =====

def clause_as_printed(chunk):
    """Returns the clause text with its number in front, as the PDF prints it ("7.4 If the score...")."""
    # Headings, diagrams and intros already start with their own label
    is_numbered_sub_clause = chunk["clause"][0].isdigit() and "." in chunk["clause"]
    if is_numbered_sub_clause:
        return f"{chunk['clause']} {chunk['text']}"
    return chunk["text"]


def join_document(document_chunks):
    """Returns one document's text, and where each clause chunk starts and ends in it."""
    parts = []
    clause_spans = []
    position = 0
    for chunk in document_chunks:
        clause_text = clause_as_printed(chunk)
        clause_spans.append({"id": chunk["id"], "start": position, "end": position + len(clause_text)})
        parts.append(clause_text)
        position += len(clause_text) + len(CLAUSE_SEPARATOR)
    return CLAUSE_SEPARATOR.join(parts), clause_spans


# ===== Cutting the text into windows =====

def clause_ids_in_window(window_start, window_end, clause_spans):
    """Returns the ids of the clauses that overlap the window, in document order."""
    covered_ids = []
    for span in clause_spans:
        overlaps_window = span["start"] < window_end and span["end"] > window_start
        if overlaps_window:
            covered_ids.append(span["id"])
    return covered_ids


def build_windows(chunks):
    """Returns the windows for every document, each with its id, document, text and covered clause ids."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=WINDOW_CHARACTERS,
        chunk_overlap=OVERLAP_CHARACTERS,
        add_start_index=True,
    )

    # Group the clause chunks by document, keeping the ingest order
    chunks_by_document = {}
    for chunk in chunks:
        chunks_by_document.setdefault(chunk["document"], []).append(chunk)

    # Cut each document on its own, so no window crosses two documents
    windows = []
    for document, document_chunks in chunks_by_document.items():
        document_text, clause_spans = join_document(document_chunks)
        pieces = splitter.create_documents([document_text])
        for window_number, piece in enumerate(pieces, start=1):
            window_start = piece.metadata["start_index"]
            window_end = window_start + len(piece.page_content)
            windows.append({
                "id": f"{document}-window-{window_number:03d}",
                "document": document,
                "text": piece.page_content,
                "search_text": piece.page_content,
                "covers": clause_ids_in_window(window_start, window_end, clause_spans),
            })
    return windows
