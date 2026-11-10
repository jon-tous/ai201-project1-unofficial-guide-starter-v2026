"""
Stage 5 of the pipeline: writing the answer.

This is the only part of your system that calls out to a service. Everything
else runs on your laptop.

Every outgoing call in this course goes through `generate()` below. That
matters for a practical reason: the free tier allows only a small number of
calls per minute, and a previous cohort ran into that wall hard. Rather than
asking three hundred students to each write their own pacing code, the pacing
lives here, once.

What this function does for you:

  • Paces requests so you stay under the per-minute limit, and tells you when
    it's waiting. A pause is the limiter doing its job, not a hang.
  • Caches repeated prompts while you're building, so re-running the same
    question twenty times while you debug costs one call.
  • Stops with a warning if a session goes through an unreasonable number of
    calls, instead of silently draining your whole day's allowance.
  • Retries when the service says you're going too fast.
  • Counts your calls, and the tokens they used, so what a run cost is a
    number you can see rather than one you estimate.

⚠️ Caching is ON while you build and OFF during evaluation. Your test week
needs three real answers to the same question, not one answer three times over.
`run_eval.py` passes cache=False for you.
"""

import contextvars
import hashlib
import json
import os
import sys
import time

import config

_call_times: list[float] = []
_session_calls = 0
_session_prompt_tokens = 0
_session_output_tokens = 0
_cache_hits = 0
_client = None
_budget_warned = False


class QuotaGuard(Exception):
    """Raised when a session blows through its request budget."""


# ─── Week 9: failure types the web layer can tell apart ─────────────────────


class ModelFailure(Exception):
    """Base class: the model call didn't produce an answer. `kind` names why."""

    kind = "model_error"

    def __init__(self, message: str, attempts: int = 0):
        super().__init__(message)
        self.attempts = attempts


class ModelTimeout(ModelFailure):
    """Every attempt timed out before the request deadline ran out."""

    kind = "model_timeout"


class ModelUnavailable(ModelFailure):
    """Every attempt hit a transient error (5xx or rate limit)."""

    kind = "model_unavailable"


class ModelEmptyResponse(ModelFailure):
    """The model answered, but with no text — every attempt."""

    kind = "model_empty"


class ModelError(ModelFailure):
    """A failure retrying won't fix: a bad key, a rejected request."""

    kind = "model_error"


# Per-request accounting and fault injection. serve.py calls begin_request() at
# the top of every /ask; these live in a ContextVar so two requests on two
# threads never see each other's numbers.
_request_stats: contextvars.ContextVar = contextvars.ContextVar("request_stats", default=None)
_request_fault: contextvars.ContextVar = contextvars.ContextVar("request_fault", default="")


def begin_request(fault: str = "") -> dict:
    """Start a fresh stats record for this request and return it.

    The dict is filled in by generate() as it runs: attempts made, whether the
    cache answered, tokens reported by the service, and why each retry happened.
    """
    stats = {
        "attempts": 0,
        "cache_hit": False,
        "prompt_tokens": 0,
        "output_tokens": 0,
        "retries": [],
    }
    _request_stats.set(stats)
    _request_fault.set((fault or config.FAULT) if config.ALLOW_FAULTS else "")
    return stats


def _stats() -> dict:
    stats = _request_stats.get()
    return stats if stats is not None else {"attempts": 0, "retries": [], "prompt_tokens": 0, "output_tokens": 0}


class _InjectedServerError(Exception):
    """Stands in for a Gemini 503 when a fault is injected."""


class _InjectedRateLimit(Exception):
    """Stands in for a Gemini 429 when a fault is injected."""


class _InjectedBadKey(Exception):
    """Stands in for a Gemini 400 API_KEY_INVALID when a fault is injected."""


def _inject_fault(attempt: int):
    """Raise (or sleep) the way the real failure would, if one was asked for.

    Returns "empty" when the empty-response fault applies, so the caller can
    skip the real call and act as though the model returned no text.
    """
    spec = _request_fault.get()
    if not spec:
        return None
    kind, _, count = spec.partition(":")
    if count and attempt >= int(count):
        return None  # e.g. server_error:1 — only the first attempt fails
    if kind == "timeout":
        time.sleep(config.MODEL_TIMEOUT_S)
        raise TimeoutError(f"injected: model call exceeded {config.MODEL_TIMEOUT_S:.0f}s")
    if kind == "server_error":
        raise _InjectedServerError("injected: 503 UNAVAILABLE")
    if kind == "rate_limit":
        raise _InjectedRateLimit("injected: 429 RESOURCE_EXHAUSTED")
    if kind == "bad_key":
        raise _InjectedBadKey("injected: 400 API_KEY_INVALID")
    if kind == "empty":
        return "empty"
    return None


