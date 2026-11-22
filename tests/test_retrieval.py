"""Corpus chunking, BM25 ranking, chunk exclusion and the optional dense backend."""

import json
import math
import re

import pytest

from src import retrieval as R

DOC = """---
source: demo
title: "Demo notes"
default_concepts: [demo]
---

# Demo

## First topic
<!-- chunk: demo.first | concepts: alpha, beta -->

Alpha paragraph one
wrapped over two lines.

```cpp
#include <iostream>

# not a heading
int main() { return 0; }
```

## Second topic

Second topic text.

### A sub topic

Sub topic text.
"""


def words(n: int, word: str = "w") -> str:
    return " ".join(f"{word}{i}" for i in range(n))


# -- chunking ------------------------------------------------------------------

def test_chunk_markdown_headings_ids_tags_and_code_fences():
    chunks = R.chunk_markdown(DOC, path="demo.md")
    assert [c.id for c in chunks] == ["demo.first", "demo.second-topic", "demo.second-topic-a-sub-topic"]
    first, second, sub = chunks
    assert first.source == "demo" and first.title == "Demo notes" and first.path == "demo.md"
    assert first.heading == "First topic" and first.concepts == ("alpha", "beta")
    assert first.text.startswith("Alpha paragraph one wrapped over two lines.")       # prose is unwrapped
    assert "#include <iostream>\n\n# not a heading\nint main()" in first.text           # fence kept verbatim
    assert "<!--" not in first.text and "chunk:" not in first.text
    assert second.concepts == ("demo",) and second.text == "Second topic text."        # default tags, slug id
    assert sub.heading == "Second topic > A sub topic" and sub.label == "Demo notes > Second topic > A sub topic"
    assert all(c.n_words == len(c.text.split()) for c in chunks)


def test_sections_are_packed_by_paragraph_and_never_merged():
    body = "\n\n".join(words(100, f"p{i}") for i in range(5))        # five 100-word paragraphs
    doc = f"---\nsource: s\n---\n\n## Long\n<!-- chunk: s.long -->\n\n{body}\n\n## Short\n\ntiny section\n"
    chunks = R.chunk_markdown(doc, min_words=150, max_words=250)
    assert [c.id for c in chunks] == ["s.long.1", "s.long.2", "s.long.3", "s.short"]
    assert [c.n_words for c in chunks] == [200, 200, 100, 2]         # 100-word tail is not folded (>= min/2)
    assert chunks[0].text.split()[0] == "p00" and chunks[1].text.split()[0] == "p20"

    body = "\n\n".join([words(120, "a"), words(120, "b"), words(40, "c")])
    doc = f"---\nsource: s\n---\n\n## Tail\n\n{body}\n"
    chunks = R.chunk_markdown(doc, min_words=150, max_words=250)
    assert [c.n_words for c in chunks] == [280] and chunks[0].id == "s.tail"   # short tail folded in


def test_chunking_is_stable_under_repeats_and_unrelated_edits():
    base = R.chunk_markdown(DOC, path="demo.md")
    assert R.chunk_markdown(DOC, path="demo.md") == base
    assert R.corpus_hash(base) == R.corpus_hash(R.chunk_markdown(DOC, path="demo.md"))

    appended = R.chunk_markdown(DOC + "\n## Third topic\n\nNew text.\n", path="demo.md")
    assert appended[:3] == base and appended[3].id == "demo.third-topic"

    edited = R.chunk_markdown(DOC.replace("Second topic text.", "Second topic text.\n\nOne more paragraph."),
                              path="demo.md")
    assert [c.id for c in edited] == [c.id for c in base]
    assert edited[0] == base[0] and edited[2] == base[2] and edited[1] != base[1]
    assert R.corpus_hash(edited) != R.corpus_hash(base)


def test_front_matter_is_required_and_malformed_sources_raise(tmp_path):
    with pytest.raises(R.CorpusError, match="source"):
        R.chunk_markdown("# No front matter\n\ntext\n")
    with pytest.raises(R.CorpusError, match="fence"):
        R.chunk_markdown("---\nsource: s\n---\n\n## H\n\n```\nnever closed\n")
    (tmp_path / "a.md").write_text(DOC)
    (tmp_path / "README.md").write_text("# Readme\n\nNot a source: no front matter.\n")
    corpus = R.load_corpus(tmp_path)
    assert [f["path"] for f in corpus.files] == ["a.md"] and len(corpus) == 3
    (tmp_path / "b.md").write_text(DOC.replace("source: demo", "source: other"))    # same explicit chunk id
    with pytest.raises(R.CorpusError, match="duplicate chunk id"):
        R.load_corpus(tmp_path)
    (tmp_path / "b.md").write_text(DOC)                                              # same source name
    with pytest.raises(R.CorpusError, match="share source"):
        R.load_corpus(tmp_path)
    with pytest.raises(R.CorpusError, match="no corpus sources"):
        R.load_corpus(tmp_path / "missing")


