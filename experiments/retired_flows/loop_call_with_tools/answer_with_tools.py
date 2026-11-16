"""
Slice 4: answers one question with tools in one call shape, ModelAnswer. The tool loop
(answer_flows/shared/tool_loop.py) runs until the model replies with no tool calls; that reply holds the
sentences per part and each part's answer, and code builds the checked answer from it.

Use:
    reply = answer_with_tools(client, model, reasoning_effort, answer_rules, question_text, starting_items, rule_tools)
"""

from mistralai.client import Mistral
from pydantic import ValidationError

from answer_flows.shared.answer_shape import RulesAnswer
from answer_flows.shared.read_model_reply import split_reply_content
from answer_flows.shared.flow_reply import FlowReply
from answer_flows.shared.rule_tools import RuleTools
from answer_flows.shared.tool_loop import build_agent_prompt, run_tool_loop
from experiments.retired_flows.single_call.answer_shape import ModelAnswer
from experiments.retired_flows.single_call.assemble_answer import assemble_answer


# ===== Reading the final reply =====

def parse_final_reply(choice, shown_chunk_by_id: dict[str, dict]) -> tuple[RulesAnswer | None, str | None, str, str]:
    """Returns the answer code builds from the reply (or None), the format error message (or None), the raw reply and the thinking."""
    raw_reply, thinking = split_reply_content(choice.message.content)
    try:
        model_answer = ModelAnswer.model_validate_json(raw_reply)
        return assemble_answer(model_answer, shown_chunk_by_id), None, raw_reply, thinking
    except ValidationError as error:
        return None, f"finish reason {choice.finish_reason}: {error}", raw_reply, thinking


# ===== One agent answer, in one call =====

def answer_with_tools(client: Mistral, model: str, reasoning_effort: str, answer_rules: str, question_text: str,
                      starting_items: list[dict], rule_tools: RuleTools,
                      extra_agent_rule_names: list[str] | None = None) -> FlowReply:
    """Answers one question, calling tools until the model replies with no tool calls."""
    messages = build_agent_prompt(answer_rules, question_text, starting_items, extra_agent_rule_names)
    loop_result = run_tool_loop(client, model, reasoning_effort, messages, starting_items, rule_tools, ModelAnswer)

    # The last reply is the answer, or a format error that still reports its tokens
    rules_answer, error_message, raw_reply, thinking = parse_final_reply(loop_result.choice,
                                                                         loop_result.shown_chunk_by_id)
    return FlowReply(
        answer=rules_answer,
        is_format_error=rules_answer is None,
        error_message=error_message,
        raw_reply=raw_reply,
        thinking=thinking,
        shown_chunks=list(loop_result.shown_chunk_by_id.values()),
        tool_rounds=loop_result.tool_rounds,
        tool_calls=loop_result.tool_calls,
        tools_turned_off=loop_result.tools_turned_off,
        model_calls=loop_result.model_calls,
        input_tokens=loop_result.input_tokens,
        output_tokens=loop_result.output_tokens,
    )
