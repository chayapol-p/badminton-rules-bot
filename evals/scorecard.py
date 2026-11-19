"""
The scorecard (record 0027): every judge line and code check as pass or fail, logged per answer and reported
per run as a share of answers, plus one combined metric for comparing experiments.

Per answer, each line passes or fails:
  correct          the judge's key_facts line
  grounded         the judge's only_from_sources line (each [n] marked claim checked against source n)
  behaviour        the judge's follows_pass_rule line
  readable         the judge's readable line: tracked, never failing an answer
  refusal_right    no missed or false refusal (code)
  citations_valid  no citation problem, markers included (code)
  right_clause     cites a clause that holds the golden answer (code; a gate line with no weight)
An answer passes only when every gate line passes. A format error has no text, so every line fails.

Per run: each line's share of answers, the share that passed the gate, and the combined metric, a weighted sum
of the shares out of 100. Record 0026 calls a win when two flows' ranges of this metric over 3 runs don't overlap.

Use:
    grade_line["scorecard"] = build_scorecard(answer_line, grade)
    run_scorecard = summarise_scorecards(grade_lines)
    print_scorecard(run_scorecard)
"""

from evals.checks.check_refusals import FALSE_REFUSAL, MISSED_REFUSAL


# Constants
## The scorecard's lines, each from the judge's rubric line or a code check
JUDGE_LINE_BY_SCORECARD_LINE = {"correct": "key_facts", "grounded": "only_from_sources",
                                "behaviour": "follows_pass_rule", "readable": "readable"}
CODE_LINES = ["refusal_right", "citations_valid", "right_clause"]
SCORECARD_LINES = list(JUDGE_LINE_BY_SCORECARD_LINE) + CODE_LINES

## The lines an answer must pass to pass (record 0027); readable is tracked only
GATE_LINES = ["correct", "grounded", "behaviour", "citations_valid", "refusal_right", "right_clause"]

## The combined metric's weight per line, out of 100 (record 0027). Citations valid and right clause have none:
## they are almost always passed and would only add noise
METRIC_WEIGHTS = {"correct": 30, "grounded": 35, "behaviour": 10, "refusal_right": 10, "readable": 15}

## Refusal outcomes that fail the refusal line
WRONG_REFUSALS = {MISSED_REFUSAL, FALSE_REFUSAL}


# ===== One answer =====

def cites_wrong_clause(answer_line: dict) -> bool:
    """True when the code checks found that the answer cites none of the clauses that hold the golden answer."""
    for failure in answer_line["code_failures"]:
        if failure.startswith("wrong clause"):
            return True
    return False


def build_scorecard(answer_line: dict, grade: dict | None) -> dict[str, bool]:
    """Returns one answer's scorecard: pass or fail on every line, then whether it passed the gate."""

    # A format error has no text to check or judge, so every line fails
    if answer_line["is_format_error"]:
        scorecard = {line_name: False for line_name in SCORECARD_LINES}
        scorecard["passed"] = False
        return scorecard

    # The judge's lines, then the code checks'
    scorecard = {}
    for scorecard_line, judge_line in JUDGE_LINE_BY_SCORECARD_LINE.items():
        scorecard[scorecard_line] = grade[judge_line]["passed"]
    scorecard["refusal_right"] = answer_line["refusal_outcome"] not in WRONG_REFUSALS
    scorecard["citations_valid"] = not answer_line["citation_problems"]
    scorecard["right_clause"] = not cites_wrong_clause(answer_line)

    # The answer passes only when every gate line passes
    scorecard["passed"] = all(scorecard[line_name] for line_name in GATE_LINES)
    return scorecard


# ===== One run =====

def count_passing(scorecards: list[dict], line_name: str) -> int:
    """Returns how many of the scorecards passed one line."""
    passed_count = 0
    for scorecard in scorecards:
        if scorecard[line_name]:
            passed_count += 1
    return passed_count


def summarise_scorecards(grade_lines: list[dict]) -> dict:
    """Returns the run's share of answers passing each line, the share passing the gate, and the combined metric."""
    scorecards = [grade_line["scorecard"] for grade_line in grade_lines]
    answer_count = len(scorecards)

    # Each line's share of answers, rounded as the other run scores are
    line_shares = {}
    for line_name in SCORECARD_LINES:
        line_shares[line_name] = round(count_passing(scorecards, line_name) / answer_count, 3)

    # The combined metric, from the unrounded shares so rounding never moves it
    combined_metric = 0.0
    for line_name, weight in METRIC_WEIGHTS.items():
        combined_metric += weight * count_passing(scorecards, line_name) / answer_count
    return {"line_shares": line_shares, "gate_passed": count_passing(scorecards, "passed"), "answers": answer_count,
            "combined_metric": round(combined_metric, 2)}


def print_scorecard(run_scorecard: dict) -> None:
    """Prints the run's scorecard: the combined metric, the gate, then every line's share."""
    print(f"combined metric {run_scorecard['combined_metric']} of 100  · gate passed {run_scorecard['gate_passed']} "
          f"of {run_scorecard['answers']}")
    shares = "  ".join(f"{line_name} {share}" for line_name, share in run_scorecard["line_shares"].items())
    print(f"  {shares}")
