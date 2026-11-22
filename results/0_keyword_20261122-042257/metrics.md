# Metrics for `0_keyword_20261122-042257`

Condition 0 (keyword), model `keyword`, evaluated 2026-11-22T12:22:57+00:00.

- Predictions: 63 records, 0 errors, 0 cached calls
- Gold: 63 of 63 rows labelled
- Citation validity (model): 1.000 (22/22 records citing student spans)
- Coverage (not abstaining): 1.000

## Predicted label distribution

| label | n |
|---|---|
| none | 41 |
| BOsearchLinearScan | 8 |
| BOsearchVsSort | 7 |
| BObestCaseSmallestInput | 4 |
| BObestWorstSwapped | 2 |
| MMstep | 1 |

## Scores

| metric | value |
|---|---|
| macro-F1 (over 7 gold classes) | 0.451 |
| 95% bootstrap CI (2000 resamples, seed 0) | [0.312, 0.564] |
| macro-F1 excluding `insufficient_evidence` | 0.527 |
| four-way macro-F1 (taxonomy / none / other_error / insufficient_evidence) | 0.362 |
| accuracy | 0.587 |
| coverage | 1.000 |
| accuracy on covered subset | 0.587 |
| rows scored / missing predictions | 63 / 0 |
| gold citation validity | 1.000 (22/22) |

## Per-class

| label | P | R | F1 | support | predicted |
|---|---|---|---|---|---|
| none | 0.610 | 0.962 | 0.746 | 26 | 41 |
| other_error | 0.000 | 0.000 | 0.000 | 14 | 0 |
| insufficient_evidence | 0.000 | 0.000 | 0.000 | 5 | 0 |
| BObestWorstSwapped | 0.500 | 0.500 | 0.500 | 2 | 2 |
| BObestCaseSmallestInput | 1.000 | 0.800 | 0.889 | 5 | 4 |
| BOsearchLinearScan | 0.625 | 0.625 | 0.625 | 8 | 8 |
| BOsearchVsSort | 0.286 | 0.667 | 0.400 | 3 | 7 |

## Confusion matrix (rows = gold, columns = predicted)

| gold \ pred | none | other_error | insufficient_evidence | BObestWorstSwapped | BObestCaseSmallestInput | BOsearchLinearScan | BOsearchVsSort | MMstep |
|---|---|---|---|---|---|---|---|---|
| none | 25 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| other_error | 8 | 0 | 0 | 1 | 0 | 0 | 5 | 0 |
| insufficient_evidence | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| BObestWorstSwapped | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 |
| BObestCaseSmallestInput | 1 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| BOsearchLinearScan | 3 | 0 | 0 | 0 | 0 | 5 | 0 | 0 |
| BOsearchVsSort | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0 |
| MMstep | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

_Caveat: rows cluster by question (7 questions), so a row-level bootstrap understates variance._