# -- the real corpus -------------------------------------------------------------

@pytest.fixture(scope="module")
def corpus():
    return R.load_corpus()


@pytest.fixture(scope="module")
def bm25(corpus):
    return R.Retriever(corpus)


def test_real_corpus_structure(corpus):
    assert [f["path"] for f in corpus.files] == ["instructor_answers.md", "notes_algorithm_analysis.md",
                                                 "notes_recursion.md"]       # README / retrieval_notes not indexed
    ids = corpus.ids()
    assert len(ids) == len(set(ids)) == len(corpus)
    answers = [c for c in corpus.chunks if c.source == "mohler_instructor_answers"]
    notes = [c for c in corpus.chunks if c.source.startswith("notes_")]
    assert len(answers) == 81 and len(answers) + len(notes) == len(corpus)
    assert all(re.fullmatch(r"ia\.E\d\d\.Q\d\d", c.id) and c.text.startswith("Question: ")
               and "\n\nInstructor answer: " in c.text for c in answers)
    assert all("-LRB-" not in c.text and "<STOP>" not in c.text for c in answers)
    for qid in ("E03.Q06", "E03.Q07", "E05.Q03", "E05.Q04", "E10.Q07", "E11.Q09", "E12.Q10"):
        assert R.instructor_answer_chunk_id(qid) in corpus
    assert len(notes) >= 16
    for c in notes:
        assert R.CHUNK_MIN_WORDS <= c.n_words <= R.CHUNK_MAX_WORDS, (c.id, c.n_words)
        assert re.fullmatch(r"(rec|ana)\.[a-z0-9-]+", c.id), c.id       # explicit ids, one chunk per section
    assert all(c.source and c.concepts and c.heading for c in corpus.chunks)
    # the course conventions for the in-scope questions are in the notes, in the instructor's words
    text = " ".join(R.tokenize(" ".join(c.text for c in notes)))
    for phrase in ("when the size of the array to be sorted is 1 (or 2)",
                   "if the recursion step is defined incorrectly, or if the base case is not included",
                   "divide a problem into smaller subproblems, solve them recursively, and then combine the solutions"):
        assert " ".join(R.tokenize(phrase)) in text, phrase


def test_real_corpus_is_stable_and_matches_the_derived_files(corpus):
    again = R.load_corpus()
    assert again.chunks == corpus.chunks and again.hash == corpus.hash and len(corpus.hash) == 64
    on_disk = [json.loads(line) for line in (R.CORPUS_DIR / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert on_disk == [c.to_dict() for c in corpus.chunks], "run `python scripts/build_corpus.py`"
    summary = json.loads((R.CORPUS_DIR / "corpus.json").read_text(encoding="utf-8"))
    assert summary["corpus_hash"] == corpus.hash and summary["n_chunks"] == len(corpus)


@pytest.mark.parametrize("query,expected", [
    ("when does a recursive merge sort stop splitting, an array of one or two elements", "rec.merge-sort-base-case"),
    ("each call gets its own stack frame with its own local variables", "rec.call-stack"),
    ("what does last in first out mean for a stack", "ia.E08.Q01"),
])
def test_bm25_ranks_the_obviously_relevant_chunk_first(bm25, query, expected):
    hits = bm25.retrieve(query, 4)
    assert hits[0].chunk.id == expected
    assert [h.rank for h in hits] == [1, 2, 3, 4]
    assert all(a.score >= b.score for a, b in zip(hits, hits[1:])) and hits[0].score > hits[1].score


def test_retrieval_is_deterministic_and_respects_k(bm25):
    q = "how many comparisons to find an element in a binary search tree"
    first = bm25.retrieve(q, 5)
    assert bm25.retrieve(q, 5) == first and R.Retriever(R.load_corpus()).retrieve(q, 5) == first
    assert bm25.retrieve(q, 2) == first[:2] and bm25.retrieve(q, 0) == []
    assert bm25.retrieve("zzzz qqqq", 5) == []                      # no query term in the corpus: no hits
    assert first[0].to_log() == {"id": first[0].chunk.id, "score": first[0].score, "rank": 1}


def test_chunk_exclusion(bm25):
    q = "what is the base case for a recursive implementation of merge sort"
    full = bm25.retrieve(q, 5)
    top = full[0].chunk.id
    without = bm25.retrieve(q, 4, exclude=[top])
    assert top not in [h.chunk.id for h in without]
    # the others keep their order and their scores; only the ranks move up
    assert [(h.chunk.id, h.score) for h in without] == [(h.chunk.id, h.score) for h in full[1:]]
    assert [h.rank for h in without] == [1, 2, 3, 4]
    two = bm25.retrieve(q, 3, exclude={full[0].chunk.id, full[2].chunk.id})
    assert [h.chunk.id for h in two] == [full[1].chunk.id, full[3].chunk.id, full[4].chunk.id]
    with pytest.raises(KeyError, match="no.such.chunk"):
        bm25.retrieve(q, 3, exclude=["no.such.chunk"])


def test_build_query_is_question_plus_student_answer():
    row = {"question": " What is a stack? ", "student_answer": " last in first out\n"}
    assert R.build_query(row) == "What is a stack? last in first out"


# -- BM25 on a hand-made index -----------------------------------------------------

def test_tokenize_and_bm25_scores_by_hand():
    assert R.tokenize("The Trees' copies, and the classes: O(n log n)!") == ["tree", "copy", "classe", "o", "n", "log", "n"]
    docs = [["tree", "search"], ["tree", "tree", "sort"], ["loop"]]
    index = R.BM25Index(docs, k1=1.5, b=0.75)
    scores = index.scores(["tree"])
    idf = math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))
    assert scores[0] == pytest.approx(idf * 1 * 2.5 / (1 + 1.5 * (0.25 + 0.75 * 2 / 2)))
    assert scores[1] == pytest.approx(idf * 2 * 2.5 / (2 + 1.5 * (0.25 + 0.75 * 3 / 2)))
    assert scores[2] == 0.0 and index.scores(["absent"]) == [0.0, 0.0, 0.0]
    assert index.scores(["tree", "tree"]) == scores                    # query terms count once


