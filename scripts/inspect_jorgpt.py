"""Print the schema, unique questions, and sample rows of every data file in data/raw/.

Column names are discovered, not assumed. A question-ID / question-text column is
guessed from column names containing "question"; override with
--question-id-col / --question-text-col.

Usage:
    python scripts/inspect_jorgpt.py [--file NAME] [--samples N]
"""

import argparse
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
READERS = {
    ".csv": pd.read_csv,
    ".tsv": lambda p: pd.read_csv(p, sep="\t"),
    ".json": pd.read_json,
    ".jsonl": lambda p: pd.read_json(p, lines=True),
    ".parquet": pd.read_parquet,
    ".xlsx": pd.read_excel,
}
TRUNC = 160


def short(value) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= TRUNC else text[:TRUNC] + "..."


def guess_question_cols(df: pd.DataFrame) -> tuple[str | None, str | None]:
    """Guess (id column, text column) among columns whose name mentions 'question'."""
    candidates = [c for c in df.columns if "question" in c.lower()]
    id_col = text_col = None
    for c in candidates:
        mean_len = df[c].astype(str).str.len().mean()
        if mean_len < 40 and id_col is None:
            id_col = c
        elif mean_len >= 40 and text_col is None:
            text_col = c
    return id_col, text_col


def inspect(path: Path, n_samples: int, id_col: str | None, text_col: str | None) -> None:
    df = READERS[path.suffix.lower()](path)
    print(f"\n{'=' * 80}\nFILE: {path.name}\n{'=' * 80}")
    print(f"Rows: {len(df)}   Columns: {len(df.columns)}\n")

    print("Schema (column, dtype, non-null, unique):")
    for c in df.columns:
        print(f"  {c:<28} {str(df[c].dtype):<10} {df[c].notna().sum():>6} {df[c].nunique():>6}")

    guessed_id, guessed_text = guess_question_cols(df)
    id_col = id_col or guessed_id
    text_col = text_col or guessed_text
    print(f"\nQuestion ID column: {id_col!r}   Question text column: {text_col!r}")

    if id_col and id_col in df.columns:
        print(f"\nUnique questions ({df[id_col].nunique()}):")
        group = df.groupby(id_col, sort=False)
        for qid, g in group:
            texts = g[text_col].dropna().unique() if text_col in df.columns else []
            label = short(texts[0]) if len(texts) else ""
            more = f" [{len(texts)} distinct texts]" if len(texts) > 1 else ""
            print(f"  {qid}  n={len(g):<4} {label}{more}")
    else:
        print("\nNo question ID column found; pass --question-id-col.")

    print(f"\nSample rows ({n_samples}):")
    for i, (_, row) in enumerate(df.sample(min(n_samples, len(df)), random_state=0).iterrows()):
        print(f"\n--- sample {i + 1} ---")
        for c in df.columns:
            print(f"  {c}: {short(row[c])}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", help="only inspect this file in data/raw/")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--question-id-col")
    parser.add_argument("--question-text-col")
    args = parser.parse_args()

    files = sorted(p for p in RAW_DIR.rglob("*") if p.suffix.lower() in READERS)
    if args.file:
        files = [p for p in files if p.name == args.file]
    if not files:
        raise SystemExit(f"No data files found in {RAW_DIR}")
    for path in files:
        inspect(path, args.samples, args.question_id_col, args.question_text_col)


if __name__ == "__main__":
    main()
