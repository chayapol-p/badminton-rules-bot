"""
Slice 5: answers one question in two calls with a code gate between them.

1. Gather call: the same tool loop as slice 4 (answer_flows/shared/tool_loop.py run_tool_loop), with GATHER_RULES and
   the tools section. It sends GatheredAnswer: the sentences that answer each part, and no answer text.
2. Code checks each pick, drops the bad ones and records them (answer_flows/gather_then_write/assemble_written_answer.py).
3. Gate: when no part has a sentence left, code refuses and the write call never runs.
4. Write call: no tools. It sees only the question and every part, each marked NO SOURCE or given with its
   picked sentences numbered [1]…[n], and sends WrittenAnswer: one natural answer, sentence by sentence, with
   inline [n] markers and its gaps flagged (record 0027). It never sees the tool calls, the unpicked results
   or the gather call's reasoning.
5. Code builds the answer from both calls, with the numbered source list.

The signature matches answer_with_tools, so a run picks either one with --flow.

Use:
    reply = gather_then_write(client, model, reasoning_effort, GATHER_RULES, question_text, starting_items, rule_tools)
"""

from mistralai.client import Mistral
from mistralai.extra import response_format_from_pydantic_model
from pydantic import ValidationError

from answer_flows.gather_then_write.answer_shape import GatheredAnswer, WrittenAnswer
from answer_flows.gather_then_write.assemble_written_answer import (assemble_written_answer, build_refusal,
                                                                    check_gathered_picks, format_parts_for_writer,
                                                                    is_refusal)
from answer_flows.gather_then_write.gather_and_write_rules import build_write_prompt
from answer_flows.shared.read_model_reply import MAX_ANSWER_TOKENS, split_reply_content
from answer_flows.shared.flow_reply import FlowReply
from answer_flows.shared.rule_tools import RuleTools
from answer_flows.shared.tool_loop import build_agent_prompt, run_tool_loop


# ===== The write call =====

def call_writer(client: Mistral, model: str, reasoning_effort: str, question_text: str, parts_text: str):
    """Sends the write call, with no tools, at the fixed settings of every eval run, and returns the response."""
    return client.chat.complete(
        model=model,
        messages=build_write_prompt(question_text, parts_text),
        response_format=response_format_from_pydantic_model(WrittenAnswer),
        reasoning_effort=reasoning_effort,
        temperature=0,
        top_p=1,
        max_tokens=MAX_ANSWER_TOKENS,
    )


# ===== One answer, in two calls =====

def gather_then_write(client: Mistral, model: str, reasoning_effort: str, gather_rules: str, question_text: str,
                      starting_items: list[dict], rule_tools: RuleTools,
                      extra_agent_rule_names: list[str] | None = None) -> FlowReply:
    """Answers one question: the gather call picks sentences with the tools, code decides the refusal, the write call answers."""

    # Gather call: the tool loop, in the GatheredAnswer shape
    messages = build_agent_prompt(gather_rules, question_text, starting_items, extra_agent_rule_names)
    loop_result = run_tool_loop(client, model, reasoning_effort, messages, starting_items, rule_tools, GatheredAnswer)
    shown_chunk_by_id = loop_result.shown_chunk_by_id
    raw_reply, thinking = split_reply_content(loop_result.choice.message.content)
    reply = FlowReply(
        answer=None,
        is_format_error=True,
        error_message=None,
        raw_reply=raw_reply,
        thinking=thinking,
        shown_chunks=list(shown_chunk_by_id.values()),
        tool_rounds=loop_result.tool_rounds,
        tool_calls=loop_result.tool_calls,
        tools_turned_off=loop_result.tools_turned_off,
        model_calls=loop_result.model_calls,
        input_tokens=loop_result.input_tokens,
        output_tokens=loop_result.output_tokens,
    )

    # A gather reply that doesn't fit the shape is a format error, as in slice 4; the run goes on
    try:
        gathered_answer = GatheredAnswer.model_validate_json(raw_reply)
    except ValidationError as error:
        reply.error_message = f"gather call, finish reason {loop_result.choice.finish_reason}: {error}"
        return reply

    # Keep the parts as the gather call sent them, before code drops any bad pick
    reply.gathered_parts = [part.model_dump() for part in gathered_answer.parts]

    # Code checks the picks; the gate refuses when no part has a sentence left, with no write call
    checked_answer, reply.bad_picks = check_gathered_picks(gathered_answer, shown_chunk_by_id)
    if is_refusal(checked_answer):
        reply.answer = build_refusal(checked_answer, shown_chunk_by_id)
        reply.is_format_error = False
        return reply

    # Write call: only the question and the parts, with no tools
    parts_text = format_parts_for_writer(checked_answer, shown_chunk_by_id, loop_result.label_by_id)
    response = call_writer(client, model, reasoning_effort, question_text, parts_text)
    write_choice = response.choices[0]
    reply.write_called = True
    reply.model_calls += 1
    reply.input_tokens += response.usage.prompt_tokens
    reply.output_tokens += response.usage.completion_tokens

    # Keep the write call's raw reply and both calls' thinking, so a failure can be read in the run file
    write_raw_reply, write_thinking = split_reply_content(write_choice.message.content)
    reply.write_reply = write_raw_reply
    reply.thinking = f"gather: {thinking}\nwrite: {write_thinking}"

    # A write reply that doesn't fit the shape, or has no sentence, is a format error; the markers are checked later
    try:
        written_answer = WrittenAnswer.model_validate_json(write_raw_reply)
    except ValidationError as error:
        reply.error_message = f"write call, finish reason {write_choice.finish_reason}: {error}"
        return reply
    reply.answer, reply.error_message = assemble_written_answer(checked_answer, written_answer, shown_chunk_by_id)
    reply.is_format_error = reply.answer is None
    return reply
