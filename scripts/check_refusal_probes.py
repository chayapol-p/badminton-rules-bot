"""
Prints the top 10 keyword and vector results for each refusal probe, so you can read them and confirm no clause answers it.

A probe only measures refusals if the corpus truly has no answer. Read each probe's results
against its why_unanswerable; when a clause answers it, rewrite or drop the probe. Then set
"checked": true on it in evals/refusal_probes.json.

  Input:  evals/refusal_probes.json, data/rule_chunks.json, saved embeddings (run scripts.build_embeddings first)
  Output: printed results, one block per probe

Run from the project root:
    uv run python -m scripts.check_refusal_probes
"""

from app.settings import load_settings
from evals.golden_answer_chunks import load_chunks
from evals.probes import load_refusal_probes
from retrieval.retrieve_sources import build_clause_vector_search
from retrieval.keyword_search import KeywordSearch


# Constants
## Results per search per probe: more than any answer run reads at top 5
RESULTS_PER_SEARCH = 10

## Characters of each clause to print
PREVIEW_CHARACTERS = 110


# ===== Printing one search's results =====

def print_results(search_name: str, results: list[dict]) -> None:
    """Prints one line per result: rank, chunk id and the start of the clause."""
    print(f"  {search_name}:")
    for rank, chunk in enumerate(results, start=1):
        preview = chunk["text"][:PREVIEW_CHARACTERS].replace("\n", " ")
        print(f"    {rank:2}. {chunk['id']:24} {preview}")


# ===== Running =====

def main() -> None:
    """Prints both searches' top results for every probe."""
    chunks = load_chunks()
    probes = load_refusal_probes()
    keyword_search = KeywordSearch(chunks, "search_text")
    vector_search = build_clause_vector_search(chunks, probes, load_settings().mistral_embedding_model)

    for probe in probes:
        print(f"\n{probe['id']} ({probe['kind']}): {probe['question']}")
        print(f"  why no answer: {probe['why_unanswerable']}")
        print_results("keyword", keyword_search.search(probe["question"], RESULTS_PER_SEARCH))
        print_results("vector", vector_search.search(probe["question"], RESULTS_PER_SEARCH))


if __name__ == "__main__":
    main()
