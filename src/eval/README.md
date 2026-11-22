# src/eval/

Metrics: macro-F1 with bootstrap CIs, paired-bootstrap comparisons, grounding-support scoring, Cohen's kappa.

`metrics.py` implements (pure numpy, tested against sklearn in `tests/test_metrics.py`): per-class
P/R/F1, macro-F1 over the labels present in gold, confusion matrix, percentile bootstrap CI (row
resampling, fixed seed), paired bootstrap on the difference between two runs (same resample indices),
exact McNemar, coverage and covered accuracy (abstention), citation-validity rate, unweighted Cohen's
kappa, and the four-way label collapse from annotation/schema.md section 7. `scripts/evaluate.py`
wires these to a run folder. Grounding-support scoring (human ratings) is not implemented yet.
