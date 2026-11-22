"""Retrieval over the course-material corpus in data/corpus/ (conditions 2 and up).

Corpus sources are the Markdown files in data/corpus/ that start with YAML front
matter containing a ``source`` key (README.md and retrieval_notes.md have none
and are never indexed). Chunking is by heading and paragraph:

  * every heading starts a new section; sections are never merged;
  * within a section, whole paragraphs (and whole fenced code blocks) are packed
    greedily into chunks of at most ``max_words`` words (default 250; target
    range 150 to 250), and a short tail is folded into the previous chunk;
  * a comment line directly under a heading, ``<!-- chunk: <id> | concepts: a, b -->``,
    gives the section a stable id and concept tags. Without it the id is
    ``<source>.<slug of the heading path>`` and the tags are the file's
    ``default_concepts``. A section that yields several chunks numbers them
    ``<id>.1``, ``<id>.2``, ...

Backends:

  * ``bm25`` (default): Okapi BM25 implemented here; deterministic, no model, no download.
  * ``dense``: cosine similarity over embeddings from Ollama's /api/embed, used only
    if an embedding model is already installed (checked through /api/tags and
    /api/show). Nothing is ever pulled.

The query for a row is the question plus the student answer (``build_query``).
``Retriever.retrieve(query, k, exclude=[chunk ids])`` withholds the named chunks
from the result without changing the scores of the others, which is what the
withheld-chunk positive control needs. ``Corpus.hash`` is a SHA-256 over the
chunk ids, tags and texts, recorded in every run manifest so runs are comparable.

    python -m src.retrieval "what is the base case of merge sort" --k 4
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

import yaml

from src.config import REPO_ROOT, load_config

CORPUS_DIR = REPO_ROOT / "data" / "corpus"
DEFAULT_K = 4
BACKENDS = ("bm25", "dense")
DEFAULT_BACKEND = "bm25"
CHUNK_MIN_WORDS = 150
CHUNK_MAX_WORDS = 250
CHUNKER_VERSION = 1          # bump when chunking or hashing rules change
BM25_K1 = 1.5
BM25_B = 0.75
INSTRUCTOR_ANSWER_PREFIX = "ia."


class CorpusError(ValueError):
    """The corpus sources are malformed (duplicate ids, missing front matter keys, ...)."""


# -- chunks --------------------------------------------------------------------

@dataclass(frozen=True)
class Chunk:
    id: str
    source: str                 # front-matter ``source`` of the file
    title: str                  # front-matter ``title`` of the file
    heading: str                # heading path below the document title, joined with " > "
    concepts: tuple[str, ...]
    text: str
    n_words: int
    path: str                   # file name inside the corpus directory

    @property
    def label(self) -> str:
        return f"{self.title} > {self.heading}" if self.heading else self.title

    def to_dict(self) -> dict:
        return {"id": self.id, "source": self.source, "title": self.title, "heading": self.heading,
                "concepts": list(self.concepts), "n_words": self.n_words, "path": self.path, "text": self.text}


@dataclass
class Corpus:
    chunks: list[Chunk]
    hash: str
    files: list[dict]           # per source file: path, source, sha256, n_chunks, n_words
    params: dict                # chunker settings
    directory: str = ""
    _by_id: dict[str, Chunk] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._by_id = {c.id: c for c in self.chunks}

    def __len__(self) -> int:
        return len(self.chunks)

    def __contains__(self, chunk_id: str) -> bool:
        return chunk_id in self._by_id

    def get(self, chunk_id: str) -> Chunk:
        try:
            return self._by_id[chunk_id]
        except KeyError:
            raise KeyError(f"unknown chunk id {chunk_id!r}") from None

    def ids(self) -> list[str]:
        return [c.id for c in self.chunks]

    def describe(self) -> dict:
        return {"corpus_hash": self.hash, "n_chunks": len(self.chunks), "directory": self.directory,
                "chunker": dict(self.params), "files": self.files}


def instructor_answer_chunk_id(question_id: str) -> str:
    """Id of the instructor-answer chunk for a Mohler question (``ia.E05.Q04``)."""
    return f"{INSTRUCTOR_ANSWER_PREFIX}{question_id}"


# -- Markdown -> chunks ----------------------------------------------------------

_FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_COMMENT = re.compile(r"^<!--\s*(.*?)\s*-->$")
_FENCE = re.compile(r"^(```|~~~)")
_LIST_ITEM = re.compile(r"^(?:[-*+]|\d+[.)])[ \t]+|^\|")
_SLUG = re.compile(r"[^a-z0-9]+")


def split_front_matter(text: str) -> tuple[dict, str]:
    """Return (front matter dict, body). The dict is empty when the file has no front matter."""
    m = _FRONT_MATTER.match(text)
    if not m:
        return {}, text
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise CorpusError("front matter must be a YAML mapping")
    return meta, text[m.end():]


def _slug(text: str) -> str:
    return _SLUG.sub("-", text.lower()).strip("-")


def _parse_meta(comment: str) -> dict:
    """``chunk: rec.base-case | concepts: recursion, base_case`` -> {"chunk": ..., "concepts": [...]}"""
    out: dict = {}
    for part in comment.split("|"):
        key, sep, value = part.partition(":")
        if not sep:
            continue
        key, value = key.strip().lower(), value.strip()
        if key == "chunk" and value:
            out["chunk"] = value
        elif key == "concepts":
            out["concepts"] = [v.strip() for v in value.split(",") if v.strip()]
    return out


def _paragraph(lines: list[str]) -> str:
    stripped = [l.strip() for l in lines]
    if any(_LIST_ITEM.match(l) for l in stripped):
        return "\n".join(stripped)                    # lists and tables keep their line structure
    return " ".join(" ".join(stripped).split())      # prose is unwrapped


def _sections(body: str) -> list[dict]:
    """Split a Markdown body into sections: {"path": [headings], "meta": {...}, "blocks": [str]}."""
    sections: list[dict] = []
    stack: list[tuple[int, str]] = []
    current = {"path": [], "meta": {}, "blocks": []}
    para: list[str] = []
    fence: list[str] | None = None
    fence_mark = ""
    after_heading = False

    def flush() -> None:
        if para:
            current["blocks"].append(_paragraph(para))
            para.clear()

    for raw in body.splitlines():
        line = raw.rstrip()
        if fence is not None:                          # inside a fenced code block: keep verbatim
            fence.append(line)
            if line.strip().startswith(fence_mark):
                current["blocks"].append("\n".join(fence))
                fence = None
            continue
        m = _FENCE.match(line.strip())
        if m:
            flush()
            fence, fence_mark, after_heading = [line], m.group(1), False
            continue
        h = _HEADING.match(line)
        if h:
            flush()
            sections.append(current)
            level, title = len(h.group(1)), h.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current = {"path": list(stack), "meta": {}, "blocks": []}
            after_heading = True
            continue
        if not line.strip():
            flush()
            continue
        c = _COMMENT.match(line.strip())
        if c and not para:
            if after_heading and not current["blocks"]:
                current["meta"].update(_parse_meta(c.group(1)))
            continue                                   # other standalone comments are dropped
        after_heading = False
        para.append(line)
    if fence is not None:
        raise CorpusError("unterminated code fence")
    flush()
    sections.append(current)
    return [s for s in sections if s["blocks"]]


def _pack(blocks: list[str], min_words: int, max_words: int) -> list[list[str]]:
    """Greedy packing of whole blocks into parts of at most ``max_words`` words."""
    parts: list[list[str]] = []
    cur: list[str] = []
    cur_words = 0
    for block in blocks:
        n = len(block.split())
        if cur and cur_words + n > max_words:
            parts.append(cur)
            cur, cur_words = [], 0
        cur.append(block)
        cur_words += n
    if cur:
        parts.append(cur)
    # fold a short tail into the previous part when the result stays close to the target size
    if len(parts) > 1:
        tail = sum(len(b.split()) for b in parts[-1])
        prev = sum(len(b.split()) for b in parts[-2])
        if tail < min_words // 2 and prev + tail <= int(max_words * 1.3):
            parts[-2].extend(parts.pop())
    return parts


def chunk_markdown(text: str, *, path: str = "", min_words: int = CHUNK_MIN_WORDS,
                   max_words: int = CHUNK_MAX_WORDS) -> list[Chunk]:
    """Chunk one corpus source file. Raises CorpusError if it has no ``source`` in its front matter."""
    meta, body = split_front_matter(text)
    source = meta.get("source")
    if not source:
        raise CorpusError(f"{path or 'document'}: front matter has no 'source'")
    title = str(meta.get("title") or source)
    defaults = [str(c) for c in (meta.get("default_concepts") or [])]
    chunks: list[Chunk] = []
    for sec in _sections(body):
        titles = [t for _, t in sec["path"]]
        below_h1 = [t for lvl, t in sec["path"] if lvl > 1] or titles[-1:]
        heading = " > ".join(below_h1)
        base_id = sec["meta"].get("chunk") or f"{source}.{_slug(' '.join(below_h1)) or 'preamble'}"
        concepts = tuple(sec["meta"].get("concepts") or defaults)
        parts = _pack(sec["blocks"], min_words, max_words)
        for i, blocks in enumerate(parts, 1):
            chunk_text = "\n\n".join(blocks)
            chunks.append(Chunk(id=base_id if len(parts) == 1 else f"{base_id}.{i}", source=str(source),
                                title=title, heading=heading, concepts=concepts, text=chunk_text,
                                n_words=len(chunk_text.split()), path=path))
    return chunks


def corpus_hash(chunks: Sequence[Chunk]) -> str:
    """SHA-256 over what retrieval and the prompt can see: ids, sources, headings, tags and texts."""
    payload = [{"id": c.id, "source": c.source, "title": c.title, "heading": c.heading,
                "concepts": list(c.concepts), "text": c.text} for c in chunks]
    blob = json.dumps({"v": CHUNKER_VERSION, "chunks": payload}, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_corpus(corpus_dir: Path | str = CORPUS_DIR, *, min_words: int = CHUNK_MIN_WORDS,
                max_words: int = CHUNK_MAX_WORDS) -> Corpus:
    """Chunk every source file in ``corpus_dir`` (sorted by file name) into one Corpus."""
    corpus_dir = Path(corpus_dir)
    chunks: list[Chunk] = []
    files: list[dict] = []
    sources: dict[str, str] = {}
    for path in sorted(corpus_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, _ = split_front_matter(text)
        if not meta.get("source"):
            continue                                   # README.md, retrieval_notes.md, ...
        if meta["source"] in sources:
            raise CorpusError(f"{path.name} and {sources[meta['source']]} share source {meta['source']!r}")
        sources[meta["source"]] = path.name
        part = chunk_markdown(text, path=path.name, min_words=min_words, max_words=max_words)
        chunks.extend(part)
        files.append({"path": path.name, "source": meta["source"],
                      "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                      "n_chunks": len(part), "n_words": sum(c.n_words for c in part)})
    if not chunks:
        raise CorpusError(f"no corpus sources found in {corpus_dir} (Markdown files with a 'source' front-matter key)")
    seen: set[str] = set()
    for c in chunks:
        if c.id in seen:
            raise CorpusError(f"duplicate chunk id {c.id!r} (in {c.path})")
        seen.add(c.id)
    try:
        shown = str(corpus_dir.resolve().relative_to(REPO_ROOT))
    except ValueError:
        shown = str(corpus_dir)
    return Corpus(chunks=chunks, hash=corpus_hash(chunks), files=files, directory=shown,
                  params={"version": CHUNKER_VERSION, "min_words": min_words, "max_words": max_words})


# -- BM25 ------------------------------------------------------------------------

_TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have how if in into is it its
of on or so such than that the their them then there these they this those to was were what when where
which while who why will with would
""".split())


