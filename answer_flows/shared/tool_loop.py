"""
The tool loop every agent flow uses (slice 4's one call, slice 5's gather call): the model searches and reads
clauses until it replies with no tool calls, in the answer shape the flow asks for.

The loop (Stage 3):
1. Send the question, with the starting sources (setup C) or none (setup B), and the two tools.
2. Read the reply's finish reason:
   "tool_calls"  run each tool it asks for, add the results, and ask again
   "stop"        the reply is the answer
   "length"      the reply was cut off: a format error, as in Stage 2
3. Tool round limit: a round is one reply that asks for tools, however many tools it asks for.
   Round 10 is the last: its tools run, its last tool result gets a note saying the tools are now
   off, and the next call can only answer. The note matters: in a live check (9 Nov), a model whose
   tools were turned off without it was still planning a read, and sent valid JSON with an empty
   answer, which passes the format check.

Every chunk any tool showed in full counts as seen: code fills a citation's quote from it, and the citation
check accepts it.

Use:
    messages = build_agent_prompt(system_prompt, question_text, starting_items, extra_agent_rule_names)
    loop_result = run_tool_loop(client, model, reasoning_effort, messages, starting_items, rule_tools, answer_shape)
"""

from dataclasses import dataclass

from mistralai.client import Mistral
from mistralai.extra import response_format_from_pydantic_model
from pydantic import BaseModel

from answer_flows.shared.prompt_sections import bullet_lines, wrap_section
from answer_flows.shared.read_model_reply import MAX_ANSWER_TOKENS
from answer_flows.shared.rule_tools import TOOL_DEFINITIONS, RuleTools, ToolResult
from answer_flows.single_call.answer_shape import ModelAnswer
from retrieval.build_bundle import format_bundle, full_chunks, label_by_full_id


# Constants
## The most tool rounds per question before the limit message replaces the results
MAX_TOOL_ROUNDS = 10


## Added to the last tool result of the last round, so the model knows to answer now
LAST_ROUND_NOTE = "\n\nThis was your last tool round: the tools are now off. Reply from the sources you have."


## The finish reason of a reply that asks for tools
FINISH_REASON_TOOL_CALLS = "tool_calls"


## The search steps every flow with tools puts between finding sentences and replying. They hold what the two
## default agent rules said (record 0022): check-each-part (9 Nov: B read 27.5 clauses a question; C never searched
## for yellow-card-before-play) and search-before-gaps (10 Nov: C still wrote "the sources don't cover" with 0 rounds,
## because the old rule 3 won over searching). As steps, searching comes before giving up on a part (record 0024)
SEARCH_STEPS = [
    "For each part that no sentence answers yet, search for it with the tools before you give up on it.",
    "Stop searching when every part has sentences, or when a search for the missing part finds nothing. "
    "When the sources given with the question already answer every part, call no tool.",
]

## The tools section, added after the flow's own sections: where the sources come from, and what each tool does
TOOL_NOTES = [
    "Your sources are every source block in this conversation: any given with the question, and every tool result.",
    "search_rules finds clauses by meaning. read_clause reads one clause by its chunk id, with every clause under it "
    "and a preview of each clause it links to.",
    "A clause that names another rule (\"Law 16.2\") or ends with a colon (\"the shuttle is:\") often needs a read_clause.",
    "A preview line shows only a clause's opening words, so read_clause it before you pick its sentences: "
    "only clauses shown in full can be cited.",
    "Your last reply, with no tool calls, is your reply in the required JSON shape.",
]

## Extra agent rules under test, by name, one per run (experiment rule 1). Each comes from a measured failure.
## Empty since record 0024: the two rules that were here became SEARCH_STEPS
EXTRA_AGENT_RULES: dict[str, str] = {}


# ===== The prompt =====

def build_tools_section(extra_agent_rule_names: list[str]) -> str:
    """Returns the tools section: the standing notes, then each named extra agent rule as one more note."""
    tool_notes = list(TOOL_NOTES)
    for rule_name in extra_agent_rule_names:
        tool_notes.append(EXTRA_AGENT_RULES[rule_name])
    return wrap_section("tools", bullet_lines(tool_notes))


def build_agent_prompt(system_prompt: str, question_text: str, starting_items: list[dict],
                       extra_agent_rule_names: list[str] | None = None) -> list[dict]:
    """Returns the first messages: the flow's system prompt with the tools section, then the starting bundle (if any) and the question."""
    question_block = f"<question>\n{question_text}\n</question>"

    # Setup B starts with no sources, setup C with setup A's bundle
    user_message = f"No sources yet: use the tools to find them.\n\n{question_block}"
    if starting_items:
        sources_text = format_bundle(starting_items)
        user_message = f"<sources>\n{sources_text}\n</sources>\n\n{question_block}"
    return [
        {"role": "system", "content": system_prompt + "\n\n" + build_tools_section(extra_agent_rule_names or [])},
        {"role": "user", "content": user_message},
    ]


# ===== One model call =====

def call_model(client: Mistral, model: str, reasoning_effort: str, messages: list, tools_allowed: bool,
               answer_shape: type[BaseModel] = ModelAnswer):
    """Sends the conversation so far with the tools, at the fixed settings of every eval run, and returns the response."""

    # After the last round, the tools stay listed but the model may not call them
    tool_choice = "auto"
    if not tools_allowed:
        tool_choice = "none"
    return client.chat.complete(
        model=model,
        messages=messages,
        tools=TOOL_DEFINITIONS,
        tool_choice=tool_choice,
        response_format=response_format_from_pydantic_model(answer_shape),
        reasoning_effort=reasoning_effort,
        temperature=0,
        top_p=1,
        max_tokens=MAX_ANSWER_TOKENS,
    )


