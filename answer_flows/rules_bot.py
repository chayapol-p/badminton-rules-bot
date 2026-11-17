"""
The product entry point: the one function the app calls to answer a rules question.

It runs the product flow, gather-then-write (record 0023, slice 5, with record 0027's natural answers), in the
hybrid setup: the retrieve step hands over the top clauses, then the gather call searches with the tools.
Both searches embed each new question with one live call, so any question works, not only the saved ones.

load_rules_bot reads the clauses, the rule map and the settings once; RulesBot.answer answers one question.
A reply that doesn't fit the answer shape raises AnswerFormatError, naming which call failed and why.
While it works, it sends progress updates (answer_flows/shared/progress_updates.py) to the function the app
passes in: the steps in plain words, then the quoted sources before the write call starts.

Use:
    rules_bot = load_rules_bot()
    rules_answer = rules_bot.answer("How tall are the posts?", report_progress=send_to_browser)
    rules_answer.answer_sentences   # the answer, sentence by sentence, with [n] markers
    rules_answer.citations          # marker [n] is citations[n - 1]: its quote and source name
"""

from collections.abc import Callable

from mistralai.client import Mistral

from answer_flows.gather_then_write.gather_and_write_rules import GATHER_RULES
from answer_flows.gather_then_write.gather_then_write import gather_then_write
from answer_flows.shared.answer_shape import RulesAnswer
from answer_flows.shared.mistral_client import build_mistral_client
from answer_flows.shared.progress_updates import (FINDING_RULES, ProgressUpdate, ReportProgress,
                                                  describe_found_rules, ignore_progress)
from answer_flows.shared.rule_tools import RuleTools
from app.settings import Settings, load_settings
from evals.golden_answer_chunks import load_chunks
from retrieval.build_bundle import full_chunks
from retrieval.expand_with_rule_links import load_rule_map
from retrieval.retrieve_sources import DEFAULT_TOP_K, build_live_vector_search, build_retrieve_function


# ===== A failed answer =====

class AnswerFormatError(RuntimeError):
    """A model reply that doesn't fit the answer shape; the message names the call and the reason."""


# ===== The bot =====

class RulesBot:
    """Answers rules questions with the product flow; holds what every question shares."""

    def __init__(self, mistral_client: Mistral, settings: Settings, chunks: list[dict], rule_map: dict,
                 search_function: Callable[[str, int], list[dict]]):
        self.mistral_client = mistral_client
        self.settings = settings
        self.chunks = chunks
        self.rule_map = rule_map
        self.search_function = search_function
        chunk_by_id = {chunk["id"]: chunk for chunk in chunks}
        self.retrieve = build_retrieve_function(search_function, DEFAULT_TOP_K, chunk_by_id, rule_map)

    def answer(self, question_text: str, report_progress: ReportProgress = ignore_progress) -> RulesAnswer:
        """Answers one question: a natural answer with [n] markers and its sources, or a refusal.
        Sends each step to report_progress as it happens, so the app can show it during the wait."""

        # The tools keep which clauses this question has seen, so each question gets fresh ones
        rule_tools = RuleTools(self.chunks, self.search_function, self.rule_map)

        # The retrieve step, then the two calls with the code gate between them
        report_progress(ProgressUpdate(step=FINDING_RULES, message="Searching the rule books"))
        starting_items = self.retrieve(question_text)
        report_progress(describe_found_rules(full_chunks(starting_items)))
        reply = gather_then_write(self.mistral_client, self.settings.mistral_answer_model,
                                  self.settings.mistral_reasoning_effort, GATHER_RULES, question_text,
                                  starting_items, rule_tools, report_progress=report_progress)

        # The app shows a failed answer as an error, so it must never pass as an empty answer
        if reply.is_format_error:
            raise AnswerFormatError(reply.error_message)
        return reply.answer


# ===== Loading =====

def load_rules_bot() -> RulesBot:
    """Returns a RulesBot with the settings, the real client, the clauses, the rule map and the live search."""
    settings = load_settings()
    mistral_client = build_mistral_client(settings)
    chunks = load_chunks()
    live_search = build_live_vector_search(chunks, mistral_client, settings.mistral_embedding_model)
    return RulesBot(mistral_client, settings, chunks, load_rule_map(), live_search.search)
