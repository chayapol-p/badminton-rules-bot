# Workshop notes

Raw lines while the labs run. No polishing. After Lab 7 they become the two skills
(building-fastapi-ai-services and building-react-chat-interfaces).

## Lab 0 · Setup

### Corpus (2 Nov): BWF rule books
- Product is the Badminton Rules Bot. Labs run on its corpus: Laws V5.0, ITTO V7.0, Alternative Laws V2.0 (in force 4 Jan 2027). Para ITTO kept in data/bwf but not ingested in v1.
- Chunk unit = one clause (Law 9.1.6 = one chunk). Citations come for free. 736 chunks: Laws 225, ITTO 481, Alt 30. Median 21 words, max 172 (ITTO 5.3.1, the match announcements).
- Hidden numbers: the Laws PDF draws two-level numbers (1.4., 7.5.) as tiny pictures. pdftotext drops them. Fix: a small picture at the left margin starts the next clause, counted under its Law heading. Rebuilt 1.1-1.11 ... 17.1-17.6, matches the PDF.
- Para clauses are printed in italics in the Laws -> para_only flag from the font (22 chunks). Only trust italics in the Laws.
- Alternative Laws repeat clause numbers per option -> id carries the option: alt-best-of-5-games-11:8.1.5.
- Bugs found while building (Lab 2 material): 5-level number on the same line as its text merged into the parent; option headings leaked into the previous chunk; a plain "or" between italic clauses switched off the para flag; all([]) is True, so 15 Law headings and Diagrams B and C were flagged para (fixed: a chunk needs at least one font flag).
- Still open: each Alternative Laws option keeps the previous option's heading (3 intro chunks, and alternative-service 9.1.6 carries "16. CONTINUOUS PLAY").
- Golden set: 39 questions in 9 categories, 13 exact-term / 26 paraphrased, each tagged dev (27) or held_out (12), stratified, seed 7.
- Chunk tests (7 Nov): tests/test_chunks.py, 32 tests on shape, counts, clause numbers, tags and coverage. Each Lab 0 bug has a regression test.
- Found by the chunk tests: in the ITTO, a clause number mid-line stays inside the previous chunk. 15 clauses lost, including 5.2.2.1 (warm-up). check_golden_questions hid it, because its text fallback matched "5.2.2.1" inside chunk 5.2.1. Fixed: clause numbers never match by text, only labels like DIAGRAM A. Open bugs are strict xfail tests.
- Decided (7 Nov): keep the list joiners ("... or", "... and") that end 38 chunks. They carry the list's logic (A or B), so stripping them would change the meaning.
- Rule map (3 Nov): scripts/build_rule_links.py reads links from the rule books into data/rule_links.json. 229 links: overrides 18, cites 179, para_exception_of 22, shows_diagram 10. Plus 3 Statutes sections outside the corpus (4.1.3, 4.1.5, 4.1.8).
- retrieval/rule_links.py follows the map after search, one hop: default Law first, every alternative labelled by option and in-force date, para exceptions only for para questions, cited Laws bring their alternatives, a cited list heading brings its sub-clauses. Plus nearby clauses: the rest of a list (15.1-15.3), or the clause before and after (7.4 -> 7.5).
- scripts/check_rule_links.py, from one hit and no search: lookup 2/2, override 4/4, para 1/1 (no leaks), cross-reference 3/5, diagram 0/1. The 2 cross-references link only through a shared cited Law (red-card, service-fault-officials), so search must find both.
- Prompt cost per hit: median 3 clauses, ~77 words; max 15 clauses, 395 words.
- Known limit: one level of list headings. Law 16.7 brings 16.7.1 but not 16.7.1.1-16.7.1.3, where the ruling is.

## Lab 1 · Search types

- Idea: the para filter is a metadata filter inside the search query, for BM25 and vector alike: where (not para_only or :question_is_para), then order by distance.
- Idea: 736 rows needs no vector index. Exact scan = exact filter. With HNSW later, pgvector filters after the index scan (ef_search 40 can return fewer than k); pgvector 0.8+ has hnsw.iterative_scan. Check the Supabase pgvector version.
- Idea: the rule map runs after search, so every search type in this lab gets it for free. Compare search types with and without expand_with_links.

## Lab 2 · Break and fix

## Lab 3 · How agents perform

- Idea (Job): flag para questions by meaning, with the LLM, not a word list (wheelchair, para, standing). Options to compare: a small-model classifier with structured output; the agent's search tool takes include_para and the agent decides; word list as the fast path, LLM only when unsure.
- Idea: try Jev (TypeSafe AI) as the para classifier. One Boolean question ("Is this about Para Badminton?") gives back a probability. About $0.04 per 1,000 calls, p50 0.15-0.25 s. Confident yes/no -> filter. Middle band -> show the para exceptions with their PARA EXCEPTION label instead of guessing. Unverified for query routing (only tested as an eval judge). Hosted API only, own SDK, no few-shot: the question wording is the only setting. Compare against the small-model classifier on the same golden questions.
- Para questions added (3 Nov): category para_question, 4 questions (golden set now 39). 2 name no para word ("I play from a chair", "the footrest of my chair"), so a word list misses them and only a meaning-based flag can pass.
- check_rule_links with the para flag set: para_question 3/4 from one hit. wheelchair-shuttle-on-net needs 14.2.3.1.1 (Lets) and 13.3.10.1 (Faults), two Laws with no link between them, so search must find both.
- Label bug found (Lab 4): for standing classes, Law 9.1.6.2 makes the alternative service law the rule, but the map still labels it "only by prior arrangement · not in force until 2027-01-04". The para exception changes what the alternative means for that class. Also unverified: which version of the alternative service law Standing Classes use before 2027.

## Lab 4 · Context enrichment

## Lab 5 · Pick the approach

## Lab 6 · Evals and citations

## Lab 7 · React chat UI
