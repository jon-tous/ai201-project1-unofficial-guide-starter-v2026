"""
Settings for The Unofficial Guide.

Everything you're likely to change lives here, at the top, on purpose.
You'll edit THRESHOLD in Milestone 4 and the chunking numbers in Milestone 3.

Anything you set in your .env file wins over the defaults here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


# ─── The corpus you're working with ──────────────────────────────────────────
# Change this to switch corpora, or pass --corpus on the command line.
# Options are the folder names inside corpora/. See corpora/README.md.

CORPUS = os.getenv("AI201_CORPUS", "campus_life")


# ─── Chunking (Milestone 3) ──────────────────────────────────────────────────
# campus_life's longest document is 554 characters. 600 is a ceiling just
# above that — every real post fits in one paragraph-group and stays one
# chunk, but a document that ran longer would still get split, at a
# paragraph break, instead of silently growing one giant chunk. See
# chunker.py::split_documents.
CHUNK_SIZE = 600        # characters per chunk

# Only used by chunker.py::fallback_split now. The paragraph-aware splitter
# never cuts mid-sentence, so it has nothing for character overlap to patch
# over.
CHUNK_OVERLAP = 120     # characters shared between neighbouring chunks


# ─── Retrieval (Milestone 4) ─────────────────────────────────────────────────

TOP_K = 5               # how many chunks to pull back per question

# The relevance gate. If the best chunk is further away than this, the system
# refuses to answer instead of handing the model thin material.
#
# LOWER IS BETTER: 0.3 is a close match, 0.9 is unrelated.
#
# Retuned in Milestone 4's diagnosis pass: the original 0.5 was picked
# against OUT_OF_SCOPE trivia (0.825-0.934) that shared no vocabulary with
# the corpus, so it never tested a real near-miss. Swapping in topically
# -adjacent out-of-scope questions (0.598-0.714) narrowed the real gap to
# my 5 test questions' 0.214-0.295. 0.45 is the highest threshold that still
# keeps >= 0.1 clear of both sides of that narrower gap. See README.md
# "The Improvement" for the full before/after numbers.
THRESHOLD = 0.45


# ─── Models ──────────────────────────────────────────────────────────────────
# Embeddings run on your own machine and cost no API quota.
# Only generation calls out to a service.

# This is the model Chroma bundles, and leaving it alone is the fast path: it
# downloads about 80 MB from Chroma's own CDN and needs nothing else installed.
#
# Setting it to any other name — week 2's "try a second embedding model"
# stretch option — switches to loading that model from Hugging Face instead,
# which needs `pip install 'sentence-transformers>=3.4,<3.5'` first. store.py
# says so with a real error message rather than a stack trace if you forget.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MODEL = os.getenv("AI201_MODEL", "gemini-3.5-flash-lite")


# ─── Rate limiting and quota guards ──────────────────────────────────────────
# You should not need to touch these. They exist so that a runaway loop costs
# you a warning instead of your whole day's allowance.

REQUESTS_PER_MINUTE = 30       # outgoing calls the limiter will allow per minute
SESSION_REQUEST_BUDGET = 300   # stop and warn rather than draining the daily quota
MAX_RETRIES = 4                # on 429 / resource-exhausted, with backoff

CACHE_ENABLED = os.getenv("AI201_CACHE", "1") != "0"
CACHE_DIR = ROOT / ".cache"


# ─── Failure handling (Week 9 capstone, Shape B) ─────────────────────────────
# How long one model call may take before it's abandoned, and how long a whole
# /ask request may spend retrying before it gives up and says so. A retry is
# only started if it could still finish inside the request deadline.

# Gemini rejects any client deadline under 10 s ("Minimum allowed deadline is
# 10s"), so that is the floor — found by the Week 9 smoke test, logged as a 400.
MODEL_TIMEOUT_S = max(10.0, float(os.getenv("AI201_MODEL_TIMEOUT", "10")))
REQUEST_DEADLINE_S = float(os.getenv("AI201_REQUEST_DEADLINE", "30"))

# Longest question /ask accepts. The longest real question in my Week 2 set is
# under 120 characters; 500 leaves room for a wordy person, not for a pasted essay.
MAX_QUESTION_CHARS = 500

# Fault injection, for testing the bad path on purpose. Off unless
# AI201_ALLOW_FAULTS=1, in which case a request can ask for a fault with an
# `X-Fault` header, or AI201_FAULT sets one for every request.
#   timeout | server_error | rate_limit | empty | bad_key    — fail every attempt
#   server_error:1                                           — fail only the first attempt
ALLOW_FAULTS = os.getenv("AI201_ALLOW_FAULTS", "0") == "1"
FAULT = os.getenv("AI201_FAULT", "") if ALLOW_FAULTS else ""

# One JSON object per line, one line per /ask request.
LOG_DIR = ROOT / "logs"
REQUEST_LOG = Path(os.getenv("AI201_REQUEST_LOG", str(LOG_DIR / "requests.jsonl")))


# ─── Paths ───────────────────────────────────────────────────────────────────

CORPORA_DIR = ROOT / "corpora"
CHROMA_DIR = ROOT / "chroma_db"
RESULTS_DIR = ROOT / "results"


def corpus_path(name: str | None = None) -> Path:
    """Folder holding the documents for a corpus."""
    return CORPORA_DIR / (name or CORPUS) / "documents"


def collection_name(name: str | None = None, variant: str = "default") -> str:
    """
    Name of the vector-store collection for a corpus.

    `variant` lets you index the same corpus two different ways and query both
    without deleting anything — you'll want that in week 2 when you compare
    chunking strategies.

    Chroma is fussy about collection names: 3 to 63 characters, starting and
    ending with a letter or digit, and nothing but letters, digits, underscores
    and hyphens in between. If you bring your own corpus and name the folder
    something Chroma won't accept, this cleans it up rather than failing.
    """
    import re

    raw = f"{name or CORPUS}__{variant}"
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", raw)
    cleaned = cleaned.strip("_-")          # must start and end alphanumeric
    if not cleaned or not cleaned[0].isalnum():
        cleaned = f"c{cleaned}"
    if not cleaned[-1].isalnum():
        cleaned = f"{cleaned}0"
    return cleaned[:63].rstrip("_-") or "collection"
