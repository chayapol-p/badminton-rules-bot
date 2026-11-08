# 0017 · Link each official to their instructions, and show the heading above each clause

- **Status:** Accepted (by Job's target-question rule, 8 Nov)
- **Date:** 2026-11-08
- **Stage:** 2 (answers, citations and refusals)

## Context
Two of the last failures were about what the bot was shown, not how it answered:
- **service-fault-officials** needs ITTO 7.2 ("call 'Fault' loudly"). Vector search ranked it 13th,
  keyword search 23rd, and no rule link reached it.
- **racket-max-size:** clause 4.2.2 reads "shall not exceed 280 mm…"; its subject sits in the heading
  above it, "4.2 The stringed area:". The bot inferred it rightly, and the judge failed the inference.
  97 of 754 clauses start mid-sentence like this.

## Options considered
1. **More search results** (top 15, top 55): tested in record 0009, more cost and no gain.
2. **Instructions links in the rule map:** Law 17.3 (service judge) -> ITTO 7.2, Law 17.4 (line judge)
   and Law 17.5.1 (umpire overruling) -> ITTO 8.2. Listed by hand: the books never cite them.
3. **Show the parent clauses in each source block.** A first version showed every parent; string-tension
   then quoted a full parent rule (Law 4.1, cut short) from it. The kept version shows only parents that
   name a subject (end in a colon, or 5 words or fewer). Search still reads `search_text` (record 0006):
   this changes what the bot and the judge read, not what search matches.

## Decision
Options 2 and 3, as the default. Rule 8 now forbids quoting the "Under:" line.

## Evidence
| Run | Passed of 22 | Notes |
|---|---|---|
| `20261108T1552-top5-official-links` | 21 | service-fault-officials passes |
| `20261108T1604-top5-parents` (all parents) | 21 | string-tension probe fails: quoted the parent |
| `20261108T1617-top5-parents-repeat` | 22 | string-tension fails again |
| `20261108T1630-top5-parent-headings` | 18 | racket-max-size, string-tension pass |
| `20261108T1643-top5-parent-headings-repeat` | 21 | racket-max-size, string-tension pass |

The fails in the 18 run are not from the headings: red-card typed "..." for the ellipsis "…" (fixed in
the citation check), wheelchair-shuttle-on-net cited the neighbouring item, and service-fault-officials
and attack-be-the-referee pass in the repeat.

## Consequences
- 341 clauses now show at least one heading line.
- The official table is short and hand-made: add a row when a new official question fails the same way.
