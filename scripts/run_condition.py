"""Run one ablation condition on the annotation sheet and write results/<run_id>/.

Outputs:
  manifest.json     condition, model, prompt template + hash, generation settings,
                    git commit, timestamp, token totals, cost placeholder, counts
  predictions.jsonl one validated record per row (see src/schema.py)
  errors.jsonl      rows whose model output could not be parsed or validated

run_id = <cond>_<model>_<timestamp>  (model = "keyword" for condition 0;
"mock" when --mock is used, so mock runs are never mistaken for real ones).

Usage:
    python scripts/run_condition.py --cond 0
    python scripts/run_condition.py --cond 1 [--limit 5] [--model ollama/gpt-oss:20b] [--mock]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import ANNOTATION_SHEET, RESULTS_DIR, TAXONOMY_PATH, load_config, sha256_file  # noqa: E402
from src.schema import label_set, load_taxonomy  # noqa: E402

CONDITIONS = {0: "keyword", 1: "direct"}
MOCK_RECORD = '{"label": "insufficient_evidence", "evidence": [], "confidence": 0.5}'


def read_sheet(path: Path, limit: int | None) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    required = {"id", "question_id", "question", "instructor_answer", "student_answer"}
    missing = required - set(rows[0].keys() if rows else [])
    if missing:
        raise SystemExit(f"{path}: missing columns {sorted(missing)}")
    return rows[:limit] if limit else rows


def git_info() -> dict:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True).strip())
        return {"commit": commit, "dirty": dirty}
    except Exception:  # noqa: BLE001
        return {"commit": None, "dirty": None}


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "-", text).strip("-")


def write_jsonl(path: Path, items: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cond", type=int, required=True, choices=sorted(CONDITIONS))
    ap.add_argument("--limit", type=int, default=None, help="only the first N rows")
    ap.add_argument("--model", default=None, help="provider/model or model (default: configs/models.yaml)")
    ap.add_argument("--sheet", type=Path, default=ANNOTATION_SHEET)
    ap.add_argument("--out-root", type=Path, default=RESULTS_DIR)
    ap.add_argument("--prompt", default=None, help="prompt template name in configs/prompts/ (cond 1)")
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--max-repairs", type=int, default=None)
    ap.add_argument("--no-cache", action="store_true", help="bypass results/cache/")
    ap.add_argument("--mock", action="store_true", help="use a mock client that returns a fixed valid record")
    ap.add_argument("--run-id", default=None, help="override the generated run id")
    args = ap.parse_args()

    rows = read_sheet(args.sheet, args.limit)
    taxonomy = load_taxonomy()
    labels = label_set(taxonomy)
    models_cfg = load_config("models")
    gen = dict(models_cfg.get("generation") or {})
    started = datetime.now().astimezone()
    t0 = time.time()

    manifest: dict = {
        "condition": args.cond,
        "condition_name": CONDITIONS[args.cond],
        "timestamp": started.isoformat(timespec="seconds"),   # local time with UTC offset
        "git": git_info(),
        "sheet": {"path": str(args.sheet.relative_to(REPO_ROOT) if args.sheet.is_absolute() and args.sheet.is_relative_to(REPO_ROOT) else args.sheet),
                  "sha256": sha256_file(args.sheet), "n_rows_total": None, "n_rows_run": len(rows), "limit": args.limit},
        "taxonomy": {"path": str(TAXONOMY_PATH.relative_to(REPO_ROOT)), "version": taxonomy.get("version"),
                     "sha256": sha256_file(TAXONOMY_PATH), "n_labels": len(labels)},
        "model": None, "provider": None, "transport": "none",
        "prompt_template": None, "temperature": None, "seed": None, "max_tokens": None, "json_mode": None,
        "max_repairs": None, "cache_used": None,
        "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "tokens_uncached": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "calls": {"uncached": 0, "cached": 0},
        "cost": {"usd": None, "note": "placeholder: computed from provider cost_per_1m_tokens when set"},
        "n_predictions": 0, "n_errors": 0, "wall_seconds": None,
    }
    with open(args.sheet, newline="", encoding="utf-8") as f:
        manifest["sheet"]["n_rows_total"] = sum(1 for _ in csv.DictReader(f))

    predictions: list[dict] = []
    errors: list[dict] = []

    if args.cond == 0:
        from src.baselines import keyword
        model_slug = "keyword"
        manifest["model"] = "keyword"
        for rec in keyword.run(rows, taxonomy):
            predictions.append(rec.to_dict())
            print(f"{rec.id}\t{rec.label}\t{rec.meta.get('matches') or ''}")
    else:
        from src.baselines import direct
        from src.llm import LLMClient, MockTransport
        if args.mock:   # own provider + model name, so mock calls never share the real model's cache
            models_cfg = {"default_model": "mock", "default_provider": "mock", "generation": gen,
                          "providers": {"mock": {"base_url": None, "api_key_env": "MOCK_API_KEY",
                                                 "api_key_required": False, "models": ["mock"]}}}
            client = LLMClient("mock", transport=MockTransport(MOCK_RECORD, model="mock"),
                               use_cache=not args.no_cache, models_cfg=models_cfg)
        else:
            client = LLMClient(args.model, use_cache=not args.no_cache, models_cfg=models_cfg)
        if not args.mock and not client.is_reachable():
            base = client.provider_cfg.get("base_url") or "the API"
            raise SystemExit(f"{client.provider}/{client.model}: endpoint {base} is not reachable. "
                             "For Ollama run `ollama serve` (or open the Ollama app), or pass --mock.")
        template = direct.load_template(args.prompt or direct.DEFAULT_TEMPLATE)
        settings = {
            "temperature": args.temperature if args.temperature is not None else float(gen.get("temperature", 0.0)),
            "seed": args.seed if args.seed is not None else gen.get("seed", 0),
            "max_tokens": args.max_tokens if args.max_tokens is not None else int(gen.get("max_output_tokens", 1024)),
            "json_mode": bool(gen.get("json_mode", True)),
            "max_repairs": args.max_repairs if args.max_repairs is not None else int(gen.get("max_repairs", 1)),
        }
        model_slug = slug(client.model)
        manifest.update({
            "model": client.model, "provider": client.provider,
            "transport": "mock" if args.mock else "openai-compatible",
            "base_url": client.provider_cfg.get("base_url"),
            "prompt_template": {"name": template.name, "path": str(Path(template.path).relative_to(REPO_ROOT)),
                                "sha256": template.sha256},
            "cache_used": client.use_cache, **settings,
        })
        print(f"condition 1: {client.provider}/{client.model} via {manifest['transport']}, "
              f"template {template.name} ({template.sha256[:12]}), {len(rows)} rows", flush=True)
        for i, row in enumerate(rows, 1):
            rec, err = direct.predict_row(row, client, template, labels, **settings)
            if rec is not None:
                predictions.append(rec.to_dict())
                flag = "" if rec.citation_valid else "  [INVALID CITATION]"
                print(f"[{i}/{len(rows)}] {rec.id}\t{rec.label}\tconf={rec.confidence}"
                      f"\t{'cached' if rec.meta.get('cached') else 'live'}{flag}", flush=True)
            else:
                errors.append(err)
                print(f"[{i}/{len(rows)}] {row['id']}\tERROR ({err['stage']}): {err['error'][:120]}", flush=True)
        stats = client.stats()
        manifest["tokens"] = stats["tokens_total"]
        manifest["tokens_uncached"] = stats["tokens_uncached"]
        manifest["calls"] = {"uncached": stats["calls_uncached"], "cached": stats["calls_cached"]}
        cost = client.provider_cfg.get("cost_per_1m_tokens")
        if cost:
            manifest["cost"]["usd"] = round(stats["tokens_total"]["prompt_tokens"] / 1e6 * float(cost.get("prompt", 0))
                                            + stats["tokens_total"]["completion_tokens"] / 1e6 * float(cost.get("completion", 0)), 6)
            manifest["cost"]["note"] = f"from {client.provider}.cost_per_1m_tokens over all tokens incl. cache hits"

    run_id = args.run_id or f"{args.cond}_{model_slug}_{started.strftime('%Y%m%d-%H%M%S')}"
    out = args.out_root / run_id
    out.mkdir(parents=True, exist_ok=False)
    manifest.update({"run_id": run_id, "n_predictions": len(predictions), "n_errors": len(errors),
                     "wall_seconds": round(time.time() - t0, 1)})
    write_jsonl(out / "predictions.jsonl", predictions)
    write_jsonl(out / "errors.jsonl", errors)
    with open(out / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    from collections import Counter
    dist = Counter(p["label"] for p in predictions)
    n_cited = sum(1 for p in predictions if any(e["source"] == "student_answer" for e in p["evidence"]))
    n_valid = sum(1 for p in predictions if p["citation_valid"] and any(e["source"] == "student_answer" for e in p["evidence"]))
    print(f"\nrun_id: {run_id}")
    print(f"wrote {out.relative_to(REPO_ROOT)}/  predictions={len(predictions)} errors={len(errors)}")
    print(f"label distribution: {dict(dist.most_common())}")
    print(f"citation validity: {n_valid}/{n_cited} records with student_answer spans are verbatim")
    if manifest["model"] != "keyword":
        print(f"tokens: {manifest['tokens']}  calls: {manifest['calls']}  cost: {manifest['cost']['usd']}")
    print(f"next: make eval RUN={run_id}")


if __name__ == "__main__":
    main()
