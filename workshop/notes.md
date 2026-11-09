# Workshop notes

Raw lines while the labs run. No polishing. After Lab 7 they become the two skills
(building-fastapi-ai-services and building-react-chat-interfaces).

## Lab 0 · Setup

### Corpus (2 Nov): BWF rule books
- Product is the Badminton Rules Bot. Labs run on its corpus: Laws V5.0, ITTO V7.0, Alternative Laws V2.0 (in force 4 Jan 2027). Para ITTO kept in data/bwf but not ingested in v1.
- Chunk unit = one clause (Law 9.1.6 = one chunk). Citations come for free. 754 chunks: Laws 225, ITTO 499, Alt 30. Median 21 words, max 172 (ITTO 5.3.1, the match announcements).
- Hidden numbers: the Laws PDF draws two-level numbers (1.4., 7.5.) as tiny pictures. pdftotext drops them. Fix: a small picture at the left margin starts the next clause, counted under its Law heading. Rebuilt 1.1-1.11 ... 17.1-17.6, matches the PDF.
- Para clauses are printed in italics in the Laws -> para_only flag from the font (22 chunks). Only trust italics in the Laws.
- Alternative Laws repeat clause numbers per option -> id carries the option: alt-best-of-5-games-11:8.1.5.
- Bugs found while building (Lab 2 material): 5-level number on the same line as its text merged into the parent; option headings leaked into the previous chunk; a plain "or" between italic clauses switched off the para flag; all([]) is True, so 15 Law headings and Diagrams B and C were flagged para (fixed: a chunk needs at least one font flag).
- Fixed (7 Nov): each Alternative Laws option kept the previous option's heading. A new option now starts with no heading, and the alternative service law borrows the Law's (9. SERVICE).
- Golden set: 39 questions in 9 categories, 13 exact-term / 26 paraphrased, each tagged dev (27) or held_out (12), stratified, seed 7.
- Chunk tests (7 Nov): tests/test_rule_chunks.py, 37 tests on shape, counts, clause numbers, tags and coverage. Each Lab 0 bug has a regression test.
- Found by the chunk tests: in the ITTO, a clause number mid-line stays inside the previous chunk. 15 clauses lost, including 5.2.2.1 (warm-up). check_golden_questions hid it, because its text fallback matched "5.2.2.1" inside chunk 5.2.1. Fixed: clause numbers never match by text, only labels like DIAGRAM A.
- Fixed (7 Nov): in the ITTO, a clause start is a number with a final dot, or a number and two or more spaces; a wrap reference ("16.7 applied") has neither. 18 clauses recovered (ITTO 481 -> 499), including 5.2.2.1. The rule map kept its 229 links; 3 cites and 1 outside-corpus reference moved to the recovered clauses.
- Decided (7 Nov): keep the list joiners ("... or", "... and") that end 38 chunks. They carry the list's logic (A or B), so stripping them would change the meaning.
- Rule map (3 Nov): scripts/build_rule_links.py reads links from the rule books into data/rule_links.json. 229 links: overrides 18, cites 179, para_exception_of 22, shows_diagram 10. Plus 3 Statutes sections outside the corpus (4.1.3, 4.1.5, 4.1.8).
- retrieval/expand_with_rule_links.py follows the map after search, one hop: default Law first, every alternative labelled by option and in-force date, para exceptions only for para questions, cited Laws bring their alternatives, a cited list heading brings its sub-clauses. Plus nearby clauses: the rest of a list (15.1-15.3), or the clause before and after (7.4 -> 7.5).
- scripts/check_rule_links.py, from one hit and no search: lookup 2/2, override 4/4, para 1/1 (no leaks), cross-reference 3/5, diagram 0/1. The 2 cross-references link only through a shared cited Law (red-card, service-fault-officials), so search must find both.
- Prompt cost per hit: median 3 clauses, ~77 words; max 15 clauses, 395 words.
- Known limit: one level of list headings. Law 16.7 brings 16.7.1 but not 16.7.1.1-16.7.1.3, where the ruling is.

