"""
Tests the answer prompt: the rules of each prompt version, and the sources and question in their tags.
"""

import hashlib

from answer.answer_shape import RulesAnswer
from answer.build_answer_prompt import (ANSWER_RULES, EXTRA_ANSWER_RULES, RULES_SUBJECT, build_answer_prompt,
                                        build_answer_rules)


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
    field_names = list(RulesAnswer.model_json_schema()["properties"])
    assert field_names == ["reasoning", "refused", "answer", "citations"]


# ===== Extra rules under test =====

def test_no_extra_rules_leaves_the_standing_rules_unchanged():
    assert build_answer_rules([]) == ANSWER_RULES


def test_extra_rules_are_numbered_on_after_the_standing_rules():
    rules_text = build_answer_rules(["complete-answers"])
    assert rules_text.startswith(ANSWER_RULES)
    assert rules_text.endswith(f"\n11. {EXTRA_ANSWER_RULES['complete-answers']}")
    assert "\n10. " in ANSWER_RULES and "\n11. " not in ANSWER_RULES


# ===== Prompt versions (Stage 3) =====

## sha256 of version 1's answer rules, taken at commit 123e484 before version 2 was added (10 Nov 2026),
## so every earlier run's prompt stays reproducible
VERSION_1_ANSWER_RULES_SHA256 = "7a3ebfc2332caffc4fb4806c7fa11ac9534042c71c79ed6ebd7fab486276ebaf"

## One phrase from each of version 2's nine rules, by rule number, as reviewed in the Stage 3 handoff
VERSION_2_RULE_PHRASES = {
    1: "Answer only questions about the rules of badminton.",
    2: "Every statement in the answer must rest on a quote you cite.",
    3: "Set refused to true only when every part is \"none\". A partial answer keeps refused false.",
    4: "Correcting an assumption is not a refusal.",
    5: "state every requirement it sets on the thing asked",
    6: "name who it applies to, in the question's own terms",
    7: "Mention the general rule only afterwards, and only to say it does not apply.",
    8: "Cite each clause your answer uses once, and no clause it does not use.",
    9: "A quote is one continuous run of words, copied character for character",
}


def sha256_of(text: str) -> str:
    """Returns the sha256 of a text, as hex."""
    return hashlib.sha256(text.encode()).hexdigest()


def rule_line(rules_text: str, rule_number: int) -> str:
    """Returns the line of the rules text that starts with the rule's number."""
    for line in rules_text.splitlines():
        if line.startswith(f"{rule_number}. "):
            return line
    raise AssertionError(f"no rule {rule_number}")


def test_version_1_builds_exactly_the_answer_rules_of_every_earlier_run():
    assert build_answer_rules([], prompt_version=1) == build_answer_rules([])
    assert sha256_of(build_answer_rules([])) == VERSION_1_ANSWER_RULES_SHA256


def test_version_2_holds_each_reviewed_rule_under_its_number():
    rules_text = build_answer_rules([], prompt_version=2)
    for rule_number, phrase in VERSION_2_RULE_PHRASES.items():
        assert phrase in rule_line(rules_text, rule_number)
    assert "\n10. " not in rules_text, "version 2 has nine rules"


def test_version_2_fills_in_the_subject_and_drops_version_1s_badminton_wording():
    rules_text = build_answer_rules([], prompt_version=2)
    assert "{subject}" not in rules_text
    assert rules_text.startswith(f"You answer questions about {RULES_SUBJECT}.")
    assert "Para Badminton" not in rules_text, "version 2's rule 7 is generic"
    assert "Alternative Laws" not in rules_text
