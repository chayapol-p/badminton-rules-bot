# 0033 · Progress steps show as a list that folds into one line after the answer

- **Status:** Accepted (Job, 17 Nov)
- **Date:** 2026-11-17
- **Stage:** Phase 2 (productise): the chat app

## Context
While the bot works (9-104 s), `/chat` sends every progress update the flow gives (record 0028). Slice 2 of
`docs/specs/ask-a-rules-question.md` shows them on the page, so the page needs a way to show a run of steps while
waiting, and a way to keep them out of the answer's way once it arrives.

## Options considered
1. **A step list that folds into one "Checked N steps in N s" line after the answer** (ChatGPT's "Thought for
   N s", Perplexity's research steps). Every step stays readable while waiting and one click away after.
2. **One line that replaces itself** (ChatGPT's web-search status). Drops the searches and the clauses read,
   against record 0028's "send every update".
3. **A step list that stays open.** Pushes the answer down the page.

## Decision
Option 1 (Job, 17 Nov). Details:
- A "still_writing" update replaces the "still_writing" line before it, so the ticks don't pile up.
- The list sits in a `role="status"` region, so screen readers announce new steps without moving focus (MDN,
  WAI-ARIA status role).
- The fold is the native `<details>` and `<summary>` elements: closed after the answer, open on a click.
- The quoted sources sent early ("sources_picked") are left for slice 3, with the citation popovers.

## Consequences
- The answer region stays empty until the whole answer arrives (record 0028); only the step list changes while
  waiting.
- `/chat` must carry updates from the "still writing" thread to the stream, so the endpoint passes them through a
  thread-safe queue.