## Lab 1 · Search types

- Idea: the para filter is a metadata filter inside the search query, for BM25 and vector alike: where (not para_only or :question_is_para), then order by distance.
- Idea: 754 rows needs no vector index. Exact scan = exact filter. With HNSW later, pgvector filters after the index scan (ef_search 40 can return fewer than k); pgvector 0.8+ has hnsw.iterative_scan. Check the Supabase pgvector version.
- Idea: the rule map runs after search, so every search type in this lab gets it for free. Compare search types with and without expand_with_links.

## Lab 2 · Break and fix

## Lab 3 · How agents perform

- Idea (Job): flag para questions by meaning, with the LLM, not a word list (wheelchair, para, standing). Options to compare: a small-model classifier with structured output; the agent's search tool takes include_para and the agent decides; word list as the fast path, LLM only when unsure.
- Idea: try Jev (TypeSafe AI) as the para classifier. One Boolean question ("Is this about Para Badminton?") gives back a probability. About $0.04 per 1,000 calls, p50 0.15-0.25 s. Confident yes/no -> filter. Middle band -> show the para exceptions with their PARA EXCEPTION label instead of guessing. Unverified for query routing (only tested as an eval judge). Hosted API only, own SDK, no few-shot: the question wording is the only setting. Compare against the small-model classifier on the same golden questions.
- Para questions added (3 Nov): category para_question, 4 questions (golden set now 39). 2 name no para word ("I play from a chair", "the footrest of my chair"), so a word list misses them and only a meaning-based flag can pass.
- check_rule_links with the para flag set: para_question 3/4 from one hit. wheelchair-shuttle-on-net needs 14.2.3.1.1 (Lets) and 13.3.10.1 (Faults), two Laws with no link between them, so search must find both.
- Label bug found (Lab 4): for standing classes, Law 9.1.6.2 makes the alternative service law the rule, but the map still labels it "only by prior arrangement · not in force until 2027-01-04". The para exception changes what the alternative means for that class. Also unverified: which version of the alternative service law Standing Classes use before 2027.

- Stage 3 prediction (Job, 9 Nov, before any run): A (full RAG) is the baseline; B (full agentic) covers what A missed by itself; C (RAG first, then tools) covers as much as B for fewer rounds, so it costs less. Checked on the 11 unseen questions by: C passes at least as many as B, C's average tool rounds are below B's, C's cost per question is below B's.
- Setup A on the 11 unseen questions (9 Nov, `20261109T0716-top5-unseen`, re-scored after record 0018): 5 of 10 answers, no-answer 1 of 1, $0.029 a question. By needs (record 0019): search only 3/4, map 1/1, tool 1/2, map and tool 0/3. The map never brings grandchildren (Law 14.2.3's net cases, Law 16.7.1's three steps): 2 fails. leaking-roof-score passed without Law 16.3.3, inferring 'the score stands' from ITTO 5.11.5. Two accidental repeat runs (`20261109T0717-top5-unseen`, both writing to one file pair, 22 lines) scored 6 and 6: every question gave the same verdict except opponent-calls-fault-mid-stroke, which passed both repeats. That is setup A's noise floor on unseen: 5 to 6 of 10.
- Tools turned off with no note (9 Nov, live, yellow-card-before-play, setup B, after 1 search round): valid JSON, empty answer, 0 citations; thinking ended 'I'll read laws-16.7.1.2 quickly'. With the note: full answer, 4 citations. Record 0020.
- Unseen, 3 runs per setup (9 Nov): A 5, 6, 6 of 10 ($0.030); C (hybrid) 10, 8, 8 ($0.037, 0.88 tool rounds); B (agentic) 7, 7, 8 ($0.056, 2.88 rounds, 1 question at the round limit). Of 30: A 17, C 26, B 22; no answer 3/3 for all. By needs, A/C/B: search only 11/11/8 of 12; map 3/3/3 of 3; tool 3/5/4 of 6; map and tool 0/7/7 of 9. Job's prediction holds on all 3 checks in every run pairing. C's misses: yellow-card-before-play 1/3 and line-judge-unsighted 2/3, both answered without the search they needed. B's misses: easy questions (cut-hand-mid-game 1/3) and over-searching (leaking-roof-score 1/3: added a replayed rally).
- Dev, one run each (9 Nov): C 19 of 22 (A 18 and 21), refusals 3/3, probes 6/6, false premises 3/3, $0.029, 0.64 rounds; B 17 of 22, probes 5/6 (answered altitude-shuttle-speed), false premises 2/3, $0.046, 2.75 rounds, 2 questions at the limit, 41 minutes.

