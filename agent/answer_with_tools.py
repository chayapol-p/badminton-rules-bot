"""
Answers one question with tools: the model searches and reads clauses until it answers, in the RulesAnswer shape.

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

Every chunk any tool showed counts as seen, so the citation check accepts a citation to it.

Prompt version 2 (Stage 3, 10 Nov) swaps in AGENT_RULES_VERSION_2 (with the extra agent rules folded in,
so it takes none), LAST_ROUND_NOTE_VERSION_2 and version 2's tool definitions. Version 1 is unchanged.

Use:
    reply = answer_with_tools(client, model, reasoning_effort, answer_rules, question_text, starting_chunks, rule_tools)
    reply = answer_with_tools(client, model, reasoning_effort, answer_rules, question_text, starting_chunks, rule_tools,
                              prompt_version=2)
"""

from dataclasses import dataclass, field

from mistralai.client import Mistral
from mistralai.extra import response_format_from_pydantic_model
from pydantic import ValidationError

from agent.rule_tools import RuleTools, build_tool_definitions
from answer.answer_shape import RulesAnswer
from answer.build_answer_prompt import format_source
from answer.generate_answer import MAX_ANSWER_TOKENS, split_reply_content


# Constants
## The most tool rounds per question before the limit message replaces the results
MAX_TOOL_ROUNDS = 10

## Added to the last tool result of the last round, so the model knows to answer now
LAST_ROUND_NOTE = "\n\nThis was your last tool round: the tools are now off. Answer from the sources you have."

## Prompt version 2's note: it points the model at answer rule 3 for any part still uncovered
LAST_ROUND_NOTE_VERSION_2 = ("\n\nThis was your last tool round: the tools are now off. Answer from the sources you "
                             "have; mark any part still uncovered as rule 3 says.")

## The finish reason of a reply that asks for tools
FINISH_REASON_TOOL_CALLS = "tool_calls"

## Added to the answer rules for the agent: where its sources come from, and how to use the tools
AGENT_RULES = """
Tools:
- Your sources are the source blocks in this conversation: any given with the question, and every tool result.
- When the sources don't fully answer the question, use the tools before you answer. search_rules finds clauses by meaning; read_clause reads one clause by its chunk id, with the clauses under it and the ids it links to.
- A source that names another rule ("Law 16.2") or ends with a colon ("the shuttle is:") often needs a read_clause.
- When the sources already answer the question, answer without calling a tool.
- Your final reply, with no tool calls, is the answer in the required JSON shape."""

## Prompt version 2's agent rules (B and C). They replace AGENT_RULES and both extra agent rules below
AGENT_RULES_VERSION_2 = """
Tools:
- Sources given with the question are a starting point. Every tool result is a source too.
- Before you answer, act on each part of the question: if a source points elsewhere (names another clause, or ends with a colon), read_clause that id; if a part has no source, search_rules for it, in the documents' own terms. If the search misses, try once more with different words.
- Mark a part "none" only after its searches found nothing. Never say the sources lack a part you have not searched for.
- Stop as soon as every part has a source. Do not search or read to confirm a part already covered, and do not cite a clause only because you read it.
- Write about the rules, not your work: never mention tools, searches, or which documents you checked.
- Your final reply, with no tool calls, is the answer in the required JSON shape."""

## Extra agent rules under test, by name, one per run (experiment rule 1). Each comes from a measured failure
EXTRA_AGENT_RULES = {
    # 9 Nov, unseen set: setup C refused yellow-card-before-play twice with no tool call (it never searched for
    # ITTO 3.7.3), and setup B read 27.5 clauses a question against C's 16.9, misquoting on cut-hand-mid-game.
    # One generic line aimed at both: search when a part is uncovered, stop when every part is, cite only what is used
    "check-each-part": ("Before you answer or refuse, check each part of the question against your sources. Search only "
                        "for a part no source covers. Cite only the clauses your answer uses."),
    # 10 Nov, unseen set with check-each-part: setup C still answered yellow-card-before-play twice with 0 tool rounds,
    # writing that the sources don't cover the card report. Answer rule 3 (written for plain RAG: say what the sources
    # don't cover) seems to win over searching when sources come with the question. This line says which rule wins
    "search-before-gaps": ("You can search, so answer rule 3 changes for you: when a part of the question has no source, "
                           "search for it first. Say the sources don't cover a part only after a search for it finds nothing."),
}


# ===== One agent answer =====

@dataclass
class AgentReply:
    """One answer, or a format error, plus every chunk the model saw, the tool calls it made and the tokens they used."""

    answer: RulesAnswer | None
    is_format_error: bool
    error_message: str | None
    raw_reply: str
    thinking: str
    shown_chunks: list[dict]
    tool_rounds: int
    tool_calls: list[dict] = field(default_factory=list)
    tools_turned_off: bool = False
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


# ===== The prompt =====

def build_agent_rules(extra_agent_rule_names: list[str], prompt_version: int = 1) -> str:
    """Returns the agent rules of a prompt version; version 1 adds the named extra rules as more bullets."""

    # Version 2 has the extra rules folded in: the run script refuses extra rules with it
    if prompt_version == 2:
        return AGENT_RULES_VERSION_2

    # Version 1: the standing bullets, then each extra rule
    agent_rules = AGENT_RULES
    for rule_name in extra_agent_rule_names:
        agent_rules += f"\n- {EXTRA_AGENT_RULES[rule_name]}"
    return agent_rules


