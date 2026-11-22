"""Run one ablation condition on the annotation sheet and write results/<run_id>/.

Conditions: 0 keyword baseline, 1 direct LLM, 2 + course-material RAG (static top-k),
3 + full taxonomy text and few-shot examples (single pass).

Outputs:
  manifest.json     condition, model, prompt template + hash, generation settings,
                    git commit, timestamp, token totals and means per row, cost
                    placeholder, counts; for conditions 2 and 3 also the retrieval
                    backend, k and corpus hash (and the few-shot file + hash for 3)
  predictions.jsonl one validated record per row (see src/schema.py); meta holds the
                    prompt and completion tokens and, for conditions 2 and 3, the ids,
                    scores and ranks of the chunks retrieved for that row
  errors.jsonl      rows whose model output could not be parsed or validated

run_id = <cond>_<model>_<timestamp>  (model = "keyword" for condition 0;
"mock" when --mock is used, so mock runs are never mistaken for real ones).

Ollama note: conditions 2 and 3 do not fit Ollama's default 4096-token context, and
Ollama truncates long prompts silently. Start the server with a larger window:
    OLLAMA_CONTEXT_LENGTH=16384 ollama serve
The run checks the loaded window before the first live call and stops if it is too small.

Usage:
    python scripts/run_condition.py --cond 0
    python scripts/run_condition.py --cond 1 [--limit 5] [--model ollama/gpt-oss:20b] [--mock]
    python scripts/run_condition.py --cond 2 [--k 4] [--retrieval-backend bm25|dense] [--exclude-chunk ID]
    python scripts/run_condition.py --cond 3 [--k 4] [--fewshot fewshot_v1]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import ANNOTATION_SHEET, RESULTS_DIR, TAXONOMY_PATH, load_config, sha256_file, sha256_text  # noqa: E402
from src.schema import label_set, load_taxonomy  # noqa: E402

CONDITIONS = {0: "keyword", 1: "direct", 2: "rag", 3: "taxonomy_fewshot"}
MOCK_RECORD = '{"label": "insufficient_evidence", "evidence": [], "confidence": 0.5}'
# Upper estimate of prompt tokens from characters for the context-window check. English prose
# and these prompts measure about 4.1 characters per token on gpt-oss:20b; 3 leaves a margin.
CHARS_PER_TOKEN_FLOOR = 3.0


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


def check_context_window(client, prepared: list[dict], settings: dict) -> dict:
    """Refuse to start when the longest prompt plus the completion budget cannot fit the context
    window the server has the model loaded with (Ollama truncates silently). The window is only
    looked up, and the model only loaded, when at least one row is not already in the cache."""
    from src.baselines.direct import prompt_chars

    max_chars = max((prompt_chars(p["messages"]) for p in prepared), default=0)
    need = math.ceil(max_chars / CHARS_PER_TOKEN_FLOOR) + settings["max_tokens"]
    info = {"context_length": None, "max_prompt_chars": max_chars, "estimated_tokens_needed": need}
    gen = {k: settings[k] for k in ("temperature", "seed", "max_tokens", "json_mode")}
    if all(client.is_cached(p["messages"], **gen) for p in prepared):
        return info
    ctx = client.loaded_context_length()
    info["context_length"] = ctx
    if ctx is not None and need > ctx:
        raise SystemExit(
            f"{client.provider}/{client.model} is loaded with a {ctx}-token context window, but this run "
            f"needs about {need} tokens (longest prompt {max_chars} characters, at most "
            f"{math.ceil(max_chars / CHARS_PER_TOKEN_FLOOR)} tokens, plus max_tokens {settings['max_tokens']}). "
            "Ollama would truncate the prompt silently. Restart the server with a larger window, for "
            "example `OLLAMA_CONTEXT_LENGTH=16384 ollama serve`, or lower --k / --max-tokens.")
    return info


def tokens_per_row(predictions: list[dict], errors: list[dict]) -> dict:
    """Mean prompt / completion / total tokens per row, over every row that reached the model."""
    usage = [(p["meta"].get("prompt_tokens", 0), p["meta"].get("completion_tokens", 0)) for p in predictions]
    usage += [(e.get("usage", {}).get("prompt_tokens", 0), e.get("usage", {}).get("completion_tokens", 0))
              for e in errors]
    n = len(usage)
    if not n:
        return {"n_rows": 0, "mean_prompt_tokens": None, "mean_completion_tokens": None, "mean_total_tokens": None}
    mp, mc = sum(u[0] for u in usage) / n, sum(u[1] for u in usage) / n
    return {"n_rows": n, "mean_prompt_tokens": round(mp, 1), "mean_completion_tokens": round(mc, 1),
            "mean_total_tokens": round(mp + mc, 1)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cond", type=int, required=True, choices=sorted(CONDITIONS))
    ap.add_argument("--limit", type=int, default=None, help="only the first N rows")
    ap.add_argument("--model", default=None, help="provider/model or model (default: configs/models.yaml)")
    ap.add_argument("--sheet", type=Path, default=ANNOTATION_SHEET)
    ap.add_argument("--out-root", type=Path, default=RESULTS_DIR)
    ap.add_argument("--prompt", default=None, help="prompt template name in configs/prompts/ (cond 1-3)")
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--max-repairs", type=int, default=None)
    ap.add_argument("--no-cache", action="store_true", help="bypass results/cache/")
    ap.add_argument("--mock", action="store_true", help="use a mock client that returns a fixed valid record")
    ap.add_argument("--run-id", default=None, help="override the generated run id")
    ap.add_argument("--k", type=int, default=None, help="chunks retrieved per row (cond 2-3; default 4)")
    ap.add_argument("--retrieval-backend", choices=("bm25", "dense"), default="bm25",
                    help="bm25 (default) or dense (needs an embedding model already installed in Ollama)")
    ap.add_argument("--corpus-dir", type=Path, default=None, help="corpus directory (default data/corpus/)")
    ap.add_argument("--exclude-chunk", action="append", default=[], metavar="CHUNK_ID",
                    help="withhold this chunk id from retrieval on every row (repeatable)")
    ap.add_argument("--keep-own-reference", action="store_true",
                    help="allow retrieval of the row's own instructor-answer chunk (already in the prompt)")
    ap.add_argument("--fewshot", default=None, help="few-shot file name in configs/prompts/ (cond 3)")
    args = ap.parse_args()
    if args.k is not None and args.k < 0:
        ap.error("--k must be >= 0")

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
        "retrieval": None, "fewshot": None, "context_window": None,
        "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "tokens_uncached": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "calls": {"uncached": 0, "cached": 0},
        "tokens_per_row": None,
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
        from src.baselines import direct, rag, taxonomy_fewshot
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
        module = {1: direct, 2: rag, 3: taxonomy_fewshot}[args.cond]
        template = direct.load_template(args.prompt or module.DEFAULT_TEMPLATE)
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
        print(f"condition {args.cond}: {client.provider}/{client.model} via {manifest['transport']}, "
              f"template {template.name} ({template.sha256[:12]}), {len(rows)} rows", flush=True)

        retriever = fewshot = None
        retrieve_args: dict = {}
        if args.cond >= 2:
            from src.retrieval import CORPUS_DIR, DEFAULT_K, CorpusError, make_retriever
            k = args.k if args.k is not None else DEFAULT_K
            try:
                retriever = make_retriever(args.retrieval_backend, corpus_dir=args.corpus_dir or CORPUS_DIR)
            except (CorpusError, RuntimeError) as e:
                raise SystemExit(f"retrieval ({args.retrieval_backend}): {e}")
            unknown = [c for c in args.exclude_chunk if c not in retriever.corpus]
            if unknown:
                raise SystemExit(f"--exclude-chunk: unknown chunk ids {unknown} (see data/corpus/chunks.jsonl)")
            retrieve_args = {"k": k, "exclude": args.exclude_chunk, "keep_own_reference": args.keep_own_reference}
            desc = retriever.describe()
            manifest["retrieval"] = {
                "backend": desc.pop("backend"), "k": k, "corpus_hash": desc.pop("corpus_hash"),
                "query": "question + student_answer",
                "own_instructor_answer_withheld": not args.keep_own_reference,
                "excluded_chunk_ids": list(args.exclude_chunk), **desc}
            print(f"retrieval: {manifest['retrieval']['backend']}, k={k}, {manifest['retrieval']['n_chunks']} chunks, "
                  f"corpus {manifest['retrieval']['corpus_hash'][:12]}", flush=True)
        if args.cond == 3:
            fewshot = taxonomy_fewshot.load_fewshot(args.fewshot or taxonomy_fewshot.DEFAULT_FEWSHOT, labels=labels)
            manifest["fewshot"] = {"name": fewshot.name, "path": str(Path(fewshot.path).relative_to(REPO_ROOT)),
                                   "sha256": fewshot.sha256, "n_examples": len(fewshot.examples),
                                   "labels": fewshot.labels, "provenance": fewshot.provenance}
            manifest["taxonomy"]["rendered_sha256"] = sha256_text(taxonomy_fewshot.taxonomy_text(taxonomy))

        def prepare(row: dict) -> dict:
            if args.cond == 1:
                return {"messages": direct.render_messages(template, row, labels), "retrieved_chunks": None,
                        "taxonomy_text": None, "extra_meta": {}}
            if args.cond == 2:
                return rag.prepare_row(row, template, labels, retriever, **retrieve_args)
            return taxonomy_fewshot.prepare_row(row, template, retriever, taxonomy, fewshot, **retrieve_args)

        prepared = [prepare(row) for row in rows]
        manifest["context_window"] = check_context_window(client, prepared, settings)

        for i, (row, prep) in enumerate(zip(rows, prepared), 1):
            rec, err = direct.complete_and_validate(
                row, client, prep["messages"], labels, retrieved_chunks=prep["retrieved_chunks"],
                taxonomy_text=prep["taxonomy_text"], extra_meta=prep["extra_meta"], **settings)
            hits = " ".join(h["id"] for h in prep["extra_meta"].get("retrieved", []))
            if rec is not None:
                predictions.append(rec.to_dict())
                flag = "" if rec.citation_valid else "  [INVALID CITATION]"
                print(f"[{i}/{len(rows)}] {rec.id}\t{rec.label}\tconf={rec.confidence}"
                      f"\t{'cached' if rec.meta.get('cached') else 'live'}"
                      f"\ttokens={rec.meta['prompt_tokens']}+{rec.meta['completion_tokens']}"
                      f"{chr(9) + hits if hits else ''}{flag}", flush=True)
            else:
                errors.append(err)
                print(f"[{i}/{len(rows)}] {row['id']}\tERROR ({err['stage']}): {err['error'][:120]}", flush=True)
        manifest["tokens_per_row"] = tokens_per_row(predictions, errors)
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

    from src.eval.metrics import citation_validity
    dist = Counter(p["label"] for p in predictions)
    cv = citation_validity(predictions)
    print(f"\nrun_id: {run_id}")
    try:
        shown = out.resolve().relative_to(REPO_ROOT)
    except ValueError:
        shown = out
    print(f"wrote {shown}/  predictions={len(predictions)} errors={len(errors)}")
    print(f"label distribution: {dict(dist.most_common())}")
    print(f"citation validity: {cv['n_valid']}/{cv['n_with_student_spans']} records with student_answer spans are verbatim")
    if args.cond >= 2:
        extra = f"; taxonomy spans {cv['taxonomy']['n_valid']}/{cv['taxonomy']['n_with_spans']}" if args.cond >= 3 else ""
        print(f"                   {cv['retrieved']['n_valid']}/{cv['retrieved']['n_with_spans']} records with "
              f"retrieved spans are verbatim{extra}")
    if manifest["model"] != "keyword":
        print(f"tokens: {manifest['tokens']}  calls: {manifest['calls']}  cost: {manifest['cost']['usd']}")
        print(f"tokens per row: {manifest['tokens_per_row']}")
    print(f"next: make eval RUN={run_id}")


if __name__ == "__main__":
    main()
