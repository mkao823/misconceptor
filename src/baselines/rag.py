"""Condition 2: direct LLM diagnosis plus static top-k course-material retrieval.

The condition 1 prompt with one addition: the top-k chunks retrieved from
data/corpus/ for the query "question + student answer" (src/retrieval.py). Still
no taxonomy descriptions and no examples: the prompt lists label ids only
(configs/prompts/rag_v1.txt). One retrieval, one model call (plus the shared
repair round-trip).

The model may cite ``retrieved`` evidence spans. Each one must be a verbatim
substring, after whitespace normalization, of one of the chunks shown for that
row; a fabricated span is flagged in the record (``citation_valid`` False), as
fabricated student spans are.

By default the row's own instructor-answer chunk (``ia.<question_id>``) is
withheld from retrieval, because that reference answer is already in the prompt
and would otherwise take the first of the k places on every row. Pass
``keep_own_reference=True`` to retrieve it anyway. Extra chunk ids can be
withheld with ``exclude`` (used by the withheld-chunk positive control).

Per row, the ids, scores and ranks of the retrieved chunks and the ids that were
withheld are stored in the record's ``meta`` (and in the error dict).
"""

from __future__ import annotations

from string import Template
from typing import Iterable

from src.baselines.direct import PromptTemplate, complete_and_validate
from src.llm import LLMClient
from src.retrieval import DEFAULT_K, Hit, Retriever, build_query, instructor_answer_chunk_id
from src.schema import Record, special_labels

CONDITION = 2
NAME = "rag"
DEFAULT_TEMPLATE = "rag_v1"
NO_CHUNKS = "(no course material was retrieved for this answer)"


def retrieve_for_row(row: dict, retriever: Retriever, *, k: int = DEFAULT_K, exclude: Iterable[str] = (),
                     keep_own_reference: bool = False) -> tuple[list[Hit], list[str]]:
    """Return (hits, withheld chunk ids) for one sheet row."""
    withheld = list(dict.fromkeys(exclude))
    own = instructor_answer_chunk_id(row.get("question_id") or "")
    if not keep_own_reference and own in retriever.corpus and own not in withheld:
        withheld.append(own)
    return retriever.retrieve(build_query(row), k, withheld), withheld


def format_chunks(hits: list[Hit]) -> str:
    """The retrieved-material block of the prompt: one excerpt per hit, best first."""
    if not hits:
        return NO_CHUNKS
    return "\n\n".join(f"[{h.chunk.id}] {h.chunk.label}\n{h.chunk.text}" for h in hits)


def retrieval_meta(hits: list[Hit], withheld: list[str]) -> dict:
    return {"retrieved": [h.to_log() for h in hits], "withheld_chunk_ids": list(withheld)}


def render_messages(template: PromptTemplate, row: dict, labels: list[str], hits: list[Hit]) -> list[dict]:
    """Fill the template. ``labels`` is the full closed set; only non-special ids are listed."""
    specials = set(special_labels())
    user = Template(template.user).substitute(
        question=row["question"].strip(),
        instructor_answer=row["instructor_answer"].strip(),
        student_answer=row["student_answer"].strip(),
        label_ids="\n".join(f"- {i}" for i in labels if i not in specials),
        retrieved_chunks=format_chunks(hits),
    )
    messages = []
    if template.system:
        messages.append({"role": "system", "content": template.system})
    messages.append({"role": "user", "content": user})
    return messages


def prepare_row(row: dict, template: PromptTemplate, labels: list[str], retriever: Retriever, *,
                k: int = DEFAULT_K, exclude: Iterable[str] = (), keep_own_reference: bool = False) -> dict:
    """Retrieve and render for one row: {"messages", "retrieved_chunks", "taxonomy_text", "extra_meta"}."""
    hits, withheld = retrieve_for_row(row, retriever, k=k, exclude=exclude, keep_own_reference=keep_own_reference)
    return {"messages": render_messages(template, row, labels, hits),
            "retrieved_chunks": [h.chunk.text for h in hits], "taxonomy_text": None,
            "extra_meta": retrieval_meta(hits, withheld)}


def predict_row(row: dict, client: LLMClient, template: PromptTemplate, labels: list[str],
                retriever: Retriever, *, k: int = DEFAULT_K, exclude: Iterable[str] = (),
                keep_own_reference: bool = False, **settings) -> tuple[Record | None, dict | None]:
    """Condition 2 for one row. ``settings`` are the generation settings of ``complete_and_validate``."""
    prepared = prepare_row(row, template, labels, retriever, k=k, exclude=exclude,
                           keep_own_reference=keep_own_reference)
    return complete_and_validate(row, client, prepared["messages"], labels,
                                 retrieved_chunks=prepared["retrieved_chunks"],
                                 extra_meta=prepared["extra_meta"], **settings)
