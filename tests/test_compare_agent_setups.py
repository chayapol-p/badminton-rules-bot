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
