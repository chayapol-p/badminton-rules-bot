"""
Measures whether search can rescue a rules question the topic check blocks: when the check says off topic, would the
closeness of the question's nearest rule clause tell a real rules question from a trick? Job's request, 19 Nov 2026.

Two groups, scored with the same pieces as the product search (the frozen clauses, the same embedding model):
- should be rescued: the casual rules questions the word-list prompt blocked in any casual-rules-baseline run, and
  every other casual question as a reference
- must stay blocked: the non-badminton questions in the off-topic set, and the red-team tricks that expect off topic

Per question: the top cosine similarity to any clause and that clause, the top BM25 score and that clause, and for the
casual questions whether the top cosine clause is the expected source. Then, per signal, the cut-off that lets no
must-block question through, and how many blocked questions it rescues. No check calls: the verdicts come from the
casual-rules-baseline run lines. One run line goes to evals/runs.jsonl under the stage "search-rescue-measure".

  Input:  evals/casual_rules_questions.json, evals/off_topic_questions.json, evals/red_team_questions.json,
          evals/runs.jsonl (the baseline verdicts), data/ (the clauses and their saved vectors), MISTRAL_API_KEY
  Output: a printed table and cut-offs, one line in evals/runs.jsonl

Run from the project root:
    uv run python -m experiments.measure_search_rescue
"""

import json
import time
from datetime import datetime, timezone

import numpy

from answer_flows.shared.mistral_client import build_mistral_client
from app.settings import load_settings
from evals.golden_answer_chunks import PROJECT_FOLDER, load_chunks
from evals.log_eval_run import append_run
from experiments.run_answer_experiment import read_code_version
from retrieval.keyword_search import tokenize, KeywordSearch
from retrieval.stored_embeddings import load_embeddings


# Constants
## The stage runs.jsonl records, and the baseline runs whose verdicts say which casual questions were blocked
MEASUREMENT_STAGE = "search-rescue-measure"
BASELINE_STAGE = "casual-rules-baseline"
BASELINE_RUN_COUNT = 3

## mistral-embed's list price per million input tokens (Mistral's pricing page; not in evals/token_costs.py)
EMBEDDING_PRICE_PER_MILLION_TOKENS = 0.10

## The group names in the table
SHOULD_RESCUE = "blocked rules question"
REFERENCE = "passed rules question"
MUST_BLOCK = "must stay blocked"


# ===== The questions =====

# Returns one set file's questions
def json_questions(file_name: str) -> list[dict]:
    return json.loads((PROJECT_FOLDER / "evals" / f"{file_name}.json").read_text(encoding="utf-8"))["questions"]


# Returns the ids of the casual questions the word-list prompt blocked in any of the last baseline runs
def load_blocked_casual_ids() -> set[str]:
    run_lines = [json.loads(line) for line in (PROJECT_FOLDER / "evals" / "runs.jsonl").read_text().splitlines()]
    baseline_runs = [run for run in run_lines if run["stage"] == BASELINE_STAGE][-BASELINE_RUN_COUNT:]
    blocked_ids = set()
    for run in baseline_runs:
        for row in run["scores"]["rows"]:
            if row["verdict"] == "off_topic":
                blocked_ids.add(row["id"])
    return blocked_ids


# Returns every question to score, each with its group and, for the casual ones, its expected source clause
def load_scored_questions() -> list[dict]:
    blocked_ids = load_blocked_casual_ids()
    questions = []
    for question in json_questions("casual_rules_questions"):
        group = SHOULD_RESCUE if question["id"] in blocked_ids else REFERENCE
        questions.append({"id": question["id"], "question": question["question"], "group": group,
                          "source": question["source"]})
    for question in json_questions("off_topic_questions"):
        if question["expected_screen"] == "off_topic":
            questions.append({"id": question["id"], "question": question["question"], "group": MUST_BLOCK,
                              "source": None})
    for question in json_questions("red_team_questions"):
        if question["expected_screen"] == "off_topic":
            questions.append({"id": question["id"], "question": question["question"], "group": MUST_BLOCK,
                              "source": None})
    return questions


# ===== The scores =====

# Embeds every question in one call and returns the vectors and the input tokens
def embed_questions(question_texts: list[str], settings) -> tuple[numpy.ndarray, int]:
    mistral_client = build_mistral_client(settings)
    response = mistral_client.embeddings.create(model=settings.mistral_embedding_model, inputs=question_texts)
    vectors = numpy.array([item.embedding for item in response.data])
    return vectors, response.usage.prompt_tokens


