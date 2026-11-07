"""
Runs every Stage 1 search setup in one go, then prints one table to compare them.

A setup already in the run log (same search, chunking, field, split and top_k) is skipped, so a
rerun only adds what is new, the same way scripts.build_embeddings skips saved sets. Pass --force
to run every setup again; the log then holds both runs, and the table shows the latest.

Each setup still changes one thing against its neighbour in the list (experiment rule 1).

  Input:  the saved embeddings (run scripts.build_embeddings first), evals/golden_questions.json
  Output: one line per new run in evals/runs.jsonl, and a table on screen

Run from the project root:
    uv run python -m experiments.run_all_search_setups
    uv run python -m experiments.run_all_search_setups --force
"""

import argparse
import json

from evals.log_eval_run import RUNS_FILE
from experiments.compare_search_types import run_one_setup


# Constants
## Every Stage 1 setup, as (search, chunks, field, top_k), all on the dev split
SEARCH_TYPES = ("keyword", "vector", "hybrid")
STAGE_1_SETUPS = (
    # The three search types on each chunking, all reading search_text (header, then text)
    [(search, "clauses", "search_text", 5) for search in SEARCH_TYPES]
    + [(search, "windows", "search_text", 5) for search in SEARCH_TYPES]
    + [(search, "sections", "search_text", 5) for search in SEARCH_TYPES]

    # Clauses without the context header, and with the parent clauses added
    + [(search, "clauses", "text", 5) for search in SEARCH_TYPES]
    + [(search, "clauses", "search_text_with_parents", 5) for search in SEARCH_TYPES]

    # Fewer results; clauses at about the windows' 1,590 words, and at the section groups' 405
    + [
        ("hybrid", "clauses", "search_text", 3),
        ("keyword", "clauses", "search_text", 45),
        ("vector", "clauses", "search_text", 55),
        ("hybrid", "clauses", "search_text", 50),
        ("vector", "clauses", "search_text", 13),
    ]
)
SPLIT = "dev"


# ===== Reading what has already run =====

def setup_key(search_type, chunk_kind, field, top_k):
    """Returns what makes two runs the same setup."""
    return (search_type, chunk_kind, field, SPLIT, top_k)


def latest_scores_by_setup():
    """Returns the scores of the latest logged run of each setup."""
    scores_by_setup = {}
    if not RUNS_FILE.exists():
        return scores_by_setup
    for line in RUNS_FILE.read_text(encoding="utf-8").splitlines():
        run = json.loads(line)
        settings = run["settings"]
        key = (settings["search"], settings["chunks"], settings["field"], settings["split"], settings["top_k"])
        scores_by_setup[key] = run["scores"]
    return scores_by_setup


# ===== Showing the results =====

def print_comparison_table(scores_by_setup):
    """Prints every Stage 1 setup that has a score, best recall first."""
    rows = []
    for search_type, chunk_kind, field, top_k in STAGE_1_SETUPS:
        scores = scores_by_setup.get(setup_key(search_type, chunk_kind, field, top_k))
        if scores is None:
            continue
        recall = scores[f"recall_at_{top_k}"]
        rows.append((recall, search_type, chunk_kind, field, top_k, scores["words_returned"]))

    print(f"\n{'recall':>6}  {'search':8} {'chunks':9} {'field':25} {'top_k':>5} {'words':>6}")
    for recall, search_type, chunk_kind, field, top_k, words in sorted(rows, reverse=True):
        print(f"{recall:>6.3f}  {search_type:8} {chunk_kind:9} {field:25} {top_k:>5} {words:>6}")


# ===== Running every setup =====

def main() -> None:
    """Runs each Stage 1 setup that isn't logged yet (or all of them with --force), then prints the table."""
    parser = argparse.ArgumentParser(description="Run every Stage 1 search setup, then compare them.")
    parser.add_argument("--force", action="store_true", help="run every setup again, even if already logged")
    arguments = parser.parse_args()

    logged_setups = latest_scores_by_setup()
    for search_type, chunk_kind, field, top_k in STAGE_1_SETUPS:
        is_logged = setup_key(search_type, chunk_kind, field, top_k) in logged_setups
        if is_logged and not arguments.force:
            print(f"skipped (already logged): {search_type} {chunk_kind} {field} top {top_k}")
            continue

        print(f"\n=== {search_type} {chunk_kind} {field} top {top_k} ===")
        run_one_setup(search_type, chunk_kind, field, SPLIT, top_k)

    print_comparison_table(latest_scores_by_setup())


if __name__ == "__main__":
    main()
