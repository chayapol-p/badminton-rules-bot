"""
Scores a search function on golden questions: are the right clauses in the top results?

Two numbers per run, overall and per category:
  recall@k  the share of a question's answer locations found in the top k, averaged
  hit@k     the share of questions with at least one answer location in the top k

Only questions with an answer are scored. Unanswerable and attack questions have no
right clause to find, so the refusal check covers them instead.

A search function takes a question and a number k, and returns up to k chunk dictionaries:
    search(question_text, top_k) -> list of chunks

A result may be a clause chunk or a bigger window. A window lists the clause chunks it
covers in "covers", and a location counts as found when a retrieved window covers its clause.
"""

from collections import defaultdict
from statistics import mean

from evals.golden_answer_chunks import expected_chunk_ids


# ===== Scoring one question =====

def clause_ids_covered_by(retrieved_items):
    """Returns the clause chunk ids the results cover: a clause chunk covers itself, a window covers several."""
    covered_ids = []
    for item in retrieved_items:
        covered_ids.extend(item.get("covers", [item["id"]]))
    return covered_ids


def count_found_locations(retrieved_ids, expected_ids_per_location):
    """Returns how many answer locations have at least one of their chunks in the retrieved ids."""
    retrieved_id_set = set(retrieved_ids)
    found_count = 0
    for expected_ids in expected_ids_per_location:
        shared_ids = retrieved_id_set.intersection(expected_ids)
        if shared_ids:
            found_count += 1
    return found_count


# ===== Scoring a whole question set =====

def score_search(search, questions, chunks, top_k=5):
    """Runs the search on every answerable question and returns recall, hit rate and misses."""
    recall_by_category = defaultdict(list)
    hit_by_category = defaultdict(list)
    misses = []

    for question in questions:
        if question["answer"] is None:
            continue

        # Run the search, then compare its chunk ids with the answer locations
        retrieved_items = search(question["question"], top_k)[:top_k]
        retrieved_ids = clause_ids_covered_by(retrieved_items)
        expected_ids_per_location = [expected_chunk_ids(location, chunks) for location in question["answer_locations"]]
        found_count = count_found_locations(retrieved_ids, expected_ids_per_location)

        # Record the question's recall and hit, grouped by its category
        category = question["category"]
        question_recall = found_count / len(expected_ids_per_location)
        is_hit = found_count > 0
        recall_by_category[category].append(question_recall)
        hit_by_category[category].append(1.0 if is_hit else 0.0)
        if question_recall < 1.0:
            misses.append({"id": question["id"], "found": found_count, "needed": len(expected_ids_per_location)})

    # Gather every question's numbers, then average them overall and per category
    all_recalls = []
    all_hits = []
    for category in recall_by_category:
        all_recalls.extend(recall_by_category[category])
        all_hits.extend(hit_by_category[category])

    return {
        f"recall_at_{top_k}": round(mean(all_recalls), 3),
        f"hit_at_{top_k}": round(mean(all_hits), 3),
        "questions_scored": len(all_recalls),
        "by_category": {
            category: {"recall": round(mean(recalls), 3), "questions": len(recalls)}
            for category, recalls in sorted(recall_by_category.items())
        },
        "misses": misses,
    }