def _classify(exc: Exception) -> str | None:
    """Which kind of transient failure this is, or None if retrying won't help."""
    if isinstance(exc, _EmptyText):
        return "empty"
    if isinstance(exc, _InjectedServerError):
        return "server"
    if isinstance(exc, _InjectedRateLimit):
        return "rate_limit"
    if isinstance(exc, _InjectedBadKey):
        return None

    try:
        import httpx

        if isinstance(exc, (httpx.TimeoutException,)):
            return "timeout"
        if isinstance(exc, (httpx.ConnectError, httpx.RemoteProtocolError)):
            return "server"
    except ImportError:
        pass
    if isinstance(exc, TimeoutError):
        return "timeout"

    try:
        from google.genai import errors

        if isinstance(exc, errors.ServerError):
            return "server"
        if isinstance(exc, errors.ClientError) and getattr(exc, "code", None) == 429:
            return "rate_limit"
    except ImportError:
        pass

    message = str(exc).lower()
    if "timed out" in message or "timeout" in message:
        return "timeout"
    if (
        "429" in message
        or "resource" in message and "exhaust" in message
        or "rate" in message and "limit" in message
    ):
        return "rate_limit"
    return None


class _EmptyText(Exception):
    """The model returned a response with no text in it."""


# ─── Cache ───────────────────────────────────────────────────────────────────


def _cache_key(prompt: str, system: str | None) -> str:
    blob = json.dumps([config.MODEL, system or "", prompt], sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _cache_read(key: str) -> str | None:
    path = config.CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    except Exception:
        return None


def _cache_write(key: str, response: str) -> None:
    config.CACHE_DIR.mkdir(exist_ok=True)
    path = config.CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps({"response": response}), encoding="utf-8")


def clear_cache() -> int:
    """Delete every cached response. Returns how many were removed."""
    if not config.CACHE_DIR.exists():
        return 0
    files = list(config.CACHE_DIR.glob("*.json"))
    for f in files:
        f.unlink()
    return len(files)


# ─── Pacing and guards ───────────────────────────────────────────────────────


