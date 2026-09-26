#!/usr/bin/env python3
"""
Mersenne Prime Hunter
=====================
Searches for Mersenne primes (primes of the form 2^p - 1, p prime) using the
Lucas-Lehmer primality test.

Runs are time-budgeted and checkpointed: when the budget expires the script
saves its progress (last exponent tested, primes found, cumulative stats) so
the next run resumes exactly where this one stopped. Designed to be run
nightly for ~6 hours by GitHub Actions (see .github/workflows/).

Usage:
    python mersenne_hunter.py --minutes 350

No third-party packages required; if gmpy2 is installed the Lucas-Lehmer
squarings run several times faster.
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

try:
    import gmpy2
    HAVE_GMPY2 = True
except ImportError:
    HAVE_GMPY2 = False

LOG10_2 = math.log10(2)


def now_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")


def exponent_is_prime(n: int) -> bool:
    """Primality of the exponent itself (deterministic for n < 3.3e24 without gmpy2)."""
    if n < 2:
        return False
    small = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    if HAVE_GMPY2:
        return bool(gmpy2.is_prime(n))
    for p in small:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for a in small:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def lucas_lehmer(p: int) -> bool:
    """True iff 2^p - 1 is prime. p must be prime."""
    if p == 2:
        return True
    if HAVE_GMPY2:
        M = (gmpy2.mpz(1) << p) - 1
        s = gmpy2.mpz(4)
        for _ in range(p - 2):
            s = (s * s - 2) % M
        return s == 0
    M = (1 << p) - 1
    s = 4
    for _ in range(p - 2):
        s = (s * s - 2) % M
    return s == 0


def digits_of_mersenne(p: int) -> int:
    """Number of decimal digits of 2^p - 1."""
    return int(math.floor(p * LOG10_2)) + 1


def format_value(p: int) -> str:
    """Full decimal value for small primes; head...tail for big ones."""
    M = (1 << p) - 1
    s = str(M)
    if len(s) <= 120:
        return s
    return s[:40] + "..." + s[-40:] + f" ({len(s)} digits)"


def load_checkpoint(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "last_exponent": 1,
        "exponents_tested": 0,
        "mersenne_primes": [],
        "total_runtime_seconds": 0.0,
        "runs_completed": 0,
        "run_log": [],
    }


def save_checkpoint(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def human_time(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s"


def write_results_md(path: str, state: dict) -> None:
    lines = [
        "# Mersenne Prime Hunt — Results",
        "",
        "Automated nightly search for Mersenne primes (2^p − 1, p prime) using the",
        "Lucas-Lehmer test. Runs 12:00 AM – 6:00 AM IST every day via GitHub Actions.",
        "",
        "## Cumulative stats",
        "",
        f"- Runs completed: **{state['runs_completed']}**",
        f"- Total search time: **{human_time(state['total_runtime_seconds'])}**",
        f"- Exponents tested: **{state['exponents_tested']}** (up to p = {state['last_exponent']})",
        f"- Mersenne primes found: **{len(state['mersenne_primes'])}**",
        "",
        "## Mersenne primes found",
        "",
        "| # | exponent p | digits of 2^p − 1 | discovered (IST) | value |",
        "|---|-----------|-------------------|------------------|-------|",
    ]
    for i, m in enumerate(state["mersenne_primes"], 1):
        lines.append(
            f"| {i} | {m['exponent']} | {m['digits']} | {m['found_at']} | `{m['value']}` |"
        )
    lines += [
        "",
        "## Run log (most recent first)",
        "",
        "| run | started (IST) | duration | exponents tested | new finds |",
        "|-----|---------------|----------|------------------|-----------|",
    ]
    for run in reversed(state["run_log"][-60:]):
        lines.append(
            f"| {run['run']} | {run['started_at']} | {human_time(run['duration_seconds'])} "
            f"| {run['exponents_tested']} | {run['new_finds']} |"
        )
    lines.append("")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Mersenne prime hunter (Lucas-Lehmer).")
    ap.add_argument("--minutes", type=float, default=350.0,
                    help="time budget in minutes (default: 350)")
    ap.add_argument("--data-dir", default=".", help="directory for checkpoint/results")
    ap.add_argument("--checkpoint-every", type=float, default=60.0,
                    help="checkpoint save interval in seconds (default: 60)")
    args = ap.parse_args()

    state_path = os.path.join(args.data_dir, "state", "checkpoint.json")
    results_path = os.path.join(args.data_dir, "RESULTS.md")

    state = load_checkpoint(state_path)
    run_number = state["runs_completed"] + 1
    started_at = now_ist()
    t0 = time.monotonic()
    budget = args.minutes * 60.0

    print(f"[hunt] run #{run_number} starting {started_at}", flush=True)
    print(f"[hunt] engine: {'gmpy2 (fast)' if HAVE_GMPY2 else 'pure python'} | "
          f"budget: {args.minutes:.0f} min | resuming after exponent {state['last_exponent']}",
          flush=True)

    p = state["last_exponent"] + 1
    tested_this_run = 0
    new_finds = 0
    last_save = t0
    next_heartbeat = t0 + 300.0

    while True:
        elapsed = time.monotonic() - t0
        if elapsed >= budget:
            break
        if exponent_is_prime(p):
            if lucas_lehmer(p):
                digits = digits_of_mersenne(p)
                entry = {
                    "exponent": p,
                    "digits": digits,
                    "found_at": now_ist(),
                    "value": format_value(p),
                }
                state["mersenne_primes"].append(entry)
                new_finds += 1
                print(f"[hunt] *** MERSENNE PRIME FOUND: 2^{p} - 1 "
                      f"({digits} digits) at {entry['found_at']} ***", flush=True)
            tested_this_run += 1
            state["exponents_tested"] += 1
        state["last_exponent"] = p
        p += 1

        now_mono = time.monotonic()
        if now_mono - last_save >= args.checkpoint_every:
            save_checkpoint(state_path, state)
            last_save = now_mono
        if now_mono >= next_heartbeat:
            print(f"[hunt] {now_ist()} | at exponent {p} | "
                  f"{tested_this_run} tested this run | {human_time(now_mono - t0)} elapsed",
                  flush=True)
            next_heartbeat = now_mono + 300.0

    duration = time.monotonic() - t0
    state["total_runtime_seconds"] += duration
    state["runs_completed"] = run_number
    state["run_log"].append({
        "run": run_number,
        "started_at": started_at,
        "duration_seconds": round(duration, 1),
        "exponents_tested": tested_this_run,
        "new_finds": new_finds,
    })
    save_checkpoint(state_path, state)
    write_results_md(results_path, state)

    print(f"[hunt] run #{run_number} finished after {human_time(duration)}: "
          f"{tested_this_run} exponents tested, {new_finds} new Mersenne prime(s). "
          f"Last exponent: {state['last_exponent']}.", flush=True)
    print(f"[hunt] checkpoint -> {state_path}", flush=True)
    print(f"[hunt] results   -> {results_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
