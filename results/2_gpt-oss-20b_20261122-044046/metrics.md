# Metrics for `2_gpt-oss-20b_20261122-044046`

Condition 2 (rag), model `gpt-oss:20b`, evaluated 2026-11-22T13:17:24+00:00.

- Predictions: 63 records, 0 errors, 6 cached calls
- Gold: 63 of 63 rows labelled
- Citation validity (model): 0.982 (56/57 records citing student spans)
- Coverage (not abstaining): 0.968

## Predicted label distribution

| label | n |
|---|---|
| other_error | 27 |
| none | 23 |
| BOsearchLinearScan | 4 |
| BObestCaseSmallestInput | 3 |
| insufficient_evidence | 2 |
| BOsearchVsSort | 2 |
| BCwrite | 1 |
| BaseCaseNotNeeded | 1 |

## Scores

| metric | value |
|---|---|
| macro-F1 (over 7 gold classes) | 0.604 |
| 95% bootstrap CI (2000 resamples, seed 0) | [0.418, 0.757] |
| macro-F1 excluding `insufficient_evidence` | 0.610 |
| four-way macro-F1 (taxonomy / none / other_error / insufficient_evidence) | 0.659 |
| accuracy | 0.698 |
| coverage | 0.968 |
| accuracy on covered subset | 0.689 |
| rows scored / missing predictions | 63 / 0 |
| gold citation validity | 1.000 (22/22) |

## Per-class

| label | P | R | F1 | support | predicted |
|---|---|---|---|---|---|
| none | 0.913 | 0.808 | 0.857 | 26 | 23 |
| other_error | 0.444 | 0.857 | 0.585 | 14 | 27 |
| insufficient_evidence | 1.000 | 0.400 | 0.571 | 5 | 2 |
| BObestWorstSwapped | 0.000 | 0.000 | 0.000 | 2 | 0 |
| BObestCaseSmallestInput | 1.000 | 0.600 | 0.750 | 5 | 3 |
| BOsearchLinearScan | 1.000 | 0.500 | 0.667 | 8 | 4 |
| BOsearchVsSort | 1.000 | 0.667 | 0.800 | 3 | 2 |

## Confusion matrix (rows = gold, columns = predicted)

| gold \ pred | none | other_error | insufficient_evidence | BObestWorstSwapped | BObestCaseSmallestInput | BOsearchLinearScan | BOsearchVsSort | BCwrite | BaseCaseNotNeeded |
|---|---|---|---|---|---|---|---|---|---|
| none | 21 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| other_error | 1 | 12 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| insufficient_evidence | 1 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| BObestWorstSwapped | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BObestCaseSmallestInput | 0 | 2 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| BOsearchLinearScan | 0 | 4 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| BOsearchVsSort | 0 | 1 | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| BCwrite | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BaseCaseNotNeeded | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Comparison with `1_gpt-oss-20b_20261122-042535`

- macro-F1 this = 0.604, other = 0.388
- paired bootstrap (this minus other): 0.216 [0.056, 0.354], p = 0.009
- McNemar exact: b = 3, c = 6, p = 0.508

_Caveat: rows cluster by question (7 questions), so a row-level bootstrap understates variance._
