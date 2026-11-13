"""
Scores an answer run, for every setup and flow: the code checks then the judge for one answer, the run's
scores, and the printout. The run script (experiments/run_answer_experiment.py), the re-scorer and the
grading kit all read the same scores.

Use:
    grade_line = check_and_grade(answer_line, rules_answer, question, shown_chunks, chunks, chunk_by_id, anthropic_client, judge_model)
    scores = summarise_answer_run(answer_lines, passed_by_id)
    print_scores(scores, answer_lines, passed_by_id)
"""

import json
from statistics import mean

from anthropic import Anthropic

from answer_flows.shared.answer_shape import RulesAnswer
from evals.checks.check_citations import find_citation_problems
from evals.checks.check_refusals import CORRECT_REFUSAL, FALSE_REFUSAL, refusal_outcome
from evals.code_checks import find_code_failures
from evals.judge_answers import grade_answer, judge_passed
from evals.token_costs import call_cost


# Constants
## Questions whose pass rule needs an image: a text-only answer fails them until images arrive in Week 4
IMAGE_ONLY_QUESTION_IDS = {"doubles-court-size", "service-judge-height-signal"}

## Each code check, and the start of its failure messages
CODE_CHECK_PREFIXES = {
    "format error": ("format error",),
    "wrong refusal": ("missed refusal", "false refusal"),
    "citation problem": ("citation",),
    "wrong clause": ("wrong clause",),
}

CODE_CHECK_NAMES = list(CODE_CHECK_PREFIXES)


# ===== One answer: the code checks, then the judge =====

def check_and_grade(answer_line: dict, rules_answer: RulesAnswer, question: dict, retrieved_chunks: list[dict],
                    chunks: list[dict], chunk_by_id: dict[str, dict], anthropic_client: Anthropic,
                    judge_model: str) -> dict:
    """Runs the code checks on one answer, then the judge when they pass; fills in the answer line's checks and judge cost, and returns the grade line."""

    # Code checks first: an answer they fail has failed, and isn't sent to the judge
    answer_line["citation_problems"] = find_citation_problems(rules_answer, retrieved_chunks)
    answer_line["refusal_outcome"] = refusal_outcome(question, rules_answer.refused)
    failures, warnings = find_code_failures(answer_line, question, chunks, chunk_by_id)
    answer_line["code_failures"] = failures
    answer_line["code_warnings"] = warnings
    answer_line["judge_cost"] = 0.0
    if failures:
        return {"id": question["id"], "passed": False, "judged": False, "grade": None}

    # Then the judge, for what only it can grade, with the code warnings to weigh
    grade_reply = grade_answer(anthropic_client, judge_model, question, rules_answer, retrieved_chunks, warnings)
    answer_line["judge_cost"] = call_cost(judge_model, grade_reply.input_tokens, grade_reply.output_tokens)
    return {"id": question["id"], "passed": judge_passed(grade_reply.grade), "judged": True,
            "grade": grade_reply.grade.model_dump()}


# ===== Scoring a run =====

def failed_check(answer_line: dict, check_name: str) -> bool:
    """True when one of the answer's code failures belongs to the named check."""
    prefixes = CODE_CHECK_PREFIXES[check_name]
    for failure in answer_line["code_failures"]:
        if failure.startswith(prefixes):
            return True
    return False


def count_passed(answer_lines: list[dict], passed_by_id: dict[str, bool]) -> int:
    """Returns how many of the answers passed: the code checks, then the judge."""
    passed_count = 0
    for line in answer_lines:
        if passed_by_id[line["id"]]:
            passed_count += 1
    return passed_count


def share(count: int, total: int) -> float:
    """Returns count / total rounded to 3 places, or 0.0 when there is nothing to count."""
    if total == 0:
        return 0.0
    return round(count / total, 3)


