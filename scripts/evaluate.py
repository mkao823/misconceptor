"""Score a run in results/<run_id>/ against annotation/pilot_sheet.csv.

Joins predictions.jsonl to primary_label by id and writes metrics.json and
metrics.md into the run folder: macro-F1 over the labels present in gold with a
95% bootstrap CI (2000 row resamples, fixed seed), per-class P/R/F1, confusion
matrix, coverage and covered accuracy (review 6.7), citation-validity rate
(review 6.4), label distribution. With --compare, a paired bootstrap on the
macro-F1 difference (this run minus the other) and an exact McNemar test.

If every gold label is empty, it says so and still reports citation validity
and the label distribution.

Usage:
    python scripts/evaluate.py --run <run_id> [--compare <other_run_id>] [--n-resamples 2000] [--seed 0]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import ANNOTATION_SHEET, RESULTS_DIR, sha256_file  # noqa: E402
from src.eval import metrics as M  # noqa: E402
from src.schema import ABSTAIN_LABEL, label_set, normalize_ws  # noqa: E402

GOLD_SPAN_JOINER = "||"


def resolve_run(run: str) -> Path:
    p = Path(run)
    if p.is_dir():
        return p
    p = RESULTS_DIR / run
    if p.is_dir():
        return p
    raise SystemExit(f"run folder not found: {run} (looked in results/)")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_run(run: str) -> tuple[Path, dict, list[dict], list[dict]]:
    folder = resolve_run(run)
    with open(folder / "manifest.json") as f:
        manifest = json.load(f)
    return folder, manifest, read_jsonl(folder / "predictions.jsonl"), read_jsonl(folder / "errors.jsonl")


def load_gold(path: Path, labels: list[str]) -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    valid = set(labels)
    labeled, invalid = {}, {}
    for r in rows:
        lab = (r.get("primary_label") or "").strip()
        if not lab:
            continue
        (labeled if lab in valid else invalid)[r["id"]] = lab
    # gold citation validity: every `||`-separated part must be verbatim in the answer
    span_rows = [r for r in rows if r["id"] in labeled and (r.get("evidence_span") or "").strip()]
    n_span_valid = 0
    bad_spans = []
    for r in span_rows:
        hay = normalize_ws(r["student_answer"])
        parts = [normalize_ws(p) for p in r["evidence_span"].split(GOLD_SPAN_JOINER) if p.strip()]
        if parts and all(p in hay for p in parts):
            n_span_valid += 1
        else:
            bad_spans.append(r["id"])
    return {"path": str(path), "sha256": sha256_file(path), "n_rows": len(rows),
            "n_labeled": len(labeled), "n_unlabeled": len(rows) - len(labeled) - len(invalid),
            "invalid_gold_labels": invalid, "labels": labeled,
            "rows": {r["id"]: r for r in rows},
            "citation_validity": {"n_with_spans": len(span_rows), "n_valid": n_span_valid,
                                  "rate": (n_span_valid / len(span_rows)) if span_rows else None,
                                  "invalid_rows": bad_spans}}


def score(gold: dict, predictions: list[dict], n_resamples: int, seed: int) -> dict:
    pred_by_id = {p["id"]: p for p in predictions}
    ids = list(gold["labels"])
    y_true = [gold["labels"][i] for i in ids]
    y_pred = [pred_by_id[i]["label"] if i in pred_by_id else M.MISSING_PREDICTION for i in ids]
    missing = [i for i in ids if i not in pred_by_id]
    labels_in_gold = M.gold_label_set(y_true)
    out = {
        "n_scored": len(ids), "n_missing_predictions": len(missing), "missing_ids": missing,
        "labels_in_gold": labels_in_gold,
        "macro_f1": M.macro_f1(y_true, y_pred, labels_in_gold),
        "macro_f1_ci": M.bootstrap_ci(y_true, y_pred, n_resamples=n_resamples, seed=seed),
        "accuracy": M.accuracy(y_true, y_pred),
        "per_class": M.per_class_metrics(y_true, y_pred, labels_in_gold),
        "confusion": M.confusion_matrix(y_true, y_pred),
        "coverage": M.coverage(y_pred),
        "covered_accuracy": M.covered_accuracy(y_true, y_pred),
        "abstention": {"n_abstained": sum(1 for p in y_pred if p == ABSTAIN_LABEL),
                       "n_gold_abstain": sum(1 for t in y_true if t == ABSTAIN_LABEL)},
        "four_way": {"macro_f1": M.macro_f1([M.collapse_four_way(t) for t in y_true],
                                            [M.collapse_four_way(p) for p in y_pred])},
        "_y": (ids, y_true, y_pred),
    }
    # macro-F1 over non-abstain classes only, so abstaining cannot game the average (review 6.8)
    non_abstain = [l for l in labels_in_gold if l != ABSTAIN_LABEL]
    out["macro_f1_excluding_abstain"] = M.macro_f1(y_true, y_pred, non_abstain) if non_abstain else None
    return out


def compare(gold: dict, this: dict, other_preds: list[dict], n_resamples: int, seed: int) -> dict:
    ids, y_true, y_pred_this = this["_y"]
    other_by_id = {p["id"]: p for p in other_preds}
    y_pred_other = [other_by_id[i]["label"] if i in other_by_id else M.MISSING_PREDICTION for i in ids]
    pb = M.paired_bootstrap(y_true, y_pred_other, y_pred_this, n_resamples=n_resamples, seed=seed)
    mc = M.mcnemar([t == p for t, p in zip(y_true, y_pred_other)], [t == p for t, p in zip(y_true, y_pred_this)])
    return {"macro_f1_other": M.macro_f1(y_true, y_pred_other, this["labels_in_gold"]),
            "macro_f1_this": this["macro_f1"], "paired_bootstrap_this_minus_other": pb, "mcnemar": mc}


def fmt(x, nd=3):
    return "n/a" if x is None or (isinstance(x, float) and x != x) else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def render_md(report: dict) -> str:
    m = report
    lines = [f"# Metrics for `{m['run_id']}`", "",
             f"Condition {m['condition']} ({m['condition_name']}), model `{m['model']}`, evaluated {m['evaluated_at']}.", ""]
    g, p = m["gold"], m["predictions"]
    lines += [f"- Predictions: {p['n']} records, {p['n_errors']} errors, {p['n_cached']} cached calls",
              f"- Gold: {g['n_labeled']} of {g['n_rows']} rows labelled"
              + (f", {len(g['invalid_gold_labels'])} with labels outside the label set" if g["invalid_gold_labels"] else ""),
              f"- Citation validity (model): {fmt(p['citation_validity']['rate'])} "
              f"({p['citation_validity']['n_valid']}/{p['citation_validity']['n_with_student_spans']} records citing student spans)",
              f"- Coverage (not abstaining): {fmt(p['coverage'])}", ""]
    lines += ["## Predicted label distribution", "", "| label | n |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in p["label_distribution"].items()]
    lines.append("")
    if not m["gold_available"]:
        lines += ["## Scores", "", "**Gold labels are all empty: nothing can be scored yet.** "
                  "Fill `primary_label` in annotation/pilot_sheet.csv and re-run `make eval`.", ""]
        return "\n".join(lines)
    s = m["scores"]
    ci = s["macro_f1_ci"]
    lines += ["## Scores", "", "| metric | value |", "|---|---|",
              f"| macro-F1 (over {len(s['labels_in_gold'])} gold classes) | {fmt(s['macro_f1'])} |",
              f"| 95% bootstrap CI ({ci['n_resamples']} resamples, seed {ci['seed']}) | [{fmt(ci['lower'])}, {fmt(ci['upper'])}] |",
              f"| macro-F1 excluding `insufficient_evidence` | {fmt(s['macro_f1_excluding_abstain'])} |",
              f"| four-way macro-F1 (taxonomy / none / other_error / insufficient_evidence) | {fmt(s['four_way']['macro_f1'])} |",
              f"| accuracy | {fmt(s['accuracy'])} |",
              f"| coverage | {fmt(s['coverage'])} |",
              f"| accuracy on covered subset | {fmt(s['covered_accuracy'])} |",
              f"| rows scored / missing predictions | {s['n_scored']} / {s['n_missing_predictions']} |",
              f"| gold citation validity | {fmt(g['citation_validity']['rate'])} ({g['citation_validity']['n_valid']}/{g['citation_validity']['n_with_spans']}) |", ""]
    lines += ["## Per-class", "", "| label | P | R | F1 | support | predicted |", "|---|---|---|---|---|---|"]
    lines += [f"| {l} | {fmt(v['precision'])} | {fmt(v['recall'])} | {fmt(v['f1'])} | {v['support']} | {v['predicted']} |"
              for l, v in s["per_class"].items()]
    cm = s["confusion"]
    lines += ["", "## Confusion matrix (rows = gold, columns = predicted)", "",
              "| gold \\ pred | " + " | ".join(cm["labels"]) + " |", "|---|" + "---|" * len(cm["labels"])]
    lines += [f"| {l} | " + " | ".join(str(x) for x in row) + " |" for l, row in zip(cm["labels"], cm["matrix"])]
    if m.get("comparison"):
        c = m["comparison"]; pb = c["paired_bootstrap_this_minus_other"]; mc = c["mcnemar"]
        lines += ["", f"## Comparison with `{c['other_run']}`", "",
                  f"- macro-F1 this = {fmt(c['macro_f1_this'])}, other = {fmt(c['macro_f1_other'])}",
                  f"- paired bootstrap (this minus other): {fmt(pb['diff'])} [{fmt(pb['lower'])}, {fmt(pb['upper'])}], p = {fmt(pb['p_value'])}",
                  f"- McNemar exact: b = {mc['b']}, c = {mc['c']}, p = {fmt(mc['p_value'])}"]
    lines += ["", "_Caveat: rows cluster by question (7 questions), so a row-level bootstrap understates variance._"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="run id under results/ or a path to a run folder")
    ap.add_argument("--gold", type=Path, default=ANNOTATION_SHEET)
    ap.add_argument("--compare", default=None, help="other run id: paired bootstrap of this minus other")
    ap.add_argument("--n-resamples", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    folder, manifest, predictions, errors = load_run(args.run)
    labels = label_set()
    gold = load_gold(args.gold, labels)
    pred_labels = [p["label"] for p in predictions]

    report: dict = {
        "run_id": manifest.get("run_id", folder.name), "condition": manifest.get("condition"),
        "condition_name": manifest.get("condition_name"), "model": manifest.get("model"),
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gold": {k: v for k, v in gold.items() if k not in ("labels", "rows")},
        "predictions": {"n": len(predictions), "n_errors": len(errors),
                        "n_cached": sum(1 for p in predictions if p.get("meta", {}).get("cached")),
                        "label_distribution": M.label_distribution(pred_labels),
                        "coverage": M.coverage(pred_labels),
                        "citation_validity": M.citation_validity(predictions)},
        "gold_available": gold["n_labeled"] > 0,
        "scores": None, "comparison": None,
    }
    if report["gold_available"]:
        scores = score(gold, predictions, args.n_resamples, args.seed)
        if args.compare:
            _, other_manifest, other_preds, _ = load_run(args.compare)
            report["comparison"] = {"other_run": other_manifest.get("run_id", args.compare),
                                    **compare(gold, scores, other_preds, args.n_resamples, args.seed)}
        scores.pop("_y")
        report["scores"] = scores

    with open(folder / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    md = render_md(report)
    (folder / "metrics.md").write_text(md, encoding="utf-8")

    print(md)
    if not report["gold_available"]:
        print(f"NOTE: gold labels are all empty in {args.gold} ({gold['n_rows']} rows); "
              "reported citation validity and label distribution only.")
    print(f"wrote {folder.relative_to(REPO_ROOT) if folder.is_relative_to(REPO_ROOT) else folder}/metrics.json and metrics.md")


if __name__ == "__main__":
    main()
