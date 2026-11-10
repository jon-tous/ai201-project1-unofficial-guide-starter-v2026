# The Unofficial Guide

Jon Toussaint — corpus: `campus_life`

> **This file is your submission.** Fill it in as you go — most sections get
> written during the milestone that produces them, not at the end.
>
> How the starter works, and every command you'll need, is in `RUNNING.md`.
> Leave that file alone.
>
> **Paste everything as text.** No screenshots, no video. A typed table gets
> full credit; a picture of the same table gets none, because the grader can't
> read it.
>
> Delete these instruction blocks as you replace them. The `<!-- -->` comments
> are notes to you and don't show up when the page renders — you can leave them
> or remove them.

---

# Week 1

## What This Does

This is a small retrieval-augmented Q&A system built on `campus_life`, a
corpus of 88 short, single-topic posts about student life — dining hall wait
times, course workloads, housing lottery rules, laundry costs, administrative
deadlines, and similar. Ask it something specific and checkable, like "How
many hours a week should I expect for CS 210?" or "By what time are the
sandwiches at The Atrium picked clean?", and it retrieves the post that
actually answers it, checks that the retrieval is close enough to be trusted,
and answers using only that text, naming the file it came from. Ask it
something the corpus doesn't cover — a recipe, sports trivia, another
school's rules — and it refuses instead of guessing.

## Chunking Strategy

**Chunk size:** 600 characters, as a ceiling, not a cut point.
**Overlap:** none — the splitter breaks at paragraph boundaries, never mid-sentence, so there's nothing for character overlap to patch over.

