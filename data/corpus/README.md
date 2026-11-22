# data/corpus/

The retrieval corpus for conditions 2 and up: the "course material" that
`src/retrieval.py` chunks, indexes and retrieves from. It is small on purpose, so that
every fact in it is known and the withheld-chunk positive control is easy to build
(docs/REVIEW_2026-10-18.md, G4 and section 6.2).

## Files

| File | Role | Written by |
|---|---|---|
| `notes_recursion.md` | Course notes on recursion: definition, base case and recursive step, convergence, causes of infinite recursion, the call stack, what happens after a recursive call returns, iteration versus recursion, divide and conquer, merge sort and its base case. 11 sections. | hand (source) |
| `notes_algorithm_analysis.md` | Course notes on algorithm analysis: counting operations, best / average / worst case, best case as an arrangement and not a size, asymptotic notation, costs of insertion sort, selection sort and merge sort, binary search tree search cost as height, balanced versus degenerate trees, linear scan versus tree search. 10 sections. | hand (source) |
| `instructor_answers.md` | The instructor's reference answer to each of the 81 Mohler questions, one entry per question id, de-tokenized. | `scripts/build_corpus.py` |
| `chunks.jsonl` | Every chunk in corpus order: `id`, `source`, `title`, `heading`, `concepts`, `n_words`, `path`, `text`. Use it to look up the chunk ids logged in `results/<run_id>/predictions.jsonl`. | `scripts/build_corpus.py` |
| `corpus.json` | Corpus hash, chunker settings, per-file statistics. | `scripts/build_corpus.py` |
| `retrieval_notes.md` | For each in-scope question, the corpus facts that are course-specific, and the chunks to withhold in the positive control. Documentation, never indexed. | hand |
| `README.md` | This file. Never indexed. | hand |

Only Markdown files that begin with YAML front matter containing a `source` key are
corpus sources. `README.md` and `retrieval_notes.md` have no front matter, so they can
never be retrieved.

## Provenance

**Course notes (`notes_*.md`).** Original text written for this project on 2026-11-22 by
Claude (Anthropic's AI assistant) at the project author's request, in the voice of an
instructor of a C++ data structures course. Nothing was copied or adapted from a textbook,
from OpenDSA, or from the web, and no student answer or model output was used. The notes
are about 2,400 words per concept (4,800 in total, 21 chunks).

The notes state this course's conventions in the words of the Mohler instructor answers
for the seven in-scope questions:

| Question | Convention as stated by the instructor | Chunk |
|---|---|---|
| E03.Q06 | Infinite recursion: "If the recursion step is defined incorrectly, or if the base case is not included." | `rec.infinite-recursion` |
| E03.Q07 | "They both involve repetition; they both have termination tests; they can both occur infinitely." | `rec.iteration-similarities` |
| E05.Q03 | "N (the length of the array) operations achieved for a sorted array." | `ana.insertion-sort` |
| E05.Q04 | "When the size of the array to be sorted is 1 (or 2)" | `rec.merge-sort-base-case` |
| E10.Q07 | "The height of the tree (or log of the number of elements in the tree)." | `ana.bst-search-height` |
| E12.Q10 | "The height of the tree." | `ana.bst-search-height` |
| E11.Q09 | "Divide a problem into smaller subproblems, solve them recursively, and then combine the solutions into a solution for the original problem." | `rec.divide-and-conquer` |

They also reuse the instructor's wording for related questions (E05.Q01, E05.Q02, E10.Q02,
E10.Q05, E11.Q05, E11.Q06, E11.Q10, E12.Q02, E12.Q04). Everything else in the notes is an
elaboration that is consistent with those answers but is **not** in the dataset.
`retrieval_notes.md` marks each fact as `Mohler` or `authored` and lists the authored
statements that take a position a grader could disagree with.