def _stem(token: str) -> str:
    """Plural stripping only (the Harman "S" stemmer): trees -> tree, copies -> copy, classes -> classe."""
    if len(token) > 3 and token.endswith("ies") and not token.endswith(("eies", "aies")):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("es") and not token.endswith(("aes", "ees", "oes")):
        return token[:-1]
    if len(token) > 2 and token.endswith("s") and not token.endswith(("us", "ss")):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """Lower-case alphanumeric tokens, stopwords removed, plurals stripped. Deterministic."""
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


class BM25Index:
    """Okapi BM25 with the non-negative idf ln(1 + (N - df + 0.5) / (df + 0.5))."""

    def __init__(self, docs: Sequence[Sequence[str]], k1: float = BM25_K1, b: float = BM25_B):
        self.k1, self.b = k1, b
        self.n_docs = len(docs)
        self.doc_len = [len(d) for d in docs]
        self.avg_len = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0
        self.tf: list[dict[str, int]] = []
        df: dict[str, int] = {}
        for doc in docs:
            counts: dict[str, int] = {}
            for tok in doc:
                counts[tok] = counts.get(tok, 0) + 1
            self.tf.append(counts)
            for tok in counts:
                df[tok] = df.get(tok, 0) + 1
        self.idf = {tok: math.log(1.0 + (self.n_docs - n + 0.5) / (n + 0.5)) for tok, n in df.items()}

    def scores(self, query_tokens: Iterable[str]) -> list[float]:
        terms = sorted(set(query_tokens) & self.idf.keys())     # sorted: fixed summation order
        out = [0.0] * self.n_docs
        for i, counts in enumerate(self.tf):
            norm = self.k1 * (1.0 - self.b + self.b * (self.doc_len[i] / self.avg_len)) if self.avg_len else self.k1
            s = 0.0
            for term in terms:
                f = counts.get(term)
                if f:
                    s += self.idf[term] * f * (self.k1 + 1.0) / (f + norm)
            out[i] = s
        return out


