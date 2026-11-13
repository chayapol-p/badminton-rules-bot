"""
Prints, for each unseen question, the vector top 10 and what setup A (full RAG) hands the model, with the answer clauses marked.

Each unseen question carries a "needs" tag (search only, map, tool, map and tool, or no answer) that a keyword search
backed when the question was written. The real search is vector search, so this check confirms
each tag against it before any setup answers. Read each block against its why_this_tag; when the
vector results contradict the tag, change the tag or the question. Then set "checked": true on it
in evals/unseen_questions.json.

  Input:  evals/unseen_questions.json, data/rule_chunks.json, data/rule_links.json, saved embeddings
          (run scripts.build_embeddings first: it embeds only the new unseen set)
  Output: printed results, one block per question

Run from the project root:
    uv run python -m scripts.check_unseen_questions
"""

from app.settings import load_settings
from evals.golden_answer_chunks import expected_chunk_ids, load_chunks
from evals.probes import load_unseen_questions
from retrieval.retrieve_sources import build_clause_vector_search, build_retrieve_function
from retrieval.expand_with_rule_links import load_rule_map


# Constants
## Results printed from the vector search: twice what setup A searches
RESULTS_PER_SEARCH = 10

## Search hits setup A starts from, before the rule links (record 0009)
SETUP_A_TOP_K = 5

## Characters of each clause to print
PREVIEW_CHARACTERS = 100

## Mark beside a clause that holds part of the answer
ANSWER_MARK = "*"


# ===== Finding the answer clauses =====

def answer_chunk_ids(question: dict, chunks: list[dict]) -> set[str]:
    """Returns the ids of every chunk that holds one of the question's answer locations."""
    found_ids = set()
    for location in question["answer_locations"]:
        found_ids.update(expected_chunk_ids(location, chunks))
    return found_ids


# ===== Printing =====

def print_results(heading: str, results: list[dict], wanted_ids: set[str]) -> None:
    """Prints one line per result, with the answer clauses marked."""
    print(f"  {heading}:")
    for rank, chunk in enumerate(results, start=1):
        mark = ANSWER_MARK if chunk["id"] in wanted_ids else " "
        preview = chunk["text"][:PREVIEW_CHARACTERS].replace("\n", " ")
        print(f"   {mark}{rank:2}. {chunk['id']:30} {preview}")


def print_coverage(label: str, results: list[dict], wanted_ids: set[str]) -> None:
    """Prints which answer clauses a result list found, and which it missed."""
    result_ids = {chunk["id"] for chunk in results}
    found = sorted(wanted_ids & result_ids)
    missed = sorted(wanted_ids - result_ids)
    print(f"  {label}: found {len(found)} of {len(wanted_ids)}; missed {missed or 'none'}")


# ===== Running =====

def main() -> None:
    """Prints the vector top 10 and setup A's sources for every unseen question."""
    chunks = load_chunks()
    chunk_by_id = {chunk["id"]: chunk for chunk in chunks}
    questions = load_unseen_questions()
    vector_search = build_clause_vector_search(chunks, questions, load_settings().mistral_embedding_model)
    retrieve_for_setup_a = build_retrieve_function(vector_search.search, SETUP_A_TOP_K, chunk_by_id, load_rule_map())

    for question in questions:
        wanted_ids = answer_chunk_ids(question, chunks)
        vector_results = vector_search.search(question["question"], RESULTS_PER_SEARCH)
        setup_a_sources = retrieve_for_setup_a(question["question"])

        print(f"\n{question['id']} · needs {question['needs']} · {question['difficulty']}")
        print(f"  question: {question['question']}")
        print(f"  why this tag: {question['why_this_tag']}")
        print_results("vector top 10", vector_results, wanted_ids)
        print_coverage("vector top 5 ", vector_results[:SETUP_A_TOP_K], wanted_ids)
        print_coverage("setup A sends", setup_a_sources, wanted_ids)


if __name__ == "__main__":
    main()
