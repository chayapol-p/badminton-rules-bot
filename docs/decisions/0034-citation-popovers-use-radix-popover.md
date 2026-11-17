# 0034 · Citation popovers use Radix Popover; the early quotes wait

- **Status:** Accepted (Job, 17 Nov)
- **Date:** 2026-11-17
- **Stage:** Phase 2 (productise): the chat app

## Context
Slice 3 of `docs/specs/ask-a-rules-question.md` makes each `[n]` marker clickable (criterion 3, record 0029): a
small box opens with the quote, the source name and a link to the PDF page, and Escape or a click outside closes
it. The page needs a way to build that box. Record 0033 also left the quoted sources the flow sends early (the
"sources_picked" step) for slice 3.

## Options considered
For the box:
1. **Radix Popover** (`@radix-ui/react-popover` 1.3.1, Oct 2026). Escape, click outside, focus and placement next
   to the marker are built in, and it runs in Vitest's simulated browser, so the whole criterion gets fast tests.
   Adds one package.
2. **The browser's own `popover` attribute.** No package, and Escape and click outside are built in. But jsdom 31,
   the simulated browser the page tests use, has no `showPopover` (checked 17 Nov), so only Playwright could test
   it, and placing the box next to the marker needs newer CSS (anchor positioning).
3. **Floating UI** (`@floating-ui/react` 0.27). Places the box, but open, close and Escape are written by hand.

For the early quotes:
- a) **Leave them for later**, so slice 3 is only the clickable markers.
- b) Show the quotes with the "Found 2 sentences that answer it" step in slice 3.

## Decision
Option 1 and a) (Job, 17 Nov). The early quotes go to the backlog.

## Consequences
- The server adds `pdf_link` to each citation of the answer event, from the chunk's page and the frozen corpus's
  file names (`corpus_frozen` in `evals/golden_questions.json`), so the page only shows links it is given.
- The PDFs come from `data/bwf/`, which is never committed: the app serves the copy on the Mac it runs on.
