# The Unofficial Guide

<!-- Replace this line with your name and which corpus you picked. -->

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

<!-- ── Stretch features ─────────────────────────────────────────────────────
     Doing one? Say so here BEFORE you start. A feature this README never
     claims earns nothing.
     ───────────────────────────────────────────────────────────────────────── -->

---

# Week 2

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

<!-- For each miss: which stage caused it, and how. The stage alone isn't
     enough — you need the mechanism.

     Not a diagnosis: "Question 3 didn't work."
     A diagnosis:     "Question 3 asks about laundry costs. The answer is in
                       one sentence that got split across two chunks, so
                       neither chunk on its own contains it."

     The five stages: loading → chunking → embedding → retrieval → generation.

     Look for a pattern. If three misses all ask about numbers, that's one
     problem, not three.

     Missed nothing? Say so, then say honestly whether your targets were set
     low, and which one you'd tighten and to what.

     Milestone 3. -->

## The Improvement

**What I changed:**

**Why I picked it:**

<!-- Connect it to a specific diagnosis above in one sentence. If you can't,
     you picked a fix because it sounded impressive. -->

### Run Log — After

<!-- Same format, same five criteria, three runs each.
     `python run_eval.py --label after` -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 |  |  |  |  |
| 2. Every answer names a source | 5 of 5 |  |  |  |  |
| 3. Gate stops out-of-corpus questions | 4 of 5 |  |  |  |  |
| 4. | | | | | |
| 5. | | | | | |

**Did it help?**

<!-- Say plainly whether it did, and how you know. If it made things worse,
     say that — a change that backfired, honestly reported, earns full credit
     and is more interesting than one that worked. What matters is that you can
     tell.

     Milestone 4. -->

## What's Still Broken

<!-- For each criterion still missed after your fix: what you'd do about it,
     and why you stopped where you did.

     "I ran out of time" is fine if it's true. Pretending nothing is left is
     not.

     Milestone 5. -->

## What I'd Do Differently

<!-- Knowing what you know now — which of your five criteria would you write
     differently, and why?

     Milestone 5. -->
