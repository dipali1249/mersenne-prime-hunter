# Mersenne Prime Hunter

An automated, continuous search for **Mersenne primes** — primes of the form
$$2^p - 1$$ (where p itself is prime) — that runs **every night from 12:00 AM
to 6:00 AM IST** on GitHub Actions and commits its results back to this repo.

## How it works

- `mersenne_hunter.py` tests candidate exponents p in increasing order using
  the **Lucas-Lehmer primality test** (the standard test for Mersenne primes,
  the same algorithm GIMPS uses — just without their heavily optimised FFT code).
- Exponents are pre-filtered with a primality check, so only prime p reach the
  Lucas-Lehmer stage.
- Each nightly run has a ~6-hour time budget. When time is up, progress is
  saved to `state/checkpoint.json`, so the next night's run **resumes exactly
  where the previous one stopped** — a continuous search across days.
- Every find is recorded in `RESULTS.md` (exponent, digit count, discovery
  timestamp, and the value — full for small primes, head/tail for huge ones).
- The GitHub Actions workflow (`.github/workflows/nightly-hunt.yml`) is
  scheduled at **18:30 UTC = 12:00 AM IST**, runs the hunt, then commits the
  updated checkpoint and results with the "mersenne-bot" identity.

## Reading the results

- `RESULTS.md` — human-readable report: cumulative stats, all primes found,
  and a per-run log.
- `state/checkpoint.json` — machine-readable state (last exponent tested,
  primes found, total runtime).

## Running locally

```bash
pip install gmpy2          # optional but several times faster
python mersenne_hunter.py --minutes 30   # hunt for 30 minutes
```

Useful flags: `--minutes` (time budget), `--data-dir` (where state is stored),
`--checkpoint-every` (seconds between checkpoint saves).

## Notes

- Keep the repo **public**: Actions minutes are free for public repositories.
  A private repo would burn ~10,800 Actions minutes/month against the free
  quota.
- GitHub cancels scheduled workflows on repos with 60 days of no activity —
  the bot's own nightly commits keep this repo active, so the hunt keeps
  running.
- GitHub's cron scheduler can start jobs a few minutes late; the 5h50m
  compute budget inside a 6h job timeout keeps each run safely inside its
  window.
- To be realistic: all Mersenne primes below ~p = 136,279,841 (the current
  record, found by GIMPS in 2024) are already known, and this script will
  re-discover the known ones first. That is by design — it is a genuine,
  continuous Lucas-Lehmer search that will keep climbing the exponent range
  night after night. Finding a *new* record prime would need GIMPS-scale
  distributed FFT code.
