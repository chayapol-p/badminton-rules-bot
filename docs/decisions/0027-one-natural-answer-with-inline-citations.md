# 0027 · One natural answer with inline citations, and a scorecard per run

- **Status:** Proposed (Job, 16 Nov): the direction is picked; the build and its runs come later
- **Date:** 2026-11-16
- **Stage:** Phase 2 (productise)

## Context
Slice 5's write call returns one answer per part, and code joins them line by line. Every line starts with
"Under Laws of Badminton 5.0 (2) (in force …), Clause …", and related rules sit inside the answer text. The
answers are exact but read like a list of clauses, not a reply to a person, and the parts are never joined
into one conclusion. Example, "We forgot to switch ends at 11 and noticed at 14-12. What now?": the user needs
"switch now and keep 14-12"; slice 5 gives Law 8.2(1) and Law 8.2(2) as two separate lines.

The run files also don't save the gather call's parts, so a missed part can't be told apart from a missed
search. And the judge grades content only, so how an answer reads is never measured.

## Options considered
1. **Keep one answer per part.** Exact and checkable per part, but stiff, and parts are never joined.
2. **Add a rewrite call after slice 5.** Natural text, but one more call, and the rewrite can drift from the
   picked sentences.
3. **One natural answer with inline citations.** The write call gets the question and every picked sentence,
   numbered [1]…[n], and writes one connected answer that marks each claim. Code checks every marker and copies
   each quote into a numbered source list (the inline-citation pattern of Anthropic's Citations API).

## Decision
Option 3, with these picks (Job, 16 Nov):
- **The write call** writes one connected answer that leads with what the user should do, joins the parts, and
  marks every claim with [n]. The "Under Laws … version" phrase leaves the answer; the source list carries it.
  The format-first limit stays.
- **Gaps:** the model writes what the rules don't say inside the answer (no fixed code line).
- **Code** checks that every [n] points to a picked sentence and that every answer sentence carries at least one
  marker (a bad one is logged by name), builds the numbered
  source list with quotes copied word for word, and keeps related rules in their own list. The refusal gate
  stays where it is.
- **Logging:** every answer line saves the gather call's parts and the raw write reply.
- **Golden answers and pass rules:** no change.
- **Judge:** it sees the numbered sources lined up with the markers, and the grounded line also checks that each
  marked claim is supported by the source it points to. A fourth line, readable, is tracked and never fails an
  answer.
- **Scorecard:** every judge line and code check stays pass or fail, and each is logged per answer and reported
  per run as a share of answers. An answer passes only when every gate line passes (correct, grounded,
  behaviour, citations valid, refusal right). One combined metric compares experiments: a weighted sum of each
  line's share of answers, with correct 30, grounded 35, behaviour 10, refusal right 10 and readable 15.
  Citations valid stays in the gate with no weight, because it is almost always 100% (0 problems in 369 answers
  of the 9 Phase 2 runs) and would only add noise. Consistency (the same verdict in all of a flow's 3 runs) has
  one value per flow, not per run, so it is reported beside the metric as a tiebreaker.

- **Build picks (Job, 16 Nov, before the build):**
  - The write call replies with a list of sentences, each with its text and inline [n] markers; a sentence that
    says what the rules don't cover is flagged as a gap. Code joins the sentences into one answer. A gap sentence
    must carry no marker, every other sentence at least one (no splitting of free text into sentences).
  - The judge grades every answer that has text, including those a code check failed, so each scorecard line
    measures only itself. A format error has no text, so every line fails.
  - The wrong-clause check (cites none of the clauses that hold the golden answer) stays as its own gate line
    with no weight, like citations valid.
- **Fixes after the first runs (Job, 17 Nov, one at a time):**
  - The write call also sees the related sentences, numbered after the parts', and adds one when it completes
    the answer; a cited related sentence joins the source list, an uncited one stays related.
  - The format-first limit: mention a standard rule only when a given sentence says how it relates to the
    format; never claim a rule doesn't apply unless a sentence says so.

## Evidence
17 Nov, hybrid, Phase 2 questions (41: 27 answerable, 14 should refuse), the same judge in every run. The
before flow is kept as `--flow gather-then-write-per-part`.
- Per-part (slice 5 before this record): combined metric 81.95, 84.63, 84.63; gate 36, 36, 36; consistency 0.951.
- Natural answers, first build: 85.85, 88.29 (2 runs, paused); gate 31, 33. Key facts the gather call filed as
  related never reached the writer (toss-choices, racket-attachments, game-point-call failed in both runs).
- With related sentences for the writer: 90.85, 90.85, 87.93; gate 36, 37, 35; consistency 0.854. Those three
  questions pass 3 of 3; best-of-five-at-10-all fails grounded 3 of 3 on "the standard rule does not apply".
- With the format-first fix: 92.07, 91.10, 89.76; gate 37, 38, 37; consistency 0.951.
- Verdict (record 0026): natural answers with both fixes win against per-part (ranges 89.76–92.07 and
  81.95–84.63). Most of the gap is the readable line (21–28 of 41 against 4–9); correct 37–39 against 36,
  grounded 39–41 against 40–41.
- Still failing in every flow: black-card, shuttle-base-came-off, shuttle-from-next-court (the gather call never
  fetches the clause with the missing fact).

## Consequences
- Option 3 trusts the model more inside the answer, so the grounded line and record 0023's change 5 (a
  grounding check with one fix-up turn) matter more.
- A win is now called on the combined metric's ranges (record 0026, updated 16 Nov).