def summarise_answer_run(answer_lines: list[dict], passed_by_id: dict[str, bool]) -> dict:
    """Returns the run's scores: answers, diagrams, citations, refusals both ways, format errors, words and cost."""

    # Split the questions into the groups each score reads; probes are scored on their own lines
    answerable = [line for line in answer_lines if not line["should_refuse"] and line["split"] != "probe"]
    text_answerable = [line for line in answerable if line["id"] not in IMAGE_ONLY_QUESTION_IDS]
    image_only = [line for line in answerable if line["id"] in IMAGE_ONLY_QUESTION_IDS]
    no_answer = [line for line in answer_lines if line["should_refuse"]]
    golden_no_answer = [line for line in no_answer if line["split"] != "probe"]
    probes = [line for line in no_answer if line["split"] == "probe"]
    false_premises = [line for line in answer_lines if line["category"] == "false_premise"]
    with_answer = [line for line in answer_lines if not line["is_format_error"]]

    # Answers the judge passed, overall and per category
    answers_passed = count_passed(text_answerable, passed_by_id)
    by_category = {}
    for category in sorted({line["category"] for line in text_answerable}):
        same_category = [line for line in text_answerable if line["category"] == category]
        by_category[category] = {"passed": count_passed(same_category, passed_by_id), "questions": len(same_category)}

    # Unseen questions: answers passed per needs tag, the reading Stage 3 compares setups on
    by_needs = {}
    for needs in sorted({line["needs"] for line in answer_lines if line.get("needs")}):
        same_needs = [line for line in answer_lines if line.get("needs") == needs]
        by_needs[needs] = {"passed": count_passed(same_needs, passed_by_id), "questions": len(same_needs)}

    # Code checks: what failed them, by check, and how many answers went on to the judge
    code_failed = [line for line in answer_lines if line["code_failures"]]
    code_failures_by_check = {}
    for check_name in CODE_CHECK_NAMES:
        failed_lines = [line for line in code_failed if failed_check(line, check_name)]
        code_failures_by_check[check_name] = len(failed_lines)

    # Citations, and refusals counted both ways
    citations_clean = [line for line in with_answer if not line["citation_problems"]]
    correct_refusals = [line for line in golden_no_answer if line["refusal_outcome"] == CORRECT_REFUSAL]
    correct_probe_refusals = [line for line in probes if line["refusal_outcome"] == CORRECT_REFUSAL]
    # Image-only questions are left out: refusing them is fair until images arrive in Week 4
    false_refusals = [line for line in text_answerable if line["refusal_outcome"] == FALSE_REFUSAL]

    # Cost of every call, answer and judge together
    costs = [line["answer_cost"] + line["judge_cost"] for line in answer_lines]

    return {
        "answers_passed": answers_passed,
        "answers_scored": len(text_answerable),
        "answer_pass_rate": share(answers_passed, len(text_answerable)),
        "by_category": by_category,
        "by_needs": by_needs,
        "image_only_passed": count_passed(image_only, passed_by_id),
        "image_only_scored": len(image_only),
        "citation_pass_rate": share(len(citations_clean), len(with_answer)),
        "refusals_correct": len(correct_refusals),
        "refusals_needed": len(golden_no_answer),
        "probe_refusals_correct": len(correct_probe_refusals),
        "probes": len(probes),
        "no_answer_passed": count_passed(golden_no_answer + probes, passed_by_id),
        "false_premise_passed": count_passed(false_premises, passed_by_id),
        "false_premise_probes": len(false_premises),
        "code_failed": len(code_failed),
        "code_failures_by_check": code_failures_by_check,
        "judge_calls": len(answer_lines) - len(code_failed),
        "false_refusals": len(false_refusals),
        "format_errors": len(answer_lines) - len(with_answer),
        "words_returned": round(mean(line["words_returned"] for line in answer_lines)),
        "cost_per_question": round(mean(costs), 4),
        "total_cost": round(sum(costs), 3),
    }


# ===== Printing the scores =====

