"""Condition 1: direct LLM diagnosis.

Zero-shot prompt with the question, the instructor's reference answer and the
student's answer. No taxonomy descriptions, no retrieval, no examples: the
prompt lists only the allowed label ids plus the three special labels and asks
for the JSON record (see configs/prompts/direct_v1.txt).

Templates are versioned files in configs/prompts/. The run manifest records
the template name and the SHA-256 of its text.

If the model's output fails to parse or validate, up to ``max_repairs`` extra
round-trips append the error and ask for a corrected JSON object. Every call
goes through the LLM cache, so repairs are deterministic too.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template

from src.config import PROMPT_DIR, sha256_text
from src.llm import LLMClient, LLMError
from src.schema import Record, SchemaError, parse_json_object, special_labels, validate_record

CONDITION = 1
NAME = "direct"
DEFAULT_TEMPLATE = "direct_v1"
SEPARATOR = "\n---\n"


@dataclass
class PromptTemplate:
    name: str
    system: str
    user: str
    sha256: str
    path: str


def load_template(name: str = DEFAULT_TEMPLATE, prompt_dir: Path = PROMPT_DIR) -> PromptTemplate:
    path = Path(prompt_dir) / f"{name}.txt"
    text = path.read_text(encoding="utf-8")
    if SEPARATOR in text:
        system, _, user = text.partition(SEPARATOR)
    else:
        system, user = "", text
    return PromptTemplate(name=name, system=system.strip(), user=user.strip(),
                          sha256=sha256_text(text), path=str(path))


def render_messages(template: PromptTemplate, row: dict, labels: list[str]) -> list[dict]:
    """Fill the template. ``labels`` is the full closed set; only non-special ids are listed."""
    specials = set(special_labels())
    ids = [l for l in labels if l not in specials]
    user = Template(template.user).substitute(
        question=row["question"].strip(),
        instructor_answer=row["instructor_answer"].strip(),
        student_answer=row["student_answer"].strip(),
        label_ids="\n".join(f"- {i}" for i in ids),
    )
    messages = []
    if template.system:
        messages.append({"role": "system", "content": template.system})
    messages.append({"role": "user", "content": user})
    return messages


def predict_row(row: dict, client: LLMClient, template: PromptTemplate, labels: list[str],
                *, temperature: float = 0.0, seed: int | None = 0, max_tokens: int = 2048,
                json_mode: bool = True, max_repairs: int = 1) -> tuple[Record | None, dict | None]:
    """Return (record, None) on success or (None, error_dict) on failure.

    The error dict carries the stage (llm_call / parse / validate), the message and
    the raw text of the last attempt, plus token usage so failed rows still count.
    """
    messages = render_messages(template, row, labels)
    usage_prompt = usage_completion = 0
    cached_all = True
    attempts = 0
    last_raw = ""
    last_err: tuple[str, str] | None = None
    while attempts <= max_repairs:
        attempts += 1
        try:
            resp = client.chat(messages, temperature=temperature, seed=seed,
                               max_tokens=max_tokens, json_mode=json_mode)
        except LLMError as e:
            return None, {"id": row["id"], "stage": "llm_call", "error": str(e), "raw": last_raw,
                          "attempts": attempts, "usage": {"prompt_tokens": usage_prompt,
                                                          "completion_tokens": usage_completion}}
        usage_prompt += resp.usage.prompt_tokens
        usage_completion += resp.usage.completion_tokens
        cached_all = cached_all and resp.cached
        last_raw = resp.text
        try:
            obj = parse_json_object(resp.text)
            stage = "validate"
            record = validate_record(obj, row_id=row["id"], student_answer=row["student_answer"],
                                     labels=labels, raw=resp.text, question_id=row.get("question_id"))
        except SchemaError as e:
            stage = "parse" if "JSON" in str(e) or "empty" in str(e) else "validate"
            last_err = (stage, str(e))
            if resp.finish_reason == "length":
                last_err = (stage, f"{e} (finish_reason=length: raise max_tokens)")
            messages = messages + [
                {"role": "assistant", "content": resp.text or ""},
                {"role": "user", "content": f"Your previous output was invalid: {last_err[1]}. "
                                            "Return only the corrected JSON object."},
            ]
            continue
        record.meta.update({
            "prompt_tokens": usage_prompt, "completion_tokens": usage_completion,
            "cached": cached_all, "attempts": attempts, "finish_reason": resp.finish_reason,
            "cache_key": resp.cache_key, "reasoning_chars": len(resp.reasoning or ""),
        })
        return record, None
    stage, msg = last_err or ("validate", "unknown")
    return None, {"id": row["id"], "stage": stage, "error": msg, "raw": last_raw, "attempts": attempts,
                  "usage": {"prompt_tokens": usage_prompt, "completion_tokens": usage_completion}}
