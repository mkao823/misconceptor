"""Condition 0: keyword / trigger-phrase baseline.

For each row, every taxonomy item's ``trigger_phrases`` are matched
case-insensitively as plain substrings of the whitespace-normalized student
answer. The prediction is the item with the most *distinct* matched phrases;
``none`` when nothing matches. Ties are broken by taxonomy file order. The
grade (``score_avg``) is never used.

Evidence: each matched phrase is cited as the verbatim slice of the student
answer it was found in (so citation validity holds by construction).
Confidence: (phrases matched by the winner) / (phrases matched by all items);
0.5 for ``none`` (uninformative).

This is a sanity floor, not a classifier: substring matching has no word
boundaries ("n-1" also matches inside "2n-1"), and residual categories with an
empty phrase list (MModd) can never be predicted.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.schema import Record, label_set, load_taxonomy, normalize_ws, validate_record

CONDITION = 0
NAME = "keyword"


@dataclass
class Trigger:
    item_id: str
    phrase: str            # as written in the taxonomy
    needle: str            # normalized, lower-cased


def compile_triggers(taxonomy: dict) -> list[Trigger]:
    triggers: list[Trigger] = []
    for item in taxonomy["items"]:
        for phrase in item.get("trigger_phrases") or []:
            needle = normalize_ws(phrase).lower()
            if needle:
                triggers.append(Trigger(item["id"], phrase, needle))
    return triggers


def match_answer(student_answer: str, triggers: list[Trigger]) -> dict[str, list[tuple[str, str]]]:
    """Return {item_id: [(phrase, verbatim span), ...]} for every item with at least one hit."""
    original = normalize_ws(student_answer)
    hay = original.lower()
    hits: dict[str, list[tuple[str, str]]] = {}
    for t in triggers:
        pos = hay.find(t.needle)
        if pos != -1:
            hits.setdefault(t.item_id, []).append((t.phrase, original[pos:pos + len(t.needle)]))
    return hits


def predict_row(row: dict, triggers: list[Trigger], labels: list[str],
                item_order: list[str]) -> Record:
    hits = match_answer(row["student_answer"], triggers)
    if not hits:
        obj = {"label": "none", "evidence": [], "confidence": 0.5}
        matched = {}
    else:
        rank = {item_id: i for i, item_id in enumerate(item_order)}
        best = max(hits, key=lambda item_id: (len(hits[item_id]), -rank[item_id]))
        total = sum(len(v) for v in hits.values())
        obj = {"label": best,
               "evidence": [{"source": "student_answer", "span": span} for _, span in hits[best]],
               "confidence": round(len(hits[best]) / total, 4)}
        matched = {k: [p for p, _ in v] for k, v in hits.items()}
    raw = f"keyword matches: {matched}"
    return validate_record(obj, row_id=row["id"], student_answer=row["student_answer"], labels=labels,
                           raw=raw, question_id=row.get("question_id"), meta={"matches": matched})


def run(rows: list[dict], taxonomy: dict | None = None) -> list[Record]:
    taxonomy = taxonomy if taxonomy is not None else load_taxonomy()
    triggers = compile_triggers(taxonomy)
    labels = label_set(taxonomy)
    order = [it["id"] for it in taxonomy["items"]]
    return [predict_row(row, triggers, labels, order) for row in rows]