# Adds the top cosine and BM25 scores and clauses to every question, as the product search computes them
def add_scores(questions: list[dict], question_vectors: numpy.ndarray, settings) -> None:
    chunks = load_chunks()
    chunk_vector_by_id = load_embeddings("clauses_search_text", settings.mistral_embedding_model)
    chunk_vectors = numpy.array([chunk_vector_by_id[chunk["id"]] for chunk in chunks])
    keyword_search = KeywordSearch(chunks, field="search_text")

    for question, question_vector in zip(questions, question_vectors):
        # Cosine: a dot product, because mistral-embed vectors have length 1 (retrieval/vector_search.py)
        similarities = numpy.dot(chunk_vectors, question_vector)
        best_vector_position = int(numpy.argmax(similarities))
        question["cosine"] = round(float(similarities[best_vector_position]), 3)
        question["cosine_clause"] = chunks[best_vector_position]["id"]

        # BM25 on the same field the product's keyword search reads
        keyword_scores = keyword_search.index.get_scores(tokenize(question["question"]))
        best_keyword_position = int(numpy.argmax(keyword_scores))
        question["bm25"] = round(float(keyword_scores[best_keyword_position]), 2)
        question["bm25_clause"] = chunks[best_keyword_position]["id"]

        has_source = question["source"] is not None
        question["cosine_hits_source"] = question["cosine_clause"] == question["source"] if has_source else None


# ===== The cut-offs =====

# Returns, for one signal, the lowest cut-off that lets no must-block question through, and what it rescues
def find_safe_cut_off(questions: list[dict], signal: str) -> dict:
    must_block_scores = [question[signal] for question in questions if question["group"] == MUST_BLOCK]
    rescue_scores = [question[signal] for question in questions if question["group"] == SHOULD_RESCUE]
    reference_scores = [question[signal] for question in questions if question["group"] == REFERENCE]
    highest_must_block = max(must_block_scores)
    rescued_count = sum(score > highest_must_block for score in rescue_scores)
    return {"signal": signal, "cut_off_above": highest_must_block,
            "rescued": rescued_count, "blocked_rules_questions": len(rescue_scores),
            "lowest_rescue_score": min(rescue_scores),
            "margin": round(min(rescue_scores) - highest_must_block, 3),
            "reference_above_cut_off": sum(score > highest_must_block for score in reference_scores),
            "reference_questions": len(reference_scores)}


# Prints every scored question, highest cosine first, then each signal's safe cut-off
def print_report(questions: list[dict], cut_offs: list[dict]) -> None:
    print(f"{'group':<24} {'cosine':>6} {'bm25':>6}  {'top cosine clause':<26} question")
    for question in sorted(questions, key=lambda question: -question["cosine"]):
        if question["group"] == REFERENCE:
            continue
        print(f"{question['group']:<24} {question['cosine']:>6.3f} {question['bm25']:>6.2f}  "
              f"{question['cosine_clause']:<26} {question['question']}")
    for cut_off in cut_offs:
        print(f"\n{cut_off['signal']}: safe cut-off above {cut_off['cut_off_above']} rescues "
              f"{cut_off['rescued']}/{cut_off['blocked_rules_questions']} · margin {cut_off['margin']} · "
              f"reference above it {cut_off['reference_above_cut_off']}/{cut_off['reference_questions']}")


# ===== Entry point =====

# Scores every question, finds the cut-offs, prints them and logs the run
def main() -> None:
    started = time.perf_counter()
    settings = load_settings()
    questions = load_scored_questions()
    question_vectors, input_tokens = embed_questions([question["question"] for question in questions], settings)
    add_scores(questions, question_vectors, settings)
    cut_offs = [find_safe_cut_off(questions, "cosine"), find_safe_cut_off(questions, "bm25")]
    print_report(questions, cut_offs)

    casual_questions = [question for question in questions if question["source"] is not None]
    source_hit_count = sum(question["cosine_hits_source"] for question in casual_questions)
    cost = input_tokens * EMBEDDING_PRICE_PER_MILLION_TOKENS / 1_000_000
    print(f"\ntop cosine clause is the expected source: {source_hit_count}/{len(casual_questions)}")
    print(f"embedding tokens {input_tokens} · cost ${cost:.5f}")

    scores = {"cut_offs": cut_offs, "cosine_hits_source": source_hit_count, "casual_questions": len(casual_questions),
              "cost_dollars": round(cost, 5),
              "rows": [{key: question[key] for key in ("id", "group", "cosine", "cosine_clause", "bm25",
                                                       "bm25_clause", "cosine_hits_source")}
                       for question in questions]}
    run_settings = {"run": f"{datetime.now(timezone.utc):%Y%m%dT%H%M}-search-rescue-measure",
                    "embedding_model": settings.mistral_embedding_model, "clause_field": "search_text",
                    "verdicts_from": BASELINE_STAGE, "questions": len(questions)}
    run_settings.update(read_code_version())
    append_run(MEASUREMENT_STAGE, run_settings, scores, round(time.perf_counter() - started, 2))


if __name__ == "__main__":
    main()