## Lab 4 · Context enrichment

- Context header (7 Nov): every chunk gets search_text = document · format · para flag · heading · clause number, then the clause. The same clause number (16.2.1) holds different rules per Alternative Laws format, and the clause text never names its format. Search reads search_text; answers cite text. Stage 1 compares text against search_text.

## Lab 5 · Pick the approach

## Lab 6 · Evals and citations

- Mistral Large 4 rejects temperature 0 unless top_p is exactly 1 (400, code 3054: "top_p must be 1 when using greedy sampling"). The SDK sends no top_p, so the server's default applied. Fixed in generate_answer (7 Nov).
- Mistral Large 4 always thinks and always sends message.content as a list of chunks (thinking, then text), whatever reasoning_effort says (Mistral's reasoning docs). Run 1 crashed writing a ThinkChunk to JSON. Now the answer text is parsed, the thinking is kept as text, and reasoning_effort is pinned to low (Large 4 takes low, medium or high; Mistral recommends high) (7 Nov).
- Claude Sonnet 5.5 rejects thinking {"type": "disabled"} (400); the API says to send {"type": "between_tools"} to turn thinking off before responding. Fixed in the judge (7 Nov).
- Grading order (8 Nov, decision record 0007): code checks first, the judge only for what they pass. On run 1, 6 of 33 answers fail the code checks (4 wrong refusals, 2 quotes not in their clause), so 27 of 33 judge calls remain. Numbers not in the sources only warn: deuce-end's "22-20" is worked out from Law 7.4, and golden answers hold context numbers (11, 60, 13.4).
- Hand grades on run 1 (8 Nov): 7 of 10 pass. A fresh grader with no sight of the drafts agreed on 10 of 10. Both are Claude, so they check each other, not the Sonnet judge's family bias.
- Judge vs hand grades on run 1, old rubric (8 Nov): 8 of 10, below the 9-of-10 bar. Both misses are the judge being stricter: post-height fails on "stays vertical", a context fact the question didn't ask; coaches-at-interval fails on "11-point interval", which comes from the question, not the sources.
- Rubric and prompt (8 Nov, decision record 0008): facts in the question count as given unless the sources contradict them; the bot corrects a false premise, then answers (not a refusal). Hand grade post-height changed to fail: "stays vertical" is a required fact. Judge now matches 9 of 10 on run 1's old-rubric grades. 3 false-premise probes added; their vectors need scripts.build_embeddings on the Mac (the VM's proxy blocks Mistral).
- Run 1 re-judged, new rubric (8 Nov): judge matches 10 of 10 hand grades after coaches-at-interval flipped to fail. The bot linked "11-point" to Law 16.2.1 from memory; Law 16.2.1 wasn't in its top 5. Cause: retrieval miss.
- Rule links on run 1's top 5, no API (8 Nov): of 7 questions missing an answer clause, links bring every missing clause for red-card, wheelchair-shuttle-on-net, standing-class-service-height and best-of-three-interval, and Law 16.2.1 for coaches-at-interval (ITTO 5.4.12 still missing). service-height-override (ITTO 7.4.1) and service-fault-officials (ITTO 7.2) stay missing. Words per question 156 to 217; top 10 would be about twice top 5.
- Stage 2 runs, 8 Nov (answer pass rate of 22): baseline 12, repeat 12 (4 questions swap places: the noise floor), quote rule 14, + rule links 16, top 15 16 ($0.015), top 55 15 ($0.028), + complete-answers 16. Kept: top 5 + rule links + quote rule (records 0009-0011). False premises 3 of 3, no-answer 9 of 9 on the winner.
- Two runs in parallel hit Mistral's rate limit (429) and both died; top 15 alone hit it too (bigger prompts). Fixed with the SDK's retry with backoff (8 Nov). Run one at a time.
- Format errors: 1 in 6 of 7 runs, always "finish reason length". Large 4's thinking uses up the 4,096-token cap on long questions (coaches, red-card). Candidate fix: raise MAX_ANSWER_TOKENS.
- Quotes with "…" fail the citation check (itto-7.4, 3 runs): the model joins pieces of one clause. Open: allow "…" between pieces that are each in the clause, or forbid it in the prompt.
- Runs 8 Nov, second batch (pass rules for umpire-overrule and service-height-override fixed first; the best run re-judged: 17 of 22). Cap 16,000: 17, format errors 0 (kept as a bug fix: the cap is a ceiling, not a charge). + para-default: 18. + para-only-when-asked: 18. + list items: 18. + value-conditions: 18. Each fixed its target (leaving-court; wheelchair-shuttle-on-net; post-height and service-height-override), each +1, none 2 apart.
- best-of-five-change-ends failed in 3 of the 4 extra-rule runs: answer rule 4 says "give the standard rule first", and its pass rule says "does not give the standard rule". The golden set and the prompt disagree; best-of-three-interval's pass rule allows the standard rule as context.
- attack-be-the-referee flips between runs: the judge fails the bot's own words ("I answer questions about the rules only") as not in the sources. Statements about the bot itself aren't rule claims.
- Combined run, 8 Nov (list items + para-only-when-asked + value-conditions, after records 0012-0013): 19, repeat 17. The cap-16k run re-judged under the same rules: 18. No gain beyond the noise: the same setup moves by 2 between runs, as large as each fix.
- The judge reads the bot's reasoning field: leaving-court failed in both combined runs because the reasoning, not the answer, named Law 16.5.3. Users see the answer and citations only.
- Anthropic API usage limit reached on 8 Nov (resets 2026-12-01 00:00 UTC, or raise it in the Console): the re-judge with the new judge (answer only, 3 votes) is blocked.
- Question history on the old grades (8 Nov), baseline 0931 + cap16k: para rule wins leaving-court 2 of 2 (0 of 2 before); list items win wheelchair-shuttle-on-net (1 of 1 alone, 2 of 2 combined); value-conditions wins post-height and service-height-override 1 of 1. The regressions it flags are attack-be-the-referee and best-of-five-change-ends (both explained by records 0012-0013) and, in the combined runs, coaches-at-interval and foot-off-footrest (judge strictness, to recheck with the new judge).
- Re-judged 7 runs with the new judge (answer only, 3 votes), 8 Nov: baselines 15 and 17; para rule 18; list items 17; value conditions 19; all three 18 and 20. No regressions anywhere. All three fixes now default (record 0015).
- New judge finding: racket-max-size fails for "stringed area" because clause 4.2.2 is a fragment whose subject sits in the heading above it. The source block shows the clause text only.
- Third round, 8 Nov: official links 21 of 22; parent headings 18 and 21 (racket-max-size and string-tension pass every run). Showing every parent made string-tension quote a full parent rule; headings only fixed it (record 0017). Citation check now treats "…" as "..." (red-card).
- Held-out, scored once (9 Nov, `20261109T0153-top5-held-out`): 7 of 10 answers (0.70), refusals 2 of 2, citations clean 1.0, 1 false refusal, $0.027 a question. Dev runs on the same setup: 18-22 of 22. Fails: phone-rings (left out the warning/fault steps of Law 16.7), shuttle-stuck-on-net (refused; the regular let rule 14.2.3.1 wasn't found), racket-parts (left out the throat). Not tuned on (experiment rule 4).
- Judge strictness still varies on context facts (coaches-at-interval failed for the 60-second break length; foot-off-footrest for "the rally ends with a fault").

## Lab 7 · React chat UI
