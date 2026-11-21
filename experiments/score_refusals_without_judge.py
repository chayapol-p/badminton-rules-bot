"""
Scores the final bot's refusals with code only, with no judge (Job, 21 Nov 2026: no judge tokens left until 1 Dec).

The full product route (RulesBot.answer, topic screen included) answers two sets the final design was never tuned on:
  - the 10 refusal probes (evals/refusal_probes.json): code records refused or answered and which kind;
    an answered probe is printed in full, because its pass rule ("gives no figure") needs a person to read it
  - the 11 unseen questions (evals/unseen_questions.json): code records false refusals, missed refusals, and
    whether the answer cites a clause that holds the golden answer
Code can't grade the pass rules or the wording; that is the judge's job.

  Input:  evals/refusal_probes.json, evals/unseen_questions.json; data/ (the chunks and their saved vectors); MISTRAL_API_KEY
  Output: one line in evals/runs.jsonl (stage "refusal-check-no-judge"), and a printed table

Run from the project root:
    uv run python -m experiments.score_refusals_without_judge
"""

import time
from datetime import datetime, timezone

from answer_flows.rules_bot import RulesBot
from answer_flows.shared.mistral_client import build_mistral_client
from answer_flows.topic_screen import build_mistral_topic_check
from evals.golden_answer_chunks import expected_chunk_ids
from evals.log_eval_run import append_run
from evals.probes import load_refusal_probes, load_unseen_questions
from experiments.run_answer_experiment import read_code_version
from experiments.run_topic_check_eval import CostTracker, RecordingClient, cost_of_calls
from retrieval.expand_with_rule_links import load_rule_map
from retrieval.load_rule_chunks import load_chunks
from retrieval.retrieve_sources import build_live_vector_search
from settings import load_settings


# Constants
## The cost at which the command stops (Job approved about $0.35), and the stage runs.jsonl records
COST_CAP_DOLLARS = 1.00
MEASUREMENT_STAGE = "refusal-check-no-judge"
## The unseen category whose questions the bot should refuse
UNANSWERABLE_CATEGORY = "unanswerable"


# Answers one question with the real bot and records what code can check: the refusal, the cited clauses, cost and time
def answer_one_question(question: dict, question_set: str, rules_bot: RulesBot, recording_client: RecordingClient,
                        cost_tracker: CostTracker, chunks: list[dict]) -> dict:
    started = time.perf_counter()
    error_text = None
    refused, refusal_kind, answer_text, cited_ids = None, None, "", []
    try:
        rules_answer = rules_bot.answer(question["question"])
        refused, refusal_kind = rules_answer.refused, rules_answer.refusal_kind
        answer_text = rules_answer.answer
        cited_ids = [citation.chunk_id for citation in rules_answer.citations]
    # One failed question is recorded by name and the run goes on: no other question depends on it
    except Exception as error:
        error_text = f"{type(error).__name__}: {error}"
    seconds = time.perf_counter() - started
    cost = cost_of_calls(recording_client.take_calls())
    cost_tracker.add(cost)

    # The right clause: the answer cites at least one chunk that holds the golden answer (unseen questions only)
    golden_ids = set()
    for location in question.get("answer_locations", []):
        golden_ids.update(expected_chunk_ids(location, chunks))
    cites_right_clause = not golden_ids.isdisjoint(cited_ids)

    return {"id": question["id"], "set": question_set, "category": question.get("category", question.get("kind")),
            "refused": refused, "refusal_kind": refusal_kind, "cites_right_clause": cites_right_clause,
            "has_golden_clause": bool(golden_ids), "answer": answer_text, "seconds": round(seconds, 1),
            "cost": cost, "error": error_text}


