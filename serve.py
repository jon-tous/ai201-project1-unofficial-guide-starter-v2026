#!/usr/bin/env python3
"""
The Unofficial Guide — the same pipeline, over HTTP.

    python serve.py                          run it locally on port 5000
    gunicorn serve:app                       run it the way a host runs it

Nothing new happens in this file. It is a wrapper: a request comes in, it
hands the question to `app.py::ask_pipeline` — the exact function the command
line uses — and hands the answer back as JSON. Retrieval, the relevance gate
and the grounded prompt all still live where they lived. If you change how
your system answers, you change it in those files and this one follows.

Two routes:

    POST /ask       {"question": "..."} in, the answer and its sources out
    GET  /health    is the service up, and is there an index to search

Why this exists: `app.py` runs once and exits, which is fine on your laptop
and impossible to deploy. A hosted service has to stay up and wait for
requests. This is the smallest thing that does that.

Week 9 capstone (Shape B — harden against failure): /ask now
  • validates the body (JSON object, `question` a non-empty string ≤ 500 chars)
  • answers 503 with a JSON message when there's no index to search
  • maps every model failure (timeout, 5xx, rate limit, empty text, bad key)
    to a JSON error with its own status code instead of a raw traceback
  • writes one structured log record per request — success or failure —
    to logs/requests.jsonl (see requestlog.py)
"""

import os
import time
import uuid

from flask import Flask, jsonify, request

import config
import requestlog

app = Flask(__name__)

# What the caller sees for each failure. Plain language, no exception text:
# the details go in the log, where the person running the service reads them.
_FAILURES = {
    "bad_input": 400,
    "no_index": 503,
    "model_timeout": 504,
    "model_unavailable": 503,
    "model_empty": 502,
    "model_error": 502,
    "internal_error": 500,
}
_MESSAGES = {
    "no_index": "The search index isn't built yet. Run `python app.py index` and try again.",
    "model_timeout": "The answer service took too long to respond. Please try again in a moment.",
    "model_unavailable": "The answer service is temporarily unavailable. Please try again in a moment.",
    "model_empty": "The answer service returned an empty response. Please try rephrasing your question.",
    "model_error": "The answer service rejected the request. The operator has been notified in the log.",
    "internal_error": "Something went wrong on our side. The operator has been notified in the log.",
}


@app.get("/health")
def health():
    """Is the service up, and is there an index to search?

    Two different questions, and the second one is the one that bites. A
    freshly deployed service answers this route happily while every /ask
    returns "no index" — hosts give you no disk that survives a restart, so
    the index has to be built as part of getting the service up. Checking
    here means you find that out in one request instead of five.
    """
    from store import index_exists

    ready = index_exists(config.CORPUS)
    return jsonify(
        {
            "status": "ok",
            "corpus": config.CORPUS,
            "index_ready": ready,
            "detail": (
                "ready"
                if ready
                else "no index for this corpus — run `python app.py index`"
            ),
        }
    )


def _validate(payload):
    """Return (question, None) or (None, reason) — never raises."""
    if not isinstance(payload, dict):
        return None, 'Send a JSON object, like {"question": "is the housing lottery random?"}'
    question = payload.get("question")
    if question is None:
        return None, 'Missing "question". Send JSON like {"question": "is the housing lottery random?"}'
    if not isinstance(question, str):
        return None, f'"question" must be a string, not {type(question).__name__}.'
    question = question.strip()
    if not question:
        return None, '"question" is empty. Ask something, like "is the housing lottery random?"'
    if len(question) > config.MAX_QUESTION_CHARS:
        return None, (
            f'"question" is {len(question)} characters; the limit is '
            f"{config.MAX_QUESTION_CHARS}. Ask one specific thing."
        )
    return question, None


