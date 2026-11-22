"""Rebuild the derived parts of the retrieval corpus in data/corpus/.

1. instructor_answers.md  one entry per Mohler question id (81), with the question and the
                          instructor's reference answer de-tokenized from the Penn-Treebank
                          form of the `cleaned` split, plus hand-assigned concept tags.
                          Skipped (existing file kept) when the raw parquet is not on disk.
2. chunks.jsonl           every chunk of every source file, in corpus order (id, source,
                          heading, concepts, n_words, text). For inspection and for looking
                          up the chunk ids logged in results/<run_id>/predictions.jsonl.
3. corpus.json            corpus hash, chunker settings and per-file statistics.

The hand-written notes (notes_*.md) are sources, not outputs: this script only reads them.
Student answers are never read; only the `id`, `question` and `instructor_answer` columns are used.

Usage:
    python scripts/build_corpus.py            # rebuild
    python scripts/build_corpus.py --check    # exit 1 if chunks.jsonl / corpus.json are stale
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.retrieval import CORPUS_DIR, instructor_answer_chunk_id, load_corpus  # noqa: E402

PARQUET = REPO_ROOT / "data" / "raw" / "mohler" / "cleaned-oe-00001.parquet"
INSTRUCTOR_ANSWERS = "instructor_answers.md"
CHUNKS = "chunks.jsonl"
CORPUS_JSON = "corpus.json"
N_QUESTIONS = 81

# Concept tags per question id, assigned by hand from the question text (not from any answer).
CONCEPTS: dict[str, list[str]] = {
    "E01.Q01": ["software_engineering"],
    "E01.Q02": ["software_engineering"],
    "E01.Q03": ["oop"],
    "E01.Q04": ["cpp_basics", "functions"],
    "E01.Q05": ["cpp_basics", "variables"],
    "E01.Q06": ["cpp_basics", "variables"],
    "E01.Q07": ["cpp_basics", "iteration"],
    "E02.Q01": ["oop", "classes"],
    "E02.Q02": ["oop", "classes", "variables"],
    "E02.Q03": ["oop", "classes", "functions"],
    "E02.Q04": ["oop", "classes"],
    "E02.Q05": ["oop", "classes"],
    "E02.Q06": ["functions"],
    "E02.Q07": ["oop", "classes"],
    "E03.Q01": ["functions"],
    "E03.Q02": ["variables"],
    "E03.Q03": ["functions"],
    "E03.Q04": ["functions"],
    "E03.Q05": ["functions"],
    "E03.Q06": ["recursion", "infinite_recursion", "base_case"],
    "E03.Q07": ["recursion", "iteration"],
    "E04.Q01": ["arrays"],
    "E04.Q02": ["arrays", "strings"],
    "E04.Q03": ["arrays", "functions"],
    "E04.Q04": ["arrays"],
    "E04.Q05": ["arrays", "functions"],
    "E05.Q01": ["sorting", "insertion_sort"],
    "E05.Q02": ["sorting", "selection_sort"],
    "E05.Q03": ["sorting", "insertion_sort", "algorithm_analysis", "best_case"],
    "E05.Q04": ["sorting", "merge_sort", "recursion", "base_case"],
    "E06.Q01": ["pointers"],
    "E06.Q02": ["pointers"],
    "E06.Q03": ["pointers"],
    "E06.Q04": ["pointers", "arrays"],
    "E06.Q05": ["cpp_basics"],
    "E06.Q06": ["pointers", "functions"],
    "E06.Q07": ["pointers", "functions"],
    "E07.Q01": ["linked_lists"],
    "E07.Q02": ["linked_lists", "arrays"],
    "E07.Q03": ["linked_lists", "arrays"],
    "E07.Q04": ["linked_lists", "functions"],
    "E07.Q05": ["linked_lists"],
    "E07.Q06": ["linked_lists", "algorithm_analysis"],
    "E07.Q07": ["linked_lists"],
    "E08.Q01": ["stacks"],
    "E08.Q02": ["stacks"],
    "E08.Q03": ["stacks", "arrays"],
    "E08.Q04": ["stacks", "linked_lists"],
    "E08.Q06": ["stacks", "expressions"],
    "E08.Q07": ["stacks", "search"],
    "E09.Q01": ["queues"],
    "E09.Q02": ["queues"],
    "E09.Q03": ["queues", "arrays"],
    "E09.Q04": ["queues", "linked_lists"],
    "E09.Q06": ["queues", "stacks"],
    "E10.Q01": ["trees"],
    "E10.Q02": ["trees", "tree_height"],
    "E10.Q03": ["trees"],
    "E10.Q04": ["trees"],
    "E10.Q05": ["trees", "bst"],
    "E10.Q06": ["trees", "traversal"],
    "E10.Q07": ["trees", "bst", "search", "tree_height", "algorithm_analysis"],
    "E11.Q01": ["oop", "classes"],
    "E11.Q02": ["oop", "classes"],
    "E11.Q03": ["oop", "classes"],
    "E11.Q04": ["functions"],
    "E11.Q05": ["recursion", "definition"],
    "E11.Q06": ["recursion", "iteration"],
    "E11.Q07": ["arrays"],
    "E11.Q08": ["arrays", "strings"],
    "E11.Q09": ["recursion", "divide_and_conquer"],
    "E11.Q10": ["sorting", "merge_sort", "divide_and_conquer"],
    "E12.Q01": ["pointers"],
    "E12.Q02": ["algorithm_analysis"],
    "E12.Q04": ["sorting", "selection_sort"],
    "E12.Q05": ["linked_lists", "arrays"],
    "E12.Q06": ["queues"],
    "E12.Q07": ["stacks"],
    "E12.Q08": ["trees", "traversal"],
    "E12.Q09": ["trees", "bst"],
    "E12.Q10": ["trees", "bst", "search", "tree_height", "algorithm_analysis"],
}

FRONT_MATTER = """---
source: mohler_instructor_answers
title: "Instructor reference answers"
course: "C++ data structures (University of North Texas)"
provenance: "Instructor answers from the Mohler ASAG dataset (Mohler, Bunescu & Mihalcea 2011; Hugging Face nkazi/MohlerASAG, cleaned open-ended split, CC-BY-4.0), de-tokenized. Generated by scripts/build_corpus.py; do not edit by hand."
default_concepts: [course_reference]
---

