# Ask a rules question

**Story:** As a workshop attendee on a laptop, I want to ask a badminton rules question and get an answer that cites the exact rule, so that I can trust the answer and check it in the rule book.
**Why now:** asking and getting a clear, cited answer is the one job the vision names (`docs/vision.md`).

## Decisions (Job, 17 Nov)
- Users: laptop first, phone later.
- One question at a time, with no memory of earlier questions.
- Citations: each [n] marker is clickable and opens a popover with the quote, the source name and a PDF link; a source list under the answer repeats them (industry check, 17 Nov: ChatGPT, Copilot, Perplexity; NN/G).
- PDF link: the frozen PDF copy the app serves, opened at `#page=N` (RFC 8118 `page=`, the physical page counted from 1, which is how the chunks store `page`).
- Front end lives in `frontend/` (the official FastAPI full-stack template's layout).
- Streaming: FastAPI's built-in server-sent events; the page reads them with `fetch` and `eventsource-parser` (records 0031, 0032). Front-end stack: Vite, React and TypeScript, no router or data library yet (record 0030).
- Progress: the steps show as a list while waiting, then fold into one "Checked N steps in N s" line after the answer; a "still writing" step replaces the one before it (record 0033).
- Popovers: each [n] opens a Radix Popover; the quoted sources the flow sends early wait for a later slice (record 0034).
- The real bot: `RULES_BOT=real` in .env switches it on, stub when unset; the Playwright tests run their own stub servers on ports 8001 and 5174; a failed answer shows an error from slice 4 on (record 0035).
- Runs locally on Job's Mac. Tested with pytest (API), Vitest (page) and one Playwright test of the full path.

## Criteria
1. Given the page is open, when I ask "How tall are the posts?", then the answer appears with its [n] markers, and under it a source list with one entry per citation, numbered in the same order as the markers.
2. Given an answer is on its way, when the bot sends a progress update, then its message (e.g. "Searching the rule books") shows within 1 s, and the answer area stays empty until the whole answer arrives.
3. Given a citation of `itto-7.2`, when I click its [n] marker, then a popover shows the quote, "Instructions to Technical Officials 7.0 (5), Clause 7.2" and a link to `/rule-books/bwf-itto-2025-v7.0.pdf#page=37`; Escape or a click outside closes it.
4. Given the bot refuses (`refused` is true), when the answer arrives, then the page shows the answer text, labelled "Not covered by the rules", with no source list.
5. Given the bot raises `AnswerFormatError`, when the stream ends, then the page shows "Couldn't write a checked answer. Please try again." and no answer text.
6. Given an empty or blank question box, when I press Ask, then I see "Please type a question" and no request is sent.

## Contract
`POST /chat` with `{"question": "How tall are the posts?"}` returns `text/event-stream` with these events:
- `progress`: one `ProgressUpdate` as JSON, sent once for each update.
- `answer`: the `RulesAnswer` as JSON. Each citation also carries `pdf_link`, e.g. `/rule-books/bwf-laws-of-badminton-2025-v5.0.pdf#page=1`.
- `error`: `{"message": "..."}`, after which the stream ends.

The app answers only through `load_rules_bot()` and `RulesBot.answer(...)`.

## Out of scope
- Follow-up questions and chat history; phone layout; deployment; sign-in; streaming the answer word by word.
- The quoted sources the flow sends early ("sources_picked") shown while waiting (backlog, record 0034).
- The Introduction's definitions read oddly in the source list: the name says "Clause Introduction" and the quote runs the defined word into its definition ("Match The basic contest…"); a fix in the ingest, not the app (backlog, Job, 17 Nov).

## Open questions
- Does Safari's built-in PDF viewer honour `#page=`? (Unchecked; check in the slice 3 demo.)

## How we test
`uv run pytest -q` (API, with a stub bot), `npm test` in `frontend/` (Vitest), `npx playwright test` (one browser test against the stub). A live check calls Mistral once, by hand, on Job's Mac.

## Slices
1. Walking skeleton: the page with a question box sends the question to `POST /chat`, which returns a fixed answer from a stub bot, and the page shows it with a source list (criterion 1, with a stub)
   - After this slice the user can: type a question and see a cited answer, from the stub
   - In scope: `POST /chat` with the `answer` event only, the stub bot, a bare React page in `frontend/`, the source list, one Playwright test
2. Progress updates while waiting (criterion 2, with the stub)
   - After this slice the user can: ask and watch the steps arrive; the answer area stays empty until the answer comes, then the steps fold into one line
   - In scope: progress events from a worker thread through a thread-safe queue, the stub sends 4 updates 0.3 s apart, the step list with fold, still-writing replace, 3 pytest + 4 Vitest + 1 Playwright tests
3. Clickable [n] popovers with PDF links (criterion 3, with the stub)
   - After this slice the user can: click [n] to see the quote, the source name and a link that opens the PDF at its page; Escape or a click outside closes it
   - In scope: `pdf_link` on each citation in the answer event, FastAPI serves `data/bwf` at `/rule-books`, a Radix popover on each [n], the same link in the source list
4. Connect the real bot, and show an error when it fails (criterion 5; Job checks it by hand with Job's own key)
   - After this slice the user can: ask any question and get the real bot's answer, steps and citations; a failed answer shows "Couldn't write a checked answer. Please try again." instead of waiting for good
   - In scope: the `RULES_BOT` setting (stub when unset), the bot loaded once at startup, the "error" event, the error message on the page, Playwright on its own stub servers
5. Refusals (criterion 4, with the stub)
   - After this slice the user can: ask a question the rule books don't answer and see the bot's own words, labelled "Not covered by the rules", with no source list
   - In scope: the page's refusal view; the stub refuses one fixed question ("What force, in newtons, should the net cord be stretched to?") with a real refusal copied from the 17 Nov run
6. Error message for an empty question

## Changes after building
- 17 Nov, slice 1: the page reads the stream with eventsource-parser, not a hand-written reader (record 0032).
- 17 Nov, slice 2 (Job, after trying it): the stub holds each step 1.5 s, not 0.3 s, so each step can be read; the step in progress shows a spinner and a shimmer, the steps before it a tick, each new step slides in, and a "Working · N s" timer counts up, so the wait looks alive (a reduced-motion setting gets a still dot and no movement).
- 17 Nov, before slice 4 (Job): criterion 5, the error for a failed answer, moves from slice 6 into slice 4, so the live check never hangs; slice 6 keeps the empty-question check (record 0035).
- 17 Nov, slice 2 (Job, after the live check: one real question sent 12 steps): while waiting, only the newest 4 steps show; older ones fold into "▸ N earlier steps", and each step is cut to one row with the full words on hover (record 0036).