**Instructor answers (`instructor_answers.md`).** From the Mohler ASAG dataset (Mohler,
Bunescu & Mihalcea 2011; University of North Texas data structures course; Hugging Face
`nkazi/MohlerASAG`, cleaned open-ended split, CC-BY-4.0; raw file
`data/raw/mohler/cleaned-oe-00001.parquet`, gitignored). Only the `id`, `question` and
`instructor_answer` columns are read; student answers are never read. The Penn-Treebank
tokenization is undone: `-LRB-`/`-RRB-` become parentheses, `<STOP>` is dropped,
`-LRB- ADDRESS -RRB-` and `-LRB- STAR -RRB-` become `(&)` and `(*)`, "C plus plus" becomes
"C++", "i. e." becomes "i.e.", and the space before punctuation is removed. Spelling is
left as in the source. For the seven in-scope questions the text matches
`annotation/pilot_sheet.csv` except for that space before punctuation. Concept tags are
assigned by hand from the question text (`CONCEPTS` in `scripts/build_corpus.py`).

## Format of a source file

```markdown
---
source: notes_recursion            # source name carried by every chunk of the file
title: "Course notes: Recursion"
default_concepts: [recursion]      # tags for sections without their own
---

# Recursion

## The base case of merge sort
<!-- chunk: rec.merge-sort-base-case | concepts: recursion, merge_sort, base_case -->

Paragraphs, separated by blank lines. Fenced code blocks are kept whole.
```

Chunking (`src/retrieval.py`): every heading starts a section and sections are never
merged; inside a section whole paragraphs are packed into chunks of at most 250 words
(target 150 to 250), and a tail shorter than 75 words is folded into the previous chunk.
The comment line under a heading gives the section a stable id and concept tags. A
section that needs more than one chunk gets `<id>.1`, `<id>.2`, and so on; the notes are
written so that each section is exactly one chunk, and `tests/test_retrieval.py` enforces
it. Each instructor answer is its own short chunk, `ia.<question id>`.

Writing rules for the notes: plain prose with no bold, italics or inline code, because
models cite evidence by copying text and the citation check is a verbatim match after
whitespace normalization; code goes in fenced blocks; one topic per section; keep each
section between 150 and 250 words.

## Rebuild

```bash
.venv/bin/python scripts/build_corpus.py
```

This regenerates `instructor_answers.md` (only if the raw parquet is on disk; otherwise
the existing file is kept), then re-chunks everything and rewrites `chunks.jsonl` and
`corpus.json`. Run it after any edit to a notes file.

```bash
.venv/bin/python scripts/build_corpus.py --check
```

exits with status 1 if the derived files are stale; `tests/test_retrieval.py` makes the
same check.

```bash
.venv/bin/python -m src.retrieval "what is the base case of merge sort" --k 4
```

prints the top chunks for a query (omit the query for corpus statistics).

## Corpus hash

`corpus.json` holds the current hash: a SHA-256 over the ids, sources, titles, headings,
concept tags and texts of all chunks, in order. Every run of conditions 2 and 3 records it
in `manifest.json` under `retrieval.corpus_hash`, next to the backend and k. Two runs are
comparable only if their corpus hashes are equal. Any edit to a notes file, to the
instructor answers, to a chunk id or tag, or to the chunker changes the hash, so treat
the corpus like a prompt template: once runs that will be reported have used it, do not
edit it in place without re-running them.

## Retrieval

- Query: question plus student answer.
- Default backend: BM25 (`k1 = 1.5`, `b = 0.75`; lower-cased alphanumeric tokens, a small
  stopword list, plural stripping), implemented in `src/retrieval.py`. Deterministic; ties
  are broken by corpus order; no model and no download.
- Optional backend: `dense`, cosine similarity over embeddings from Ollama's `/api/embed`.
  It is used only if an embedding model is already installed (looked up through
  `/api/tags` and `/api/show`); nothing is ever pulled. As of 2026-11-22 no embedding
  model is installed on the project machine, so the dense path has been exercised only
  with a fake embedder in the tests.
- Default k: 4.
- The row's own instructor-answer chunk is withheld by default, because that reference
  answer is already in the prompt (`--keep-own-reference` turns this off).
- `Retriever.retrieve(query, k, exclude=[chunk ids])` and `--exclude-chunk ID` withhold
  chunks. The scores of the remaining chunks do not change, and an unknown id is an error.
