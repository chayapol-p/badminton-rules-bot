# 0029 · The chat app answers one question at a time, and cites each claim with a popover and the PDF page

- **Status:** Accepted (Job, 17 Nov)
- **Date:** 2026-11-17
- **Stage:** Phase 2 (productise): the chat app

## Context
The vision (`docs/vision.md`) asks for a web app to ask about the badminton rules, "with clear and cited rules
reference". The spec (`docs/specs/ask-a-rules-question.md`) needed the users, the conversation shape and the way a
citation shows its source.

## Options considered
Users: laptop only; phone at court only; both. Conversation: one question at a time (what `RulesBot.answer` does
today); follow-up questions with history (changes the flow and needs new eval runs).

Citation display (industry check, 17 Nov):
1. **Clickable `[n]` that opens a popover, plus a source list under the answer**: ChatGPT (claim popovers and a
   Sources sidebar), Copilot (hover previews), Perplexity (inline markers). NN/G: put each source next to its claim,
   don't bury it, link deep into the source.
2. **A footnote list only**: the AI design-patterns catalogue warns against footnote-only lists.
3. **A side panel**: cramped on a laptop next to the answer.

PDF link:
4. **The frozen PDF the app serves, opened at `#page=N`**: RFC 8118 defines `page=` as the physical page counted
   from 1, which is how `build_rule_chunks.py` stores `page`. Checked: ITTO 7.2 is on physical page 37 and
   Laws 17.3 on page 11.
5. **The BWF website**: its Statutes page shows no direct PDF links and listed the Laws as "Updated 31 May 2019",
   so its copy may not match the frozen 2025 corpus.

## Decision
Laptop first, phone later; one question at a time. Options 1 and 4: each `[n]` opens a popover with the quote, the
source name and a link to the served PDF at its page, and a source list under the answer repeats them.

## Evidence
The industry check above; the page check of two clauses against the PDFs.

## Consequences
- The answer event carries a `pdf_link` per citation (slice 3); the app serves `data/bwf/` at `/rule-books/`.
- Open: does Safari's built-in PDF viewer honour `#page=`? Check in the slice 3 demo.
