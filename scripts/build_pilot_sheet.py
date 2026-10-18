"""Build annotation/pilot_sheet.csv for the week-1 annotation pilot.

Selection (see docs/REVIEW_2026-10-18.md, section 5 step 3):
  * every answer to the seven in-scope Mohler questions with score_avg < 3.5
    (the misconception-candidate pool), plus
  * the 20 highest-scoring answers across the same questions, ties broken by
    normalized answer length, longest first (to populate the `none` class).

Text normalization undoes the Penn-Treebank tokenization of the `cleaned`
split: -LRB- -> "(", -RRB- -> ")", drop <STOP>, collapse whitespace. It is
applied to question, instructor_answer and student_answer alike.

Label columns (primary_label, secondary_label, evidence_span, annotator_notes)
are written empty; a human fills them in following annotation/schema.md.

Usage:
    python scripts/build_pilot_sheet.py [--out annotation/pilot_sheet.csv]
"""

import argparse
import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PARQUET = REPO_ROOT / "data" / "raw" / "mohler" / "cleaned-oe-00001.parquet"
OUT = REPO_ROOT / "annotation" / "pilot_sheet.csv"

IN_SCOPE = ["E03.Q06", "E05.Q04", "E05.Q03", "E10.Q07", "E12.Q10", "E03.Q07", "E11.Q09"]
LOW_SCORE_THRESHOLD = 3.5
N_HIGH = 20
COLUMNS = ["id", "question_id", "question", "instructor_answer", "student_answer", "score_avg",
           "primary_label", "secondary_label", "evidence_span", "annotator_notes"]


def normalize(text: str) -> str:
    text = str(text)
    text = text.replace("-LRB-", "(").replace("-RRB-", ")")
    text = text.replace("<STOP>", " ")
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return " ".join(text.split())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    df = pd.read_parquet(PARQUET)
    df["question_id"] = df["id"].str.extract(r"^(E\d+\.Q\d+)", expand=False)
    df = df[df["question_id"].isin(IN_SCOPE)].copy()
    for col in ("question", "instructor_answer", "student_answer"):
        df[col] = df[col].map(normalize)
    df["score_avg"] = df["score_avg"].astype(float).round(2)

    low = df[df["score_avg"] < LOW_SCORE_THRESHOLD]
    rest = df[df["score_avg"] >= LOW_SCORE_THRESHOLD].copy()
    rest["_len"] = rest["student_answer"].str.len()
    high = rest.sort_values(["score_avg", "_len", "id"], ascending=[False, False, True]).head(N_HIGH)

    sheet = pd.concat([low, high]).drop(columns=["_len"], errors="ignore")
    assert sheet["id"].is_unique, "low and high pools overlap"
    sheet["question_id"] = pd.Categorical(sheet["question_id"], categories=IN_SCOPE, ordered=True)
    sheet = sheet.sort_values(["question_id", "id"]).reset_index(drop=True)
    for col in ("primary_label", "secondary_label", "evidence_span", "annotator_notes"):
        sheet[col] = ""
    sheet = sheet[COLUMNS]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.to_csv(args.out, index=False)

    print(f"Wrote {args.out.relative_to(REPO_ROOT) if args.out.is_relative_to(REPO_ROOT) else args.out}")
    print(f"rows: {len(sheet)}  (low-score < {LOW_SCORE_THRESHOLD}: {len(low)}, top-{N_HIGH} high: {len(high)})")
    print("per-question counts (low / high / total):")
    counts = pd.DataFrame({
        "low": low.groupby("question_id").size(),
        "high": high.groupby("question_id").size(),
    }).reindex(IN_SCOPE).fillna(0).astype(int)
    counts["total"] = counts["low"] + counts["high"]
    print(counts.to_string())


if __name__ == "__main__":
    main()
