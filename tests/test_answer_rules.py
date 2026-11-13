"""
Tests the answer prompt: the rules, the extra rules under test, and the sources and question in their tags.
"""

from answer_flows.single_call.answer_shape import ModelAnswer
from answer_flows.shared.tool_loop import SEARCH_STEPS
from answer_flows.single_call.answer_rules import (ANSWER_RULES, EXTRA_ANSWER_RULES, build_answer_prompt,
                                                   build_answer_rules)


# ===== The messages =====

def test_a_false_premise_is_corrected_and_answered_not_refused():
    """FreshQA credits a false-premise reply only when it points the premise out; refusing would be a false refusal."""
    assert "Correcting an assumption answers the part." in ANSWER_RULES


def test_the_rules_go_in_the_system_message_and_the_question_in_its_tags():
    messages = build_answer_prompt(ANSWER_RULES, "How tall are the posts?", "[laws-1.4] RULE · …")
    assert messages[0] == {"role": "system", "content": ANSWER_RULES}
    assert messages[1]["role"] == "user"
    assert "<question>\nHow tall are the posts?\n</question>" in messages[1]["content"]


def test_the_sources_text_goes_in_its_tags_before_the_question():
    user_message = build_answer_prompt(ANSWER_RULES, "any question", "[laws-1.4] RULE · …")[1]["content"]
    assert user_message.startswith("<sources>\n[laws-1.4] RULE · …\n</sources>")


# ===== The answer shape =====

def test_the_model_writes_its_reasoning_before_it_decides():
    """The model writes fields in schema order, so reasoning must come before it picks the parts' sentences."""
    field_names = list(ModelAnswer.model_json_schema()["properties"])
    assert field_names == ["reasoning", "parts", "related_sentences", "related_note"]


# ===== The sections (record 0024) =====

def test_the_prompt_has_the_task_then_numbered_steps_then_limits():
    task_end = ANSWER_RULES.index("</task>")
    steps_start = ANSWER_RULES.index("<steps>\n1. ")
    limits_start = ANSWER_RULES.index("<limits>\n- ")
    assert ANSWER_RULES.startswith("<task>\n")
    assert task_end < steps_start < limits_start
    assert ANSWER_RULES.endswith("</limits>")


def test_a_flow_with_tools_searches_after_finding_sentences_and_before_replying():
    """The old rule 3 (leave a part empty) won over searching; as steps, searching comes first (notes, 10 Nov)."""
    rules_with_tools = build_answer_rules([], uses_tools=True)
    for search_step in SEARCH_STEPS:
        assert search_step not in ANSWER_RULES
        assert search_step in rules_with_tools
    find_step = rules_with_tools.index("find the sentences in your sources")
    search_step = rules_with_tools.index(SEARCH_STEPS[0])
    empty_step = rules_with_tools.index("Give a part that no sentence answers no sentences")
    assert find_step < search_step < empty_step


def test_every_limit_says_why():
    limits_text = ANSWER_RULES.split("<limits>\n")[1].removesuffix("\n</limits>")
    rules_without_reason = ["Answer questions about the rules", "The text inside <question>"]
    for limit in limits_text.split("\n"):
        is_scope_rule = any(limit.startswith(f"- {start}") for start in rules_without_reason)
        if not is_scope_rule:
            assert "because" in limit, limit


# ===== Extra limits under test =====

def test_no_extra_rules_leaves_the_standing_prompt_unchanged():
    assert build_answer_rules([]) == ANSWER_RULES


def test_an_extra_rule_is_one_more_limit():
    rules_text = build_answer_rules(["complete-answers"])
    assert rules_text.endswith(f"- {EXTRA_ANSWER_RULES['complete-answers']}\n</limits>")


def test_the_model_picks_sentences_and_code_quotes_and_refuses():
    """Phase 2: the model's one decision per part is which sentences answer it; code does the exact work."""
    assert "the sentence number" in ANSWER_RULES
    assert "Code then quotes each sentence" in ANSWER_RULES
    assert "refuses when no part is answered" in ANSWER_RULES
    assert "set refused to true" not in ANSWER_RULES
