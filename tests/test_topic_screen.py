"""
Tests for the topic check (docs/specs/refuse-off-topic-questions-fast.md): a topic check runs before the search.
An off-topic question gets the fixed off-topic reply with no search and no model call (criterion 1); a failing
check lets the question through to the full flow (criterion 5); every refusal says which kind it is.

The bot runs on a stub client and a stub search, so no test calls the API.
"""

import pytest

from answer_flows.rules_bot import RulesBot
from answer_flows.shared.answer_shape import RulesAnswer
from answer_flows.shared.progress_updates import CHECKING_QUESTION, FINDING_RULES, ProgressUpdate
from answer_flows.topic_screen import OFF_TOPIC_REPLY, build_off_topic_answer, is_rules_question_by_stub
from app.stub_rules_bot import SAMPLE_REFUSAL_ANSWER_FILE
from tests.test_gather_then_write import GATHER_REPLY, REFUSAL_GATHER_REPLY, StubTwoCallClient
from tests.test_rules_bot import CHUNKS, NEW_QUESTION, RULE_MAP, SETTINGS, StubSearch


# ===== Test helpers =====

# Returns a bot on the stub client and search, with the given topic check
def build_bot_with_check(client: StubTwoCallClient, stub_search: StubSearch, is_rules_question) -> RulesBot:
    return RulesBot(client, SETTINGS, CHUNKS, RULE_MAP, stub_search.search, is_rules_question=is_rules_question)


# Answers one question and returns the answer with every progress update it sent
def answer_with_updates(rules_bot: RulesBot, question_text: str) -> tuple[RulesAnswer, list[ProgressUpdate]]:
    updates = []
    rules_answer = rules_bot.answer(question_text, report_progress=updates.append)
    return rules_answer, updates


# Stub checks: one calls every question off topic, one every question a rules question
def call_off_topic(question_text: str) -> bool:
    return False


def call_on_topic(question_text: str) -> bool:
    return True


# ===== Off topic (criterion 1) =====

def test_an_off_topic_question_gets_the_reply_with_no_search_and_no_model_call():
    client = StubTwoCallClient(GATHER_REPLY)
    stub_search = StubSearch()

    rules_answer, updates = answer_with_updates(build_bot_with_check(client, stub_search, call_off_topic), "test")

    assert rules_answer.refused
    assert rules_answer.refusal_kind == "off_topic"
    assert rules_answer.answer == OFF_TOPIC_REPLY
    assert rules_answer.citations == []
    assert rules_answer.related_citations == []
    assert client.requests == []
    assert stub_search.queries == []
    assert [update.step for update in updates] == [CHECKING_QUESTION]
    assert updates[0].message == "Checking the question"


# ===== On topic =====

def test_a_rules_question_passes_the_check_and_runs_the_full_flow():
    client = StubTwoCallClient(GATHER_REPLY)

    rules_answer, updates = answer_with_updates(build_bot_with_check(client, StubSearch(), call_on_topic), NEW_QUESTION)

    assert not rules_answer.refused
    assert rules_answer.refusal_kind is None
    assert len(client.requests) == 2
    assert [update.step for update in updates[:2]] == [CHECKING_QUESTION, FINDING_RULES]


# ===== A failing check (criterion 5) =====

@pytest.mark.parametrize("check_error", [TimeoutError("no reply in 5 s"), ConnectionError("Mistral did not answer")])
def test_a_failing_check_lets_the_question_through_to_the_full_flow(check_error):
    def failing_check(question_text: str) -> bool:
        raise check_error

    client = StubTwoCallClient(GATHER_REPLY)
    rules_answer, updates = answer_with_updates(build_bot_with_check(client, StubSearch(), failing_check), NEW_QUESTION)

    assert not rules_answer.refused
    assert len(client.requests) == 2


# ===== Which kind of refusal =====

def test_a_refusal_from_the_flow_is_marked_not_covered():
    client = StubTwoCallClient(REFUSAL_GATHER_REPLY)

    rules_answer, updates = answer_with_updates(build_bot_with_check(client, StubSearch(), call_on_topic), NEW_QUESTION)

    assert rules_answer.refused
    assert rules_answer.refusal_kind == "not_covered"


def test_an_answer_from_before_the_field_existed_still_loads():
    old_refusal = RulesAnswer.model_validate_json(SAMPLE_REFUSAL_ANSWER_FILE.read_text(encoding="utf-8"))

    assert old_refusal.refused
    assert old_refusal.refusal_kind is None


# ===== The stub check of this slice =====

@pytest.mark.parametrize("question_text", ["test", "Test", " test "])
def test_the_stub_check_calls_test_off_topic(question_text):
    assert not is_rules_question_by_stub(question_text)


def test_the_stub_check_passes_a_rules_question():
    assert is_rules_question_by_stub("How tall are the posts?")


def test_the_off_topic_answer_is_one_fixed_refusal():
    assert build_off_topic_answer() == build_off_topic_answer()
    assert build_off_topic_answer().refusal_kind == "off_topic"