# -- dense (optional) --------------------------------------------------------------

def ollama_root(models_cfg: dict | None = None) -> str:
    """Root URL of the Ollama server, derived from configs/models.yaml (``.../v1`` stripped)."""
    cfg = models_cfg if models_cfg is not None else load_config("models")
    base = ((cfg.get("providers") or {}).get("ollama") or {}).get("base_url") or "http://localhost:11434/v1"
    base = base.rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def _http_json(url: str, payload: dict | None = None, timeout: float = 120.0) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


_EMBED_FAMILIES = {"bert", "nomic-bert", "xlm-roberta"}


class OllamaEmbedder:
    """Embeddings from an already-installed Ollama embedding model. Never pulls a model."""

    def __init__(self, model: str | None = None, base_url: str | None = None, *,
                 http: Callable[..., dict] = _http_json):
        self.base_url = (base_url or ollama_root()).rstrip("/")
        self.http = http
        installed = self.installed_embedding_models()
        if model is None:
            if not installed:
                raise RuntimeError(
                    f"dense retrieval needs an embedding model in Ollama at {self.base_url}, and none is "
                    "installed. Use --retrieval-backend bm25, or install one yourself "
                    "(for example `ollama pull nomic-embed-text`).")
            model = installed[0]
        elif model not in installed:
            raise RuntimeError(f"embedding model {model!r} is not installed in Ollama (installed embedding "
                               f"models: {installed or 'none'}); it will not be pulled automatically")
        self.model = model

    def installed_embedding_models(self) -> list[str]:
        """Names from /api/tags whose /api/show capabilities include "embedding" (name/family fallback)."""
        try:
            tags = self.http(f"{self.base_url}/api/tags", timeout=10.0).get("models") or []
        except Exception as e:  # noqa: BLE001 - unreachable server means no dense backend
            raise RuntimeError(f"Ollama is not reachable at {self.base_url} ({type(e).__name__}: {e}); "
                               "dense retrieval is unavailable, use --retrieval-backend bm25") from e
        found = []
        for m in tags:
            name = m.get("name") or m.get("model") or ""
            caps = None
            try:
                caps = self.http(f"{self.base_url}/api/show", {"model": name}, timeout=10.0).get("capabilities")
            except Exception:  # noqa: BLE001 - older servers: fall back to the name and family
                caps = None
            if caps is not None:
                is_embed = "embedding" in caps
            else:
                details = m.get("details") or {}
                is_embed = "embed" in name.lower() or details.get("family") in _EMBED_FAMILIES
            if is_embed:
                found.append(name)
        return sorted(found)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), 32):
            resp = self.http(f"{self.base_url}/api/embed",
                             {"model": self.model, "input": list(texts[start:start + 32])}, timeout=300.0)
            out.extend(resp["embeddings"])
        return out


