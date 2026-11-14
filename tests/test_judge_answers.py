"""
Tests the judge's prompt and its overall grade, without calling the API.
"""

from types import SimpleNamespace

from answer_flows.shared.answer_shape import Citation, RulesAnswer
from evals.judge_answers import (JUDGE_RULES, JUDGE_VOTES, JudgeGrade, RubricLine, build_judge_prompt, combine_votes,
                                 describe_reply, grade_answer, judge_passed)
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
    prompt = build_judge_prompt(SAMPLE_QUESTIONS[1], POSTS_REPLY, SAMPLE_CHUNKS, [])
    assert SAMPLE_QUESTIONS[1]["answer"] in prompt
    assert "[laws-1.4]" in prompt
    assert '- [laws-1.4] "The posts shall be 1.55 metres in height"' in prompt
    assert "<pass_rule>\nNone\n</pass_rule>" in prompt
    assert "Law 1.4 gives the posts' height" not in prompt, "the reasoning is the bot's notes, not shown to the user"


def test_a_question_without_an_answer_shows_why_and_its_pass_rule():
    prompt = build_judge_prompt(SAMPLE_QUESTIONS[2], CEILING_REPLY, SAMPLE_CHUNKS, [])
    assert SAMPLE_QUESTIONS[2]["why_unanswerable"] in prompt
    assert SAMPLE_QUESTIONS[2]["pass_rule"] in prompt
    assert "Citations (the answer's sources):\n(none)" in prompt


def test_the_judge_sees_related_sentences_apart_from_the_answers_sources():
    """14 Nov baseline: with one list, the judge read related laws as the answer and failed correct refusals (record 0025)."""
    related = Citation(chunk_id="laws-1.4", quote="The posts shall be 1.55 metres in height")
    reply = RulesAnswer(reasoning="", refused=True, answer="The sources do not say it.", citations=[],
                        related_citations=[related])
    reply_text = describe_reply(reply)
    assert "Citations (the answer's sources):\n(none)" in reply_text
    assert 'Related sentences (context only, not part of the answer):\n- [laws-1.4] "The posts shall be 1.55 metres in height"' in reply_text


def test_a_run_file_from_before_the_split_still_loads():
    old_line = {"reasoning": "", "refused": False, "answer": "1.55 m.", "citations": [{"chunk_id": "laws-1.4", "quote": "x"}]}
    assert RulesAnswer.model_validate(old_line).related_citations == []


def test_the_code_warnings_reach_the_judge_as_hints():
    prompt = build_judge_prompt(SAMPLE_QUESTIONS[1], POSTS_REPLY, SAMPLE_CHUNKS, ["golden answer numbers not in the reply: 11"])
    assert "<code_notes>\ngolden answer numbers not in the reply: 11\n" in prompt
    assert "Hints, not verdicts" in prompt


def test_without_warnings_the_code_notes_say_none():
    prompt = build_judge_prompt(SAMPLE_QUESTIONS[1], POSTS_REPLY, SAMPLE_CHUNKS, [])
    assert "<code_notes>\nNone\n</code_notes>" in prompt


def test_facts_stated_in_the_question_count_as_given():
    """Run 1: the judge failed "11-point interval", which came from the question, not the sources."""
    assert "or stated in the question" in JUDGE_RULES


def test_the_bots_words_about_itself_are_not_rule_claims():
    """8 Nov: attack-be-the-referee refused correctly but failed for "I answer questions about the rules only"."""
    assert "What the bot says about itself" in JUDGE_RULES


def test_the_prompt_never_names_the_answer_model():
    """Hiding who wrote the answer keeps the judge from favouring or doubting a model by name."""
    prompt = build_judge_prompt(SAMPLE_QUESTIONS[1], POSTS_REPLY, SAMPLE_CHUNKS, [])
    assert "mistral" not in prompt.lower()


# ===== The request =====

class StubJudgeClient:
    """Stub: grades every reply as a pass on all three lines, and records the request."""

    def __init__(self):
        self.requests = []
        self.messages = SimpleNamespace(parse=self.parse)

    def parse(self, **request):
        self.requests.append(request)
        usage = SimpleNamespace(input_tokens=1200, output_tokens=80)
        return SimpleNamespace(parsed_output=grade_with(True, True, True), usage=usage)


def test_the_judge_request_turns_thinking_off_the_way_sonnet_5_5_accepts():
    """Sonnet 5.5 rejects a temperature and rejects thinking type "disabled"; "between_tools" turns it off."""
    client = StubJudgeClient()
    reply = grade_answer(client, "claude-sonnet-5-5", SAMPLE_QUESTIONS[1], POSTS_REPLY, SAMPLE_CHUNKS, [])
    request = client.requests[0]
    assert request["thinking"] == {"type": "between_tools"}
    assert "temperature" not in request
    assert judge_passed(reply.grade)


# ===== Majority of the votes =====

def test_each_rubric_line_goes_with_the_majority_of_the_votes():
    grades = [grade_with(True, False, True), grade_with(True, True, True), grade_with(False, True, True)]
    combined = combine_votes(grades)
    assert combined.key_facts.passed
    assert combined.only_from_sources.passed
    assert judge_passed(combined)


def test_the_judge_is_asked_once_per_vote():
    client = StubJudgeClient()
    grade_answer(client, "claude-sonnet-5-5", SAMPLE_QUESTIONS[1], POSTS_REPLY, SAMPLE_CHUNKS, [])
    assert len(client.requests) == JUDGE_VOTES
