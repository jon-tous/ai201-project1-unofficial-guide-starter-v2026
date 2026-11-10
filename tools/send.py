#!/usr/bin/env python3
"""
Send questions to a running /ask service and print what came back — Week 9.

The service writes the real record (logs/requests.jsonl); this just drives it.

    .venv/bin/python tools/send.py --set in --repeat 2          # 10 in-corpus questions
    .venv/bin/python tools/send.py --set out                    # 5 out-of-scope questions
    .venv/bin/python tools/send.py --set in --fault timeout     # needs AI201_ALLOW_FAULTS=1 on the server
    .venv/bin/python tools/send.py --raw '{"question": 123}'    # any body you like

Start the server first with `./run.sh` (port 5001). Run with AI201_CACHE=0 on the
server when measuring, so each request is a real model call.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from questions import OUT_OF_SCOPE, answered  # noqa: E402


def post(url, body: bytes, fault: str = "", timeout: float = 90):
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if fault:
        req.add_header("X-Fault", fault)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, text = resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode()
    except Exception as e:  # noqa: BLE001 — a dropped connection is a result too
        status, text = 0, f"{type(e).__name__}: {e}"
    return status, text, time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:5001/ask")
    ap.add_argument("--set", choices=["in", "out", "both"], default="in")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--fault", default="")
    ap.add_argument("--raw", help="send this exact body instead of the question set")
    args = ap.parse_args()

    if args.raw is not None:
        bodies = [args.raw.encode()] * args.repeat
    else:
        qs = []
        if args.set in ("in", "both"):
            qs += [q["question"] for q in answered()]
        if args.set in ("out", "both"):
            qs += OUT_OF_SCOPE
        bodies = [json.dumps({"question": q}).encode() for q in qs] * args.repeat

    for body in bodies:
        status, text, secs = post(args.url, body, args.fault)
        try:
            data = json.loads(text)
            summary = data.get("kind") or ("refused" if data.get("refused") else "answered")
            rid = data.get("request_id", "")
            is_json = True
        except json.JSONDecodeError:
            summary, rid, is_json = text[:60].replace("\n", " "), "", False
        print(f"{status:>3}  {secs:6.2f}s  json={'y' if is_json else 'N'}  {summary:<18} {rid}  {body[:60].decode(errors='replace')}")


if __name__ == "__main__":
    main()