def print_scores(scores: dict, answer_lines: list[dict], passed_by_id: dict[str, bool]) -> None:
    """Prints the scores, then every question that failed a check or the judge, for Step 6."""
    print(f"answers  {scores['answers_passed']} of {scores['answers_scored']} passed ({scores['answer_pass_rate']})"
          f"  · image-only {scores['image_only_passed']} of {scores['image_only_scored']}")
    for category, numbers in scores["by_category"].items():
        print(f"  {category:16} {numbers['passed']} of {numbers['questions']}")
    for needs, numbers in scores["by_needs"].items():
        print(f"  needs {needs:12} {numbers['passed']} of {numbers['questions']}")
    print(f"citations clean {scores['citation_pass_rate']}  · format errors {scores['format_errors']}")
    print(f"code checks failed {scores['code_failed']}  {scores['code_failures_by_check']}  · judge calls {scores['judge_calls']}")
    print(f"refusals {scores['refusals_correct']} of {scores['refusals_needed']}  · probes {scores['probe_refusals_correct']} "
          f"of {scores['probes']}  · no-answer passed {scores['no_answer_passed']} of "
          f"{scores['refusals_needed'] + scores['probes']}  · false refusals {scores['false_refusals']}")
    print(f"false premises corrected and answered {scores['false_premise_passed']} of {scores['false_premise_probes']}")
    print(f"words per question {scores['words_returned']}  · cost per question ${scores['cost_per_question']}"
          f"  · total ${scores['total_cost']}")

    # One line per failure: the code checks it failed, or the judge's fail, so Step 6 can tag a cause
    for line in answer_lines:
        if passed_by_id[line["id"]]:
            continue
        reason = "judge fail"
        if line["code_failures"]:
            reason = "; ".join(line["code_failures"])
        print(f"  fail: {line['id']}  {reason}")


# ===== The tool flows' own numbers =====

def requested_top_k(tool_call: dict) -> object:
    """Returns the top_k a search_rules call asked for, as the model sent it (None when it sent none or bad JSON)."""
    arguments = tool_call["arguments"]
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return None
    return arguments.get("top_k")


def summarise_tool_use(answer_lines: list[dict]) -> dict:
    """Returns how the agent used its tools: rounds, calls, errors, questions that reached the limit and the top_k it asked for."""

    # Every tool call in the run, and the top_k of each search
    tool_calls = []
    for line in answer_lines:
        tool_calls.extend(line["tool_calls"])
    requested_top_ks = []
    for tool_call in tool_calls:
        if tool_call["tool"] == "search_rules":
            requested_top_ks.append(requested_top_k(tool_call))
    rounds = [line["tool_rounds"] for line in answer_lines]
    return {
        "mean_tool_rounds": round(mean(rounds), 2),
        "most_tool_rounds": max(rounds),
        "questions_with_no_tool_call": sum(1 for round_count in rounds if round_count == 0),
        "tool_calls": len(tool_calls),
        "tool_errors": sum(1 for call in tool_calls if call["error"]),
        "questions_at_limit": sum(1 for line in answer_lines if line["tools_turned_off"]),
        "mean_model_calls": round(mean(line["model_calls"] for line in answer_lines), 2),
        "bad_picks": sum(len(line["bad_picks"]) for line in answer_lines),
        "questions_with_a_bad_pick": sum(1 for line in answer_lines if line["bad_picks"]),
        "write_calls": sum(1 for line in answer_lines if line["write_called"]),
        "requested_top_ks": requested_top_ks,
    }


def print_tool_use(tool_use: dict) -> None:
    """Prints the agent's tool use, under the Stage 2 scores."""
    print(f"tool rounds  mean {tool_use['mean_tool_rounds']}  · most {tool_use['most_tool_rounds']}  "
          f"· no tool call on {tool_use['questions_with_no_tool_call']} questions  · model calls mean {tool_use['mean_model_calls']}")
    print(f"tool calls {tool_use['tool_calls']}  · errors {tool_use['tool_errors']}  "
          f"· questions that reached the round limit {tool_use['questions_at_limit']}")
    print(f"top_k asked for: {tool_use['requested_top_ks']}")
    print(f"bad picks {tool_use['bad_picks']} on {tool_use['questions_with_a_bad_pick']} questions  "
          f"· write calls {tool_use['write_calls']}")
