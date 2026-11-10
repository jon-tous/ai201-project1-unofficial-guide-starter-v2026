"""
Structured request log — Week 9 capstone.

One JSON object per line in logs/requests.jsonl, one line per /ask request,
written whether the request succeeded, was refused, or failed. A failure that
leaves no record is a failure nobody finds.

Read it back with:

    python requestlog.py               # last 15 records as a table
    python requestlog.py --summary     # counts by outcome, latency, tokens
    tail -n 5 logs/requests.jsonl      # the raw lines
"""

import json
import sys
import threading
from datetime import datetime, timezone

import config

_lock = threading.Lock()

# Long text is clipped in the log so one pasted essay can't bloat the file.
_CLIP = 300


def _clip(value):
    if isinstance(value, str) and len(value) > _CLIP:
        return value[:_CLIP] + f"… [+{len(value) - _CLIP} chars]"
    return value


def write(record: dict) -> None:
    """Append one record. Never raises: logging must not break the request."""
    try:
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **record}
        record = {k: _clip(v) for k, v in record.items()}
        line = json.dumps(record, ensure_ascii=False)
        config.REQUEST_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _lock, open(config.REQUEST_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as exc:  # noqa: BLE001
        print(f"  [requestlog] could not write log record: {exc}", file=sys.stderr)


def read(path=None) -> list[dict]:
    path = path or config.REQUEST_LOG
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _table(rows):
    print(f"{'ts':<24} {'status':>6} {'outcome':<18} {'ms':>7} {'att':>3} {'tok':>5}  question")
    for r in rows:
        tok = (r.get("prompt_tokens") or 0) + (r.get("output_tokens") or 0)
        q = str(r.get("question", ""))[:50]
        print(
            f"{r.get('ts','')[:23]:<24} {r.get('status',''):>6} {r.get('outcome',''):<18} "
            f"{r.get('latency_ms',''):>7} {r.get('attempts',''):>3} {tok:>5}  {q}"
        )


def _summary(rows):
    from collections import Counter
    from statistics import mean, median

    print(f"{len(rows)} records in {config.REQUEST_LOG}")
    for outcome, n in Counter(r.get("outcome") for r in rows).most_common():
        print(f"  {outcome:<20} {n}")
    answered = [r for r in rows if r.get("outcome") == "answered" and not r.get("cache_hit")]
    if answered:
        lat = [r["latency_ms"] for r in answered]
        tok_in = [r.get("prompt_tokens", 0) for r in answered]
        tok_out = [r.get("output_tokens", 0) for r in answered]
        print(f"\nAnswered, not cached (n={len(answered)}):")
        print(f"  latency ms   mean {mean(lat):.0f}  median {median(lat):.0f}  max {max(lat)}")
        print(f"  tokens in    mean {mean(tok_in):.0f}")
        print(f"  tokens out   mean {mean(tok_out):.0f}")


if __name__ == "__main__":
    rows = read()
    if "--summary" in sys.argv:
        _summary(rows)
    else:
        _table(rows[-15:])
