# 0016 · The racket angle is context for a question about serve height

- **Status:** Accepted (Job, 8 Nov)
- **Date:** 2026-11-08
- **Stage:** 2 (answers, citations and refusals)

## Context
service-height-override asks "How high can the shuttle be when I hit my serve?" Record 0012 made its
pass rule ask for both parts of Alternative Service Law 9.1.6: (a) below the waist, a height rule, and
(b) the racket shaft and head pointing downward, a racket angle rule. The bot gave 1.15 m and the waist
rule in every run, and left out (b) in most.

## Options considered
1. **Keep (b) required,** and add a prompt rule to give every lettered part of a rule. Pushes every
   answer to be longer than its question.
2. **(b) is context:** the question asks about height. Same reasoning as umpire-overrule (record 0012):
   answer what was asked.

## Decision
Option 2. Unlike post-height, where "stays vertical" sits in the same clause as the 1.55 m height,
part (b) is a separate rule about something else.

## Evidence
`20261108T1347` and `20261108T1358` (all three fixes of record 0015): service-height-override failed
both, each time only for leaving out part (b).

## Consequences
Record 0012's wording for this pass rule is superseded by this one.
