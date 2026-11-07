"""
Runs one search setup on the golden questions, prints its scores and adds one line to the run log.

One run changes one thing: the search type, the chunking or the text field.
  --search  keyword | vector | hybrid
  --chunks  clauses | windows
  --field   search_text | text | search_text_with_parents
            (clauses only: the header, no header, or the header plus the parent clauses)
  --split   dev | held_out       (held_out only once, for the published number)
  --top-k   results per question  (default 5; raise it to compare at the same number of words)

Vector and hybrid runs read saved embeddings, so run scripts.build_embeddings first.

Run from the project root, for example:
    uv run python -m experiments.compare_search_types --search keyword --chunks clauses
"""

import argparse
import time
from statistics import mean

import numpy

from app.settings import load_settings
from evals.golden_answer_chunks import load_chunks, load_questions
from evals.log_eval_run import append_run
from evals.score_retrieval import score_search
from retrieval.hybrid_search import HybridSearch
from retrieval.keyword_search import KeywordSearch
from retrieval.stored_embeddings import load_embeddings
from retrieval.vector_search import VectorSearch
from retrieval.window_chunks import build_windows


# Constants
## Results per question that the scorer reads, unless --top-k says otherwise
DEFAULT_TOP_K = 5


# ===== Building the search for one setup =====

def embedding_set_name(chunk_kind, field):
    """Returns the saved embedding set that matches the chunking and the field."""
    if chunk_kind == "windows":
        return "windows"
    return f"clauses_{field}"


def build_vector_search(items, chunk_kind, field, questions, model):
    """Returns a VectorSearch over the items, using saved vectors for both items and questions."""
    vector_by_id = load_embeddings(embedding_set_name(chunk_kind, field), model)
    item_vectors = numpy.array([vector_by_id[item["id"]] for item in items])

    # The eval reads each question's saved vector instead of calling the API
    question_vector_by_id = load_embeddings("questions", model)
    question_vector_by_text = {}
    for question in questions:
        question_vector_by_text[question["question"]] = question_vector_by_id[question["id"]]

    def saved_question_vector(question_text):
        """Returns the saved vector of a golden question, found by its text."""
        return question_vector_by_text[question_text]

    return VectorSearch(items, item_vectors, embed_question=saved_question_vector)


def build_search(search_type, items, chunk_kind, field, questions, model):
    """Returns the search function for one setup: search(question_text, top_k) -> items."""
    if search_type == "keyword":
        return KeywordSearch(items, field).search

    vector_search = build_vector_search(items, chunk_kind, field, questions, model)
    if search_type == "vector":
        return vector_search.search

    keyword_search = KeywordSearch(items, field)
    return HybridSearch(keyword_search, vector_search).search


# ===== Measuring one run =====

def average_words_returned(search, questions, top_k):
    """Returns the mean number of words the search hands to the model per question."""
    word_counts = []
    for question in questions:
        results = search(question["question"], top_k)[:top_k]
        word_counts.append(sum(len(result["text"].split()) for result in results))
    return round(mean(word_counts))


def scores_by_wording(search, questions, chunks, top_k):
    """Returns recall@k for exact-term questions and for paraphrased ones, scored separately."""
    recall_by_wording = {}
    for wording in ("exact_term", "paraphrased"):
        same_wording = [question for question in questions if question["wording"] == wording]
        recall_by_wording[wording] = score_search(search, same_wording, chunks, top_k)[f"recall_at_{top_k}"]
    return recall_by_wording


def print_scores(scores, top_k):
    """Prints the overall numbers, then each category, then the misses."""
    print(f"recall@{top_k} {scores[f'recall_at_{top_k}']}  hit@{top_k} {scores[f'hit_at_{top_k}']}  "
          f"questions {scores['questions_scored']}  words per question {scores['words_returned']}")
    print(f"by wording: {scores['by_wording']}")
    for category, numbers in scores["by_category"].items():
        print(f"  {category:16} recall {numbers['recall']}  ({numbers['questions']} questions)")
    for miss in scores["misses"]:
        print(f"  miss: {miss['id']} found {miss['found']} of {miss['needed']}")


# ===== Running one setup =====

def main() -> None:
    parser = argparse.ArgumentParser(description="Score one search setup on the golden questions.")
    parser.add_argument("--search", choices=["keyword", "vector", "hybrid"], required=True)
    parser.add_argument("--chunks", choices=["clauses", "windows"], default="clauses")
    parser.add_argument("--field", choices=["search_text", "text", "search_text_with_parents"], default="search_text")
    parser.add_argument("--split", choices=["dev", "held_out"], default="dev")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    arguments = parser.parse_args()

    # The scorer always reads clause chunks: a window counts through the clauses it covers
    clause_chunks = load_chunks()
    is_window_run = arguments.chunks == "windows"
    items = build_windows(clause_chunks) if is_window_run else clause_chunks
    questions = load_questions(arguments.split)
    model = load_settings().mistral_embedding_model

    # Build the search, then score it and time the whole run
    started = time.perf_counter()
    search = build_search(arguments.search, items, arguments.chunks, arguments.field, questions, model)
    top_k = arguments.top_k
    scores = score_search(search, questions, clause_chunks, top_k)
    scores["by_wording"] = scores_by_wording(search, questions, clause_chunks, top_k)
    scores["words_returned"] = average_words_returned(search, questions, top_k)
    seconds = time.perf_counter() - started

    # Print for reading now, and log for comparing later
    print_scores(scores, top_k)
    settings = {"search": arguments.search, "chunks": arguments.chunks, "field": arguments.field,
                "split": arguments.split, "top_k": top_k}
    append_run("1", settings, scores, seconds)


if __name__ == "__main__":
    main()