def build_agent_prompt(answer_rules: str, question_text: str, starting_chunks: list[dict],
                       extra_agent_rule_names: list[str] | None = None, prompt_version: int = 1) -> list[dict]:
    """Returns the first messages: the rules with the agent rules, then the starting sources (if any) and the question."""
    question_block = f"<question>\n{question_text}\n</question>"

    # Setup B starts with no sources, setup C with setup A's
    user_message = f"No sources yet: use the tools to find them.\n\n{question_block}"
    if starting_chunks:
        sources_text = "\n\n".join(format_source(chunk) for chunk in starting_chunks)
        user_message = f"<sources>\n{sources_text}\n</sources>\n\n{question_block}"
    return [
        {"role": "system", "content": answer_rules + "\n" + build_agent_rules(extra_agent_rule_names or [], prompt_version)},
        {"role": "user", "content": user_message},
    ]


# ===== One model call =====

def call_model(client: Mistral, model: str, reasoning_effort: str, messages: list, tools_allowed: bool,
               prompt_version: int = 1):
    """Sends the conversation so far with the tools, at the fixed settings of every eval run, and returns the response."""

    # After the last round, the tools stay listed but the model may not call them
    tool_choice = "auto"
    if not tools_allowed:
        tool_choice = "none"
    return client.chat.complete(
        model=model,
        messages=messages,
        tools=build_tool_definitions(prompt_version),
        tool_choice=tool_choice,
        response_format=response_format_from_pydantic_model(RulesAnswer),
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

def last_round_note(prompt_version: int) -> str:
    """Returns the note a prompt version adds to the last tool result of the last round."""
    if prompt_version == 2:
        return LAST_ROUND_NOTE_VERSION_2
    return LAST_ROUND_NOTE


def run_tool_round(tool_calls: list, rule_tools: RuleTools, round_number: int,
                   is_last_round: bool, prompt_version: int = 1) -> tuple[list[dict], list[dict], list[dict]]:
    """Runs every tool call in one reply; returns the tool messages, the log lines and the chunks shown."""
    tool_messages = []
    log_lines = []
    shown_chunks = []
    for tool_call in tool_calls:
        tool_result = rule_tools.run_tool_call(tool_call.function.name, tool_call.function.arguments)
        shown_chunks.extend(tool_result.shown_chunks)

        # One tool message per call, matched to it by id, and one log line for the run file
        tool_messages.append({"role": "tool", "name": tool_call.function.name, "content": tool_result.text,
                              "tool_call_id": tool_call.id})
        log_lines.append({"round": round_number, "tool": tool_call.function.name,
                          "arguments": tool_call.function.arguments, "error": tool_result.error,
                          "shown_ids": [chunk["id"] for chunk in tool_result.shown_chunks]})

    # In the last round, the last result tells the model the tools are now off
    if is_last_round:
        tool_messages[-1]["content"] += last_round_note(prompt_version)
    return tool_messages, log_lines, shown_chunks


# ===== Reading the final reply =====

def parse_final_reply(choice) -> tuple[RulesAnswer | None, str | None, str, str]:
    """Returns the parsed answer (or None), the format error message (or None), the raw reply and the thinking."""
    raw_reply, thinking = split_reply_content(choice.message.content)
    try:
        return RulesAnswer.model_validate_json(raw_reply), None, raw_reply, thinking
    except ValidationError as error:
        return None, f"finish reason {choice.finish_reason}: {error}", raw_reply, thinking


# ===== The loop =====

def answer_with_tools(client: Mistral, model: str, reasoning_effort: str, answer_rules: str, question_text: str,
                      starting_chunks: list[dict], rule_tools: RuleTools,
                      extra_agent_rule_names: list[str] | None = None, prompt_version: int = 1) -> AgentReply:
    """Answers one question, calling tools until the model replies with no tool calls."""
    messages = build_agent_prompt(answer_rules, question_text, starting_chunks, extra_agent_rule_names, prompt_version)
    shown_chunk_by_id = {chunk["id"]: chunk for chunk in starting_chunks}
    tool_call_log = []
    tool_rounds_used = 0
    tools_allowed = True
    model_calls = 0
    input_tokens = 0
    output_tokens = 0

    # Ask, run the tools the reply asks for, and ask again. A while loop, because the number of
    # calls is the model's choice; the round limit makes sure it ends
    while True:
        response = call_model(client, model, reasoning_effort, messages, tools_allowed, prompt_version)
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

        # Tool round: run the tools it asked for, and get the tool messages, the log lines and the chunks they showed
        tool_calls = choice.message.tool_calls
        tool_messages, log_lines, shown_chunks = run_tool_round(tool_calls, rule_tools, tool_rounds_used,
                                                                has_reached_tool_limit(tool_rounds_used), prompt_version)

        # Add the tool messages to the conversation, and the log lines to the run file, and the chunks to the seen set
        messages.extend(tool_messages)
        tool_call_log.extend(log_lines)
        shown_chunk_by_id.update({chunk["id"]: chunk for chunk in shown_chunks})

        # After the last round, the next call can only answer
        if has_reached_tool_limit(tool_rounds_used):
            tools_allowed = False

    # The last reply is the answer, or a format error that still reports its tokens
    rules_answer, error_message, raw_reply, thinking = parse_final_reply(choice)
    return AgentReply(
        answer=rules_answer,
        is_format_error=rules_answer is None,
        error_message=error_message,
        raw_reply=raw_reply,
        thinking=thinking,
        shown_chunks=list(shown_chunk_by_id.values()),
        tool_rounds=tool_rounds_used,
        tool_calls=tool_call_log,
        tools_turned_off=not tools_allowed,
        model_calls=model_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