Every document in `campus_life` is a short, single-topic post: 183 to 554
characters, all of them under the old 800-character `CHUNK_SIZE`, which is why
the starter's fixed-window chunker never split anything (88 documents in, 88
chunks out). I read all 88 in Milestone 1 to check whether that was luck or
the right call, and it's the right call: a post's paragraphs are sub-points of
one topic (a course post's intro/format, workload line, and advice line; a
dining post's wait-times, hours, and cost), not separate topics worth pulling
apart.

So `split_documents` (`chunker.py`) walks each document's paragraphs and
groups them up to `CHUNK_SIZE`, splitting only at a paragraph break if a
document ever runs long. I set `CHUNK_SIZE` to 600 — just above the longest
real document (554) — instead of leaving it at 800, so the ceiling is doing
real work: every actual post still lands in one chunk, but a future document
that ran past 600 characters would get split at a paragraph boundary rather
than mid-sentence, or silently kept whole under a needlessly generous limit.
Splits are also never allowed to leave a trailing fragment under 80
characters (`MIN_CHUNK_CHARS`, the same floor as acceptance criterion 4) —
a bare fragment like "Expect 4 hours a week outside class." with no course
name in it gets merged back into the chunk before it instead of standing
alone.

I didn't change my mind partway through — the corpus made this call pretty
clearly once I'd read it.

## Sample Chunks

<!-- Five chunks, pasted as text. Label each one and name the file it came from
     AND the function that produced it — the grader checks your code against
     what you claim here.

     `python app.py chunks -n 5` prints all three for you. Copy them straight
     across.

     Milestone 3. -->

**Chunk 1** — source: `admin_add_drop_deadline.txt#0` — produced by: `chunker.py::split_documents`

```
On the add/drop deadline

You can add a course through the end of the second week. Dropping is a longer window — through the end of week six — but a drop after week two shows as a W on your transcript. Nothing anywhere on the registrar's site says this plainly, and students find out from each other.
```

**Chunk 2** — source: `course_biol_160.txt#0` — produced by: `chunker.py::split_documents`

```
BIOL 160 Cell Biology

I lived here my sophomore year. Format is lecture three times a week with a weekly lab. Assessment: four unit tests and a cumulative final. Not curved.

Expect 9 to 11 hours a week, the heaviest first-year course by reputation.

The one piece of advice: the unit tests come fast, roughly every three weeks; falling behind once is very hard to recover from.
```

**Chunk 3** — source: `course_hist_118_workload.txt#0` — produced by: `chunker.py::split_documents`

```
Workload for HIST 118 Modern World History

People keep asking so: a lot of reading, about 120 pages a week, but no problem sets. That's real time, not optimistic time.

It's front-loaded — the first month is heavier than the rest, partly because you're learning the format.
```

**Chunk 4** — source: `dining_pellew_dining_hall_followup.txt#0` — produced by: `chunker.py::split_documents`

```
Re: Pellew Dining Hall

Adding to what people have said about Pellew Dining Hall. The wait figure of 12 to 18 minutes at peak matches what I've seen. If you're trying to eat between classes, go before 11:45 and it's a different building entirely.

Also worth saying: the furthest hall from anywhere, next to the athletics centre. Nobody tells you this at orientation.
```

**Chunk 5** — source: `housing_innisfree_hall.txt#0` — produced by: `chunker.py::split_documents`

```
Innisfree Hall — what it's actually like

Transferred in last year, so take this with a grain of salt. Built 1991, renovated 2022. Rooms are doubles arranged as pairs sharing one bathroom between two rooms.

The good: the shared-bathroom-between-two-rooms arrangement is the best compromise on campus.

The bad: no air conditioning, which matters for the first three weeks of September.

Laundry costs $1.75 wash, $1.75 dry, app-based. On noise: moderate; the building is L-shaped and the short wing is much quieter.
```

## Sample Answer

<!-- One complete question and answer, pasted as text, with the source line
     visible. Milestone 4. -->

**Question:** How much printing does each student get per semester, and does it roll over?

**Answer:**

```
Each student gets $30 of printing per semester (roughly 600 black-and-white pages), and it does not roll over.

Source: admin_printing_quota.txt
```

**My relevance cutoff:** 0.5

I ran my 5 test questions and the 5 in `OUT_OF_SCOPE` through `python app.py
retrieve` and recorded each one's best (lowest) distance. The in-corpus
questions came back 0.214–0.295; the out-of-scope ones came back 0.825–0.934
— a gap of over half a point with nothing in it. 0.5 sits in the middle of
that gap: comfortably above every real question's best distance and
comfortably below every off-topic one's, so a small shift in either group on
a different run isn't likely to cross it. I left the old 0.6 default behind
on purpose — it happens to also fall in the gap here, but it wasn't chosen
from these numbers, and 0.5 is more centered.

| Question | In corpus? | Best distance |
|---|---|---|
| How much printing does each student get per semester, and does it roll over? | Yes | 0.260 |
| How late in the term can I declare a course pass/fail? | Yes | 0.215 |
| By what time are the sandwiches at The Atrium usually picked clean? | Yes | 0.295 |
| How many hours a week outside class should I expect for CS 210? | Yes | 0.278 |
| How is housing lottery order decided for juniors and seniors? | Yes | 0.214 |
| What is the capital of Mongolia? | No | 0.825 |
| How do I change the oil in a diesel engine? | No | 0.934 |
| Who won the 1994 World Cup? | No | 0.886 |
| What is the recommended dosage of ibuprofen for a headache? | No | 0.844 |
| How do I write a for loop in Rust? | No | 0.896 |

## How I Used AI

**1.** For Milestone 3, I asked Claude what would happen if I chunked
`campus_life` by naively splitting on paragraph breaks instead of the
starter's fixed 800-character window. It found that `course_econ_101.txt`'s
workload paragraph would come out as its own 42-character chunk — "Expect 4
hours a week outside class." — with no course name anywhere in it, useless on
its own. That's what convinced me the splitter needed a hard floor, not just
a paragraph-aware split, so I had it add the merge-back rule: any trailing
paragraph group under 80 characters gets folded into the chunk before it
instead of standing alone. That floor is now `MIN_CHUNK_CHARS` in
`chunker.py`, and it's the same 80 I used for acceptance criterion 4.

**2.** For Milestone 4, I asked Claude to run my 5 test questions and the 5
`OUT_OF_SCOPE` questions through `python app.py retrieve` and read off the
gap between the two groups rather than reusing the starter's 0.6 default. It
came back with 0.214–0.295 for the real questions, 0.825–0.934 for the
out-of-scope ones, and proposed 0.5 as the midpoint. Before accepting that
number I had it show me the CS 210 question specifically — criterion 5 in
`criteria.md` already flagged it as the one riskiest for source attribution,
since `course_cs_210.txt` and `course_cs_210_workload.txt` state the same fact
— and its best distance (0.278) was comfortably clear of 0.5 too, so I kept
the number instead of second-guessing it further.

**3.** For Milestone 3, all five criteria came back MET on the first real
run, so I asked Claude whether that meant the pipeline was solid or the
targets were too easy — and to look for one pattern across the five
rather than explain each MET individually. It came back with a pattern I
hadn't seen coming in from the run log alone: three of the five criteria
(2, 3, 4) couldn't really have failed, for three different structural
reasons (prompt instruction-following, code construction, and circular
threshold tuning), not because retrieval was actually reliable on those
three. To pressure-test criterion 3 specifically, it proposed harder,
topically-adjacent out-of-scope questions and came back with four of
them; I had it add a fifth, since criteria.md's own "4 of 5" target needs
five things to be a fraction of, and picked the parking-ticket-appeal
question over its other suggestions because it shared the same
near-duplicate-vocabulary risk ("appeal") I'd already used for CS 210
under criterion 5, instead of taking whichever one came back first.

<!-- ── Stretch features ─────────────────────────────────────────────────────
     Doing one? Say so here BEFORE you start. A feature this README never
     claims earns nothing.
     ───────────────────────────────────────────────────────────────────────── -->

---

# Week 2

> Week 2's criteria now live in [criteria_week2.md](criteria_week2.md); references to `criteria.md` in the Week 1–2 sections mean that file. `criteria.md` holds the Week 9 capstone criteria.

<!-- These sections get ADDED to what's already above. Don't delete or rewrite
     week 1 — the point is that someone can see what you said before you knew
     how it went. -->

## Run Log — Before

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 | 5 of 5 | 5 of 5 | 5 of 5 | MET |
| 2. Every answer names a source | 5 of 5 | 5 of 5 | 5 of 5 | 5 of 5 | MET |
| 3. Gate stops out-of-corpus questions | 4 of 5 | 5 of 5 | 5 of 5 | 5 of 5 | MET |
| 4. No chunk is shorter than 80 characters | all of them | 88 of 88 | 88 of 88 | 88 of 88 | MET |
| 5. Named source actually backs the answer | 4 of 5 | 5 of 5 | 5 of 5 | 5 of 5 | MET |

`scorer.py` doesn't exist, so runs 1–3 for criteria 1, 2, and 5 are my own
reading of the real output below (from `results/run_2026-09-20_1747_before.md`,
produced by `run_eval.py::main`), question by question, run by run — not a
description of it. Criteria 3 and 4 are each one deterministic pass
(`run_eval.py::check_out_of_scope` for the gate; `chunker.py::split_documents`
for chunk length), so the same number holds across all three run columns on
purpose.

Real output, run 1, for the question I expected to be the shaky one:

```
### How is housing lottery order decided for juniors and seniors? — run 1

- Best distance: 0.2143 (passed the gate)
- Sources retrieved: admin_housing_lottery.txt, admin_parking_permits.txt, advising_registration.txt, dining_the_atrium_followup.txt, housing_tamsin_court.txt

Juniors and seniors are ordered by accumulated credit hours first, and only tie-break randomly (admin_housing_lottery.txt).
```

Real output for criterion 3 and 4, one pass each:

```
## The relevance gate on out-of-corpus questions
Produced by `run_eval.py::check_out_of_scope`, cutoff 0.5. Refused 5 of 5.

| Out-of-scope question | Best distance | Gate |
|---|---|---|
| What is the capital of Mongolia? | 0.825 | refused |
| How do I change the oil in a diesel engine? | 0.934 | refused |
| Who won the 1994 World Cup? | 0.886 | refused |
| What is the recommended dosage of ibuprofen for a headache? | 0.844 | refused |
| How do I write a for loop in Rust? | 0.896 | refused |
```

```
$ python -c "from ingest import load_documents; from chunker import split_documents as s; c = s(load_documents()); print(len(c), 'chunks,', min(len(x.text) for x in c), 'shortest')"
88 chunks, 178 shortest
```

## Verdicts

| # | Criterion | Verdict | How I decided |
|---|---|---|---|
| 1 | Retrieved chunks contain the answer (target: 4 of 5) | MET | Judged by hand since `scorer.py` doesn't exist. For all 5 questions, every one of the 3 runs produced an answer containing the exact `expects` phrase (`$30`, `week eight`, `1:15`, `8 to 10 hours`, `credit hours`), and generation is grounded to only the retrieved chunks — so the answer chunk was in the retrieved set 15/15 times, including the housing-lottery question I'd flagged as the one likely to miss. 5 of 5, not just 4. |
| 2 | Every answer names a source (target: 5 of 5) | MET | Read all 15 runs (5 questions × 3 runs) in `results/run_2026-09-20_1747_before.md`. Every single one names at least one source filename, whether as `Source: file.txt` or inline in parentheses. 15/15. |
| 3 | Gate stops out-of-corpus questions (target: 4 of 5) | MET | `run_eval.py::check_out_of_scope` refused all 5 `OUT_OF_SCOPE` questions, with best distances 0.825–0.934 against the 0.5 cutoff — comfortably refused, not a borderline call. 5 of 5. |
| 4 | No chunk is shorter than 80 characters (target: all of them) | MET | Ran `split_documents` fresh: 88 documents in, 88 chunks out, shortest chunk 178 characters, zero chunks under 80. Not close. |
| 5 | Named source actually backs the answer (target: 4 of 5) | MET | For each of the 5 questions I grepped the exact source file named in the answer for the `expects` phrase from `questions.py`. All 5 files contain their phrase verbatim, including `course_cs_210_workload.txt` for the CS 210 question — the one I built specifically to risk a mix-up with its near-duplicate `course_cs_210.txt`, and it named the right one all 3 runs. 5 of 5. |

## Diagnoses

I missed nothing — all five criteria came in MET on every run (see
Verdicts, above). There's no failure to trace through the five stages
here, so the honest thing to do is check whether that's because the
pipeline is solid or because the targets never put it at real risk.

Looking criterion by criterion, three of my five never had a real chance
to fail, for three different reasons — that's one pattern, not three
separate problems:

- **Criterion 2** (every answer names a source) was never really at risk.
  `criteria.md`'s own "why this target" already said this out loud:
  `generate.py` labels every chunk `[from filename]` in the prompt and its
  system instruction tells the model outright to name the file. Passing
  this is instruction-following, not a retrieval result.
- **Criterion 4** (no chunk under 80 characters) is guaranteed by
  construction. `MIN_CHUNK_CHARS = 80` and the merge-back rule are inside
  `chunker.py::split_documents` itself — a trailing fragment gets folded
  into the previous chunk before it can ever become a standalone chunk. On
  this corpus the criterion can't fail; it's testing whether I wrote the
  code I said I'd write, not whether the pipeline behaves well on new input.
- **Criterion 3** (gate refuses out-of-corpus questions) is circular as
  measured. I picked `THRESHOLD = 0.5` in Milestone 4 by looking directly
  at these same five `OUT_OF_SCOPE` questions' distances (0.825–0.934) and
  choosing a cutoff that clears them with room. Evaluating criterion 3
  against the same five questions used to set the cutoff doesn't test
  whether the gate generalizes — it tests whether I can draw a line
  between two clusters I already had in front of me.

To find out whether criterion 3 would survive a harder test, I ran four
new out-of-scope questions that were never part of tuning — not trivia,
but campus-life-*shaped* topics this corpus doesn't actually cover:

| Question | Best distance | Gate |
|---|---|---|
| How do I request a safety escort to walk home at night? | 0.672 | refused |
| How do I sign up for a campus gym membership? | 0.617 | refused |
| How do I book a tutoring appointment for calculus? | 0.598 | refused |
| How do I report a lost student ID card? | 0.714 | refused |

All four still refused — the gate holds. But the margin above the 0.5
cutoff shrank from 0.325–0.434 (the trivia set) to 0.098–0.214 (this set).
The tutoring question in particular cleared the cutoff by less than a
tenth of a point, retrieving `money_textbooks.txt` on vocabulary overlap
("book," presumably) rather than any real topical match. Nothing broke,
but the pipeline has far less room here than a "5 of 5, comfortably
refused" result suggests.

**Which I'd tighten, and to what:** criterion 3. I'd swap the trivia
questions in `OUT_OF_SCOPE` for topically-adjacent ones like the four
above — plausible campus questions this corpus genuinely doesn't cover,
not questions from a different universe entirely — and I'd add a margin
requirement: not just "refused," but "refused with best distance at least
0.1 clear of the cutoff." A gate that barely clears isn't meaningfully
different from one that's about to fail on the next slightly-closer
question, and "4 of 5 refused" alone can't tell those apart.

Only criteria 1 and 5 tested something with real uncertainty going in —
whether retrieval would surface a fact buried mid-paragraph (the housing
lottery question) or correctly pick between two near-duplicate files
(CS 210) — and both held up on their merits rather than by construction or
circular tuning. Those are the two results I actually trust.

## The Improvement

**What I changed:** Retuned the relevance gate against a harder,
non-circular out-of-scope set. Two parts, one change: (1) swapped
`OUT_OF_SCOPE` in `questions.py` from five unrelated trivia questions to
five topically-adjacent ones the corpus genuinely doesn't cover — safety
escorts, gym membership, tutoring appointments, lost ID cards, parking-ticket
appeals — several sharing a word with a real document the way an actual
off-topic question might (`appeal`/`admin_grade_appeals.txt`,
`book`/`money_textbooks.txt`); (2) lowered `THRESHOLD` in `config.py` from
0.5 to 0.45, the highest value that still keeps at least 0.1 clear of both
the real questions' worst distance (0.295) and the new out-of-scope
questions' best distance (0.598). Chunking and retrieval are untouched —
same 88 chunks, same embeddings, same `top_k`.

**Why I picked it:** This is exactly what the diagnosis named. Criterion 3
was measured against the same trivia questions used to pick the original
0.5 cutoff, so "5 of 5, comfortably refused" never tested anything — it
just confirmed I could draw a line between two clusters I already had in
front of me. Testing against genuinely adjacent questions, and retuning the
cutoff against *that* set instead, is the fix the circularity pointed at.

### Run Log — After

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 | 5 of 5 | 5 of 5 | 5 of 5 | MET |
| 2. Every answer names a source | 5 of 5 | 5 of 5 | 5 of 5 | 5 of 5 | MET |
| 3. Gate stops out-of-corpus questions (harder set, cutoff 0.45) | 4 of 5 | 5 of 5 | 5 of 5 | 5 of 5 | MET |
| 4. No chunk is shorter than 80 characters | all of them | 88 of 88 | 88 of 88 | 88 of 88 | MET |
| 5. Named source actually backs the answer | 4 of 5 | 5 of 5 | 5 of 5 | 5 of 5 | MET |

Real output, produced by `run_eval.py::check_out_of_scope`
(`results/run_2026-09-20_1820_after.md`), cutoff 0.45:

```
| Out-of-scope question | Best distance | Gate |
|---|---|---|
| How do I request a safety escort to walk home at night? | 0.672 | refused |
| How do I sign up for a campus gym membership? | 0.617 | refused |
| How do I book a tutoring appointment for calculus? | 0.598 | refused |
| How do I report a lost student ID card? | 0.714 | refused |
| How do I appeal a parking ticket I think was issued unfairly? | 0.641 | refused |
```

Everything else — the five real-question answers, their sources, the
88/88 chunk floor — came back byte-for-byte the same distances as the
before run (`results/run_2026-09-20_1747_before.md`), which is expected:
this change touched only the gate and its test set, not chunking or
retrieval.

**Did it help?** Yes, but not by moving a raw count — criteria 1, 2, 4,
and 5 were already 5 of 5 and stayed there, because chunking and
retrieval weren't touched. Criterion 3's count didn't move either (still
5 of 5); what changed is what that "5 of 5" proves. Under the harder,
non-circular test, the margin above cutoff dropped from 0.325–0.434
(trivia, at 0.5) to 0.148–0.264 (adjacent questions, at 0.45) — real
headroom, but far less than the original measurement implied. And the
retune specifically mattered: at the *old* 0.5 cutoff, the tutoring
question's margin against the harder set would have been 0.098, missing
the ≥0.1 margin rule I set in the diagnosis; only after lowering the
cutoff to 0.45 does it clear that bar (0.148). So the fix didn't just
relabel the same result — without it, my own tightened version of
criterion 3 would have failed on the question closest to the line.

