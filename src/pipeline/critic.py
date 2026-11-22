"""The Critic of condition 4: one model call that judges whether the shown material is sufficient.

Specification: docs/CRITIC_SPEC.md, sections 2 and 3. The Critic sees the question, the
instructor's reference answer, the student answer, every chunk shown so far, the draft
record and the catalogue entry of the draft label. It returns

    {"sufficient": bool, "missing": str, "query": str}

``missing`` names the specific information needed and ``query`` is the search query for it;
both must be non-empty when ``sufficient`` is false. The Critic never changes a label.

Template: configs/prompts/critic_v1.txt (same ``system --- user`` format and
``string.Template`` placeholders as the diagnosis templates). An invalid verdict gets the
same repair round-trip as an invalid diagnosis; every call, repairs included, is made
through the client passed in, so the caller can count its tokens.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from string import Template

from src.baselines import rag
from src.baselines.direct import PromptTemplate, prompt_chars
from src.llm import LLMError
from src.retrieval import Hit
from src.schema import Record, SchemaError, normalize_ws, parse_json_object

DEFAULT_TEMPLATE = "critic_v1"


@dataclass
class Verdict:
    sufficient: bool
    missing: str
    query: str
    raw: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_log(self) -> dict:
        """What the trace keeps for a verdict."""
        return {"sufficient": self.sufficient, "missing": self.missing, "query": self.query}


def parse_verdict(text: str) -> Verdict:
    """Parse and validate the Critic's output; raise SchemaError when it is not a usable verdict.

    ``sufficient`` must be a JSON boolean (the strings "true" / "false" are accepted with a
    warning). When it is false, ``missing`` and ``query`` must be non-empty strings: an
    "insufficient" verdict that does not say what to look for cannot drive a re-query.
    When it is true the two strings are kept as given and ignored by the loop.
    """
    obj = parse_json_object(text)
    warnings: list[str] = []
    sufficient = obj.get("sufficient")
    if isinstance(sufficient, str) and sufficient.strip().lower() in ("true", "false"):
        warnings.append(f"sufficient was the string {sufficient!r}; converted")
        sufficient = sufficient.strip().lower() == "true"
    if not isinstance(sufficient, bool):
        raise SchemaError(f"sufficient must be true or false, got {obj.get('sufficient')!r}")
    out: dict[str, str] = {}
    for key in ("missing", "query"):
        value = obj.get(key)
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise SchemaError(f"{key} must be a string, got {type(value).__name__}")
        out[key] = normalize_ws(value)
    if not sufficient:
        for key in ("missing", "query"):
            if not out[key]:
                raise SchemaError(f"{key} must be a non-empty string when sufficient is false")
    return Verdict(sufficient=sufficient, missing=out["missing"], query=out["query"], raw=text, warnings=warnings)


def label_definition(label: str, taxonomy: dict) -> str:
    """The catalogue entry (or special-label definition) of ``label``, in the diagnosis prompt's layout."""
    for item in taxonomy["items"]:
        if item["id"] == label:
            line = f"- {item['id']} ({item.get('concept', '')}): {normalize_ws(item['description'])}"
            if item.get("notes"):
                line += f" Notes: {normalize_ws(item['notes'])}"
            return line
    for sp in taxonomy["special_labels"]:
        if sp["id"] == label:
            return f"- {sp['id']}: {normalize_ws(sp['definition'])}"
    raise KeyError(f"label {label!r} is not in the taxonomy")


def draft_json(record: Record) -> str:
    """The draft as the Critic sees it: label, evidence, confidence. Nothing from ``meta``."""
    return json.dumps({"label": record.label,
                       "evidence": [asdict(e) for e in record.evidence],
                       "confidence": record.confidence}, ensure_ascii=False)


def render_messages(template: PromptTemplate, row: dict, hits: list[Hit], draft: Record,
                    taxonomy: dict) -> list[dict]:
    user = Template(template.user).substitute(
        question=row["question"].strip(),
        instructor_answer=row["instructor_answer"].strip(),
        student_answer=row["student_answer"].strip(),
        retrieved_chunks=rag.format_chunks(hits),
        draft_record=draft_json(draft),
        draft_label_definition=label_definition(draft.label, taxonomy),
    )
    messages = []
    if template.system:
        messages.append({"role": "system", "content": template.system})
    messages.append({"role": "user", "content": user})
    return messages


def judge(row: dict, client, template: PromptTemplate, hits: list[Hit], draft: Record, taxonomy: dict,
          *, temperature: float = 0.0, seed: int | None = 0, max_tokens: int = 2048,
          json_mode: bool = True, max_repairs: int = 1) -> tuple[Verdict | None, dict]:
    """One Critic verdict on ``draft`` given the chunks shown so far.

    Returns (verdict, info). ``verdict`` is None when the call failed or the output was still
    invalid after ``max_repairs`` repair round-trips; ``info`` then carries ``stage`` and
    ``error``. ``info`` always has ``attempts``, ``prompt_tokens``, ``completion_tokens``,
    ``cached``, ``prompt_chars`` and the last ``raw`` text.
    """
    messages = render_messages(template, row, hits, draft, taxonomy)
    info = {"attempts": 0, "prompt_tokens": 0, "completion_tokens": 0, "cached": True,
            "prompt_chars": prompt_chars(messages), "raw": ""}
    last_err: tuple[str, str] = ("validate", "unknown")
    while info["attempts"] <= max_repairs:
        info["attempts"] += 1
        try:
            resp = client.chat(messages, temperature=temperature, seed=seed, max_tokens=max_tokens,
                               json_mode=json_mode)
        except LLMError as e:
            info.update(stage="llm_call", error=str(e))
            return None, info
        info["prompt_tokens"] += resp.usage.prompt_tokens
        info["completion_tokens"] += resp.usage.completion_tokens
        info["cached"] = info["cached"] and resp.cached
        info["raw"] = resp.text
        try:
            verdict = parse_verdict(resp.text)
        except SchemaError as e:
            stage = "parse" if "JSON" in str(e) or "empty" in str(e) else "validate"
            msg = f"{e} (finish_reason=length: raise max_tokens)" if resp.finish_reason == "length" else str(e)
            last_err = (stage, msg)
            messages = messages + [
                {"role": "assistant", "content": resp.text or ""},
                {"role": "user", "content": f"Your previous output was invalid: {msg}. "
                                            "Return only the corrected JSON object."},
            ]
            continue
        return verdict, info
    info.update(stage=last_err[0], error=last_err[1])
    return None, info
