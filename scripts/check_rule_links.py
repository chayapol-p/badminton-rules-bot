"""
Checks the rule map against the golden questions, before any search runs.

For each golden question with more than one answer location, it pretends search found
one location and follows the rule map, plus the clauses around it, from there. The
question passes when the other locations arrive this way. This shows which hard cases
one search hit can solve, and which still need search to find more than one clause.

It also checks the para filter both ways: for a regular-play question (para_filter), no
Para Badminton clause may arrive; for a para question (para_question), the map runs with
question_is_para=True, as if the para flag on the question were already right.

Run from the project root (after scripts.ingest_rules and scripts.build_rule_links):
    uv run python -m scripts.check_rule_links
"""

import json
from collections import defaultdict
from pathlib import Path

from evals.golden import expected_chunk_ids
from retrieval.rule_links import expand_with_links, load_rule_map


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
QUESTIONS_FILE = PROJECT_FOLDER / "evals" / "golden_questions.json"
CHUNKS_FILE = PROJECT_FOLDER / "data" / "rule_chunks.json"


# ===== Load the questions, the chunks and the map =====

golden_set = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
chunks_by_id = {chunk["id"]: chunk for chunk in chunks}
rule_map = load_rule_map()


# ===== Turn an answer location into chunk ids =====

def location_ids(location):
    """Chunk ids for one location, with the matcher the scorer uses."""
    return set(expected_chunk_ids(location, chunks))


# ===== Follow the map from each location in turn =====

results_by_category = defaultdict(list)
for question in golden_set["questions"]:
    locations = [location_ids(location) for location in question["answer_locations"]]
    locations = [ids for ids in locations if ids]
    if len(locations) < 2:
        continue

    # Pass when, starting from some location, every other location arrives through the map
    question_is_para = question["category"] == "para_question"
    passed = False
    for start in locations:
        context = expand_with_links(sorted(start), chunks_by_id, rule_map, question_is_para=question_is_para)
        reached_ids = {item["chunk"]["id"] for item in context}
        if all(ids & reached_ids for ids in locations):
            passed = True
            break
    results_by_category[question["category"]].append((question["id"], passed))

# Para filter: following the map from a regular-play answer must bring no para clause
para_leaks = []
for question in golden_set["questions"]:
    if question["category"] != "para_filter":
        continue
    start_ids = sorted(set().union(*(location_ids(location) for location in question["answer_locations"])))
    context = expand_with_links(start_ids, chunks_by_id, rule_map, question_is_para=False)
    para_leaks += [(question["id"], item["chunk"]["id"]) for item in context if item["chunk"]["para_only"]]


# ===== Report =====

for category, results in results_by_category.items():
    passed_count = sum(passed for _, passed in results)
    failed_ids = [question_id for question_id, passed in results if not passed]
    print(f"{category}: {passed_count}/{len(results)} reached from one hit", f"| not reached: {failed_ids}" if failed_ids else "")
print("para leaks:", para_leaks or "none")