# ===== The round limit =====

def has_reached_tool_limit(tool_rounds_used: int) -> bool:
    """True when the round limit is reached or passed, so the tools turn off after this round."""
    return tool_rounds_used >= MAX_TOOL_ROUNDS


# ===== One tool round =====

def run_tool_round(tool_calls: list, rule_tools: RuleTools, round_number: int,
                   is_last_round: bool) -> tuple[list[dict], list[dict], list[ToolResult]]:
    """Runs every tool call in one reply; returns the tool messages, the log lines and the tool results."""
    tool_messages = []
    log_lines = []
    tool_results = []
    for tool_call in tool_calls:
        tool_result = rule_tools.run_tool_call(tool_call.function.name, tool_call.function.arguments)
        tool_results.append(tool_result)

        # One tool message per call, matched to it by id, and one log line for the run file
        tool_messages.append({"role": "tool", "name": tool_call.function.name, "content": tool_result.text,
                              "tool_call_id": tool_call.id})
        log_lines.append({"round": round_number, "tool": tool_call.function.name,
                          "arguments": tool_call.function.arguments, "error": tool_result.error,
                          "shown_ids": [chunk["id"] for chunk in tool_result.shown_chunks]})

    # In the last round, the last result tells the model the tools are now off
    if is_last_round:
        tool_messages[-1]["content"] += LAST_ROUND_NOTE
    return tool_messages, log_lines, tool_results


# ===== The loop =====

@dataclass
class ToolLoopResult:
    """The loop's last reply, every clause shown in full with its label, the tool calls, and the calls and tokens used."""

    choice: object
    shown_chunk_by_id: dict[str, dict]
    label_by_id: dict[str, str]
    tool_rounds: int
    tool_calls: list[dict]
    tools_turned_off: bool
    model_calls: int
    input_tokens: int
    output_tokens: int


def run_tool_loop(client: Mistral, model: str, reasoning_effort: str, messages: list, starting_items: list[dict],
                  rule_tools: RuleTools, answer_shape: type[BaseModel]) -> ToolLoopResult:
    """Calls the model, runs the tools each reply asks for, and calls again, until a reply asks for none."""

    # The clauses shown in full so far: the tools leave these out of their results, and the model may cite them
    shown_chunk_by_id = {chunk["id"]: chunk for chunk in full_chunks(starting_items)}
    label_by_id = label_by_full_id(starting_items)
    rule_tools.start_question(set(shown_chunk_by_id))
    tool_call_log = []
    tool_rounds_used = 0
    tools_allowed = True
    model_calls = 0
    input_tokens = 0
    output_tokens = 0

    # Ask, run the tools the reply asks for, and ask again. A while loop, because the number of
    # calls is the model's choice; the round limit makes sure it ends
    while True:
        response = call_model(client, model, reasoning_effort, messages, tools_allowed, answer_shape)
        choice = response.choices[0]
        model_calls += 1
        input_tokens += response.usage.prompt_tokens
        output_tokens += response.usage.completion_tokens

        # A call made with the tools off is the last call, whatever it returns: even a reply that
        # still holds tool calls ends the loop (as a format error), so no model can loop past the limit
        if not tools_allowed:
            break

        # A reply that says "tool calls" but holds none is broken: end the loop, and the parse step records
        # it as a format error with its finish reason. No later question depends on this one, so the run
        # goes on (coding style rule 14)
        is_tool_reply_without_calls = choice.finish_reason == FINISH_REASON_TOOL_CALLS and not choice.message.tool_calls
        if is_tool_reply_without_calls:
            break

        # Break if model didn't ask for tools: the reply is the answer, or a format error if it doesn't fit the shape
        if choice.finish_reason != FINISH_REASON_TOOL_CALLS:
            break

        # Count the round, and add the model's own message, so each tool result follows the call it answers
        tool_rounds_used += 1
        messages.append(choice.message)

        # Tool round: run the tools it asked for, and get the tool messages, the log lines and the results
        tool_messages, log_lines, tool_results = run_tool_round(choice.message.tool_calls, rule_tools, tool_rounds_used,
                                                                has_reached_tool_limit(tool_rounds_used))

        # Add the tool messages to the conversation, the log lines to the run file, and the clauses to the seen set.
        # A clause keeps the first label it was shown with
        messages.extend(tool_messages)
        tool_call_log.extend(log_lines)
        for tool_result in tool_results:
            shown_chunk_by_id.update({chunk["id"]: chunk for chunk in tool_result.shown_chunks})
            for chunk_id, label in tool_result.shown_label_by_id.items():
                label_by_id.setdefault(chunk_id, label)

        # After the last round, the next call can only answer
        if has_reached_tool_limit(tool_rounds_used):
            tools_allowed = False

    return ToolLoopResult(
        choice=choice,
        shown_chunk_by_id=shown_chunk_by_id,
        label_by_id=label_by_id,
        tool_rounds=tool_rounds_used,
        tool_calls=tool_call_log,
        tools_turned_off=not tools_allowed,
        model_calls=model_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
