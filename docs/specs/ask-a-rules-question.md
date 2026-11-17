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

## Open questions
- Does Safari's built-in PDF viewer honour `#page=`? (Unchecked; check in the slice 3 demo.)

## How we test
`uv run pytest -q` (API, with a stub bot), `npm test` in `frontend/` (Vitest), `npx playwright test` (one browser test against the stub). A live check calls Mistral once, by hand, on Job's Mac.

## Slices
1. Walking skeleton: the page with a question box sends the question to `POST /chat`, which returns a fixed answer from a stub bot, and the page shows it with a source list (criterion 1, with a stub)
   - After this slice the user can: type a question and see a cited answer, from the stub
   - In scope: `POST /chat` with the `answer` event only, the stub bot, a bare React page in `frontend/`, the source list, one Playwright test
2. Progress updates while waiting
3. Clickable [n] popovers with PDF links
4. Connect the real bot (Job checks it by hand with Job's own key)
5. Refusals
6. Error messages for a bad answer and an empty question

## Changes after building
- (none yet)