# -- dense backend (fake embedder / fake Ollama) ------------------------------------

class FakeEmbedder:
    model = "fake-embed"

    def embed(self, texts):
        return [[float("recursion" in t.lower()), float("tree" in t.lower()), 0.1] for t in texts]


def test_dense_backend_ranks_by_cosine_and_supports_exclusion():
    doc = "---\nsource: s\n---\n\n## Recursion\n\nrecursion calls\n\n## Trees\n\ntree height\n\n## Other\n\nqueues\n"
    corpus = R.Corpus(chunks=R.chunk_markdown(doc), hash="h", files=[], params={})
    dense = R.Retriever(corpus, "dense", embedder=FakeEmbedder())
    hits = dense.retrieve("how tall is a tree", 3)
    assert [h.chunk.id for h in hits] == ["s.trees", "s.other", "s.recursion"]
    assert [h.chunk.id for h in dense.retrieve("how tall is a tree", 2, exclude=["s.trees"])] == ["s.other", "s.recursion"]
    assert dense.describe()["backend"] == "dense" and dense.describe()["embedding_model"] == "fake-embed"
    with pytest.raises(ValueError, match="unknown retrieval backend"):
        R.Retriever(corpus, "faiss")


def fake_ollama(models: dict[str, list[str]]):
    """A stand-in for _http_json: ``models`` maps installed model name -> capabilities."""
    calls = []

    def http(url, payload=None, timeout=0.0):
        calls.append((url, payload))
        if url.endswith("/api/tags"):
            return {"models": [{"name": name, "details": {"family": "x"}} for name in models]}
        if url.endswith("/api/show"):
            return {"capabilities": models[payload["model"]]}
        if url.endswith("/api/embed"):
            return {"embeddings": [[1.0, float(len(t))] for t in payload["input"]]}
        raise AssertionError(url)

    http.calls = calls
    return http


def test_ollama_embedder_only_uses_installed_embedding_models():
    http = fake_ollama({"gpt-oss:20b": ["completion", "tools"], "nomic-embed-text:latest": ["embedding"]})
    emb = R.OllamaEmbedder(base_url="http://localhost:11434", http=http)
    assert emb.model == "nomic-embed-text:latest"
    assert emb.embed(["ab", "abcd"]) == [[1.0, 2.0], [1.0, 4.0]]
    assert not any(url.endswith(("/api/pull", "/api/create")) for url, _ in http.calls)

    with pytest.raises(RuntimeError, match="none is\\s+installed"):
        R.OllamaEmbedder(base_url="http://localhost:11434", http=fake_ollama({"gpt-oss:20b": ["completion"]}))
    with pytest.raises(RuntimeError, match="not installed"):
        R.OllamaEmbedder(model="mxbai-embed-large", base_url="http://localhost:11434",
                         http=fake_ollama({"nomic-embed-text:latest": ["embedding"]}))

    def unreachable(url, payload=None, timeout=0.0):
        raise OSError("connection refused")

    with pytest.raises(RuntimeError, match="not reachable"):
        R.OllamaEmbedder(base_url="http://localhost:11434", http=unreachable)
