#!/usr/bin/env python3
"""
Run one trial of all five capstone criteria (criteria.md) — Week 9.

    .venv/bin/python tools/trials.py --trial 1                 # before the fix
    .venv/bin/python tools/trials.py --trial 1 --label after   # after the fix

Each trial is self-contained: it starts a fresh server with
`AI201_CACHE=0 AI201_ALLOW_FAULTS=1 ./run.sh`, waits for /health, runs the
criteria, stops the server, prints one line per criterion, and saves every raw
response to results/capstone/<label>_trial<N>.json.

Order inside a trial: C5 (warm normal path) → C1 + C4 (one mixed batch of 20,
C4 is scored from its 10 bad-path responses) → 60 s pause → C2 → C3.

The 60 s pause is there because the system's own limiter allows 30 real model
calls per minute (config.REQUESTS_PER_MINUTE) and C5 + C1 make ~26 of them. Without
it, C2's 6-second target would be measuring the limiter's wait, not the retry logic.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from questions import OUT_OF_SCOPE, answered  # noqa: E402

PORT = int(os.getenv("TRIAL_PORT", "5001"))
BASE = f"http://127.0.0.1:{PORT}"
IN_CORPUS = [q["question"] for q in answered()]

MALFORMED = [
    ("non_string", json.dumps({"question": 123})),
    ("empty_string", json.dumps({"question": ""})),
    ("too_long_600", json.dumps({"question": "a" * 600})),
    ("json_array", json.dumps(["is the housing lottery random?"])),
    ("non_json", "is the housing lottery random?"),
]
FAULTS = ["timeout", "server_error", "rate_limit", "empty", "bad_key"]
FAULT_STATUS = {"timeout": 504, "server_error": 503, "rate_limit": 503, "empty": 502, "bad_key": 502}
FORBIDDEN = ["traceback", "exception", "google", "genai", "api_key", "injected"]


# ─── HTTP ────────────────────────────────────────────────────────────────────


def post(body: str, fault: str = "", timeout: float = 120) -> dict:
    req = urllib.request.Request(f"{BASE}/ask", data=body.encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if fault:
        req.add_header("X-Fault", fault)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, text, rid = resp.status, resp.read().decode(), resp.headers.get("X-Request-ID")
    except urllib.error.HTTPError as e:
        status, text, rid = e.code, e.read().decode(), e.headers.get("X-Request-ID")
    except Exception as e:  # noqa: BLE001 — a dropped connection is a result
        status, text, rid = 0, f"{type(e).__name__}: {e}", None
    secs = round(time.perf_counter() - t0, 3)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    return {"status": status, "secs": secs, "request_id": rid, "json": data, "text": text[:500]}


def q(question: str) -> str:
    return json.dumps({"question": question})


def log_records() -> list[dict]:
    if not config.REQUEST_LOG.exists():
        return []
    rows = []
    for line in config.REQUEST_LOG.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


# ─── Server lifecycle ────────────────────────────────────────────────────────


def start_server(out_path: Path):
    env = {**os.environ, "AI201_CACHE": "0", "AI201_ALLOW_FAULTS": "1", "PORT": str(PORT)}
    out = open(out_path, "w")
    proc = subprocess.Popen(
        ["./run.sh"], cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT, start_new_session=True
    )
    for _ in range(120):
        try:
            urllib.request.urlopen(f"{BASE}/health", timeout=2)
            return proc
        except Exception:  # noqa: BLE001
            time.sleep(1)
    stop_server(proc)
    raise SystemExit(f"Server didn't come up on {BASE} — see {out_path}")


def stop_server(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=15)
    except Exception:  # noqa: BLE001
        pass


# ─── Criteria ────────────────────────────────────────────────────────────────


def c5_normal_path():
    post(q(IN_CORPUS[0]))  # discarded warm-up
    rows = [dict(post(q(question)), question=question) for question in IN_CORPUS * 4]
    ok = [r for r in rows if r["status"] == 200 and r["json"] and r["json"].get("refused") is False]
    fast = [r for r in rows if r["secs"] < 2.0]
    met = len(ok) == 20 and len(fast) >= 18
    return {
        "score": f"{len(ok)}/20 answered, {len(fast)}/20 <2.0s",
        "met": met,
        "max_secs": max(r["secs"] for r in rows),
        "rows": rows,
    }


def c1_batch():
    batch = [("in_corpus", question, "", q(question)) for question in IN_CORPUS]
    batch += [("out_of_scope", question, "", q(question)) for question in OUT_OF_SCOPE]
    batch += [("malformed", name, "", body) for name, body in MALFORMED]
    batch += [("fault", fault, fault, q(IN_CORPUS[4])) for fault in FAULTS]
    rows = []
    for kind, name, fault, body in batch:
        rows.append(dict(post(body, fault=fault), kind=kind, name=name))
    return rows


def c1_score(rows):
    records = log_records()
    by_id = {}
    for rec in records:
        if rec.get("request_id"):
            by_id.setdefault(rec["request_id"], []).append(rec)
    passed = 0
    for r in rows:
        recs = by_id.get(r["request_id"] or "", [])
        r["c1_log_count"] = len(recs)
        r["c1_log_status"] = recs[0].get("status") if recs else None
        r["c1_pass"] = len(recs) == 1 and recs[0].get("status") == r["status"]
        passed += r["c1_pass"]
    return {"score": f"{passed}/20", "met": passed == 20}


def c4_score(rows):
    bad = [r for r in rows if r["kind"] in ("malformed", "fault")]
    passed = 0
    for r in bad:
        expected = 400 if r["kind"] == "malformed" else FAULT_STATUS[r["name"]]
        data = r["json"]
        shape = isinstance(data, dict) and set(data) == {"error", "kind", "request_id"}
        clean = shape and not any(w in str(data["error"]).lower() for w in FORBIDDEN)
        r["c4_expected_status"] = expected
        r["c4_pass"] = bool(r["status"] == expected and shape and clean)
        r["c4_why"] = (
            "ok" if r["c4_pass"]
            else f"status {r['status']}≠{expected}" if r["status"] != expected
            else "shape" if not shape
            else "leak"
        )
        passed += r["c4_pass"]
    return {"score": f"{passed}/10", "met": passed == 10}


def c2_recovery():
    rows = [dict(post(q(question), fault="server_error:2"), question=question) for question in IN_CORPUS]
    by_id = {rec.get("request_id"): rec for rec in log_records()}
    passed = 0
    for r in rows:
        rec = by_id.get(r["request_id"] or "", {})
        data = r["json"] or {}
        r["log_attempts"], r["log_retries"] = rec.get("attempts"), rec.get("retries")
        r["c2_pass"] = (
            r["status"] == 200
            and data.get("refused") is False
            and bool((data.get("answer") or "").strip())
            and r["secs"] < 6.0
            and rec.get("attempts") == 3
            and rec.get("retries") == ["server", "server"]
        )
        passed += r["c2_pass"]
    return {"score": f"{passed}/5", "met": passed == 5, "rows": rows}


def c3_concurrent_timeout():
    rows = [None] * 5

    def worker(i):
        rows[i] = post(q(IN_CORPUS[i]), fault="timeout", timeout=120)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    passed = 0
    for r in rows:
        r["c3_pass"] = r["status"] == 504 and isinstance(r["json"], dict) and r["secs"] < 30.0
        passed += r["c3_pass"]
    return {
        "score": f"{passed}/5",
        "met": passed == 5,
        "secs": sorted(r["secs"] for r in rows),
        "rows": rows,
    }


# ─── Main ────────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trial", type=int, required=True)
    ap.add_argument("--label", default="before")
    args = ap.parse_args()

    outdir = ROOT / "results" / "capstone"
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.label}_trial{args.trial}"

    proc = start_server(outdir / f"{stem}_server.log")
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    try:
        print(f"[{stem}] C5 normal path…", flush=True)
        c5 = c5_normal_path()
        print(f"[{stem}] C1/C4 mixed batch of 20…", flush=True)
        batch = c1_batch()
        time.sleep(0.5)  # let the last log line land
        c1, c4 = c1_score(batch), c4_score(batch)
        print(f"[{stem}] pausing 60s so the per-minute limiter window clears before C2…", flush=True)
        time.sleep(60)
        print(f"[{stem}] C2 recovery…", flush=True)
        c2 = c2_recovery()
        print(f"[{stem}] C3 5 concurrent timeouts…", flush=True)
        c3 = c3_concurrent_timeout()
    finally:
        stop_server(proc)

    results = {
        "label": args.label,
        "trial": args.trial,
        "started": started,
        "C1": {**c1, "rows": batch},
        "C2": c2,
        "C3": c3,
        "C4": {k: v for k, v in c4.items()},
        "C5": c5,
    }
    (outdir / f"{stem}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"\n{stem}  ({started})")
    for key, extra in [
        ("C1", ""),
        ("C2", f"  secs={[r['secs'] for r in c2['rows']]}"),
        ("C3", f"  secs={c3['secs']}"),
        ("C4", "  " + ", ".join(f"{r['name']}:{r['c4_why']}" for r in batch if r.get("c4_why") and r["c4_why"] != "ok")),
        ("C5", f"  max={c5['max_secs']}s"),
    ]:
        r = results[key]
        print(f"  {key}  {r['score']:<28} {'MET' if r['met'] else 'MISSED'}{extra}")
    print(f"\nRaw responses: {outdir / (stem + '.json')}")


if __name__ == "__main__":
    main()