## What's Still Broken

No criterion is currently missed — all five are MET, before and after the
fix. But a clean Verdicts column hides three things I know are still
fragile, and I'm calling them out on purpose rather than letting "MET"
stand in for "solid":

- **Criterion 3's margin is real but thin, and I only stress-tested it
  against five questions I picked myself.** After the retune, the closest
  call (tutoring, 0.598) clears the 0.45 cutoff by 0.148 — comfortably
  over my own 0.1 margin rule, but nowhere near the 0.325+ margin the old
  trivia set implied. I didn't do a systematic or adversarial search for
  the single hardest near-miss question this corpus admits; I found one
  failure mode (shared vocabulary — "book," "appeal") and patched against
  that specific shape. A genuinely adversarial fifth or sixth question I
  haven't thought of could still land under 0.45. **Why I stopped here:**
  Milestone 4 asks for one change, measured properly, not an open-ended
  search for the worst case — I judged that finding and fixing one real
  failure mode, with numbers, was worth more than guessing at others I
  hadn't observed.
- **The paragraph-splitting branch in `chunker.py::split_documents` has
  never actually run.** `campus_life` produced 88 chunks from 88 documents
  both before and after Milestone 3 — every document's paragraphs fit
  under `CHUNK_SIZE` in one group, so the code path that splits a
  document at a paragraph break (instead of leaving it whole) has zero
  coverage from real data. I'm confident it's correct because I traced it
  by hand, but "I traced it by hand" is a weaker claim than "I watched it
  fire." **Why I stopped here:** fixing this means fabricating a synthetic
  long document, which risks testing my synthetic example instead of my
  actual corpus — I judged that out of scope for this submission rather
  than worth faking.
