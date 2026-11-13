"""
The retrieve step every setup with starting sources uses (setups plain-rag and hybrid), and the live search the tools use.

build_clause_vector_search  vector search on the clauses' search_text (decision record 0006), reading saved
                            vectors for the clauses and the questions, so a run calls no embedding API
build_retrieve_function     the top k from that search, and the bundle the rule map builds for them, every
                            clause in full (records 0009, 0015, 0017)
build_live_vector_search    the same clause vectors, but each new query is embedded with one live call, for
                            the tools' searches with the model's own words

Use:
    search = build_clause_vector_search(chunks, questions, settings.mistral_embedding_model).search
    retrieve = build_retrieve_function(search, DEFAULT_TOP_K, chunk_by_id, rule_map)
    source_items = retrieve(question_text)
"""

from collections.abc import Callable

import numpy
from mistralai.client import Mistral

from retrieval.build_bundle import build_bundle
from retrieval.stored_embeddings import embeddings_file, load_embeddings
from retrieval.vector_search import VectorSearch


# Constants
## Clauses handed to the model per question, unless --top-k says otherwise
DEFAULT_TOP_K = 5


# ===== The search, fixed by decision record 0006 =====

def build_clause_vector_search(chunks: list[dict], questions: list[dict], model: str) -> VectorSearch:
    """Returns vector search over the clauses' search_text, reading saved vectors for the clauses and the questions."""
    chunk_vector_by_id = load_embeddings("clauses_search_text", model)
    chunk_vectors = numpy.array([chunk_vector_by_id[chunk["id"]] for chunk in chunks])

    # Golden questions, the two probe kinds and the unseen questions are saved as separate sets; the search looks each one up by its text
    question_vector_by_id = load_embeddings("questions", model)
    question_vector_by_id.update(load_embeddings("refusal_probes", model))
    question_vector_by_id.update(load_embeddings("false_premise_probes", model))

    # The unseen questions (Stage 3) join once their vectors are saved, so older runs still work without them
    if embeddings_file("unseen_questions").exists():
        question_vector_by_id.update(load_embeddings("unseen_questions", model))
    # Every question needs its vector, so a missing one stops the run before the first paid call
    question_vector_by_text = {}
    for question in questions:
        if question["id"] not in question_vector_by_id:
            raise KeyError(f"no saved vector for the question {question['id']!r}: run scripts.build_embeddings first")
        question_vector_by_text[question["question"]] = question_vector_by_id[question["id"]]

    def saved_question_vector(question_text: str) -> numpy.ndarray:
        """Returns the saved vector of a golden question or probe, found by its text."""
        return question_vector_by_text[question_text]

    return VectorSearch(chunks, chunk_vectors, embedding_function=saved_question_vector)


# ===== The retrieve step =====

def build_retrieve_function(search: Callable, top_k: int, chunk_by_id: dict[str, dict],
                            rule_map: dict) -> Callable[[str], list[dict]]:
    """Returns the retrieve step: the top k from search, and the bundle the rule map builds for them (records 0009, 0015, 0023)."""

    def retrieve(question_text: str) -> list[dict]:
        """Returns the bundle handed to the answer model for one question: every clause in full, with its role label."""
        hits = search(question_text, top_k)
        hit_ids = [chunk["id"] for chunk in hits]
        return build_bundle(hit_ids, chunk_by_id, rule_map, related_in_full=True)

    return retrieve


# ===== The tools' search: live query vectors =====

def build_live_vector_search(chunks: list[dict], mistral_client: Mistral, model: str) -> VectorSearch:
    """Returns vector search over the clauses' saved vectors, embedding each new query with one live API call."""
    chunk_vector_by_id = load_embeddings("clauses_search_text", model)
    chunk_vectors = numpy.array([chunk_vector_by_id[chunk["id"]] for chunk in chunks])
    vector_by_query = {}

    def embed_query(query_text: str) -> list[float]:
        """Returns the query's vector, calling the API only the first time a query is seen."""
        if query_text not in vector_by_query:
            response = mistral_client.embeddings.create(model=model, inputs=[query_text])
            vector_by_query[query_text] = response.data[0].embedding
        return vector_by_query[query_text]

    return VectorSearch(chunks, chunk_vectors, embedding_function=embed_query)
