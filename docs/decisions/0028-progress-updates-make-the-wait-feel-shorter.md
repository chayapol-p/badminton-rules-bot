# 0028 · Progress updates make the wait feel shorter; the answer shows only once checked

- **Status:** Accepted (Job, 17 Nov)
- **Date:** 2026-11-17
- **Stage:** Phase 2 (productise)

## Context
An answer takes 9-104 s (median 34 s over the 122 answers of 17 Nov's three natural-answer runs). The write call
is the long part: about 35-50 s, most of it thinking (median 8,300 characters of thinking for a 420-character
answer). A spinner for that long loses the user: past about 10 s, a progress display is needed (Nielsen's
response-time limits). Job chose to make the wait feel shorter, not to change the flow's speed, and to send
every update the flow can give.

## Options considered
For the wait:
1. **Plain-language steps, then the quoted sources early** (Perplexity's research steps; LangGraph's custom
   progress events). No change to the model calls. The sources arrive about 10-25 s in, before the write call.
2. **The model's thinking text**, folded under "show thinking", or a live count of it. Needs the write call to
   stream. Mistral returns the raw thinking, which reads like a draft; OpenAI advises showing a summary, not
   the raw thinking.
3. **A percent-done bar.** The write call's length can't be predicted, so the bar would stall.

For the answer text:
4. **Only the answer that passed the code checks.**
5. **Each sentence as a draft while it streams**, then the checked answer. The answer text comes in the last
   few seconds, so this saves little, and a failed check would have to replace the drafts.

## Decision
Options 1 and 4 (Job, 17 Nov). The product flow sends progress updates as it works: finding the rules, the
rules found, each check, each search with its words, each clause read, the picked sentences with their quotes,
then "writing the answer". The answer shows once it passes the checks. The model calls stay as they are.

Added the same day (Job, 17 Nov): Job accepts the current speed, and the silent write stretch is closed with more
updates only: what the question asks, part by part, at the code gate, and "still writing the answer · N s" every
5 s while the write call runs.

## Consequences
- `answer_flows/shared/progress_updates.py` holds the update shape and its lines; `RulesBot.answer`,
  `gather_then_write` and `run_tool_loop` take a `report_progress` function. Eval runs leave it at
  `ignore_progress`, so runs and their results don't change.
- The write call needs no streaming. The "still writing" updates come from a second thread while the write call
  runs (`call_with_still_writing_updates`), so the app's `report_progress` must accept calls from another thread.
- The early source list is the start of the final numbered list: the picked sentences keep their numbers
  [1]…[k], and the final list adds after them only the related sentences the answer cites. So the app can
  number the sources as soon as they arrive.
