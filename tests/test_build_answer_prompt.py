"""
Tests the answer prompt: the rules, the extra rules under test, and the sources and question in their tags.
"""

from answer.answer_shape import ModelAnswer
from answer.build_answer_prompt import ANSWER_RULES, EXTRA_ANSWER_RULES, build_answer_prompt, build_answer_rules


# ===== The messages =====

def test_a_false_premise_is_corrected_and_answered_not_refused():
    """FreshQA credits a false-premise reply only when it points the premise out; refusing would be a false refusal."""
    assert "Correcting an assumption is an answer, not a refusal" in ANSWER_RULES


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
    """The model writes fields in schema order, so reasoning must come before refused and the answer."""
    field_names = list(ModelAnswer.model_json_schema()["properties"])
    assert field_names == ["reasoning", "refused", "answer", "citations"]


# ===== Extra rules under test =====

def test_no_extra_rules_leaves_the_standing_rules_unchanged():
    assert build_answer_rules([]) == ANSWER_RULES


def test_extra_rules_are_numbered_on_after_the_standing_rules():
    rules_text = build_answer_rules(["complete-answers"])
    assert rules_text.startswith(ANSWER_RULES)
    assert rules_text.endswith(f"\n11. {EXTRA_ANSWER_RULES['complete-answers']}")
    assert "\n10. " in ANSWER_RULES and "\n11. " not in ANSWER_RULES


def test_the_model_cites_a_sentence_number_not_a_quote():
    """Phase 2: code copies the cited sentence in, so the rules never ask the model to copy words."""
    assert "the number of the sentence that supports it" in ANSWER_RULES
    assert "quote the exact words" not in ANSWER_RULES
