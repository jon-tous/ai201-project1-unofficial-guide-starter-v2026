# Capstone Acceptance Criteria — Week 9

System: The Unofficial Guide (`serve.py` `POST /ask`), hardened against failure (Shape B).
Written before any trial was run. Week 2's criteria are in [criteria_week2.md](criteria_week2.md).

Conventions for every criterion:

- Each criterion is tested in **three separate trials** against a server started with
  `AI201_CACHE=0 AI201_ALLOW_FAULTS=1 ./run.sh` (port 5001), restarted between trials.
- "Client-side" time is wall-clock from sending the request to receiving the full
  response, measured by the test driver (`tools/trials.py`), not the log's `latency_ms`.
- "In-corpus questions" are the five in `questions.py::QUESTIONS`; "out-of-scope
  questions" are the five in `questions.py::OUT_OF_SCOPE`.
- Faults are injected with the `X-Fault` header (see RUNNING.md).
- A target must hold in **all three** trials for the criterion to be MET.

---

## 1. Every request leaves exactly one log record

**Criterion:** Each trial sends the same mixed batch of 20 requests to `/ask` — the 5
in-corpus questions, the 5 out-of-scope questions, 5 malformed bodies (a non-string
`question`, an empty string, a 600-character question, a JSON array, non-JSON text), and
5 injected faults (one each of `timeout`, `server_error`, `rate_limit`, `empty`,
`bad_key`). For every response, its `request_id` appears in `logs/requests.jsonl`
**exactly once**, and that record's `status` equals the HTTP status the client received.

**Target:** 20 of 20 per trial. Any missing record, duplicate record, or status mismatch
is a miss.

**Why this target:** The log is the only way to diagnose this system after the fact, and
the requests most likely to go unlogged are the failures — exactly the ones I'd need to
find. A log that drops one request in twenty can't be trusted to tell me what happened,
so anything short of all of them is a miss, not a near-pass. The status check makes sure
the record describes what the caller actually got, not just that a line was written.

## 2. Recovery from a transient model outage

**Criterion:** Each of the 5 in-corpus questions, sent with `X-Fault: server_error:2`
(the first two model attempts fail with a 503), returns HTTP 200 with `refused: false`
and a non-empty answer within **6 seconds** client-side, and its log record shows
`attempts: 3` and `retries: ["server", "server"]`.

**Target:** 5 of 5 per trial.

**Why this target:** Two consecutive 503s is a realistic brief outage, and before this
unit a single one failed the request. Two failures, not one, so the test exercises more
than a single retry. Six seconds because the backoff schedule should cost 1 s + 2 s of
waiting plus about 1 s for the real call (~4 s) — the time limit keeps retries from
quietly slowing every request. Stricter (three 503s) adds another 4 s of backoff, which
I'd rather report as a known limit than design around. Caveat: this tests my retry logic
against a simulated 503, not Gemini's own outage behaviour.

## 3. Bounded latency when the model hangs, under concurrent load

**Criterion:** With every model attempt timing out (`X-Fault: timeout`), **5 requests
sent at the same time** each receive a 504 JSON response within **30 seconds** of being
sent, client-side.

**Target:** 5 of 5 per trial.

**Why this target:** An outage hits everyone who is asking at that moment, not one
person at a time, so testing a single request would only cover the easy case. 30 s is
about the longest a person waits on a chat answer before reloading. It's also half of
gunicorn's 60 s worker timeout: past that, a request gets killed with no response and no
log record, so it would break criterion 1 as well.

## 4. Every failure follows the error contract

**Criterion:** Each of the 10 bad-path inputs from criterion 1 (5 malformed bodies, 5
faults) returns:

- (a) valid JSON whose keys are exactly `error`, `kind`, `request_id`;
- (b) this status: malformed body → 400, `timeout` → 504, `server_error` → 503,
  `rate_limit` → 503, `empty` → 502, `bad_key` → 502;
- (c) an `error` string containing none of `Traceback`, `Exception`, `google`, `genai`,
  `API_KEY`, `injected` (case-insensitive).

**Target:** 10 of 10 per trial.

**Why this target:** A client program decides what to do from the status code — retry
on 503/504, fix the request on 400 — so a wrong code makes it retry something that will
never work, or give up on something that would have succeeded. Leaked internal text
exposes the provider and its error details to whoever is calling. This is an interface
rule, so every case must pass, not most.

## 5. Normal answers didn't slow down

**Criterion:** After one discarded warm-up request, the 5 in-corpus questions are each
sent 4 times in a row (20 requests, cache off). All 20 return HTTP 200 with
`refused: false`, and **at least 18 of 20** complete in under **2.0 seconds**
client-side.

**Target:** 20/20 answered, and ≥ 18/20 under 2.0 s, per trial.

**Why this target:** This checks that the hardening didn't break or slow the system it
wraps. On the normal path the only new code is input validation and one appended log
line, which should add only milliseconds, so any noticeable slowdown points to a bug.
2.0 s comes from the measured session before these criteria were written — 15 uncached
answers, max 1.92 s. Two of twenty allowed over covers Gemini's own variability without
ignoring a real slowdown.
