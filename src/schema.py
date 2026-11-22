"""Output record schema, the closed label set, and validators.

A prediction record (one per student answer) has:
  label       a taxonomy id from taxonomy/recursion_bigO.yaml or one of the special labels
  evidence    list of {source: student_answer | retrieved | taxonomy, span: str}
  confidence  float in [0, 1]
  raw         the model's raw text

``validate_record`` checks all of that and also computes citation validity
(review section 6.4), after whitespace normalization:

  * every ``student_answer`` span must be a verbatim substring of that row's student answer;
  * every ``retrieved`` span must be a verbatim substring of one of the chunks actually
    shown for that row (conditions 2 and up pass them as ``retrieved_chunks``);
  * every ``taxonomy`` span must be a verbatim substring of the taxonomy text shown
    (condition 3 passes it as ``taxonomy_text``).

A source is only checked when its reference text is passed, so conditions 0 and 1,
which show neither chunks nor taxonomy text, behave as before. A fabricated span does
not make the record invalid: it is flagged. ``citation_valid`` is True when no checked
span is fabricated (vacuously True when nothing is cited); the offending spans are in
``invalid_spans`` and, per source, in ``invalid_by_source``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

import yaml

from src.config import TAXONOMY_PATH

SPECIAL_LABELS: tuple[str, ...] = ("none", "other_error", "insufficient_evidence")
EVIDENCE_SOURCES: tuple[str, ...] = ("student_answer", "retrieved", "taxonomy")
ABSTAIN_LABEL = "insufficient_evidence"


class SchemaError(ValueError):
    """The object is not a valid prediction record."""


# -- taxonomy ------------------------------------------------------------------

def load_taxonomy(path: Path | str | None = None) -> dict:
    with open(path or TAXONOMY_PATH) as f:
        return yaml.safe_load(f)


def taxonomy_ids(taxonomy: dict) -> list[str]:
    """Item ids in file order (the tie-break order for the keyword baseline)."""
    return [item["id"] for item in taxonomy["items"]]


def special_labels(taxonomy: dict | None = None) -> list[str]:
    if taxonomy is None:
        return list(SPECIAL_LABELS)
    ids = [sp["id"] for sp in taxonomy.get("special_labels", [])]
    if set(ids) != set(SPECIAL_LABELS):
        raise SchemaError(f"taxonomy special_labels {ids} differ from {list(SPECIAL_LABELS)}")
    return ids


def label_set(taxonomy: dict | None = None) -> list[str]:
    """Closed label set: taxonomy ids in file order followed by the three special labels."""
    taxonomy = taxonomy if taxonomy is not None else load_taxonomy()
    return taxonomy_ids(taxonomy) + special_labels(taxonomy)


# -- text ----------------------------------------------------------------------

_WS = re.compile(r"\s+")


def normalize_ws(text: str) -> str:
    """Collapse runs of whitespace to one space and strip the ends. Nothing else."""
    return _WS.sub(" ", str(text)).strip()


# -- records -------------------------------------------------------------------

@dataclass
class Evidence:
    source: str
    span: str


@dataclass
class Record:
    id: str
    label: str
    evidence: list[Evidence]
    confidence: float
    raw: str
    citation_valid: bool
    invalid_spans: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    question_id: str | None = None
    meta: dict = field(default_factory=dict)   # tokens, cache hit, repair count, retrieved chunk ids, ...
    invalid_by_source: dict = field(default_factory=dict)   # {"retrieved": [span, ...]}; only sources with a bad span
    sources_checked: list[str] = field(default_factory=lambda: ["student_answer"])   # sources whose spans were verified

    def to_dict(self) -> dict:
        d = asdict(self)
        d["evidence"] = [asdict(e) for e in self.evidence]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Record":
        d = dict(d)
        d["evidence"] = [Evidence(**e) if isinstance(e, dict) else e for e in d.get("evidence", [])]
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    @property
    def student_spans(self) -> list[str]:
        return [e.span for e in self.evidence if e.source == "student_answer"]

    @property
    def retrieved_spans(self) -> list[str]:
        return [e.span for e in self.evidence if e.source == "retrieved"]


def invalid_evidence(evidence: list[Evidence], student_answer: str,
                     retrieved_chunks: Sequence[str] | None = None,
                     taxonomy_text: str | None = None) -> dict[str, list[str]]:
    """Fabricated spans per source: {source: [span, ...]}, empty when every checked span is verbatim.

    student_answer spans are always checked against the answer. retrieved spans are checked
    against ``retrieved_chunks`` (the texts shown for this row; a span must lie inside ONE
    chunk) and taxonomy spans against ``taxonomy_text``, each only when that argument is not
    None. An empty ``retrieved_chunks`` list means nothing was shown, so every retrieved
    span is fabricated. All comparisons are after whitespace normalization.
    """
    references: dict[str, list[str]] = {"student_answer": [normalize_ws(student_answer)]}
    if retrieved_chunks is not None:
        references["retrieved"] = [normalize_ws(c) for c in retrieved_chunks]
    if taxonomy_text is not None:
        references["taxonomy"] = [normalize_ws(taxonomy_text)]
    bad: dict[str, list[str]] = {}
    for e in evidence:
        haystacks = references.get(e.source)
        if haystacks is None:
            continue
        span = normalize_ws(e.span)
        if not any(span in h for h in haystacks):
            bad.setdefault(e.source, []).append(e.span)
    return bad


def check_citations(evidence: list[Evidence], student_answer: str,
                    retrieved_chunks: Sequence[str] | None = None,
                    taxonomy_text: str | None = None) -> tuple[bool, list[str]]:
    """Citation validity as (valid, offending spans); see ``invalid_evidence`` for the rules.
    Vacuously valid when no checked span is cited."""
    bad = invalid_evidence(evidence, student_answer, retrieved_chunks, taxonomy_text)
    spans = [e.span for e in evidence if e.span in bad.get(e.source, ())]
    return (not spans), spans


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def parse_json_object(text: str) -> dict:
    """Parse the model's text as one JSON object; tolerate fences and surrounding prose."""
    if not isinstance(text, str) or not text.strip():
        raise SchemaError("empty output")
    candidates = [text.strip()]
    m = _FENCE.match(text)
    if m:
        candidates.insert(0, m.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for cand in candidates:
        try:
            obj = json.loads(cand)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    raise SchemaError(f"output is not a JSON object: {text[:200]!r}")


def _canonical_label(value, labels: list[str], warnings: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"label must be a non-empty string, got {value!r}")
    value = value.strip()
    if value in labels:
        return value
    lowered = {l.lower(): l for l in labels}
    if value.lower() in lowered:
        warnings.append(f"label {value!r} normalized to {lowered[value.lower()]!r}")
        return lowered[value.lower()]
    raise SchemaError(f"label {value!r} is not in the label set")


def _coerce_evidence(value, warnings: list[str]) -> list[Evidence]:
    if value is None:
        warnings.append("evidence missing; treated as []")
        return []
    if isinstance(value, (str, dict)):
        value = [value]
    if not isinstance(value, list):
        raise SchemaError(f"evidence must be a list, got {type(value).__name__}")
    out: list[Evidence] = []
    for i, item in enumerate(value):
        if isinstance(item, str):
            warnings.append(f"evidence[{i}] was a bare string; assumed source=student_answer")
            item = {"source": "student_answer", "span": item}
        if not isinstance(item, dict):
            raise SchemaError(f"evidence[{i}] must be an object, got {type(item).__name__}")
        source, span = item.get("source"), item.get("span")
        if source not in EVIDENCE_SOURCES:
            raise SchemaError(f"evidence[{i}].source {source!r} not in {EVIDENCE_SOURCES}")
        if not isinstance(span, str) or not span.strip():
            raise SchemaError(f"evidence[{i}].span must be a non-empty string")
        out.append(Evidence(source=source, span=span))
    return out


def _coerce_confidence(value, warnings: list[str]) -> float:
    if isinstance(value, bool):
        raise SchemaError("confidence must be a number, got a boolean")
    if isinstance(value, str):
        try:
            value = float(value.strip().rstrip("%")) / (100 if value.strip().endswith("%") else 1)
            warnings.append("confidence was a string; converted")
        except ValueError as e:
            raise SchemaError(f"confidence {value!r} is not numeric") from e
    if not isinstance(value, (int, float)):
        raise SchemaError(f"confidence must be a number, got {type(value).__name__}")
    conf = float(value)
    if not 0.0 <= conf <= 1.0:
        raise SchemaError(f"confidence {conf} outside [0, 1]")
    return conf


def validate_record(obj: dict, *, row_id: str, student_answer: str, labels: list[str],
                    raw: str | None = None, question_id: str | None = None,
                    meta: dict | None = None, retrieved_chunks: Sequence[str] | None = None,
                    taxonomy_text: str | None = None) -> Record:
    """Validate a parsed output object against the schema and the row; raise SchemaError if invalid.

    Lenient coercions (case of the label, bare-string evidence, numeric-string
    confidence) are recorded in ``warnings``; anything else is an error.
    ``retrieved_chunks`` are the chunk texts shown for this row and ``taxonomy_text`` the
    taxonomy text shown; pass them to have ``retrieved`` / ``taxonomy`` spans checked.
    """
    if not isinstance(obj, dict):
        raise SchemaError(f"record must be an object, got {type(obj).__name__}")
    warnings: list[str] = []
    label = _canonical_label(obj.get("label"), labels, warnings)
    evidence = _coerce_evidence(obj.get("evidence"), warnings)
    confidence = _coerce_confidence(obj.get("confidence"), warnings)
    by_source = invalid_evidence(evidence, student_answer, retrieved_chunks, taxonomy_text)
    bad = [e.span for e in evidence if e.span in by_source.get(e.source, ())]
    checked = ["student_answer"] + (["retrieved"] if retrieved_chunks is not None else []) \
        + (["taxonomy"] if taxonomy_text is not None else [])
    return Record(id=row_id, label=label, evidence=evidence, confidence=confidence,
                  raw=raw if raw is not None else json.dumps(obj, ensure_ascii=False),
                  citation_valid=not bad, invalid_spans=bad, warnings=warnings,
                  question_id=question_id, meta=dict(meta or {}), invalid_by_source=by_source,
                  sources_checked=checked)


def is_taxonomy_label(label: str) -> bool:
    return label not in SPECIAL_LABELS
