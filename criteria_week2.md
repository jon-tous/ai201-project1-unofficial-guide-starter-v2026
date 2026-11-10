# Acceptance criteria — The Unofficial Guide

Five criteria that say what "working" means for this system, written in week 1
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"Retrieval works"* is an opinion. *"For at
least 4 of my 5 test questions, the top results include a chunk containing the
answer"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter or looser one. A reason that says something about your corpus or your
pipeline earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next week costs you nothing. Setting a target so
> easy you can't miss it does.

---

## 1. Retrieved chunks contain the answer

For at least 4 of my 5 test questions, the retrieved chunks include one that
contains the answer.

**Why this target:** The housing lottery question's answer sentence
("juniors and seniors are ordered by accumulated credit hours") sits right
after a sentence about random tie-breaks — I expect that one to be the
occasional miss, since a similarity search could easily surface the sentence
about randomness instead. My other four questions each sit alone as the main
point of a short, single-topic document, so I expect those to retrieve
cleanly. 4 of 5 gives room for exactly the one I predict will be shaky.

---

## 2. Every answer names a source

Every answer the system produces names at least one source document.

**Why this target:** generate.py already labels every retrieved chunk with
`[from filename]` in the prompt and its system instruction tells the model
outright to name the file it used. Naming a source is instruction-following,
not retrieval luck — the filename is sitting right there in the context — so
I'm holding this to 5 of 5 rather than 4. If this one comes in below 5, that's
a sign the model is ignoring the instruction, not that retrieval had a bad
day.

---

## 3. The relevance gate stops out-of-corpus questions

When I ask a question my documents clearly don't cover, the relevance gate
stops it and the system returns "I don't have enough information about that" —
in at least 4 of 5 tries.

<!-- The five questions are the ones in `OUT_OF_SCOPE` at the bottom of
     `questions.py`, and `run_eval.py` puts them through the gate and writes
     what happened into your run log. Swap them for your own if you'd rather —
     just keep five of them, or the "4 of 5" above has nothing to be 4 of. -->

**Why this target:** I haven't measured my actual distance distribution yet —
that's Milestone 4 — so this is a guess, not a measurement. None of my five
out-of-scope questions (Mongolia's capital, diesel oil changes, the 1994 World
Cup, ibuprofen dosage, a Rust for-loop) share real vocabulary with dining
halls, courses, or housing, so I'd expect the gate to catch all five. I'm
leaving one slot of slack because I don't yet know how the embedding model
handles a generic-sounding question, and this is the criterion I most expect
to revise once I've looked at real distances.

---

## 4. No chunk is shorter than 80 characters

Every document in `campus_life` is between 183 and 554 characters — well
under the 800-character `CHUNK_SIZE` — so the fixed-size fallback never
splits anything; the real risk is in what I replace it with. If I split on
paragraph breaks instead of raw length, some documents fall apart into
fragments that lose their subject: `course_econ_101.txt`'s second paragraph is
just "Expect 4 hours a week outside class." (42 characters), with no mention
of Econ 101 anywhere in it.

**Why this target:** 80 characters comfortably fits a real, self-contained
fact — my printing-quota answer sentence alone is 92 characters — while still
catching a bare, subject-less fragment like the one above. It's a floor meant
to catch a specific failure mode I already found by reading the corpus, not a
number picked in the abstract.

---

## 5. The named source actually backs the answer

For at least 4 of my 5 test questions, the source document named in the
answer is one that actually contains the `expects` phrase — not just a
plausible-looking file from the same topic.

**Why this target:** `campus_life` has topic clusters where the same fact
repeats across files — `course_cs_210.txt` and `course_cs_210_workload.txt`
both state the "8 to 10 hours" figure, and every dining hall has a
`_followup` file that echoes its parent — so naming *a* source (criterion 2)
is easy, but naming the one that actually backs the specific fact used is the
real test. I'm holding this to 4 of 5, the same margin as criterion 1 and for
the same reason: my CS 210 question is the one built with an honest
near-duplicate, so I'd forgive a mix-up between those two files without
calling attribution broken — I would not forgive it naming the exams file,
which never mentions hours at all.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     WEEK 2 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 1. Retrieved chunks contain the answer

         For at least 4 of my 5 test questions, the retrieved chunks include
         one that contains the answer.

         **Why this target:** ...

         > **Revised in week 2:** For at least 4 of 5 questions, the top three
         > results contain the answer.
         >
         > **Why revised:** I couldn't judge "the chunks include one that
         > contains the answer" the same way twice — I scored two questions
         > differently on Monday than on Wednesday. The new version is
         > something I can actually check.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said 4 of 5 but got 2 of 5, so 2 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.

     The whole reason the originals stay visible is so someone can see what you
     said before you knew the answer.
     ───────────────────────────────────────────────────────────────────────── -->
