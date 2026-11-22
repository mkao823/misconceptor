"""Shared helpers for the condition 4 / 4b / positive-control tests (mock client, no network)."""

import csv
import importlib.util
import json
from pathlib import Path

from src.config import REPO_ROOT
from src.llm import LLMClient

CFG = {"default_model": "fake-model", "default_provider": "fake",
       "providers": {"fake": {"base_url": None, "api_key_env": "X", "api_key_required": False, "models": []}}}
# A synthetic row (not from the sheet) on an in-scope question id.
ROW = {"id": "E05.Q04.SYN", "question_id": "E05.Q04",
       "question": "What is the base case for a recursive implementation of merge sort?",
       "instructor_answer": "When the size of the array to be sorted is 1 (or 2)",
       "student_answer": "it stops when the piece has two   elements left"}
SETTINGS = {"temperature": 0.0, "seed": 0, "max_tokens": 2048, "json_mode": True, "max_repairs": 1}
CRITIC_MARKER = "Draft diagnosis"          # only the Critic template contains this


def reply(label="none", evidence=(), confidence=0.9) -> str:
    return json.dumps({"label": label, "evidence": list(evidence), "confidence": confidence})


def verdict(sufficient=True, missing="", query="") -> str:
    return json.dumps({"sufficient": sufficient, "missing": missing, "query": query})


def is_critic(request: dict) -> bool:
    user = next(m["content"] for m in request["messages"] if m["role"] == "user")
    return CRITIC_MARKER in user


class Scripted:
    """Transport that answers diagnosis and Critic prompts from two scripts.

    ``diagnoses`` and ``verdicts`` are lists of reply strings (or callables taking the request),
    used in order per kind; the last entry repeats. Token usage differs on every call, so a
    test that sums tokens cannot pass by accident.
    """

    def __init__(self, diagnoses, verdicts=()):
        self.scripts = {"diagnosis": list(diagnoses), "critic": list(verdicts)}
        self.seen = {"diagnosis": 0, "critic": 0}
        self.calls: list[dict] = []
        self.kinds: list[str] = []

    def __call__(self, request: dict) -> dict:
        kind = "critic" if is_critic(request) else "diagnosis"
        script = self.scripts[kind]
        if not script:
            raise AssertionError(f"unexpected {kind} call")
        item = script[min(self.seen[kind], len(script) - 1)]
        self.seen[kind] += 1
        self.calls.append(request)
        self.kinds.append(kind)
        text = item(request) if callable(item) else item
        n = len(self.calls)
        prompt_tokens = 100 + 11 * n + sum(len(m["content"]) for m in request["messages"]) // 4
        completion_tokens = 5 + 3 * n
        return {"id": f"scripted-{n}", "model": "fake-model",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                          "total_tokens": prompt_tokens + completion_tokens}}


def client_for(transport, cache_dir=None) -> LLMClient:
    """A client on ``transport``; no disk cache unless ``cache_dir`` is given."""
    return LLMClient("fake-model", transport=transport, cache_dir=cache_dir, models_cfg=CFG)


def load_script(name: str):
    """Import scripts/<name>.py as a module (the scripts are not a package)."""
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_sheet(path: Path) -> Path:
    """A two-row sheet of invented answers on two in-scope questions (never the real sheet)."""
    rows = [{"id": "E05.Q04.S1", "question_id": "E05.Q04", "question": ROW["question"],
             "instructor_answer": ROW["instructor_answer"], "student_answer": "two elements", "score_avg": "5.0"},
            {"id": "E10.Q07.S1", "question_id": "E10.Q07",
             "question": "How many comparisons does it take to find an element in a binary search tree?",
             "instructor_answer": "The height of the tree (or log of the number of elements in the tree) .",
             "student_answer": "about half of the nodes", "score_avg": "1.0"}]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def run_script(rc, monkeypatch, capsys, tmp_path, *argv) -> dict:
    """Run scripts/run_condition.py main() with the mock client on the synthetic sheet; return its outputs."""
    sheet = tmp_path / "sheet.csv"
    if not sheet.exists():
        synthetic_sheet(sheet)
    monkeypatch.setattr("sys.argv", ["run_condition.py", "--mock", "--no-cache", "--sheet", str(sheet),
                                     "--out-root", str(tmp_path), *argv])
    rc.main()
    capsys.readouterr()
    folder = tmp_path / argv[argv.index("--run-id") + 1]
    return {"manifest": json.loads((folder / "manifest.json").read_text()),
            "predictions": [json.loads(l) for l in (folder / "predictions.jsonl").read_text().splitlines()],
            "errors": [json.loads(l) for l in (folder / "errors.jsonl").read_text().splitlines()]}