# Instructor reference answers
"""


def detokenize(text: str) -> str:
    """Undo the Penn-Treebank tokenization of Mohler's `cleaned` split.

    Parentheses, <STOP> and whitespace are handled as in scripts/build_pilot_sheet.py; on top
    of that, the operator placeholders, "C plus plus", "i. e." and the space the tokenizer puts
    before punctuation are restored. For the seven in-scope questions the result differs from
    annotation/pilot_sheet.csv only by that space before punctuation ("tree) ." in the sheet,
    "tree)." here). Spelling is left as in the source.
    """
    text = str(text)
    text = text.replace("-LRB- ADDRESS -RRB-", "(&)").replace("-LRB- STAR -RRB-", "(*)")
    text = text.replace("-LRB-", "(").replace("-RRB-", ")").replace("<STOP>", " ")
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = text.replace("C plus plus", "C++").replace("i. e.", "i.e.")
    text = re.sub(r"\s+('s)\b", r"\1", text)
    text = re.sub(r"\s+([.,;:?!])", r"\1", text)
    text = text.replace("do... while", "do ... while")       # keep the C++ keyword pair readable
    return " ".join(text.split())


def read_questions() -> list[tuple[str, str, str]]:
    import pandas as pd

    df = pd.read_parquet(PARQUET, columns=["id", "question", "instructor_answer"])
    df["question_id"] = df["id"].str.extract(r"^(E\d+\.Q\d+)", expand=False)
    out = []
    for qid, grp in df.groupby("question_id", sort=True):
        if grp["question"].nunique() != 1 or grp["instructor_answer"].nunique() != 1:
            raise SystemExit(f"{qid}: question or instructor answer is not unique across its rows")
        out.append((qid, detokenize(grp["question"].iloc[0]), detokenize(grp["instructor_answer"].iloc[0])))
    return out


def render_instructor_answers(questions: list[tuple[str, str, str]]) -> str:
    if len(questions) != N_QUESTIONS:
        raise SystemExit(f"expected {N_QUESTIONS} questions, found {len(questions)}")
    missing = [qid for qid, _, _ in questions if qid not in CONCEPTS]
    extra = sorted(set(CONCEPTS) - {qid for qid, _, _ in questions})
    if missing or extra:
        raise SystemExit(f"CONCEPTS out of sync with the dataset: missing {missing}, extra {extra}")
    parts = [FRONT_MATTER]
    for qid, question, answer in questions:
        parts.append(f"## {qid}\n<!-- chunk: {instructor_answer_chunk_id(qid)} | concepts: {', '.join(CONCEPTS[qid])} -->\n\n"
                     f"Question: {question}\n\nInstructor answer: {answer}\n")
    return "\n".join(parts)


def derived_files(corpus) -> dict[str, str]:
    chunks = "".join(json.dumps(c.to_dict(), ensure_ascii=False) + "\n" for c in corpus.chunks)
    words = [c.n_words for c in corpus.chunks]
    summary = {"corpus_hash": corpus.hash, "n_chunks": len(corpus), "chunker": corpus.params,
               "words_per_chunk": {"min": min(words), "max": max(words), "total": sum(words)},
               "files": corpus.files}
    return {CHUNKS: chunks, CORPUS_JSON: json.dumps(summary, indent=2, ensure_ascii=False) + "\n"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus-dir", type=Path, default=CORPUS_DIR)
    ap.add_argument("--check", action="store_true", help="verify the derived files instead of writing them")
    args = ap.parse_args()
    corpus_dir: Path = args.corpus_dir

    stale: list[str] = []
    if PARQUET.exists():
        text = render_instructor_answers(read_questions())
        target = corpus_dir / INSTRUCTOR_ANSWERS
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != text:
                stale.append(INSTRUCTOR_ANSWERS)
        else:
            target.write_text(text, encoding="utf-8")
            print(f"wrote {target.relative_to(REPO_ROOT)} ({N_QUESTIONS} questions)")
    else:
        print(f"note: {PARQUET.relative_to(REPO_ROOT)} not found; keeping the existing {INSTRUCTOR_ANSWERS}")

    corpus = load_corpus(corpus_dir)
    for name, text in derived_files(corpus).items():
        target = corpus_dir / name
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            target.write_text(text, encoding="utf-8")
            print(f"wrote {target.relative_to(REPO_ROOT)}")

    print(f"corpus_hash {corpus.hash}")
    print(f"{len(corpus)} chunks")
    for f in corpus.files:
        sizes = [c.n_words for c in corpus.chunks if c.path == f["path"]]
        print(f"  {f['path']}: {f['n_chunks']} chunks, {f['n_words']} words "
              f"(per chunk min {min(sizes)}, max {max(sizes)})")
    if stale:
        raise SystemExit(f"stale: {', '.join(stale)}. Run `python scripts/build_corpus.py`.")


if __name__ == "__main__":
    main()
