"""
Tests the run script's command line: which flows each setup allows, the agent rules and top k a run gets, and its name.
"""

import pytest

from experiments.run_answer_experiment import GATHER_RULES_BY_FLOW, parse_run_choices, read_code_version


# ===== The defaults each setup gets =====

def test_plain_rag_answers_in_one_call_with_the_default_top_k_and_keeps_its_old_run_names():
    choices = parse_run_choices(["--setup", "plain-rag"])
    assert (choices.flow, choices.top_k, choices.agent_rule_names) == ("single-call", 5, [])
    assert choices.label == "top5"
    assert parse_run_choices(["--setup", "plain-rag", "--held-out"]).label == "top5-held-out"


def test_a_tool_setup_uses_slice_4_and_no_extra_agent_rules_by_default():
    """Record 0024: the two default agent rules became the search steps, so a run names no extra ones."""
    choices = parse_run_choices(["--setup", "hybrid"])
    assert choices.flow == "loop-call-with-tools"
    assert choices.agent_rule_names == []
    assert choices.label == "hybrid"


def test_agentic_has_no_starting_sources_so_no_top_k():
    assert parse_run_choices(["--setup", "agentic"]).top_k is None


def test_a_flow_that_is_not_the_default_is_in_the_run_name():
    choices = parse_run_choices(["--setup", "hybrid", "--flow", "gather-then-write", "--unseen", "--dry-run"])
    assert choices.flow == "gather-then-write"
    assert choices.label == "hybrid-gather-then-write-unseen-dry-run"


# ===== Choices a setup has no use for stop the run before any call =====

@pytest.mark.parametrize("command_line", [
    ["--setup", "plain-rag", "--flow", "gather-then-write"],
    ["--setup", "agentic", "--flow", "single-call"],
    ["--setup", "agentic", "--top-k", "10"],
    ["--setup", "hybrid", "--agent-rule", "check-each-part"],
    ["--setup", "hybrid", "--flow", "gather-then-write", "--rule", "complete-answers"],
])
def test_a_choice_the_setup_has_no_use_for_stops_the_run(command_line):
    with pytest.raises(SystemExit):
        parse_run_choices(command_line)


def test_the_phase2_set_is_its_own_question_set_and_in_the_run_name():
    choices = parse_run_choices(["--setup", "hybrid", "--phase2", "--dry-run"])
    assert choices.question_set == "phase2"
    assert choices.label == "hybrid-phase2-dry-run"


def test_one_run_answers_one_question_set():
    with pytest.raises(SystemExit):
        parse_run_choices(["--setup", "hybrid", "--phase2", "--unseen"])


def test_read_code_version_names_the_commit_and_any_changes():
    """Each run records the commit its code is at, so a result links back to the code that produced it."""
    code_version = read_code_version()
    assert set(code_version) == {"code_commit", "code_has_uncommitted_changes"}
    assert len(code_version["code_commit"]) >= 7
    assert isinstance(code_version["code_has_uncommitted_changes"], bool)


def test_the_retired_per_part_flow_runs_with_its_own_gather_prompt():
    """Record 0027: the per-part slice 5 stays runnable, so 3 runs per flow can compare it with natural answers."""
    choices = parse_run_choices(["--setup", "hybrid", "--flow", "gather-then-write-per-part", "--phase2"])
    assert choices.label == "hybrid-gather-then-write-per-part-phase2"
    assert GATHER_RULES_BY_FLOW["gather-then-write-per-part"] != GATHER_RULES_BY_FLOW["gather-then-write"]


def test_parallel_defaults_to_one_question_at_a_time():
    assert parse_run_choices(["--setup", "hybrid", "--phase2"]).parallel == 1
    assert parse_run_choices(["--setup", "hybrid", "--phase2", "--parallel", "4"]).parallel == 4


def test_parallel_below_one_stops_the_run():
    with pytest.raises(SystemExit):
        parse_run_choices(["--setup", "hybrid", "--parallel", "0"])