- **Criteria 1, 2, and 5 are still graded by me reading the output, not by
  a scorer.** `run_eval.py` prints `—` in the Run columns because
  `scorer.py` doesn't exist; my Verdicts and Run Log entries for those
  three criteria are my own reading of 15 real answers each, not an
  automated, rerunnable check. I also noticed the model's phrasing isn't
  stable — "Source: file.txt", "(file.txt)", and "Sources: file.txt and
  other.txt" all showed up for the same question across different runs —
  so any `scorer.py` I build later has to tolerate that variance or it
  will mark correct answers wrong. **Why I stopped here:** `run_eval.py`'s
  own docstring says building `scorer.py` and deciding what counts as
  correct is deliberately left as a later, separate exercise, not part of
  this submission — building it now would mean grading my own work with a
  tool I built to agree with myself.

## What I'd Do Differently

Mainly criterion 3. I'd write it from the start the way I rewrote it in
Milestone 4 — a topically-adjacent out-of-scope set plus an explicit
margin requirement ("refused, and by at least X") — instead of "4 of 5
refused" against whatever out-of-scope questions I happened to write in
Milestone 2. The tell was available earlier than I used it: the moment I
wrote five out-of-scope questions that shared *no* vocabulary at all with
dining halls, courses, or housing (criteria.md's own "why this target"
already says as much), I could have asked whether that made the test too
easy, not just whether the gate would pass it. I didn't need Milestone 4's
measurements to notice that; I needed to ask the question in Milestone 2.

