"""Flag questions likely about recursion or Big-O, using the keyword list in configs/.

This is only a first-pass filter for human review. For each dataset in
configs/datasets.yaml, the configured text fields are scanned per question ID
(across all of that dataset's files, e.g. JorGPT EN + ES). Matched keywords are
recorded so false positives are easy to spot. Writes
data/processed/scope_report.md.

Usage:
    python scripts/filter_scope.py [--dataset NAME ...]
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from src.config import load_config  # noqa: E402

RAW_DIR = REPO_ROOT / "data" / "raw"
REPORT = REPO_ROOT / "data" / "processed" / "scope_report.md"
READERS = {".csv": pd.read_csv, ".parquet": pd.read_parquet, ".jsonl": lambda p: pd.read_json(p, lines=True)}


def compile_concepts(cfg: dict) -> dict[str, list[tuple[str, re.Pattern]]]:
    compiled = {}
    for concept, spec in cfg["concepts"].items():
        rules = [(t, re.compile(rf"(?<!\w){re.escape(t)}(?!\w)", re.IGNORECASE)) for t in spec.get("terms", [])]
        rules += [(p, re.compile(p, re.IGNORECASE)) for p in spec.get("patterns", [])]
        compiled[concept] = rules
    return compiled


def one_line(text: str, limit: int = 400) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "..."


def question_ids(df: pd.DataFrame, spec) -> pd.Series:
    if isinstance(spec, str):
        return df[spec]
    return df[spec["column"]].astype(str).str.extract(spec["regex"], expand=False)


def scan_dataset(name: str, ds: dict, concepts: dict) -> dict:
    files = sorted(RAW_DIR.glob(ds["files"]))
    if not files:
        raise SystemExit(f"[{name}] no files match data/raw/{ds['files']}")

    texts = defaultdict(lambda: defaultdict(set))   # qid -> file -> {question texts}
    hits = defaultdict(lambda: defaultdict(set))    # qid -> concept -> {matched keyword}
    n_responses = {}
    for path in files:
        df = READERS[path.suffix.lower()](path)
        for tok in ds.get("strip_tokens", []):
            df = df.replace(re.escape(tok), " ", regex=True)
        needed = [ds["question_text"], *ds["scan_fields"]]
        missing = [c for c in needed if c not in df.columns]
        if missing:
            raise SystemExit(f"[{name}] {path.name} is missing {missing}; columns are {list(df.columns)}")
        df = df.assign(_qid=question_ids(df, ds["question_id"]))
        for qid, g in df.groupby("_qid", sort=True):
            n_responses[qid] = max(n_responses.get(qid, 0), len(g))
            texts[qid][path.name].update(" ".join(t.split()) for t in g[ds["question_text"]].dropna().unique())
            blob = " ".join(str(v) for f in ds["scan_fields"] for v in g[f].dropna().unique())
            for concept, rules in concepts.items():
                for label, rx in rules:
                    if rx.search(blob):
                        hits[qid][concept].add(label)
    return {"files": files, "texts": texts, "hits": hits, "n": n_responses}


def report_section(name: str, ds: dict, r: dict, concepts: dict) -> list[str]:
    n, hits, texts = r["n"], r["hits"], r["texts"]
    in_scope = [q for q in n if hits[q]]
    lines = [
        f"## Dataset: {name}",
        "",
        f"- Source: {ds.get('source', 'TODO')}",
        f"- Files scanned: {', '.join(p.relative_to(RAW_DIR).as_posix() for p in r['files'])}",
        f"- Fields scanned: {', '.join(ds['scan_fields'])}",
        f"- Questions total: {len(n)}",
        f"- Responses total (max across files): {sum(n.values())}",
        f"- **Questions flagged in scope: {len(in_scope)}**",
        f"- **Responses to flagged questions: {sum(n[q] for q in in_scope)}**",
    ]
    for concept in concepts:
        qs = [q for q in in_scope if concept in hits[q]]
        lines.append(f"- {concept}: {len(qs)} questions, {sum(n[q] for q in qs)} responses")
    lines += ["", f"### Flagged questions ({name})", ""]
    if not in_scope:
        lines.append("None.")
    else:
        lines += ["| question_id | responses | concepts | matched keywords | question_text |", "|---|---|---|---|---|"]
        for q in in_scope:
            all_texts = [t for ts in texts[q].values() for t in ts]
            shortest = min(all_texts, key=len) if all_texts else ""
            kws = "; ".join(f"{c}: {', '.join(sorted(k))}" for c, k in hits[q].items())
            lines.append(f"| {q} | {n[q]} | {', '.join(hits[q])} | {kws} | {one_line(shortest, 300).replace('|', '/')} |")
    lines += ["", f"### All questions ({name}, for manual review)", "",
              "| question_id | responses | flagged | question_text |", "|---|---|---|---|"]
    for q in n:
        # Prefer the shortest text across files (JorGPT's EN column sometimes holds answer-like text).
        all_texts = [t for ts in texts[q].values() for t in ts]
        shortest = min(all_texts, key=len) if all_texts else ""
        lines.append(f"| {q} | {n[q]} | {', '.join(hits[q])} | {one_line(shortest, 200).replace('|', '/')} |")
    lines.append("")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", nargs="*", help="dataset names from configs/datasets.yaml (default: all)")
    args = parser.parse_args()

    concepts = compile_concepts(load_config("scope_keywords"))
    datasets = load_config("datasets")
    names = args.dataset or list(datasets)

    lines = [
        "# Scope report: recursion / Big-O (first-pass keyword filter)",
        "",
        "Generated by `scripts/filter_scope.py` using `configs/scope_keywords.yaml` and `configs/datasets.yaml`.",
        "Keyword matches are candidates for **manual review**, not final scope decisions.",
        "",
    ]
    for name in names:
        r = scan_dataset(name, datasets[name], concepts)
        lines += report_section(name, datasets[name], r, concepts)
        flagged = [q for q in r["n"] if r["hits"][q]]
        print(f"[{name}] questions flagged: {len(flagged)} / {len(r['n'])}; "
              f"responses: {sum(r['n'][q] for q in flagged)} / {sum(r['n'].values())}")
        for q in flagged:
            print(f"  {q} n={r['n'][q]} {dict((c, sorted(k)) for c, k in r['hits'][q].items())}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"Wrote {REPORT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
