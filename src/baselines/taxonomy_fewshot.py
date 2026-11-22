"""Condition 3: condition 2 plus the full taxonomy text and few-shot examples, single pass.

On top of condition 2 (question, reference answer, top-k retrieved chunks) the
prompt carries

  * the taxonomy text: id, concept, description and notes of every item in
    taxonomy/recursion_bigO.yaml, and the definitions of the three special
    labels, rendered at run time so the prompt always matches the taxonomy file
    (whose SHA-256 is in the manifest);
  * the worked examples in configs/prompts/fewshot_v1.yaml. They are authored
    for this prompt, never taken from the eval sheet or from any Mohler answer;
    ``load_fewshot`` refuses a file that is not marked as authored.

Still one retrieval and one model call per row (plus the shared repair
round-trip). The model may cite ``student_answer``, ``retrieved`` and
``taxonomy`` spans; retrieved spans are checked against the chunks shown for the
row and taxonomy spans against the taxonomy text shown.

Template: configs/prompts/taxonomy_fewshot_v1.txt. The static part (taxonomy,
examples) comes first so the server can reuse its prompt cache across rows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Iterable

import yaml

from src.baselines import rag
from src.baselines.direct import PromptTemplate, complete_and_validate
from src.config import PROMPT_DIR, sha256_text
from src.llm import LLMClient
from src.retrieval import DEFAULT_K, Hit, Retriever
from src.schema import Record, SchemaError, label_set, normalize_ws, validate_record

CONDITION = 3
NAME = "taxonomy_fewshot"
DEFAULT_TEMPLATE = "taxonomy_fewshot_v1"
DEFAULT_FEWSHOT = "fewshot_v1"


# -- few-shot examples -----------------------------------------------------------

@dataclass
class FewShotSet:
    name: str
    path: str
    sha256: str
    provenance: str
    examples: list[dict]

    @property
    def labels(self) -> list[str]:
        return [ex["output"]["label"] for ex in self.examples]


def load_fewshot(name: str = DEFAULT_FEWSHOT, prompt_dir: Path = PROMPT_DIR,
                 labels: list[str] | None = None) -> FewShotSet:
    """Load and check configs/prompts/<name>.yaml.

    Refuses the file unless it and every example are marked as authored, every example's
    output is a valid record for its own student answer, and every cited span is verbatim.
    """
    path = Path(prompt_dir) / f"{name}.yaml"
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict) or data.get("provenance") != "authored":
        raise SchemaError(f"{path.name}: top-level 'provenance: authored' is required; few-shot examples "
                          "must be written for the prompt, never copied from the eval sheet or Mohler")
    labels = labels if labels is not None else label_set()
    examples = data.get("examples") or []
    if not examples:
        raise SchemaError(f"{path.name}: no examples")
    seen: set[str] = set()
    for ex in examples:
        ex_id = ex.get("id")
        if not ex_id or ex_id in seen:
            raise SchemaError(f"{path.name}: example ids must be present and unique (got {ex_id!r})")
        seen.add(ex_id)
        if ex.get("authored") is not True:
            raise SchemaError(f"{path.name}: example {ex_id} is not marked 'authored: true'")
        for key in ("question", "instructor_answer", "student_answer", "output"):
            if not ex.get(key):
                raise SchemaError(f"{path.name}: example {ex_id} has no {key}")
        rec = validate_record(ex["output"], row_id=ex_id, student_answer=ex["student_answer"], labels=labels,
                              retrieved_chunks=[], taxonomy_text="")
        if rec.warnings or not rec.citation_valid:
            raise SchemaError(f"{path.name}: example {ex_id} output is not clean: "
                              f"{rec.warnings or rec.invalid_spans}")
    return FewShotSet(name=name, path=str(path), sha256=sha256_text(text),
                      provenance=str(data.get("source_statement") or data["provenance"]), examples=examples)


def render_fewshot(fewshot: FewShotSet) -> str:
    """Examples in the same layout as the real task, each followed by its expected JSON output."""
    blocks = []
    for i, ex in enumerate(fewshot.examples, 1):
        out = ex["output"]
        record = {"label": out["label"],
                  "evidence": [{"source": e["source"], "span": e["span"]} for e in out.get("evidence") or []],
                  "confidence": out["confidence"]}
        blocks.append(f"Example {i}\n"
                      f"Exam question: {normalize_ws(ex['question'])}\n"
                      f"Instructor's reference answer: {normalize_ws(ex['instructor_answer'])}\n"
                      f"Student's answer: {normalize_ws(ex['student_answer'])}\n"
                      f"Output: {json.dumps(record, ensure_ascii=False)}")
    return "\n\n".join(blocks)


# -- taxonomy text ---------------------------------------------------------------

def render_taxonomy_items(taxonomy: dict) -> str:
    """One entry per item, in file order: ``- <id> (<concept>): <description> Notes: <notes>``."""
    lines = []
    for item in taxonomy["items"]:
        line = f"- {item['id']} ({item.get('concept', '')}): {normalize_ws(item['description'])}"
        if item.get("notes"):
            line += f" Notes: {normalize_ws(item['notes'])}"
        lines.append(line)
    return "\n".join(lines)


def render_special_labels(taxonomy: dict) -> str:
    return "\n".join(f"- {sp['id']}: {normalize_ws(sp['definition'])}" for sp in taxonomy["special_labels"])


def taxonomy_text(taxonomy: dict) -> str:
    """Everything taken from the taxonomy file that the prompt shows; taxonomy spans are checked against it."""
    return f"{render_taxonomy_items(taxonomy)}\n{render_special_labels(taxonomy)}"


# -- prompt ----------------------------------------------------------------------

def render_messages(template: PromptTemplate, row: dict, hits: list[Hit], taxonomy: dict,
                    fewshot: FewShotSet) -> list[dict]:
    user = Template(template.user).substitute(
        question=row["question"].strip(),
        instructor_answer=row["instructor_answer"].strip(),
        student_answer=row["student_answer"].strip(),
        retrieved_chunks=rag.format_chunks(hits),
        taxonomy_items=render_taxonomy_items(taxonomy),
        special_labels=render_special_labels(taxonomy),
        fewshot_examples=render_fewshot(fewshot),
    )
    messages = []
    if template.system:
        messages.append({"role": "system", "content": template.system})
    messages.append({"role": "user", "content": user})
    return messages


def prepare_row(row: dict, template: PromptTemplate, retriever: Retriever, taxonomy: dict,
                fewshot: FewShotSet, *, k: int = DEFAULT_K, exclude: Iterable[str] = (),
                keep_own_reference: bool = False) -> dict:
    """Retrieve and render for one row: {"messages", "retrieved_chunks", "taxonomy_text", "extra_meta"}."""
    hits, withheld = rag.retrieve_for_row(row, retriever, k=k, exclude=exclude,
                                          keep_own_reference=keep_own_reference)
    return {"messages": render_messages(template, row, hits, taxonomy, fewshot),
            "retrieved_chunks": [h.chunk.text for h in hits], "taxonomy_text": taxonomy_text(taxonomy),
            "extra_meta": rag.retrieval_meta(hits, withheld)}


def predict_row(row: dict, client: LLMClient, template: PromptTemplate, labels: list[str],
                retriever: Retriever, taxonomy: dict, fewshot: FewShotSet, *, k: int = DEFAULT_K,
                exclude: Iterable[str] = (), keep_own_reference: bool = False,
                **settings) -> tuple[Record | None, dict | None]:
    """Condition 3 for one row. ``settings`` are the generation settings of ``complete_and_validate``."""
    prepared = prepare_row(row, template, retriever, taxonomy, fewshot, k=k, exclude=exclude,
                           keep_own_reference=keep_own_reference)
    return complete_and_validate(row, client, prepared["messages"], labels,
                                 retrieved_chunks=prepared["retrieved_chunks"],
                                 taxonomy_text=prepared["taxonomy_text"],
                                 extra_meta=prepared["extra_meta"], **settings)