Criteria 2 and 4 I'd leave mostly alone but with lower expectations of
what they're proving. Both turned out to be guaranteed by things I'd
already built before I ever ran the eval — the prompt's citation
instruction, and `MIN_CHUNK_CHARS`'s merge-back rule — so "MET" for
either one is closer to confirming I wrote the code I said I'd write than
to learning something about the system's behavior. I'd keep them (a
regression could still break either), but I wouldn't count on them to
catch anything new.

---

# Week 9 — Capstone

## What This Extends

This extends **Project 1, The Unofficial Guide** — the retrieval-augmented Q&A
system over the `campus_life` corpus (retrieve → relevance gate → grounded
Gemini answer), served over HTTP by `serve.py`'s `POST /ask`.

What's new is a **failure-handling layer on the `/ask` request path**, plus the
structured log that records every request, including the ones that fail. Before
this unit, `/ask` only behaved well when everything went right: the Gemini call
had no timeout, only rate-limit errors were retried, an empty model response came
back as a 200 with a blank answer, a non-string `question` crashed into Flask's
HTML error page, and nothing was logged anywhere.

## The Shape

**Shape B — Harden against failure.** I'm making `/ask` survive the bad path:
every request either gets a grounded answer or a JSON error with a deliberate
status code and a plain-language message, within a bounded amount of time, and
every request — good or bad — leaves a structured log record. Concretely: a
timeout on the model call, retries with backoff on transient errors (timeouts and
5xx, not just 429s), a fallback when the model returns nothing, validation of the
`question` field (type and length), and a switch that lets me inject each of
those faults on purpose so they can be tested.

**Out of scope:**

- **I'm not touching retrieval, the relevance gate, chunking, or the prompt.**
  Answer quality was Week 2's job; this unit is only about what happens when a
  request goes wrong.
- **I'm not hosting it (Path B, local with logs) and not adding auth or inbound
  rate limiting.** Protecting the service from callers is a different problem
  from surviving failures of the things it depends on.
- **I'm not adding a fallback model or a response queue.** When Gemini is down
  after retries, `/ask` says so cleanly; it doesn't try to answer some other way.

## Running It

**Path B — local with logs.** The service runs on my machine under gunicorn,
started by one command — `./run.sh` — which builds the search index if the
checkout doesn't have one and serves `POST /ask` and `GET /health` on port 5001.
The environment (Python 3.13, pinned `requirements.txt`, the ~80 MB bundled
embedder, a `GEMINI_API_KEY`) and the one-time setup are in
[RUNNING.md](RUNNING.md). I tested those instructions from a fresh `git clone`
into an empty folder with a new Python 3.13 venv: it built the index (13.3s),
served, answered, and logged on the first try.

Two things I hit getting here, both now handled in `run.sh` / RUNNING.md:
my old venv was Python 3.14, which `test.py` rejects (9/10 checks — rebuilt on
3.13, now 10/10); and port 5000 is taken on macOS by the AirPlay Receiver, so
the default port is 5001. Gunicorn's default 30s worker timeout would also
kill a request in the middle of its retries (the request deadline is 30s), so
`run.sh` sets `--timeout 60`.

## Instrumentation

Every `/ask` request — answered, refused, rejected, or failed — appends one JSON
line to `logs/requests.jsonl` (`requestlog.py::write`, called from
`serve.py::ask`). Unhandled errors and unknown routes are logged too, by
`serve.py::_unhandled`. Fields:

| Field | What it holds |
|---|---|
| `ts` | UTC timestamp, ms precision |
| `request_id` | 12-hex id, also returned in the JSON body and `X-Request-ID` header |
| `question` | what came in (clipped at 300 chars; non-string input logged as-is) |
| `fault` | injected fault, if any (`null` in normal use) |
| `answer`, `refused`, `best_distance`, `sources` | what went out, on a 200 |
| `status`, `outcome` | HTTP status and one of `answered`, `refused`, `bad_input`, `no_index`, `model_timeout`, `model_unavailable`, `model_empty`, `model_error`, `internal_error` |
| `latency_ms` | whole request, end to end inside the server |
| `retrieval_ms`, `model_ms` | time to the gate decision, and time from prompt to answer |
| `attempts`, `retries` | model calls made, and the failure kind behind each retry |
| `cache_hit` | answered from the local response cache (no API cost) |
| `prompt_tokens`, `output_tokens` | as reported by Gemini's `usage_metadata`, summed over attempts |
| `error` | the full internal error text — kept here, never sent to the caller |

`.venv/bin/python requestlog.py` prints the last 15 as a table;
`--summary` gives counts by outcome, latency, and mean tokens.

Extract from a real session (`AI201_CACHE=0 AI201_ALLOW_FAULTS=1 ./run.sh`,
driven by `tools/send.py`) — answered, refused, bad input, a request that
recovered from an injected 503, and an injected empty response:

