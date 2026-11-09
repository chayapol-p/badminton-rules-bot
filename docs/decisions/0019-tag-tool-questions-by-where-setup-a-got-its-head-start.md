# 0019 · Tag "tool" and "map and tool" by where setup A's head start came from

- **Status:** Accepted (Job, 9 Nov)
- **Date:** 2026-11-09
- **Stage:** 3 (agent vs plain RAG)

## Context
Both tags mean a model's own search or read is needed. Record 0018 split them by whether the map
brings a fact the pass rule requires. But Stage 3 compares steps: setup C starts from setup A's
sources, setup B from nothing, and a link in setup A's sources saves B a step whether or not the
clause it brings is a required fact.

sweat-on-court shows the gap: setup A gets Law 16.7.1 through the map's link from ITTO 5.9.1.6
("Law 16.7"), but the pass rule needs the three steps under 16.7.1, so it was tagged "tool". Setup C
needs one read; setup B must follow "Law 16.7" itself first.

## Options considered
1. **Keep the required-fact rule.** Tags say which facts each part supplies, not how many steps each
   setup needs.
2. **Tag by where setup A's head start came from:** "tool" when whatever setup A has came from
   search alone; "map and tool" when some of it came through a link.

## Decision
Option 2. It matches what the run measures: on "tool", setup B catches up with searches only; on
"map and tool", it must also spot a pointer and read it.

## Evidence
`20261109T0716-top5-unseen`: setup A sent sweat-on-court ITTO 5.9.1.6 and Law 16.7.1, and failed it
for leaving out the steps under 16.7.1.

## Consequences
- sweat-on-court is "map and tool". The spread is: search only 4, map 1, tool 2, map and tool 3,
  no answer 1.
- No agent setup had run on the unseen set yet; setup A's score only re-sorts by tag.
