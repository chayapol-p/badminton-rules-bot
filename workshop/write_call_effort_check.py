"""Times the write call at two reasoning efforts on one question: runs the gather call once, then the same write call
twice at each effort, and prints seconds, thinking length and the answer. A Mistral error for an effort is printed
and that effort is skipped. Run: PYTHONPATH=. uv run python workshop/write_call_effort_check.py"""

import time

from mistralai.extra import response_format_from_pydantic_model

from answer_flows.gather_then_write.answer_shape import GatheredAnswer, WrittenAnswer
from answer_flows.gather_then_write.assemble_written_answer import check_gathered_picks, format_parts_for_writer
from answer_flows.gather_then_write.gather_and_write_rules import GATHER_RULES, build_write_prompt
from answer_flows.rules_bot import load_rules_bot
from answer_flows.shared.read_model_reply import MAX_ANSWER_TOKENS, split_reply_content
from answer_flows.shared.rule_tools import RuleTools
from answer_flows.shared.tool_loop import build_agent_prompt, run_tool_loop


# Constants
## The same new question as the live checks, and the efforts to compare
QUESTION = "Can I serve while my partner is still walking to the court?"
EFFORTS = ["low", "none"]
TRIES_PER_EFFORT = 2


# Gather once, as the product flow does, to get the exact input the write call sees
rules_bot = load_rules_bot()
starting_items = rules_bot.retrieve(QUESTION)
rule_tools = RuleTools(rules_bot.chunks, rules_bot.search_function, rules_bot.rule_map)
messages = build_agent_prompt(GATHER_RULES, QUESTION, starting_items, None)
loop_result = run_tool_loop(rules_bot.mistral_client, rules_bot.settings.mistral_answer_model,
                            rules_bot.settings.mistral_reasoning_effort, messages, starting_items, rule_tools,
                            GatheredAnswer)
gather_reply, _ = split_reply_content(loop_result.choice.message.content)
checked_answer, _ = check_gathered_picks(GatheredAnswer.model_validate_json(gather_reply), loop_result.shown_chunk_by_id)
parts_text = format_parts_for_writer(checked_answer, loop_result.shown_chunk_by_id, loop_result.label_by_id)

# Time the same write call at each effort
for effort in EFFORTS:
    for try_number in range(1, TRIES_PER_EFFORT + 1):
        started = time.perf_counter()
        try:
            response = rules_bot.mistral_client.chat.complete(
                model=rules_bot.settings.mistral_answer_model,
                messages=build_write_prompt(QUESTION, parts_text),
                response_format=response_format_from_pydantic_model(WrittenAnswer),
                reasoning_effort=effort, temperature=0, top_p=1, max_tokens=MAX_ANSWER_TOKENS,
            )
        except Exception as error:
            print(f"{effort}: Mistral refused it: {error}", flush=True)
            break
        seconds = time.perf_counter() - started
        reply, thinking = split_reply_content(response.choices[0].message.content)
        print(f"{effort} try {try_number}: {seconds:.1f} s, thinking {len(thinking)} chars, "
              f"output tokens {response.usage.completion_tokens}", flush=True)
        print(f"   {reply[:300]}", flush=True)