```
{"ts": "2026-11-10T01:48:29.692+00:00", "request_id": "3bf54758026a", "question": "How much printing does each student get per semester, and does it roll over?", "fault": null, "answer": "Each student gets $30 of printing per semester (roughly 600 black-and-white pages), and it does not roll over. \n\nSource: admin_printing_quota.txt", "refused": false, "best_distance": 0.2598, "sources": ["admin_printing_quota.txt", "course_cs_210.txt", "course_cs_340.txt", "money_jobs.txt", "money_textbooks.txt"], "status": 200, "outcome": "answered", "latency_ms": 1236, "retrieval_ms": 70, "model_ms": 1166, "attempts": 1, "retries": null, "cache_hit": false, "prompt_tokens": 620, "output_tokens": 41, "error": null}
{"ts": "2026-11-10T01:48:30.474+00:00", "request_id": "111e991ce805", "question": "How late in the term can I declare a course pass/fail?", "fault": null, "answer": "You can declare a course pass/fail as late as week eight, after you've seen your midterm. (Source: admin_pass_fail_option.txt)", "refused": false, "best_distance": 0.2154, "sources": ["admin_add_drop_deadline.txt", "admin_declaring_a_major.txt", "admin_graduation_requirements.txt", "admin_pass_fail_option.txt", "course_cs_340.txt"], "status": 200, "outcome": "answered", "latency_ms": 779, "retrieval_ms": 72, "model_ms": 707, "attempts": 1, "retries": null, "cache_hit": false, "prompt_tokens": 547, "output_tokens": 35, "error": null}
{"ts": "2026-11-10T01:48:31.250+00:00", "request_id": "866e6d7e6c72", "question": "By what time are the sandwiches at The Atrium usually picked clean?", "fault": null, "answer": "The sandwiches at The Atrium are usually picked clean by 1:15. (Source: dining_the_atrium.txt and dining_the_atrium_followup.txt)", "refused": false, "best_distance": 0.2952, "sources": ["dining_halden_hall_followup.txt", "dining_kestrel_commons_followup.txt", "dining_north_kitchen_followup.txt", "dining_the_atrium.txt", "dining_the_atrium_followup.txt"], "status": 200, "outcome": "answered", "latency_ms": 775, "retrieval_ms": 65, "model_ms": 710, "attempts": 1, "retries": null, "cache_hit": false, "prompt_tokens": 664, "output_tokens": 41, "error": null}
{"ts": "2026-11-10T01:48:37.138+00:00", "request_id": "afa5a34eae6f", "question": "How do I request a safety escort to walk home at night?", "fault": null, "answer": "I don't have enough information about that.", "refused": true, "best_distance": 0.6715, "sources": [], "status": 200, "outcome": "refused", "latency_ms": 63, "retrieval_ms": 63, "model_ms": null, "attempts": 0, "retries": null, "cache_hit": false, "prompt_tokens": 0, "output_tokens": 0, "error": null}
{"ts": "2026-11-10T01:48:37.203+00:00", "request_id": "b6e492d077c1", "question": "How do I sign up for a campus gym membership?", "fault": null, "answer": "I don't have enough information about that.", "refused": true, "best_distance": 0.6169, "sources": [], "status": 200, "outcome": "refused", "latency_ms": 63, "retrieval_ms": 63, "model_ms": null, "attempts": 0, "retries": null, "cache_hit": false, "prompt_tokens": 0, "output_tokens": 0, "error": null}
{"ts": "2026-11-10T01:48:37.474+00:00", "request_id": "3dc53be9870b", "question": 123, "fault": null, "status": 400, "outcome": "bad_input", "latency_ms": 0, "retrieval_ms": null, "model_ms": null, "attempts": 0, "retries": null, "cache_hit": false, "prompt_tokens": 0, "output_tokens": 0, "error": "\"question\" must be a string, not int."}
{"ts": "2026-11-10T01:48:37.550+00:00", "request_id": "0ddd2cd1cd0b", "question": "", "fault": null, "status": 400, "outcome": "bad_input", "latency_ms": 0, "retrieval_ms": null, "model_ms": null, "attempts": 0, "retries": null, "cache_hit": false, "prompt_tokens": 0, "output_tokens": 0, "error": "\"question\" is empty. Ask something, like \"is the housing lottery random?\""}
{"ts": "2026-11-10T01:48:37.625+00:00", "request_id": "ad9bcba6d275", "question": null, "fault": null, "status": 400, "outcome": "bad_input", "latency_ms": 0, "retrieval_ms": null, "model_ms": null, "attempts": 0, "retries": null, "cache_hit": false, "prompt_tokens": 0, "output_tokens": 0, "error": "Send a JSON object, like {\"question\": \"is the housing lottery random?\"}"}
{"ts": "2026-11-10T01:48:39.550+00:00", "request_id": "29cdc10e3964", "question": "How much printing does each student get per semester, and does it roll over?", "fault": "server_error:1", "answer": "Each student gets $30 of printing per semester (roughly 600 black-and-white pages), and it does not roll over. \n\nSource: admin_printing_quota.txt", "refused": false, "best_distance": 0.2598, "sources": ["admin_printing_quota.txt", "course_cs_210.txt", "course_cs_340.txt", "money_jobs.txt", "money_textbooks.txt"], "status": 200, "outcome": "answered", "latency_ms": 1852, "retrieval_ms": 62, "model_ms": 1790, "attempts": 2, "retries": ["server"], "cache_hit": false, "prompt_tokens": 620, "output_tokens": 41, "error": null}
{"ts": "2026-11-10T01:48:41.326+00:00", "request_id": "31f38d2361c2", "question": "How late in the term can I declare a course pass/fail?", "fault": "server_error:1", "answer": "You can declare a course pass/fail as late as week eight, after you've seen your midterm. \n\nSource: admin_pass_fail_option.txt", "refused": false, "best_distance": 0.2154, "sources": ["admin_add_drop_deadline.txt", "admin_declaring_a_major.txt", "admin_graduation_requirements.txt", "admin_pass_fail_option.txt", "course_cs_340.txt"], "status": 200, "outcome": "answered", "latency_ms": 1774, "retrieval_ms": 65, "model_ms": 1709, "attempts": 2, "retries": ["server"], "cache_hit": false, "prompt_tokens": 547, "output_tokens": 35, "error": null}
{"ts": "2026-11-10T01:48:54.019+00:00", "request_id": "e90d0854fc93", "question": "How much printing does each student get per semester, and does it roll over?", "fault": "empty", "status": 502, "outcome": "model_empty", "latency_ms": 7080, "retrieval_ms": 69, "model_ms": 7012, "attempts": 4, "retries": ["empty", "empty", "empty", "empty"], "cache_hit": false, "prompt_tokens": 0, "output_tokens": 0, "error": "Model returned no text. 4 attempt(s); last error: injected: model returned no text"}
{"ts": "2026-11-10T01:49:01.099+00:00", "request_id": "68001e023384", "question": "How late in the term can I declare a course pass/fail?", "fault": "empty", "status": 502, "outcome": "model_empty", "latency_ms": 7078, "retrieval_ms": 66, "model_ms": 7012, "attempts": 4, "retries": ["empty", "empty", "empty", "empty"], "cache_hit": false, "prompt_tokens": 0, "output_tokens": 0, "error": "Model returned no text. 4 attempt(s); last error: injected: model returned no text"}
```

