"""
Tests the judge's prompt and its overall grade, without calling the API.
"""

from answer.answer_shape import Citation, RulesAnswer
from evals.judge_answers import JudgeGrade, RubricLine, build_judge_prompt, judge_passed
from tests.sample_data import SAMPLE_CHUNKS, SAMPLE_QUESTIONS


# ===== Sample replies =====

POSTS_REPLY = RulesAnswer(
    reasoning="Law 1.4 gives the posts' height, which is what was asked.",
    answer="The posts are 1.55 metres high (Laws of Badminton 5.0 (2), Law 1.4).",
    citations=[Citation(chunk_id="laws-1.4", quote="The posts shall be 1.55 metres in height")],
    refused=False,
)
CEILING_REPLY = RulesAnswer(reasoning="No source gives a ceiling height.", refused=True,
                            answer="The sources give no ceiling height.", citations=[])


def grade_with(key_facts: bool, only_from_sources: bool, follows_pass_rule: bool) -> JudgeGrade:
    """Returns a grade with the given pass or fail on each rubric line."""
    return JudgeGrade(
        key_facts=RubricLine(passed=key_facts, reason="sample reason"),
        only_from_sources=RubricLine(passed=only_from_sources, reason="sample reason"),
        follows_pass_rule=RubricLine(passed=follows_pass_rule, reason="sample reason"),
    )


# ===== The overall grade =====

def test_the_answer_passes_only_when_every_rubric_line_passes():
    assert judge_passed(grade_with(True, True, True))
    assert not judge_passed(grade_with(True, False, True))
    assert not judge_passed(grade_with(False, True, True))
    assert not judge_passed(grade_with(True, True, False))


# ===== The prompt =====

def test_the_prompt_holds_the_expected_answer_the_sources_and_the_reply():
    prompt = build_judge_prompt(SAMPLE_QUESTIONS[1], POSTS_REPLY, SAMPLE_CHUNKS)
    assert SAMPLE_QUESTIONS[1]["answer"] in prompt
    assert "[laws-1.4]" in prompt
    assert '- [laws-1.4] "The posts shall be 1.55 metres in height"' in prompt
    assert "<pass_rule>\nNone\n</pass_rule>" in prompt
    assert "Reasoning: Law 1.4 gives the posts' height" in prompt


def test_a_question_without_an_answer_shows_why_and_its_pass_rule():
    prompt = build_judge_prompt(SAMPLE_QUESTIONS[2], CEILING_REPLY, SAMPLE_CHUNKS)
    assert SAMPLE_QUESTIONS[2]["why_unanswerable"] in prompt
    assert SAMPLE_QUESTIONS[2]["pass_rule"] in prompt
    assert "Citations:\n(none)" in prompt


def test_the_prompt_never_names_the_answer_model():
    """Hiding who wrote the answer keeps the judge from favouring or doubting a model by name."""
    prompt = build_judge_prompt(SAMPLE_QUESTIONS[1], POSTS_REPLY, SAMPLE_CHUNKS)
    assert "mistral" not in prompt.lower()
