"""Condition 4b: compute-matched self-consistency on condition 3's prompt.

Specification: docs/CRITIC_SPEC.md, section 7. Condition 3's exact messages are sampled N
times at temperature 0.7 with seeds ``seed``, ``seed + 1``, ...; every sample goes through
condition 3's own call / validate / repair code. Then:

  * the label is the plurality vote over the valid samples;
  * a tie goes to the label with the higher mean confidence, and if that is tied too, to
    the label whose first sample came earliest;
  * evidence and confidence are those of the highest-confidence sample that voted for the
    winning label (the earliest such sample on a tie).

A sample that is still invalid after the repair round-trip is dropped from the vote; its
tokens still count. A row with no valid sample is an error.

N is not a free parameter. It is derived from a named condition 4 run:

    N = max(3, ceil(T4 / T3))

T4 is that run's mean total tokens per row, T3 the mean tokens of one condition 3 call on
the same rows (the first attempt of that run's first pass, which is a condition 3 call).
Rounding up, and the floor of 3, can give 4b more tokens than condition 4; that favours
this baseline. ``derive_n_samples`` returns N together with both means and the planned
budget ratio so the run manifest can record them.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.baselines.direct import complete_and_validate
from src.config import RESULTS_DIR
from src.schema import Record

CONDITION = "4b"
NAME = "self_consistency"
MIN_SAMPLES = 3
DEFAULT_TEMPERATURE = 0.7


# -- N -------------------------------------------------------------------------------

def derive_n_samples(mean_tokens_cond4: float, mean_tokens_cond3_call: float,
                     floor: int = MIN_SAMPLES) -> dict:
    """N = max(floor, ceil(T4 / T3)), with what the manifest needs to show the budget match."""
    if not (mean_tokens_cond4 and mean_tokens_cond4 > 0 and mean_tokens_cond3_call and mean_tokens_cond3_call > 0):
        raise ValueError("both token means must be positive "
                         f"(got T4={mean_tokens_cond4!r}, T3={mean_tokens_cond3_call!r})")
    ratio = mean_tokens_cond4 / mean_tokens_cond3_call
    # ceil of a ratio that is an integer up to float noise must not jump to the next integer
    unfloored = max(1, math.ceil(round(ratio, 9)))
    n = max(int(floor), unfloored)
    return {"n_samples": n, "n_before_floor": unfloored, "floor": int(floor), "floor_applied": n > unfloored,
            "mean_tokens_per_row_cond4": mean_tokens_cond4,
            "mean_tokens_single_cond3_call": mean_tokens_cond3_call,
            "token_ratio_cond4_to_single_call": round(ratio, 4),
            "budget_ratio_4b_to_4_planned": round(n * mean_tokens_cond3_call / mean_tokens_cond4, 4)}


def load_match_run(run: str | Path, results_dir: Path = RESULTS_DIR) -> dict:
    """Read the budget reference of a condition 4 run (a run id under results/, or a path).

    Returns {"run_id", "path", "manifest", "mean_tokens_per_row", "mean_tokens_single_cond3_call",
    "n_rows"}. Raises ValueError when the run is not a condition 4 run or has no budget reference.
    """
    folder = Path(run)
    if not (folder / "manifest.json").exists():
        folder = Path(results_dir) / str(run)
    path = folder / "manifest.json"
    if not path.exists():
        raise ValueError(f"--match-run {run}: no manifest.json in {folder}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("condition") != 4:
        raise ValueError(f"--match-run {run}: condition is {manifest.get('condition')!r}, not 4")
    ref = manifest.get("budget_reference") or {}
    t4, t3 = ref.get("mean_total_tokens_per_row"), ref.get("mean_first_call_tokens_per_row")
    if not t4 or not t3:
        raise ValueError(f"--match-run {run}: manifest has no budget_reference token means "
                         "(was the run empty, or made with a mock client that reports no tokens?)")
    return {"run_id": manifest.get("run_id", folder.name), "path": str(folder), "manifest": manifest,
            "mean_tokens_per_row": float(t4), "mean_tokens_single_cond3_call": float(t3),
            "n_rows": ref.get("n_rows")}


# -- vote ------------------------------------------------------------------------------

@dataclass
class VoteResult:
    label: str
    chosen: int                 # index, in the list given to ``vote``, of the representative sample
    counts: dict                # label -> votes, in order of first appearance
    tie_break: str              # "none" | "mean_confidence" | "first_sample"
    tied_labels: list[str]      # labels that shared the top count (one label when there was no tie)

    @property
    def share(self) -> float:
        return self.counts[self.label] / sum(self.counts.values())


def vote(samples: list[tuple[str, float]]) -> VoteResult:
    """Plurality vote over (label, confidence) pairs given in sample order.

    Ties on the count go to the higher mean confidence, then to the label whose first sample
    is earliest. The representative is the highest-confidence sample with the winning label,
    the earliest one when several share that confidence.
    """
    if not samples:
        raise ValueError("no samples to vote on")
    counts: dict[str, int] = dict(Counter(label for label, _ in samples))     # insertion = first appearance
    top = max(counts.values())
    tied = [label for label, n in counts.items() if n == top]
    tie_break = "none"
    winner = tied[0]
    if len(tied) > 1:
        mean_conf = {label: round(sum(c for l, c in samples if l == label) / counts[label], 9) for label in tied}
        best = max(mean_conf.values())
        best_labels = [label for label in tied if mean_conf[label] == best]
        winner = best_labels[0]                       # ``tied`` is in order of first appearance
        tie_break = "mean_confidence" if len(best_labels) == 1 else "first_sample"
    voters = [(i, conf) for i, (label, conf) in enumerate(samples) if label == winner]
    chosen = max(voters, key=lambda ic: (ic[1], -ic[0]))[0]
    return VoteResult(label=winner, chosen=chosen, counts=counts, tie_break=tie_break, tied_labels=tied)


# -- one row -----------------------------------------------------------------------------

def sample_seeds(seed: int | None, n_samples: int) -> list[int]:
    """N distinct seeds: seed, seed + 1, ..., seed + N - 1 (seed None counts as 0)."""
    base = 0 if seed is None else int(seed)
    return [base + i for i in range(n_samples)]


def predict_row(row: dict, client, prepared: dict, labels: list[str], *, n_samples: int,
                temperature: float = DEFAULT_TEMPERATURE, seed: int | None = 0, max_tokens: int = 2048,
                json_mode: bool = True, max_repairs: int = 1) -> tuple[Record | None, dict | None]:
    """Condition 4b for one row.

    ``prepared`` is condition 3's ``taxonomy_fewshot.prepare_row`` output for the row, so the
    messages are condition 3's exactly. Returns (record, None), or (None, error) when no
    sample is valid. ``meta`` holds the row's total tokens and calls over all samples, the
    vote, and one entry per sample.
    """
    if n_samples < 1:
        raise ValueError("n_samples must be >= 1")
    samples: list[dict] = []
    valid: list[tuple[int, Record]] = []
    for index, s in enumerate(sample_seeds(seed, n_samples)):
        rec, err = complete_and_validate(
            row, client, prepared["messages"], labels, temperature=temperature, seed=s,
            max_tokens=max_tokens, json_mode=json_mode, max_repairs=max_repairs,
            retrieved_chunks=prepared["retrieved_chunks"], taxonomy_text=prepared["taxonomy_text"],
            extra_meta=prepared["extra_meta"])
        if rec is not None:
            valid.append((index, rec))
            samples.append({"index": index, "seed": s, "valid": True, "label": rec.label,
                            "confidence": rec.confidence, "citation_valid": rec.citation_valid,
                            "prompt_tokens": rec.meta["prompt_tokens"],
                            "completion_tokens": rec.meta["completion_tokens"],
                            "attempts": rec.meta["attempts"], "cached": rec.meta["cached"]})
        else:
            samples.append({"index": index, "seed": s, "valid": False, "label": None, "confidence": None,
                            "stage": err["stage"], "error": err["error"],
                            "prompt_tokens": err["usage"]["prompt_tokens"],
                            "completion_tokens": err["usage"]["completion_tokens"],
                            "attempts": err["attempts"], "cached": False})
    prompt = sum(s["prompt_tokens"] for s in samples)
    completion = sum(s["completion_tokens"] for s in samples)
    n_calls = sum(s["attempts"] for s in samples)
    extra = dict(prepared.get("extra_meta") or {})
    if not valid:
        return None, {"id": row["id"], "stage": "all_samples_invalid",
                      "error": f"none of the {n_samples} samples was a valid record",
                      "raw": "", "attempts": n_calls, "n_calls": n_calls,
                      "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
                      "samples": samples, **extra}
    result = vote([(rec.label, rec.confidence) for _, rec in valid])
    index, chosen = valid[result.chosen]
    chosen.meta.update({
        "prompt_tokens": prompt, "completion_tokens": completion,       # row totals over all samples
        "n_calls": n_calls, "cached": all(s["cached"] for s in samples),
        "n_samples": n_samples, "n_valid_samples": len(valid), "temperature": temperature,
        "votes": result.counts, "vote_share": round(result.share, 4), "tie_break": result.tie_break,
        "tied_labels": result.tied_labels, "chosen_sample": index, "samples": samples,
    })
    return chosen, None