## What It Costs

**Per answered request: 598.6 input tokens + 38.9 output tokens ≈ $0.00028.**

How I measured it: with the cache off (`AI201_CACHE=0`), I sent my five Week 2
in-corpus questions twice each — ten real model calls — through the running
service and averaged the `prompt_tokens` and `output_tokens` fields the log
records from Gemini's own `usage_metadata` (first ten records of
`logs/requests.jsonl`). Input ranged 547–664 tokens, output 35–41. To turn
tokens into dollars I used gemini-3.5-flash-lite's listed price of $0.30 per
million input tokens and $2.50 per million output tokens:

    598.6 × $0.30 / 1,000,000 = $0.000180
     38.9 × $2.50 / 1,000,000 = $0.000097
                         total ≈ $0.000277 per answered request

Refused questions cost **$0** — the gate stops them before any model call
(the five out-of-scope requests logged 0 tokens and ~70 ms). Mean latency over
the ten answered requests was 852 ms, of which ~70 ms is retrieval.

**A hundred people a day:** if each asks 5 questions, that's 500 requests/day ×
$0.000277 = **$0.14/day**, about **$4.20/month**. On the free tier I actually
use, it's $0 — the binding cost there is quota, not money: 500 requests/day
fits, but the limiter's 30 requests/minute would make a burst of 100 people
asking at once queue for over 15 minutes.

## Run Log and Verdicts

Criteria: [criteria.md](criteria.md) (committed in `9ddfb14`, before any trial ran).
Each trial is one run of `tools/trials.py --trial N`, which starts a fresh server
(`AI201_CACHE=0 AI201_ALLOW_FAULTS=1 ./run.sh`), runs all five criteria, and stops it.
Nothing was changed between trials. Raw responses: `results/capstone/before_trial{1,2,3}.json`;
server-side records: `logs/requests.jsonl`.

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Every request leaves exactly one matching log record | 20 of 20 | 20/20 | 20/20 | 20/20 | **MET** |
| 2. Two injected 503s → 200 answer in < 6 s, log shows 3 attempts | 5 of 5 | 5/5 | 1/5 | 0/5 | **MISSED** |
| 3. 5 concurrent timed-out requests each get a 504 in < 30 s | 5 of 5 | 4/5 | 4/5 | 4/5 | **MISSED** |
| 4. Every bad-path response follows the error contract | 10 of 10 | 10/10 | 10/10 | 10/10 | **MET** |
| 5. Warm normal path: 20/20 answered and ≥ 18/20 < 2.0 s | both | 17/20 answered, 16/20 fast | 19/20, 19/20 | 20/20, 6/20 | **MISSED** |

Driver summary as printed (`tools/trials.py::main`):

```
before_trial1  (2026-11-09T21:54:46-0500)
  C1  20/20                        MET
  C2  5/5                          MET  secs=[4.209, 3.738, 3.876, 3.736, 3.708]
  C3  4/5                          MISSED  secs=[21.117, 21.123, 21.124, 21.125, 42.204]
  C4  10/10                        MET
  C5  17/20 answered, 16/20 <2.0s  MISSED  max=27.048s

before_trial2  (2026-11-09T21:59:04-0500)
  C1  20/20                        MET
  C2  1/5                          MISSED  secs=[9.299, 8.378, 3.809, 9.269, 7.724]
  C3  4/5                          MISSED  secs=[21.123, 21.124, 21.127, 21.128, 42.222]
  C4  10/10                        MET
  C5  19/20 answered, 19/20 <2.0s  MISSED  max=7.756s

before_trial3  (2026-11-09T22:03:26-0500)
  C1  20/20                        MET
  C2  0/5                          MISSED  secs=[13.076, 8.356, 11.834, 11.402, 24.714]
  C3  4/5                          MISSED  secs=[21.145, 21.147, 21.148, 21.151, 42.224]
  C4  10/10                        MET
  C5  20/20 answered, 6/20 <2.0s   MISSED  max=8.094s
```

### Real output, per criterion (trial 1)

**C1** — log records written by `requestlog.py::write` from `serve.py::ask`, for the
non-JSON body and the injected bad key; each `request_id` matched the response's
`X-Request-ID` exactly once (`tools/trials.py::c1_score`):

```
{"ts": "2026-11-10T02:55:52.992+00:00", "request_id": "e4fe55d52942", "status": 400, "outcome": "bad_input", "latency_ms": 0, "attempts": 0, "retries": null, "prompt_tokens": 0, "output_tokens": 0, "error": "Send a JSON object, like {\"question\": \"is the housing lottery random?\"}"}
{"ts": "2026-11-10T02:56:35.380+00:00", "request_id": "f49d876d6ae0", "status": 502, "outcome": "model_error", "latency_ms": 63, "attempts": 1, "retries": null, "prompt_tokens": 0, "output_tokens": 0, "error": "_InjectedBadKey: injected: 400 API_KEY_INVALID"}
```

