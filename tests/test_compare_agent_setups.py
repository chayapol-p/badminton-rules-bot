"""
Tests the agent run script's command line: prompt version 2 can't be combined with an extra agent rule.
"""

import pytest

from experiments.compare_agent_setups import main as run_agent_setup_from_command_line


def test_prompt_version_2_with_an_extra_agent_rule_stops_before_any_call(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["compare_agent_setups", "--setup", "hybrid", "--prompt-version", "2",
                                     "--agent-rule", "check-each-part"])
    with pytest.raises(SystemExit):
        run_agent_setup_from_command_line()
    assert "drop --agent-rule" in capsys.readouterr().err


def capture_run_arguments(monkeypatch, command_line: list[str]) -> tuple:
    """Runs the command line with a stub in place of the run, and returns the arguments the run would get."""
    captured = []
    monkeypatch.setattr("experiments.compare_agent_setups.run_agent_setup",
                        lambda *arguments: captured.append(arguments))
    monkeypatch.setattr("sys.argv", ["compare_agent_setups"] + command_line)
    run_agent_setup_from_command_line()
    return captured[0]


def test_prompt_version_1_runs_with_both_agent_rules_by_default(monkeypatch):
    """Record 0022: setup C keeps check-each-part and search-before-gaps."""
    arguments = capture_run_arguments(monkeypatch, ["--setup", "hybrid"])
    assert arguments[4] == ["check-each-part", "search-before-gaps"]
    assert arguments[1] == "hybrid-check-each-part-search-before-gaps"


def test_no_agent_rules_reproduces_the_runs_before_record_0022(monkeypatch):
    arguments = capture_run_arguments(monkeypatch, ["--setup", "hybrid", "--no-agent-rules"])
    assert arguments[4] == []


def test_prompt_version_2_gets_no_extra_rules_by_default(monkeypatch):
    arguments = capture_run_arguments(monkeypatch, ["--setup", "hybrid", "--prompt-version", "2"])
    assert arguments[4] == []
