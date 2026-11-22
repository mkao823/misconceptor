"""Output record schema, the closed label set, and validators.

A prediction record (one per student answer) has:
  label       a taxonomy id from taxonomy/recursion_bigO.yaml or one of the special labels
  evidence    list of {source: student_answer | retrieved | taxonomy, span: str}
  confidence  float in [0, 1]
  raw         the model's raw text

``validate_record`` checks all of that and also computes citation validity
(review section 6.4): every ``student_answer`` span must be a verbatim substring of
that row's student answer after whitespace normalization. The result is stored
per record as ``citation_valid`` (True when no student_answer span is cited) with
the offending spans in ``invalid_spans``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

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
    meta: dict = field(default_factory=dict)   # tokens, cache hit, repair count, ...

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


def check_citations(evidence: list[Evidence], student_answer: str) -> tuple[bool, list[str]]:
    """Citation validity: every student_answer span is a verbatim substring of the answer
    after whitespace normalization. Vacuously valid when no student_answer span is cited."""
    haystack = normalize_ws(student_answer)
    bad = [e.span for e in evidence
           if e.source == "student_answer" and normalize_ws(e.span) not in haystack]
    return (not bad), bad


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
                    meta: dict | None = None) -> Record:
    """Validate a parsed output object against the schema and the row; raise SchemaError if invalid.

    Lenient coercions (case of the label, bare-string evidence, numeric-string
    confidence) are recorded in ``warnings``; anything else is an error.
    """
    if not isinstance(obj, dict):
        raise SchemaError(f"record must be an object, got {type(obj).__name__}")
    warnings: list[str] = []
    label = _canonical_label(obj.get("label"), labels, warnings)
    evidence = _coerce_evidence(obj.get("evidence"), warnings)
    confidence = _coerce_confidence(obj.get("confidence"), warnings)
    valid, bad = check_citations(evidence, student_answer)
    return Record(id=row_id, label=label, evidence=evidence, confidence=confidence,
                  raw=raw if raw is not None else json.dumps(obj, ensure_ascii=False),
                  citation_valid=valid, invalid_spans=bad, warnings=warnings,
                  question_id=question_id, meta=dict(meta or {}))


def is_taxonomy_label(label: str) -> bool:
    return label not in SPECIAL_LABELS