**C2** — client result, then its log record (`generate.py::generate` retry loop):

```
{"status": 200, "secs": 4.209, "request_id": "0552debb2fb6"}
{"ts": "2026-11-10T02:57:40.099+00:00", "request_id": "0552debb2fb6", "status": 200, "outcome": "answered", "latency_ms": 4205, "attempts": 3, "retries": ["server", "server"], "prompt_tokens": 620, "output_tokens": 41, "error": null}
```

**C3** — the five concurrent responses (`tools/trials.py::c3_concurrent_timeout`):

```
{"status": 504, "secs": 21.117, "body": {"error": "The answer service took too long to respond. Please try again in a moment.", "kind": "model_timeout", "request_id": "f5f654032611"}}
{"status": 504, "secs": 21.123, "body": {"error": "The answer service took too long to respond. Please try again in a moment.", "kind": "model_timeout", "request_id": "7dcfba187e31"}}
{"status": 504, "secs": 21.125, "body": {"error": "The answer service took too long to respond. Please try again in a moment.", "kind": "model_timeout", "request_id": "b73eb4d19780"}}
{"status": 504, "secs": 21.124, "body": {"error": "The answer service took too long to respond. Please try again in a moment.", "kind": "model_timeout", "request_id": "6e8df5f908d9"}}
{"status": 504, "secs": 42.204, "body": {"error": "The answer service took too long to respond. Please try again in a moment.", "kind": "model_timeout", "request_id": "e8c69d3408e7"}}
```

**C4** — three of the ten bad-path bodies (`serve.py::ask` → `fail`):

```
400 {"error": "\"question\" must be a string, not int.", "kind": "bad_input", "request_id": "352368146724"}
504 {"error": "The answer service took too long to respond. Please try again in a moment.", "kind": "model_timeout", "request_id": "92950bd74191"}
503 {"error": "The answer service is temporarily unavailable. Please try again in a moment.", "kind": "model_unavailable", "request_id": "308eababf095"}
```

**C5** — the 16th and 17th normal requests, where Gemini started returning real 429s:

```
{"ts": "2026-11-10T02:55:04.205+00:00", "request_id": "b91235e0e256", "status": 200, "outcome": "answered", "latency_ms": 4119, "attempts": 3, "retries": ["rate_limit", "rate_limit"], "prompt_tokens": 620, "output_tokens": 41, "error": null}
{"ts": "2026-11-10T02:55:12.009+00:00", "request_id": "25c2ab9e8e98", "status": 503, "outcome": "model_unavailable", "latency_ms": 7800, "attempts": 4, "retries": ["rate_limit", "rate_limit", "rate_limit", "rate_limit"], "prompt_tokens": 0, "output_tokens": 0, "error": "Model service unavailable. 4 attempt(s); last error: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://aistudio.google.com/docs/rate-limits. To monitor your cur… [+1108 chars]"}
```

### Diagnoses

**C3 — stage: the serving layer (`run.sh`'s gunicorn pool). Mechanism: the request
deadline doesn't count time spent queued.** `run.sh` starts 1 worker with 4 threads.
Each timed-out request holds a thread for ~21 s (a 10 s attempt, 1 s backoff, a second
10 s attempt, then the deadline check in `generate.py::generate` stops it). Four requests
take all four threads; the fifth sits in gunicorn's queue for 21 s, then runs its own
21 s → 42.2 s. The 30 s deadline is measured from inside `generate()`, so the queue time
is invisible to it. The fifth time was 42.20–42.22 s in all three trials — a structural
result, not variance.

**C5 and C2 — one problem, two symptoms. Stage: the model call (Gemini, upstream).
Mechanism: the test's sustained call rate exceeds what this API key gets, and the
system's pacing and backoff are sized for a limit it doesn't actually have.**

- *Trial 1, C5:* after ~16 real calls in ~15 s Gemini returned real `429
  RESOURCE_EXHAUSTED`. The local limiter (`config.REQUESTS_PER_MINUTE = 30`) never
  stepped in because it assumes twice the rate Gemini allowed. The retry backoff
  (1 s, 2 s, 4 s) is seconds long against a one-minute window, so three requests used
  all four attempts and returned 503. Retries also count against the local limiter,
  which is why one of them took 27 s: the limiter slept before its fourth attempt. The
  very next request succeeded in 1.4 s — the window had rolled over, so this is a
  per-minute limit, not the daily quota.
- *Trial 3, C5:* no 429s and no retries — every request took 1 attempt — but 14 of 20
  took 3–8 s. `retrieval_ms` stayed ~70 ms, so all of it was inside the Gemini call. By
  then the key had made ~70 real calls in ten minutes; slower responses with no error is
  consistent with the provider throttling by latency, but the log can't confirm it (it
  doesn't record response headers).
- *C2, trials 2–3:* the retry logic did its job every time — 15 of 15 requests returned
  200 answers after exactly the injected failures. Every miss is on the 6 s limit, and
  `model_ms` puts the time in the final, real call. Two trial-3 requests logged a third
  `server` retry — a real transient error from Gemini on top of the two injected ones.
  C2 met in trial 1 and degraded through trials 2–3, tracking the same upstream slowdown
  as C5.

**Observability gaps the diagnosis exposed:** `retries` records only the failure *kind*,
not its text, so I can't tell whether trial 3's extra `server` retry was a 503 or a
dropped connection; and `requestlog.py` clips errors at 300 characters, which cut off the
part of Gemini's 429 that names which quota was hit.

**C1 and C4 met in all three trials.** The logging and the error contract held for every
request, including the 429-driven failures nobody planned for in C5.