def _unit(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else list(vec)


# -- retriever ---------------------------------------------------------------------

@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    rank: int

    def to_log(self) -> dict:
        return {"id": self.chunk.id, "score": self.score, "rank": self.rank}


def build_query(row: dict) -> str:
    """The retrieval query for one sheet row: question plus student answer."""
    return f"{row['question'].strip()} {row['student_answer'].strip()}"


class Retriever:
    """Top-k retrieval over a Corpus with a BM25 or dense backend."""

    def __init__(self, corpus: Corpus, backend: str = DEFAULT_BACKEND, *, k1: float = BM25_K1,
                 b: float = BM25_B, embedder=None):
        if backend not in BACKENDS:
            raise ValueError(f"unknown retrieval backend {backend!r}; choose from {BACKENDS}")
        self.corpus = corpus
        self.backend = backend
        self.embedding_model: str | None = None
        self._ids = set(corpus.ids())
        if backend == "bm25":
            self._bm25 = BM25Index([tokenize(f"{c.heading} {c.text}") for c in corpus.chunks], k1=k1, b=b)
        else:
            self._embedder = embedder if embedder is not None else OllamaEmbedder()
            self.embedding_model = getattr(self._embedder, "model", None)
            self._vectors = [_unit(v) for v in self._embedder.embed([f"{c.heading}\n{c.text}" for c in corpus.chunks])]

    def _scores(self, query: str) -> list[float]:
        if self.backend == "bm25":
            return self._bm25.scores(tokenize(query))
        q = _unit(self._embedder.embed([query])[0])
        return [sum(a * b for a, b in zip(q, v)) for v in self._vectors]

    def retrieve(self, query: str, k: int = DEFAULT_K, exclude: Iterable[str] = ()) -> list[Hit]:
        """Top-k chunks by score (ties broken by corpus order). ``exclude`` withholds chunk ids:
        they are skipped in the ranking, and the scores of all other chunks are unchanged.
        BM25 never returns a chunk with no query term in it, so fewer than k hits are possible."""
        if k < 0:
            raise ValueError("k must be >= 0")
        excluded = set(exclude)
        unknown = sorted(excluded - self._ids)
        if unknown:
            raise KeyError(f"cannot exclude unknown chunk ids {unknown}")
        scores = self._scores(query)
        hits: list[Hit] = []
        for i in sorted(range(len(scores)), key=lambda j: (-scores[j], j)):
            if len(hits) >= k:
                break
            chunk = self.corpus.chunks[i]
            if chunk.id in excluded:
                continue
            if self.backend == "bm25" and scores[i] <= 0.0:
                break
            hits.append(Hit(chunk=chunk, score=round(scores[i], 6), rank=len(hits) + 1))
        return hits

    def describe(self) -> dict:
        """Settings for the run manifest."""
        out = {"backend": self.backend, **self.corpus.describe()}
        if self.backend == "bm25":
            out["bm25"] = {"k1": self._bm25.k1, "b": self._bm25.b, "tokenizer": "alnum-lower+stopwords+s-stem"}
        else:
            out["embedding_model"] = self.embedding_model
        return out


def make_retriever(backend: str = DEFAULT_BACKEND, corpus: Corpus | None = None,
                   corpus_dir: Path | str = CORPUS_DIR, **kwargs) -> Retriever:
    return Retriever(corpus if corpus is not None else load_corpus(corpus_dir), backend, **kwargs)


def _main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Query the retrieval corpus, or print its statistics.")
    ap.add_argument("query", nargs="?", help="query text; omit to print corpus statistics")
    ap.add_argument("--k", type=int, default=DEFAULT_K)
    ap.add_argument("--backend", choices=BACKENDS, default=DEFAULT_BACKEND)
    ap.add_argument("--exclude", action="append", default=[], metavar="CHUNK_ID")
    ap.add_argument("--corpus-dir", type=Path, default=CORPUS_DIR)
    args = ap.parse_args()
    corpus = load_corpus(args.corpus_dir)
    if not args.query:
        print(f"corpus_hash {corpus.hash}\n{len(corpus)} chunks")
        for f in corpus.files:
            print(f"  {f['path']}: source={f['source']} chunks={f['n_chunks']} words={f['n_words']}")
        return
    for hit in Retriever(corpus, args.backend).retrieve(args.query, args.k, args.exclude):
        print(f"{hit.rank}. {hit.score:9.4f}  {hit.chunk.id}  [{hit.chunk.label}]  ({hit.chunk.n_words} words)")


if __name__ == "__main__":
    _main()
