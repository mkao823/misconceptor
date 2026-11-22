import math

import numpy as np
import pytest
from sklearn.metrics import cohen_kappa_score, confusion_matrix, f1_score, precision_recall_fscore_support

from src.eval import metrics as M

# Hand-computed example: 3 gold classes, 8 rows.
Y_TRUE = ["a", "a", "a", "b", "b", "c", "c", "c"]
Y_PRED = ["a", "a", "b", "b", "c", "c", "c", "a"]
# a: tp=2 pred=3 gold=3 -> P=2/3 R=2/3 F1=2/3
# b: tp=1 pred=2 gold=2 -> P=1/2 R=1/2 F1=1/2
# c: tp=2 pred=3 gold=3 -> P=2/3 R=2/3 F1=2/3
HAND_MACRO = (2 / 3 + 1 / 2 + 2 / 3) / 3


def test_macro_f1_by_hand():
    assert M.macro_f1(Y_TRUE, Y_PRED) == pytest.approx(HAND_MACRO)


def test_per_class_by_hand():
    pc = M.per_class_metrics(Y_TRUE, Y_PRED)
    assert pc["a"] == {"precision": pytest.approx(2 / 3), "recall": pytest.approx(2 / 3),
                       "f1": pytest.approx(2 / 3), "support": 3, "predicted": 3}
    assert pc["b"]["f1"] == pytest.approx(0.5) and pc["b"]["support"] == 2


def test_against_sklearn():
    labels = ["a", "b", "c"]
    assert M.macro_f1(Y_TRUE, Y_PRED, labels) == pytest.approx(f1_score(Y_TRUE, Y_PRED, labels=labels, average="macro"))
    p, r, f, s = precision_recall_fscore_support(Y_TRUE, Y_PRED, labels=labels, zero_division=0)
    pc = M.per_class_metrics(Y_TRUE, Y_PRED, labels)
    for i, l in enumerate(labels):
        assert pc[l]["precision"] == pytest.approx(p[i])
        assert pc[l]["recall"] == pytest.approx(r[i])
        assert pc[l]["f1"] == pytest.approx(f[i])
        assert pc[l]["support"] == s[i]
    assert M.confusion_matrix(Y_TRUE, Y_PRED, labels)["matrix"] == confusion_matrix(Y_TRUE, Y_PRED, labels=labels).tolist()


def test_prediction_outside_gold_label_set_counts_as_wrong():
    # predicting a label nobody annotated costs recall but creates no extra class
    y_true = ["a", "a", "b"]
    y_pred = ["a", "zzz", "b"]
    assert M.gold_label_set(y_true) == ["a", "b"]
    assert M.macro_f1(y_true, y_pred) == pytest.approx(f1_score(y_true, y_pred, labels=["a", "b"], average="macro"))
    cm = M.confusion_matrix(y_true, y_pred)
    assert cm["labels"] == ["a", "b", "zzz"] and cm["matrix"][0] == [1, 0, 1]


def test_macro_over_gold_classes_only():
    # class "c" is never in gold -> not averaged in as a zero
    assert M.macro_f1(["a", "b"], ["a", "c"]) == pytest.approx((1.0 + 0.0) / 2)


def test_bootstrap_ci_deterministic_and_brackets_point():
    ci1 = M.bootstrap_ci(Y_TRUE, Y_PRED, n_resamples=500, seed=1)
    ci2 = M.bootstrap_ci(Y_TRUE, Y_PRED, n_resamples=500, seed=1)
    assert ci1 == ci2
    assert ci1["lower"] <= ci1["point"] <= ci1["upper"]
    assert ci1["point"] == pytest.approx(HAND_MACRO)
    perfect = M.bootstrap_ci(Y_TRUE, Y_TRUE, n_resamples=100, seed=0)
    assert perfect["lower"] == perfect["upper"] == 1.0


def test_paired_bootstrap_identical_runs_is_zero():
    pb = M.paired_bootstrap(Y_TRUE, Y_PRED, Y_PRED, n_resamples=300, seed=0)
    assert pb["diff"] == 0.0 and pb["lower"] == 0.0 and pb["upper"] == 0.0 and pb["p_value"] == 1.0
    better = M.paired_bootstrap(Y_TRUE, Y_PRED, Y_TRUE, n_resamples=300, seed=0)
    assert better["diff"] == pytest.approx(1 - HAND_MACRO) and better["lower"] > 0


def test_mcnemar_hand():
    assert M.mcnemar([True, True, False], [True, True, False]) == {"b": 0, "c": 0, "p_value": 1.0}
    r = M.mcnemar([True, True, True, False], [False, False, False, False])  # b=3, c=0
    assert r["b"] == 3 and r["c"] == 0 and r["p_value"] == pytest.approx(2 * (1 / 8))


def test_coverage_and_covered_accuracy():
    y_true = ["a", "b", "c", "insufficient_evidence"]
    y_pred = ["a", "insufficient_evidence", "a", "insufficient_evidence"]
    assert M.coverage(y_pred) == pytest.approx(0.5)
    assert M.covered_accuracy(y_true, y_pred) == pytest.approx(0.5)


def test_cohen_kappa_against_sklearn():
    a = ["x", "x", "y", "z", "y", "x", "z", "z"]
    b = ["x", "y", "y", "z", "y", "x", "x", "z"]
    assert M.cohen_kappa(a, b) == pytest.approx(cohen_kappa_score(a, b))
    assert M.cohen_kappa(a, a) == 1.0
    assert M.cohen_kappa(["x", "y"], ["y", "x"]) == pytest.approx(-1.0)


def test_citation_validity_rate():
    recs = [{"evidence": [{"source": "student_answer", "span": "s"}], "citation_valid": True},
            {"evidence": [{"source": "student_answer", "span": "s"}], "citation_valid": False},
            {"evidence": [], "citation_valid": True}]
    cv = M.citation_validity(recs)
    assert cv["n_with_student_spans"] == 2 and cv["n_valid"] == 1 and cv["rate"] == 0.5
    assert cv["rate_all"] == pytest.approx(2 / 3)


def test_collapse_four_way():
    assert M.collapse_four_way("BOsearchVsSort") == "taxonomy"
    assert M.collapse_four_way("none") == "none"


def test_label_subset_matches_sklearn():
    # gold rows outside the subset only create false positives; preds outside only false negatives
    y_true = ["a", "a", "b", "insufficient_evidence", "insufficient_evidence"]
    y_pred = ["a", "b", "insufficient_evidence", "a", "insufficient_evidence"]
    subset = ["a", "b"]
    assert M.macro_f1(y_true, y_pred, subset) == pytest.approx(f1_score(y_true, y_pred, labels=subset, average="macro"))
    pc = M.per_class_metrics(y_true, y_pred, subset)
    assert pc["a"] == {"precision": pytest.approx(0.5), "recall": pytest.approx(0.5), "f1": pytest.approx(0.5),
                       "support": 2, "predicted": 2}
