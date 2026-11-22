# Metrics for `1_gpt-oss-20b_20261122-042535`

Condition 1 (direct), model `gpt-oss:20b`, evaluated 2026-11-22T13:17:24+00:00.

- Predictions: 63 records, 0 errors, 6 cached calls
- Gold: 63 of 63 rows labelled
- Citation validity (model): 1.000 (46/46 records citing student spans)
- Coverage (not abstaining): 0.984

## Predicted label distribution

| label | n |
|---|---|
| other_error | 29 |
| none | 25 |
| BOsearchLinearScan | 3 |
| BCwrite | 2 |
| MMstep | 2 |
| BObestCaseSmallestInput | 1 |
| insufficient_evidence | 1 |

## Scores

| metric | value |
|---|---|
| macro-F1 (over 7 gold classes) | 0.388 |
| 95% bootstrap CI (2000 resamples, seed 0) | [0.256, 0.534] |
| macro-F1 excluding `insufficient_evidence` | 0.398 |
| four-way macro-F1 (taxonomy / none / other_error / insufficient_evidence) | 0.575 |
| accuracy | 0.651 |
| coverage | 0.984 |
| accuracy on covered subset | 0.645 |
| rows scored / missing predictions | 63 / 0 |
| gold citation validity | 1.000 (22/22) |

## Per-class

| label | P | R | F1 | support | predicted |
|---|---|---|---|---|---|
| none | 0.920 | 0.885 | 0.902 | 26 | 25 |
| other_error | 0.448 | 0.929 | 0.605 | 14 | 29 |
| insufficient_evidence | 1.000 | 0.200 | 0.333 | 5 | 1 |
| BObestWorstSwapped | 0.000 | 0.000 | 0.000 | 2 | 0 |
| BObestCaseSmallestInput | 1.000 | 0.200 | 0.333 | 5 | 1 |
| BOsearchLinearScan | 1.000 | 0.375 | 0.545 | 8 | 3 |
| BOsearchVsSort | 0.000 | 0.000 | 0.000 | 3 | 0 |

## Confusion matrix (rows = gold, columns = predicted)

| gold \ pred | none | other_error | insufficient_evidence | BObestWorstSwapped | BObestCaseSmallestInput | BOsearchLinearScan | BOsearchVsSort | BCwrite | MMstep |
|---|---|---|---|---|---|---|---|---|---|
| none | 23 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| other_error | 0 | 13 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| insufficient_evidence | 2 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| BObestWorstSwapped | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BObestCaseSmallestInput | 0 | 4 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| BOsearchLinearScan | 0 | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 2 |
| BOsearchVsSort | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BCwrite | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| MMstep | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Comparison with `0_keyword_20261122-042257`

- macro-F1 this = 0.388, other = 0.451
- paired bootstrap (this minus other): -0.063 [-0.244, 0.129], p = 0.551
- McNemar exact: b = 12, c = 16, p = 0.572

_Caveat: rows cluster by question (7 questions), so a row-level bootstrap understates variance._
