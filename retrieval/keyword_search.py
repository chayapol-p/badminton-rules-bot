"""
Keyword search: ranks chunks with BM25, the standard keyword baseline, using rank_bm25.

BM25 scores a chunk higher when it holds the question's words, more so for rare words
("shuttlecock" more than "the") and less for long chunks. It only matches words that are
spelled the same, so it finds "1.55 metres" but not "how tall".

Use:
    keyword_search = KeywordSearch(chunks, field="search_text")
    results = keyword_search.search("How tall are the posts?", top_k=5)
"""

import re

from rank_bm25 import BM25Okapi


# Constants
## A clause number kept whole ("9.1.6"), or a run of letters and digits
TOKEN_PATTERN = re.compile(r"\d+(?:\.\d+)+|\w+")


# ===== Turning text into words =====

def tokenize(text):
    """Lowercases the text and splits it into words, keeping clause numbers such as 9.1.6 whole."""
    return TOKEN_PATTERN.findall(text.lower())


# ===== The search =====

class KeywordSearch:
    """Ranks chunks by BM25 on one text field."""

    def __init__(self, chunks, field="search_text"):
        # Index every chunk's words once; each search then only scores the question
        self.chunks = chunks
        tokenized_texts = [tokenize(chunk[field]) for chunk in chunks]
        self.index = BM25Okapi(tokenized_texts)

    def search(self, question_text, top_k):
        """Returns the top_k chunks with the highest BM25 score for the question."""
        # Score every chunk against the question's words, and keep the top_k, best first
        return self.index.get_top_n(tokenize(question_text), self.chunks, n=top_k)
