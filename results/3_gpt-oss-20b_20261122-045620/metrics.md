# Metrics for `3_gpt-oss-20b_20261122-045620`

Condition 3 (taxonomy_fewshot), model `gpt-oss:20b`, evaluated 2026-11-22T13:17:24+00:00.

- Predictions: 62 records, 1 errors, 1 cached calls
- Gold: 63 of 63 rows labelled
- Citation validity (model): 1.000 (40/40 records citing student spans)
- Coverage (not abstaining): 0.984

## Predicted label distribution

| label | n |
|---|---|
| none | 23 |
| other_error | 22 |
| BOsearchLinearScan | 6 |
| BObestCaseSmallestInput | 4 |
| BObestWorstSwapped | 3 |
| BOsearchVsSort | 2 |
| BCwrite | 1 |
| insufficient_evidence | 1 |

## Scores

| metric | value |
|---|---|
| macro-F1 (over 7 gold classes) | 0.757 |
| 95% bootstrap CI (2000 resamples, seed 0) | [0.592, 0.883] |
| macro-F1 excluding `insufficient_evidence` | 0.828 |
| four-way macro-F1 (taxonomy / none / other_error / insufficient_evidence) | 0.703 |
| accuracy | 0.794 |
| coverage | 0.984 |
| accuracy on covered subset | 0.790 |
| rows scored / missing predictions | 63 / 1 |
| gold citation validity | 1.000 (22/22) |

## Per-class

| label | P | R | F1 | support | predicted |
|---|---|---|---|---|---|
| none | 0.957 | 0.846 | 0.898 | 26 | 23 |
| other_error | 0.591 | 0.929 | 0.722 | 14 | 22 |
| insufficient_evidence | 1.000 | 0.200 | 0.333 | 5 | 1 |
| BObestWorstSwapped | 0.667 | 1.000 | 0.800 | 2 | 3 |
| BObestCaseSmallestInput | 1.000 | 0.800 | 0.889 | 5 | 4 |
| BOsearchLinearScan | 1.000 | 0.750 | 0.857 | 8 | 6 |
| BOsearchVsSort | 1.000 | 0.667 | 0.800 | 3 | 2 |

## Confusion matrix (rows = gold, columns = predicted)

| gold \ pred | none | other_error | insufficient_evidence | BObestWorstSwapped | BObestCaseSmallestInput | BOsearchLinearScan | BOsearchVsSort | BCwrite | __missing__ |
|---|---|---|---|---|---|---|---|---|---|
| none | 22 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| other_error | 0 | 13 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| insufficient_evidence | 1 | 3 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| BObestWorstSwapped | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| BObestCaseSmallestInput | 0 | 0 | 0 | 1 | 4 | 0 | 0 | 0 | 0 |
| BOsearchLinearScan | 0 | 2 | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| BOsearchVsSort | 0 | 1 | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| BCwrite | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| __missing__ | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Comparison with `2_gpt-oss-20b_20261122-044046`

- macro-F1 this = 0.757, other = 0.604
- paired bootstrap (this minus other): 0.153 [-0.062, 0.336], p = 0.152
- McNemar exact: b = 4, c = 10, p = 0.180

_Caveat: rows cluster by question (7 questions), so a row-level bootstrap understates variance._