@app.post("/ask")
def ask():
    """One question in, one grounded answer — or one clear error — out.

    A refused question is a 200, not an error. The gate refusing is your
    system working — it is an answer, and the JSON says so with
    `"refused": true` so whatever calls this can tell the two apart.
    """
    t0 = time.perf_counter()  # first line: the timer covers everything below

    import generate
    from app import ask_pipeline
    from store import index_exists

    request_id = uuid.uuid4().hex[:12]
    fault = request.headers.get("X-Fault", "") if config.ALLOW_FAULTS else ""
    stats = generate.begin_request(fault)
    marks = {}

    raw = request.get_json(silent=True)
    record = {
        "request_id": request_id,
        "question": raw.get("question") if isinstance(raw, dict) else raw,
        "fault": fault or config.FAULT or None,
    }

    def finish(status, outcome, body, error=None):
        latency_ms = round((time.perf_counter() - t0) * 1000)
        record.update(
            {
                "status": status,
                "outcome": outcome,
                "latency_ms": latency_ms,
                "retrieval_ms": marks.get("retrieval_ms"),
                "model_ms": (
                    round((time.perf_counter() - marks["prompt_at"]) * 1000)
                    if "prompt_at" in marks
                    else None
                ),
                "attempts": stats["attempts"],
                "retries": stats["retries"] or None,
                "cache_hit": stats["cache_hit"],
                "prompt_tokens": stats["prompt_tokens"],
                "output_tokens": stats["output_tokens"],
                "error": error,
            }
        )
        requestlog.write(record)
        body = {**body, "request_id": request_id}
        resp = jsonify(body)
        resp.status_code = status
        resp.headers["X-Request-ID"] = request_id
        return resp

    def fail(outcome, error=None, message=None):
        return finish(
            _FAILURES[outcome],
            outcome,
            {"error": message or _MESSAGES[outcome], "kind": outcome},
            error=error,
        )

    question, problem = _validate(raw)
    if problem:
        return fail("bad_input", error=problem, message=problem)
    record["question"] = question

    if not index_exists(config.CORPUS):
        return fail("no_index", error=f"no index for corpus {config.CORPUS}")

    def on_gate(_decision):
        marks["retrieval_ms"] = round((time.perf_counter() - t0) * 1000)

    def on_prompt(_prompt):
        marks["prompt_at"] = time.perf_counter()

    try:
        outcome = ask_pipeline(
            question, corpus=config.CORPUS, on_gate=on_gate, on_prompt=on_prompt
        )
    except generate.ModelFailure as exc:
        return fail(exc.kind, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — logged, not shown
        return fail("internal_error", error=f"{type(exc).__name__}: {exc}")

    record.update(
        {
            "answer": outcome["answer"],
            "refused": outcome["refused"],
            "best_distance": round(outcome["best_distance"], 4),
            "sources": outcome["sources"],
        }
    )
    return finish(
        200,
        "refused" if outcome["refused"] else "answered",
        {
            "question": question,
            "answer": outcome["answer"],
            "refused": outcome["refused"],
            "sources": outcome["sources"],
            "best_distance": round(outcome["best_distance"], 4),
            "threshold": outcome["threshold"],
            "corpus": config.CORPUS,
        },
    )


@app.errorhandler(Exception)
def _unhandled(exc):
    """Last line of defence: anything that escapes a route still comes back as
    JSON and still leaves a log record, instead of Flask's HTML error page."""
    from werkzeug.exceptions import HTTPException

    status = exc.code if isinstance(exc, HTTPException) else 500
    requestlog.write(
        {
            "route": request.path,
            "status": status,
            "outcome": "http_error" if status < 500 else "internal_error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    )
    message = exc.description if isinstance(exc, HTTPException) else _MESSAGES["internal_error"]
    return jsonify({"error": message}), status


def _warm_up():
    """Load the pipeline's heavy imports (chromadb, the embedder) at startup,
    so the first person to ask isn't the one who pays for them."""
    import app as _app  # noqa: F401
    import generate as _generate  # noqa: F401
    from store import search

    try:
        search("warm up", top_k=1, corpus=config.CORPUS)
    except Exception as exc:  # noqa: BLE001 — /health and /ask report this properly
        print(f"  [warm-up] skipped: {type(exc).__name__}: {exc}")


_warm_up()


def main():
    # Hosts tell you which port to listen on through PORT, and they expect you
    # on 0.0.0.0. Binding 127.0.0.1 instead works perfectly on your laptop and
    # then answers nothing at all once deployed, because the host's router
    # can't reach a socket that only accepts connections from inside the
    # container. It is the single most common way a first deploy "succeeds"
    # and is unreachable.
    port = int(os.getenv("PORT", "5000"))

    # Debug mode reloads on save, which is handy, and prints a console that
    # runs arbitrary code, which is not something to leave switched on where
    # strangers can reach it. Off unless you ask for it.
    debug = os.getenv("AI201_DEBUG", "0") == "1"

    print(f"Serving The Unofficial Guide on http://localhost:{port}")
    print(f"Corpus: {config.CORPUS}    (Ctrl-C to stop)\n")
    print("Try it from another terminal:\n")
    print(f"  curl http://localhost:{port}/health")
    print(
        f"  curl -X POST http://localhost:{port}/ask \\\n"
        f"    -H 'Content-Type: application/json' \\\n"
        f"    -d '{{\"question\": \"is the housing lottery random?\"}}'\n"
    )

    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    main()
