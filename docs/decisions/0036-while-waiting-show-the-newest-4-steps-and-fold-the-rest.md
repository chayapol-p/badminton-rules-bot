# 0036 · While waiting, show the newest 4 steps and fold the rest; each step is one row

- **Status:** Accepted (Job, 17 Nov)
- **Date:** 2026-11-17
- **Stage:** Phase 2 (productise): the chat app
- **Amends:** [0033](0033-progress-steps-show-as-a-list-that-folds-after-the-answer.md), the step list while waiting.

## Context
Record 0033 shows every step while the bot works. In Job's live check of the real bot (17 Nov), one question sent
12 steps in 33 s, most of them searches with long search words, and the list kept growing down the page.

## Options considered
1. **Show the newest 4 steps; older ones fold into one "▸ N earlier steps" line that opens on a click.** The list
   keeps one height, so the page doesn't jump (CI build logs fold finished steps the same way). Nothing is lost.
2. **Group repeats into one line**, such as "Searched the rules 6 times · latest: …" (Perplexity's search block).
   Shorter, but the list still grows with each kind of step, and each kind needs its own grouping rule.
3. **A fixed-height box that scrolls** to the newest step, like a terminal. Least code, but a scroll box inside the
   page is fiddly on a phone, and older steps sit half hidden.

With any of them: **cut each step to one row** with "…", the full words on hover.

## Decision
Option 1 with 4 steps visible, and the one-row cut (Job, 17 Nov).

## Consequences
- The step in progress is always one of the 4 visible steps.
- The cut text stays whole in the page, so screen readers still read every word; the hover shows it too.
- The fold after the answer keeps every step, as in record 0033.
