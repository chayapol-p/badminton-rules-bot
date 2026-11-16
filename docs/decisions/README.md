# Decision log

Each file records one decision: the problem, the options weighed, what was chosen and why, and the
numbers behind it. Read in order, the files tell the story of how the bot was built.

The format is MADR (Markdown Architectural Decision Records). It extends Michael Nygard's record
(title, status, context, decision, consequences) with the options considered, so every choice
shows what it was chosen over. See https://adr.github.io/adr-templates/.

## How the log works

- **Only Job's decisions.** A record is written when Job makes a choice. Options Claude suggests stay
  out of the log until Job picks one.
- **One decision per file**, named `NNNN-what-was-decided.md`, numbered in the order decided.
- **Status:** Proposed (being tested) → Accepted, or Rejected. A later decision that replaces one
  gets a new file; the old file's status becomes "Superseded by NNNN", so the story stays readable.
- **Numbers** come from `evals/runs.jsonl`, on the dev split unless the record says otherwise.
  One dev question is about 4 points of recall; a win needs 2 or more questions (experiment rule 5).
- Raw findings stay in `workshop/notes.md`; a record is written once a choice is made or tested.

## Records

| # | Decision | Status |
|---|---|---|
| [0001](0001-test-section-groups-as-a-third-chunking.md) | Test section groups as a third chunking | Rejected |
| [0002](0002-name-each-alternative-laws-clause-by-its-format.md) | Name each Alternative Laws clause by its format | Accepted |
| [0003](0003-add-a-context-header-to-every-chunk.md) | Add a context header to every chunk's search text | Accepted |
| [0004](0004-use-rank-bm25-for-keyword-search.md) | Use rank_bm25 for keyword search, and keep the class simple | Accepted |
| [0005](0005-search-vectors-exactly-first.md) | Search the vectors exactly first | Accepted |
| [0006](0006-vector-search-on-clauses-goes-to-stage-2.md) | Vector search on clauses goes forward to Stage 2 | Accepted |
| [0007](0007-grade-with-code-checks-first-and-the-judge-for-the-rest.md) | Grade with code checks first, and the judge only for what code can't decide | Accepted |
| [0008](0008-facts-stated-in-the-question-count-as-given.md) | Facts in the question count as given; a false premise is corrected, then answered | Accepted |
| [0009](0009-top-5-plus-rule-links.md) | Keep top_k at 5, and add the clauses the hits link to | Accepted |
| [0010](0010-quote-clause-text-only.md) | Quote only clause text, never a source's first line | Accepted |
| [0011](0011-complete-answers-rule-not-adopted.md) | The "complete answers" rule is not adopted | Rejected |
| [0012](0012-three-pass-rules-fixed.md) | Fix three pass rules that asked for more than the question or the corpus | Accepted |
| [0013](0013-the-bots-words-about-itself-are-not-rule-claims.md) | The judge doesn't count the bot's words about itself as rule claims | Accepted |
| [0014](0014-the-judge-grades-what-the-user-sees-by-majority-of-3.md) | The judge grades what the user sees, by a majority of 3 votes | Accepted |
| [0015](0015-three-fixes-become-the-default.md) | List items, the para rule and the value-conditions rule become the default | Accepted |
| [0016](0016-racket-angle-is-context-for-a-height-question.md) | The racket angle is context for a question about serve height | Accepted |
| [0017](0017-official-links-and-parent-headings.md) | Link each official to their instructions, and show the heading above each clause | Accepted |
| [0018](0018-two-label-fixes-in-the-unseen-set.md) | Fix two labels in the unseen set after setup A's run | Accepted |
| [0019](0019-tag-tool-questions-by-where-setup-a-got-its-head-start.md) | Tag "tool" and "map and tool" by where setup A's head start came from | Accepted |
| [0020](0020-the-last-tool-round-carries-a-note-then-the-tools-turn-off.md) | The last tool round carries a note, then the tools turn off | Accepted |
| [0021](0021-setup-c-goes-to-phase-2.md) | Setup C (RAG first, then tools) goes forward to Phase 2 | Accepted |
| [0022](0022-setup-c-keeps-prompt-version-1-with-two-agent-rules.md) | Setup C keeps prompt version 1, with check-each-part and search-before-gaps | Superseded by 0024 |
| [0023](0023-move-exact-work-from-prompt-rules-to-code.md) | Move the exact work from prompt rules to code, one change at a time | Accepted (change 5 open) |
| [0024](0024-every-prompt-as-task-steps-and-limits.md) | Every answer prompt as a task, numbered steps and limits with reasons | Accepted |
| [0025](0025-related-sentences-get-their-own-list.md) | Related sentences get their own list, and the judge sees them as context | Accepted |
| [0026](0026-call-a-win-with-3-runs-per-flow.md) | Call a win with 3 runs per flow and a gap bigger than the noise | Accepted |

## Template

```markdown
# NNNN · <the decision, as a short statement>

- **Status:** Proposed | Accepted | Rejected | Superseded by NNNN
- **Date:** YYYY-MM-DD
- **Stage:** <workshop stage>

## Context
What problem forced a choice, with the numbers that showed it.

## Options considered
1. **<option>**: who uses it (source), and why it fits or misses here.
2. ...

## Decision
What was chosen, in one or two sentences, and why.

## Evidence
The runs that support it (settings and scores), or the runs still to do.

## Consequences
What gets easier, what gets harder, and what to watch.
```
