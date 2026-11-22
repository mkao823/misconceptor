"""Classification metrics for the ablation ladder (docs/REVIEW_2026-10-18.md, 6.4, 6.7, 6.8).

All functions take plain Python sequences of label strings. Macro-F1 is averaged
over the label set actually present in gold (classes nobody annotated are
"not observable in this data", annotation/schema.md section 8, and are excluded
rather than averaged in as zeros). Bootstrap resamples rows with replacement
and recomputes macro-F1 over the classes present in the resampled gold.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

import numpy as np

from src.schema import ABSTAIN_LABEL, SPECIAL_LABELS

MISSING_PREDICTION = "__missing__"   # sentinel for rows with no prediction record


# -- helpers -------------------------------------------------------------------

def gold_label_set(y_true: Sequence[str]) -> list[str]:
    """Labels present in gold, in order of first appearance."""
    seen: dict[str, None] = {}
    for y in y_true:
        seen.setdefault(y, None)
    return list(seen)


def _encode(y_true, y_pred, labels):
    """Map labels to ints; anything outside ``labels`` gets index k ('none of these').

    A gold label outside the set makes its row count only as a false positive for
    whatever was predicted; a prediction outside the set counts only as a false
    negative for the gold class. This matches sklearn's ``labels=`` semantics.
    """
    index = {l: i for i, l in enumerate(labels)}
    k = len(labels)
    yt = np.array([index.get(y, k) for y in y_true], dtype=np.int64)
    yp = np.array([index.get(y, k) for y in y_pred], dtype=np.int64)
    return yt, yp, k


def _counts(yt: np.ndarray, yp: np.ndarray, k: int) -> np.ndarray:
    """(k+1)x(k+1) confusion counts: rows gold, cols predicted; last col = outside label set."""
    return np.bincount(yt * (k + 1) + yp, minlength=(k + 1) * (k + 1)).reshape(k + 1, k + 1)


def _prf_from_counts(cm: np.ndarray, k: int):
    tp = np.diag(cm)[:k].astype(float)
    pred = cm.sum(axis=0)[:k].astype(float)
    gold = cm.sum(axis=1)[:k].astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        precision = np.where(pred > 0, tp / pred, 0.0)
        recall = np.where(gold > 0, tp / gold, 0.0)
        denom = precision + recall
        f1 = np.where(denom > 0, 2 * precision * recall / denom, 0.0)
    return precision, recall, f1, gold


def _macro_f1_present(yt: np.ndarray, yp: np.ndarray, k: int) -> float:
    cm = _counts(yt, yp, k)
    _, _, f1, gold = _prf_from_counts(cm, k)
    present = gold > 0
    return float(f1[present].mean()) if present.any() else float("nan")


# -- point metrics --------------------------------------------------------------

def per_class_metrics(y_true: Sequence[str], y_pred: Sequence[str],
                      labels: Sequence[str] | None = None) -> dict[str, dict]:
    labels = list(labels) if labels is not None else gold_label_set(y_true)
    yt, yp, k = _encode(y_true, y_pred, labels)
    cm = _counts(yt, yp, k)
    precision, recall, f1, gold = _prf_from_counts(cm, k)
    predicted = cm.sum(axis=0)[:k]
    return {l: {"precision": float(precision[i]), "recall": float(recall[i]), "f1": float(f1[i]),
                "support": int(gold[i]), "predicted": int(predicted[i])}
            for i, l in enumerate(labels)}


def macro_f1(y_true: Sequence[str], y_pred: Sequence[str], labels: Sequence[str] | None = None) -> float:
    """Unweighted mean of per-class F1 over ``labels`` (default: the labels present in gold)."""
    labels = list(labels) if labels is not None else gold_label_set(y_true)
    if not labels:
        return float("nan")
    yt, yp, k = _encode(y_true, y_pred, labels)
    cm = _counts(yt, yp, k)
    _, _, f1, _ = _prf_from_counts(cm, k)
    return float(f1.mean())


def accuracy(y_true: Sequence[str], y_pred: Sequence[str]) -> float:
    n = len(y_true)
    return sum(a == b for a, b in zip(y_true, y_pred)) / n if n else float("nan")


def confusion_matrix(y_true: Sequence[str], y_pred: Sequence[str],
                     labels: Sequence[str] | None = None) -> dict:
    """Rows = gold, columns = predicted. Labels: gold labels first, then extra predicted ones."""
    if labels is None:
        labels = gold_label_set(y_true)
        extra = [l for l in gold_label_set(y_pred) if l not in labels]
        labels = labels + extra
    labels = list(labels)
    index = {l: i for i, l in enumerate(labels)}
    m = [[0] * len(labels) for _ in labels]
    for t, p in zip(y_true, y_pred):
        if t in index and p in index:
            m[index[t]][index[p]] += 1
    return {"labels": labels, "matrix": m}


# -- bootstrap -----------------------------------------------------------------

def bootstrap_ci(y_true: Sequence[str], y_pred: Sequence[str], *, n_resamples: int = 2000,
                 seed: int = 0, alpha: float = 0.05) -> dict:
    """Percentile bootstrap CI on macro-F1: resample rows with replacement (fixed seed)."""
    labels = gold_label_set(y_true)
    yt, yp, k = _encode(y_true, y_pred, labels)
    n = len(yt)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    stats = np.array([_macro_f1_present(yt[i], yp[i], k) for i in idx])
    lo, hi = np.nanpercentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"point": macro_f1(y_true, y_pred, labels), "lower": float(lo), "upper": float(hi),
            "mean": float(np.nanmean(stats)), "n_resamples": n_resamples, "seed": seed,
            "alpha": alpha, "n_rows": n}


def paired_bootstrap(y_true: Sequence[str], y_pred_a: Sequence[str], y_pred_b: Sequence[str], *,
                     n_resamples: int = 2000, seed: int = 0, alpha: float = 0.05) -> dict:
    """CI and two-sided p-value for macro-F1(b) - macro-F1(a), same resample indices for both."""
    labels = gold_label_set(y_true)
    yt, ya, k = _encode(y_true, y_pred_a, labels)
    _, yb, _ = _encode(y_true, y_pred_b, labels)
    n = len(yt)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    diffs = np.array([_macro_f1_present(yt[i], yb[i], k) - _macro_f1_present(yt[i], ya[i], k) for i in idx])
    lo, hi = np.nanpercentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    p_le = float(np.mean(diffs <= 0)); p_ge = float(np.mean(diffs >= 0))
    return {"diff": macro_f1(y_true, y_pred_b, labels) - macro_f1(y_true, y_pred_a, labels),
            "lower": float(lo), "upper": float(hi), "p_value": min(1.0, 2 * min(p_le, p_ge)),
            "n_resamples": n_resamples, "seed": seed, "alpha": alpha, "n_rows": n}


def mcnemar(correct_a: Sequence[bool], correct_b: Sequence[bool]) -> dict:
    """Exact McNemar test on per-row correctness (review 6.8). b: a right & b wrong; c: a wrong & b right."""
    b = sum(1 for x, y in zip(correct_a, correct_b) if x and not y)
    c = sum(1 for x, y in zip(correct_a, correct_b) if not x and y)
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "p_value": 1.0}
    tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1)) / 2 ** n
    return {"b": b, "c": c, "p_value": min(1.0, 2 * tail)}


# -- abstention, citations, agreement ------------------------------------------------

def coverage(y_pred: Sequence[str], abstain: str = ABSTAIN_LABEL) -> float:
    """Fraction of rows where the system did not abstain (predict insufficient_evidence)."""
    return (sum(1 for p in y_pred if p != abstain) / len(y_pred)) if len(y_pred) else float("nan")


def covered_accuracy(y_true: Sequence[str], y_pred: Sequence[str], abstain: str = ABSTAIN_LABEL) -> float:
    pairs = [(t, p) for t, p in zip(y_true, y_pred) if p != abstain]
    return (sum(t == p for t, p in pairs) / len(pairs)) if pairs else float("nan")


def citation_validity(records: Sequence[dict]) -> dict:
    """Validity rate over records that cite at least one student_answer span (and over all)."""
    cited = [r for r in records if any(e.get("source") == "student_answer" for e in r.get("evidence", []))]
    n_valid = sum(1 for r in cited if r.get("citation_valid"))
    return {"n_records": len(records), "n_with_student_spans": len(cited), "n_valid": n_valid,
            "rate": (n_valid / len(cited)) if cited else None,
            "rate_all": (sum(1 for r in records if r.get("citation_valid")) / len(records)) if records else None}


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """Unweighted Cohen's kappa between two label columns of equal length."""
    if len(a) != len(b):
        raise ValueError("label columns differ in length")
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[l] * cb[l] for l in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1.0 else (po - pe) / (1 - pe)


def collapse_four_way(label: str) -> str:
    """Collapse a label to {taxonomy, none, other_error, insufficient_evidence} (schema section 7)."""
    return label if label in SPECIAL_LABELS else "taxonomy"


def label_distribution(labels: Sequence[str]) -> dict[str, int]:
    return dict(Counter(labels).most_common())
