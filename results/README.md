# results/

Experiment outputs, one subfolder per run, plus the LLM-call cache.

- `<cond>_<model>_<YYYYMMDD-HHMMSS>/` written by `scripts/run_condition.py`:
  `manifest.json` (condition, model, prompt template + SHA-256, temperature, seed, git commit, token
  totals, cost), `predictions.jsonl` (one validated record per row: label, evidence, confidence,
  citation_valid, raw), `errors.jsonl` (rows whose output failed to parse or validate), and after
  `scripts/evaluate.py`: `metrics.json`, `metrics.md`. Model name `keyword` is condition 0; `mock` runs
  used a fixed canned record and must never be reported.
- `cache/<2 hex>/<sha256>.json`: every LLM response keyed by (model, messages, temperature, seed,
  max_tokens, json_mode). Re-running a condition with the same settings costs nothing and reproduces
  the same outputs; delete a file (or pass `--no-cache`) to force a fresh call.
