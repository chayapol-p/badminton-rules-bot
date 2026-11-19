"""
Skips the tests that read data built from the BWF rule books, which are never committed: the clauses and the rule
map (free to build), and the saved vectors (built with paid Mistral calls). A fresh clone skips these tests with the
steps to build what they need, instead of failing.
"""

import pytest

from retrieval.expand_with_rule_links import LINKS_FILE
from retrieval.load_rule_chunks import CHUNKS_FILE
from retrieval.stored_embeddings import embeddings_file


# Constants
## The steps that build the missing files, in order
MISSING_DATA_MESSAGE = ("data/ is missing: run scripts.download_rule_books, then scripts.build_rule_chunks, "
                        "then scripts.build_rule_links")
MISSING_VECTORS_MESSAGE = "data/embeddings/ is missing: run scripts.build_embeddings (it calls Mistral)"


# Skips the test that calls it, or the whole test file when called at its top, when the clauses or the rule map
# are missing
def skip_without_rule_data() -> None:
    is_data_missing = not CHUNKS_FILE.exists() or not LINKS_FILE.exists()
    if is_data_missing:
        pytest.skip(MISSING_DATA_MESSAGE, allow_module_level=True)


# Skips one test when the clauses' saved vectors are missing
def skip_test_without_saved_vectors() -> None:
    if not embeddings_file("clauses_search_text").exists():
        pytest.skip(MISSING_VECTORS_MESSAGE)
