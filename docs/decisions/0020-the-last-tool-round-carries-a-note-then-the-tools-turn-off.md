# 0020 · The last tool round carries a note, then the tools turn off

- **Status:** Accepted (Job, 9 Nov)
- **Date:** 2026-11-09
- **Stage:** 3 (agent vs plain RAG)

## Context
The agent loop needs an end. A hard cut on a step count was ruled out first: it can stop a model
mid-search. The loop instead counts tool rounds (one reply that asks for tools, however many it asks
for) and caps them at 10. What happens at the cap decides how many calls a question can cost, and
whether the last answer is any good.

## Options considered
1. **Limit message in round 11, tools still on.** Each round-11 call gets "Tool call limit reached
   … Answer from the sources you have." A model that asks again gets the message again, and the
   tools turn off after round 12: up to 13 calls.
2. **Limit message in round 11, tools off in the same step.** Up to 12 calls. The round-11 call
   still buys nothing: no tool result can come back after round 10.
3. **Tools off after round 10, no message.** Up to 11 calls, but the model doesn't know why it
   can't call a tool.
4. **Tools off after round 10, with a note on round 10's last tool result:** "This was your last
   tool round: the tools are now off. Answer from the sources you have." Up to 11 calls, and the
   model knows to answer.

## Decision
Option 4. It costs the fewest calls of the options that answer well.

## Evidence
Live check, 9 Nov, yellow-card-before-play, setup B, one real search round, then the tools off:
- Option 3 (no note): finish "stop", valid JSON, an empty answer and no citations. Its thinking
  ended "I'll read laws-16.7.1.2 quickly": it was still planning a read. The format check passes
  such an answer; only the judge would catch it.
- Option 4 (the note): a full answer to both parts, citing ITTO 5.17.10, ITTO 3.7.3 and Law 16.7.1.2.
One question, one run each, so it shows the failure exists, not how often.

## Consequences
- Job's blank is `has_reached_tool_limit` (`>= 10`): reached or passed, so a round past 10 can never
  leave the tools on.
- A call made with the tools off is always the last call: a reply that still holds tool calls ends
  the loop as a format error, so no model can loop past the limit.
- The run reports questions that reached the round limit.