def _wait_for_slot() -> None:
    """Sleep, if we've used up this minute's allowance."""
    now = time.monotonic()
    _call_times[:] = [t for t in _call_times if now - t < 60.0]

    if len(_call_times) < config.REQUESTS_PER_MINUTE:
        return

    sleep_for = 60.0 - (now - _call_times[0]) + 0.1
    if sleep_for > 0:
        print(
            f"  [rate limit] {config.REQUESTS_PER_MINUTE} requests used this "
            f"minute. Waiting {sleep_for:.0f}s. This is normal.",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(sleep_for)
        _call_times[:] = [t for t in _call_times if time.monotonic() - t < 60.0]


def _check_budget() -> None:
    global _budget_warned
    if _session_calls < config.SESSION_REQUEST_BUDGET:
        return
    if not _budget_warned:
        _budget_warned = True
    raise QuotaGuard(
        f"This session has made {_session_calls} requests, which is the "
        f"budget set in config.py (SESSION_REQUEST_BUDGET).\n"
        f"That usually means a loop is running away rather than that you've "
        f"done {_session_calls} requests' worth of real work.\n"
        f"Stop the program and look for the loop. If you really do need more, "
        f"raise the number in config.py — but look first."
    )


def _record_tokens(response) -> None:
    """Add one response's token counts to this session's running totals.

    These come off the response itself, which is the point. When you work out
    what a run costs, a number read back from the service is a measurement and
    a number multiplied out of the pricing page is a guess — they disagree more
    often than you'd think, and only one of them is evidence.

    Deliberately forgiving: `usage_metadata` is missing on some responses and
    half-filled on others, and a token count you didn't get is never a good
    enough reason to end someone's run.
    """
    global _session_prompt_tokens, _session_output_tokens

    try:
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return
        prompt_tokens = int(getattr(meta, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(meta, "candidates_token_count", 0) or 0)
        _session_prompt_tokens += prompt_tokens
        _session_output_tokens += output_tokens
        stats = _stats()
        stats["prompt_tokens"] += prompt_tokens
        stats["output_tokens"] += output_tokens
    except Exception:
        pass  # accounting never breaks the thing it is accounting for


def usage() -> str:
    """One line on what this session has spent. Printed by app.py on exit."""
    tokens = ""
    total = _session_prompt_tokens + _session_output_tokens
    if total:
        tokens = (
            f", {total} tokens "
            f"({_session_prompt_tokens} in, {_session_output_tokens} out)"
        )
    return (
        f"{_session_calls} model calls this session"
        f"{tokens}"
        f"{f', {_cache_hits} served from cache' if _cache_hits else ''}"
    )


def call_count() -> int:
    return _session_calls


def token_counts() -> dict[str, int]:
    """Tokens this session actually used, as reported by the service.

    Cache hits are not in here, because they never reached the service and so
    cost nothing. That is a real difference between a run and a cached rerun,
    and it is worth knowing which one you measured.
    """
    return {
        "prompt": _session_prompt_tokens,
        "output": _session_output_tokens,
        "total": _session_prompt_tokens + _session_output_tokens,
    }


# ─── The call ────────────────────────────────────────────────────────────────


def _get_client():
    global _client
    if _client is None:
        from google import genai

        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "No GEMINI_API_KEY found.\n"
                "Copy .env.example to .env and paste your key in, then try "
                "again. `python test.py` will confirm it's working."
            )
        # Week 9: without a timeout, a hung call hangs the whole request.
        _client = genai.Client(
            api_key=key,
            http_options={"timeout": int(config.MODEL_TIMEOUT_S * 1000)},
        )
    return _client


def generate(prompt: str, system: str | None = None, cache: bool = True) -> str:
    """
    Send a prompt and get text back.

    Args:
        prompt: what you're asking.
        system: an optional instruction about how to behave.
        cache:  reuse an identical earlier answer if there is one. Leave this
                True while building. Pass False when you're evaluating — three
                runs of the same question have to be three real answers.

    Every call in this course goes through here. If you need to change how the
    model is called, change it in this one place.
    """
    global _session_calls, _cache_hits

    stats = _stats()
    fault = _request_fault.get()
    # An injected fault has to reach the call path, so it skips the cache.
    use_cache = cache and config.CACHE_ENABLED and not fault
    key = _cache_key(prompt, system)

    if use_cache:
        hit = _cache_read(key)
        if hit is not None:
            _cache_hits += 1
            stats["cache_hit"] = True
            return hit

    _check_budget()

    # Week 9: retry on anything transient (timeouts, 5xx, 429, empty text), not
    # just rate limits — but only while another attempt could still finish
    # inside the request deadline. Past that, stop and say which failure it was.
    deadline = time.monotonic() + config.REQUEST_DEADLINE_S
    last_error: Exception | None = None
    last_kind = "server"
    for attempt in range(config.MAX_RETRIES):
        _wait_for_slot()
        stats["attempts"] += 1
        try:
            injected = _inject_fault(attempt)
            if injected == "empty":
                raise _EmptyText("injected: model returned no text")

            client = _get_client()
            _call_times.append(time.monotonic())
            _session_calls += 1

            kwargs = {"model": config.MODEL, "contents": prompt}
            if system:
                kwargs["config"] = {"system_instruction": system}

            response = client.models.generate_content(**kwargs)
            _record_tokens(response)
            try:
                text = (response.text or "").strip()
            except Exception:  # noqa: BLE001 — a blocked response can raise here
                text = ""
            if not text:
                raise _EmptyText("model returned a response with no text")

            if use_cache:
                _cache_write(key, text)
            return text

        except Exception as exc:  # noqa: BLE001 — classified below
            last_error = exc
            kind = _classify(exc)
            if kind is None:
                raise ModelError(
                    f"{type(exc).__name__}: {exc}", attempts=stats["attempts"]
                ) from exc
            last_kind = kind
            backoff = 2 ** attempt
            stats["retries"].append(kind)
            if time.monotonic() + backoff + config.MODEL_TIMEOUT_S > deadline:
                break  # another attempt couldn't finish in time
            if attempt + 1 < config.MAX_RETRIES:
                print(
                    f"  [{kind}] retrying in {backoff}s "
                    f"(attempt {attempt + 1} of {config.MAX_RETRIES}).",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(backoff)

    attempts = stats["attempts"]
    detail = f"{attempts} attempt(s); last error: {last_error}"
    if last_kind == "timeout":
        raise ModelTimeout(f"Model call timed out. {detail}", attempts=attempts)
    if last_kind == "empty":
        raise ModelEmptyResponse(f"Model returned no text. {detail}", attempts=attempts)
    raise ModelUnavailable(f"Model service unavailable. {detail}", attempts=attempts)


# ─── The grounded answer ─────────────────────────────────────────────────────

GROUNDING_INSTRUCTION = """You answer questions using only the documents provided to you.

Rules:
- Use only the information in the documents below. Do not use anything you know from elsewhere.
- If the documents don't cover the question, say you don't have enough information. Do not guess.
- Name the document your answer came from, using the filename given in each excerpt.
- Be brief. Two or three sentences is usually enough."""


def build_prompt(question: str, results) -> str:
    """
    Assemble the grounded prompt out of retrieved chunks.

    Split out from `answer_from_chunks` so the prompt can be looked at without
    being sent — `python app.py ask "..." --show-prompt` prints exactly what
    this returns. Reading it once is the fastest way to see that retrieval,
    not the model, decides what an answer can possibly be based on.
    """
    context = "\n\n".join(
        f"[from {r.source}]\n{r.text}" for r in results
    )
    return (
        f"Documents:\n\n{context}\n\n"
        f"---\n\nQuestion: {question}\n\n"
        f"Answer using only the documents above, and name the file you used."
    )


def answer_from_chunks(question: str, results, cache: bool = True) -> str:
    """
    Build a grounded prompt out of retrieved chunks and send it.

    This is the second layer of grounding. The relevance gate in gate.py is the
    first — it has already decided these chunks are close enough to be worth
    answering from.
    """
    prompt = build_prompt(question, results)
    return generate(prompt, system=GROUNDING_INSTRUCTION, cache=cache)