# Counts what code can grade: refusals on the probes, and false or missed refusals and right clauses on the unseen set
def score_rows(rows: list[dict]) -> dict:
    probe_rows = [row for row in rows if row["set"] == "probes"]
    unseen_rows = [row for row in rows if row["set"] == "unseen"]
    answerable_rows = [row for row in unseen_rows if row["category"] != UNANSWERABLE_CATEGORY]
    unanswerable_rows = [row for row in unseen_rows if row["category"] == UNANSWERABLE_CATEGORY]
    answered_rows = [row for row in answerable_rows if row["refused"] is False]
    return {
        "probes": len(probe_rows),
        "probes_off_topic": sum(row["refusal_kind"] == "off_topic" for row in probe_rows),
        "probes_not_covered": sum(row["refusal_kind"] == "not_covered" for row in probe_rows),
        "probes_answered": sorted(row["id"] for row in probe_rows if row["refused"] is False),
        "unseen_answerable": len(answerable_rows),
        "false_refusals": sorted(row["id"] for row in answerable_rows if row["refused"] is True),
        "unseen_should_refuse": len(unanswerable_rows),
        "missed_refusals": sorted(row["id"] for row in unanswerable_rows if row["refused"] is False),
        "answers_citing_right_clause": sum(row["cites_right_clause"] for row in answered_rows),
        "answers_scored_for_clause": len(answered_rows),
        "errors": sorted(f"{row['id']} ({row['error']})" for row in rows if row["error"] is not None),
        "cost_dollars": round(sum(row["cost"] for row in rows), 4),
        "rows": [{key: row[key] for key in ("id", "set", "category", "refused", "refusal_kind", "cites_right_clause",
                                            "seconds", "error", "answer")} for row in rows],
    }


# Prints one line per question, then each answered probe in full for a person to read against its pass rule
def print_results(rows: list[dict], scores: dict, probes: list[dict]) -> None:
    for row in rows:
        print(f"{row['set']:7} {row['id']:34} {str(row['category']):18} refused={row['refused']!s:5} "
              f"kind={row['refusal_kind']!s:11} right_clause={row['cites_right_clause']!s:5} {row['seconds']:5.1f} s")
    pass_rule_by_id = {probe["id"]: probe["pass_rule"] for probe in probes}
    for row in rows:
        if row["set"] == "probes" and row["refused"] is False:
            print(f"\n--- {row['id']} (pass rule: {pass_rule_by_id[row['id']]})\n{row['answer']}")
    summary = {key: value for key, value in scores.items() if key != "rows"}
    print(f"\n{summary}", flush=True)


def main() -> None:
    # Built like load_rules_bot(), with the recording client so each call's cost is counted
    settings = load_settings()
    recording_client = RecordingClient(build_mistral_client(settings))
    cost_tracker = CostTracker(COST_CAP_DOLLARS)
    chunks = load_chunks()
    live_search = build_live_vector_search(chunks, recording_client, settings.mistral_embedding_model)
    topic_check = build_mistral_topic_check(recording_client, settings.mistral_draft_model)
    rules_bot = RulesBot(recording_client, settings, chunks, load_rule_map(), live_search.search,
                         is_rules_question=topic_check)

    # Answer both sets one question at a time, stopping before a question once the cost passes the cap
    probes = load_refusal_probes()
    questions = [(probe, "probes") for probe in probes] + [(question, "unseen") for question in load_unseen_questions()]
    started = time.perf_counter()
    rows = []
    for question, question_set in questions:
        if cost_tracker.is_over_cap():
            print(f"stopped: spent ${cost_tracker.spent_dollars:.2f}, over the ${COST_CAP_DOLLARS:.2f} cap")
            break
        rows.append(answer_one_question(question, question_set, rules_bot, recording_client, cost_tracker, chunks))

    # Log the run, then print it
    scores = score_rows(rows)
    run_settings = {"run": f"{datetime.now(timezone.utc):%Y%m%dT%H%M}-refusal-check-no-judge",
                    "answer_model": settings.mistral_answer_model, "check_model": settings.mistral_draft_model,
                    "reasoning_effort": settings.mistral_reasoning_effort, "flow": "gather-then-write",
                    "setup": "hybrid", "route": "RulesBot.answer", "questions": len(rows)}
    run_settings.update(read_code_version())
    append_run(MEASUREMENT_STAGE, run_settings, scores, round(time.perf_counter() - started, 2))
    print_results(rows, scores, probes)


if __name__ == "__main__":
    main()
