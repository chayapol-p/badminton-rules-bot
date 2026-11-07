# Decision log

Each file records one decision: the problem, the options weighed, what was chosen and why, and the
numbers behind it. Read in order, the files tell the story of how the bot was built.

The format is MADR (Markdown Architectural Decision Records). It extends Michael Nygard's record
(title, status, context, decision, consequences) with the options considered, so every choice
shows what it was chosen over. See https://adr.github.io/adr-templates/.

## How the log works

- **One decision per file**, named `NNNN-what-was-decided.md`, numbered in the order decided.
- **Status:** Proposed (being tested) → Accepted, or Rejected. A later decision that replaces one
  gets a new file; the old file's status becomes "Superseded by NNNN", so the story stays readable.
- **Numbers** come from `evals/runs.jsonl`, on the dev split unless the record says otherwise.
  One dev question is about 4 points of recall; a win needs 2 or more questions (experiment rule 5).
- Raw findings stay in `workshop/notes.md`; a record is written once a choice is made or tested.

## Records

| # | Decision | Status |
|---|---|---|
| [0001](0001-test-section-groups-as-a-third-chunking.md) | Test section groups as a third chunking | Proposed |

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
