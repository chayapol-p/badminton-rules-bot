"""
Checks the rule map against the golden questions, before any search runs.

For each golden question with more than one answer location, it pretends search found
one location and follows the rule map from there. The
question passes when the other locations arrive this way. This shows which hard cases
one search hit can solve, and which still need search to find more than one clause.

It also checks the para filter both ways: for a regular-play question (para_filter), no
Para Badminton clause may arrive; for a para question (para_question), the map runs with
question_is_para=True, as if the para flag on the question were already right.

  Input:  evals/golden_questions.json, data/rule_chunks.json, data/rule_links.json
  Output: printed results, one line per question category, then the para leaks

Run from the project root (after scripts.build_rule_chunks and scripts.build_rule_links):
    uv run python -m scripts.check_rule_links
"""

import json
from collections import defaultdict

from evals.golden_answer_chunks import QUESTIONS_FILE, expected_chunk_ids
from retrieval.expand_with_rule_links import expand_with_links, load_rule_map
from retrieval.load_rule_chunks import load_chunks


# ===== Turning an answer location into chunk ids =====

def find_location_chunk_ids(location: dict, chunks: list[dict]) -> set[str]:
    """Returns the chunk ids for one answer location, with the matcher the scorer uses."""
    return set(expected_chunk_ids(location, chunks))


def is_location_reached(location_chunk_ids: set[str], reached_ids: set[str]) -> bool:
    """True when at least one of the location's chunks is among the reached chunks."""
    return not location_chunk_ids.isdisjoint(reached_ids)


# ===== Following the map from one start =====

def follow_rule_map(start_chunk_ids: set[str], chunks_by_id: dict[str, dict], rule_map: dict,
                    question_is_para: bool) -> list[str]:
    """Returns the ids of every chunk the rule map brings, starting from these chunks, in prompt order."""
    context = expand_with_links(sorted(start_chunk_ids), chunks_by_id, rule_map, question_is_para=question_is_para)
    return [item["chunk"]["id"] for item in context]


def reaches_every_location(start_chunk_ids: set[str], location_chunk_id_sets: list[set[str]],
                           chunks_by_id: dict[str, dict], rule_map: dict, question_is_para: bool) -> bool:
    """True when every answer location arrives through the map, starting from one location's chunks."""
    reached_ids = set(follow_rule_map(start_chunk_ids, chunks_by_id, rule_map, question_is_para))
    return all(is_location_reached(location_chunk_ids, reached_ids) for location_chunk_ids in location_chunk_id_sets)


# ===== Checking each kind of question =====

def check_multi_location_questions(questions: list[dict], chunks: list[dict], chunks_by_id: dict[str, dict],
                                   rule_map: dict) -> dict[str, list[tuple[str, bool]]]:
    """Returns, per category, each multi-location question's id and whether one hit reaches every location."""
    results_by_category = defaultdict(list)
    for question in questions:

        # Keep the locations that match at least one chunk; a question needs two to test the map
        location_chunk_id_sets = []
        for location in question["answer_locations"]:
            location_chunk_ids = find_location_chunk_ids(location, chunks)
            if location_chunk_ids:
                location_chunk_id_sets.append(location_chunk_ids)
        if len(location_chunk_id_sets) < 2:
            continue

        # Pass when, starting from some location, every other location arrives through the map
        question_is_para = question["category"] == "para_question"
        passed = any(
            reaches_every_location(start_chunk_ids, location_chunk_id_sets, chunks_by_id, rule_map, question_is_para)
            for start_chunk_ids in location_chunk_id_sets
        )
        results_by_category[question["category"]].append((question["id"], passed))
    return results_by_category


def find_para_leaks(questions: list[dict], chunks: list[dict], chunks_by_id: dict[str, dict],
                    rule_map: dict) -> list[tuple[str, str]]:
    """Returns each para clause the map brings to a regular-play question, with the question's id."""
    para_leaks = []
    for question in questions:
        if question["category"] != "para_filter":
            continue

        # Start from every answer location at once
        start_chunk_ids = set()
        for location in question["answer_locations"]:
            start_chunk_ids.update(find_location_chunk_ids(location, chunks))

        # Following the map from a regular-play answer must bring no para clause
        reached_ids = follow_rule_map(start_chunk_ids, chunks_by_id, rule_map, question_is_para=False)
        for chunk_id in reached_ids:
            if chunks_by_id[chunk_id]["para_only"]:
                para_leaks.append((question["id"], chunk_id))
    return para_leaks


# ===== Printing =====

def describe_ids(ids: list) -> str:
    """Returns the list as text, or "none" when it is empty."""
    if ids:
        return str(ids)
    return "none"


def print_category_results(results_by_category: dict[str, list[tuple[str, bool]]]) -> None:
    """Prints one line per category: how many questions one hit solves, and which it doesn't."""
    for category, results in results_by_category.items():
        passed_count = 0
        failed_ids = []
        for question_id, passed in results:
            if passed:
                passed_count += 1
            else:
                failed_ids.append(question_id)

        # Name the failed questions only when there are some
        line = f"{category}: {passed_count}/{len(results)} reached from one hit "
        if failed_ids:
            line += f"| not reached: {failed_ids}"
        print(line)


# ===== Running =====

def main() -> None:
    """Checks every multi-location golden question, then the para filter."""

    # Load the questions, the chunks and the map
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]
    chunks = load_chunks()
    chunks_by_id = {chunk["id"]: chunk for chunk in chunks}
    rule_map = load_rule_map()

    # Check both kinds of question, then report
    results_by_category = check_multi_location_questions(questions, chunks, chunks_by_id, rule_map)
    para_leaks = find_para_leaks(questions, chunks, chunks_by_id, rule_map)
    print_category_results(results_by_category)
    print("para leaks:", describe_ids(para_leaks))


if __name__ == "__main__":
    main()
