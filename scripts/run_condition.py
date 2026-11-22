"""Run one ablation condition on the annotation sheet and write results/<run_id>/.

Conditions: 0 keyword baseline, 1 direct LLM, 2 + course-material RAG (static top-k),
3 + full taxonomy text and few-shot examples (single pass), 4 + Critic-driven re-retrieval
(src/pipeline/, docs/CRITIC_SPEC.md), 4b self-consistency on condition 3's prompt with a
token budget matched to a named condition 4 run (src/baselines/self_consistency.py).

Outputs:
  manifest.json     condition, model, prompt template + hash, generation settings,
                    git commit, timestamp, token totals and means per row, total tokens
                    and number of model calls for every row (`per_row`, `calls_per_row`),
                    cost placeholder, counts; for conditions 2 and up also the retrieval
                    backend, k and corpus hash (and the few-shot file + hash from 3 up);
                    for 4 the Critic template, max_rounds, stop reasons and the budget
                    reference that 4b matches; for 4b N, both token means and the
                    planned and measured budget ratio 4b to 4
  predictions.jsonl one validated record per row (see src/schema.py); meta holds the
                    prompt and completion tokens (row totals over every call) and, for
                    conditions 2 and up, the ids, scores and ranks of the chunks shown;
                    condition 4 adds `trace` (per round: chunk ids, Critic verdict,
                    query, tokens; and every model call), 4b adds the vote and samples
  errors.jsonl      rows whose model output could not be parsed or validated

run_id = <cond>_<model>_<timestamp>  (model = "keyword" for condition 0;
"mock" when --mock is used, so mock runs are never mistaken for real ones).

Ollama note: conditions 2 and up do not fit Ollama's default 4096-token context, and
Ollama truncates long prompts silently. Start the server with a larger window:
    OLLAMA_CONTEXT_LENGTH=16384 ollama serve
The run checks the loaded window before the first live call and stops if it is too small.

Usage:
    python scripts/run_condition.py --cond 0
    python scripts/run_condition.py --cond 1 [--limit 5] [--model ollama/gpt-oss:20b] [--mock]
    python scripts/run_condition.py --cond 2 [--k 4] [--retrieval-backend bm25|dense] [--exclude-chunk ID]
    python scripts/run_condition.py --cond 3 [--k 4] [--fewshot fewshot_v1]
    python scripts/run_condition.py --cond 4 [--max-rounds 2] [--critic-prompt critic_v1]
    python scripts/run_condition.py --cond 4b --match-run <condition 4 run id or folder>
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

# Conditions 0 to 4 are integers (in --cond, in the manifest and as keys here); "4b" is a string.
CONDITIONS = {0: "keyword", 1: "direct", 2: "rag", 3: "taxonomy_fewshot", 4: "critic_loop",
              "4b": "self_consistency"}
RETRIEVAL_CONDITIONS = (2, 3, 4, "4b")
TAXONOMY_CONDITIONS = (3, 4, "4b")             # condition 3's prompt: taxonomy text + few-shot examples
MOCK_RECORD = '{"label": "insufficient_evidence", "evidence": [], "confidence": 0.5}'
MOCK_VERDICT = '{"sufficient": true, "missing": "", "query": ""}'
# Upper estimate of prompt tokens from characters for the context-window check. English prose
# and these prompts measure about 4.1 characters per token on gpt-oss:20b; 3 leaves a margin.
CHARS_PER_TOKEN_FLOOR = 3.0


def parse_cond(text: str):
    """--cond value: "0".."4" -> int, "4b" -> "4b"."""
    value = text.strip().lower()
    if value == "4b":
        return "4b"
    try:
        cond = int(value)
    except ValueError:
        cond = None
    if cond not in CONDITIONS:
        raise argparse.ArgumentTypeError(f"invalid condition {text!r} (choose from 0, 1, 2, 3, 4, 4b)")
    return cond


def mock_content(request: dict) -> str:
    """Canned --mock reply: a "sufficient" verdict for a Critic prompt, the fixed record otherwise."""
    first_user = next((m.get("content") or "" for m in request["messages"] if m.get("role") == "user"), "")
    return MOCK_VERDICT if '"sufficient"' in first_user else MOCK_RECORD


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


def check_context_window(client, prepared: list[dict], settings: dict, *, extra_chars: int = 0,
                         always: bool = False) -> dict:
    """Refuse to start when the longest prompt plus the completion budget cannot fit the context
    window the server has the model loaded with (Ollama truncates silently). The window is only
    looked up, and the model only loaded, when at least one row is not already in the cache.

    ``extra_chars`` is added to the longest prompt (condition 4: the chunks that later rounds can
    append). ``always`` skips the cache shortcut, for conditions whose later calls cannot be
    known to be cached from the first-pass prompts (4 and 4b)."""
    from src.baselines.direct import prompt_chars

    max_chars = max((prompt_chars(p["messages"]) for p in prepared), default=0) + extra_chars
    need = math.ceil(max_chars / CHARS_PER_TOKEN_FLOOR) + settings["max_tokens"]
    info = {"context_length": None, "max_prompt_chars": max_chars, "estimated_tokens_needed": need}
    gen = {k: settings[k] for k in ("temperature", "seed", "max_tokens", "json_mode")}
    if not always and all(client.is_cached(p["messages"], **gen) for p in prepared):
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


def per_row_usage(predictions: list[dict], errors: list[dict]) -> list[dict]:
    """Total tokens and number of model calls for every row that reached the model, in sheet order.

    Conditions 1 to 3 make one call per attempt (``attempts``); conditions 4 and 4b record the
    row's call count as ``n_calls`` and its token totals over all calls."""
    out = []
    for p in predictions:
        meta = p["meta"]
        pt, ct = meta.get("prompt_tokens", 0), meta.get("completion_tokens", 0)
        out.append({"id": p["id"], "prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct,
                    "calls": meta.get("n_calls", meta.get("attempts", 0)), "error": False})
    for e in errors:
        usage = e.get("usage", {})
        pt, ct = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        out.append({"id": e["id"], "prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct,
                    "calls": e.get("n_calls", e.get("attempts", 0)), "error": True})
    return out


def calls_per_row(per_row: list[dict]) -> dict:
    n = len(per_row)
    if not n:
        return {"n_rows": 0, "mean_calls": None, "min_calls": None, "max_calls": None}
    calls = [r["calls"] for r in per_row]
    return {"n_rows": n, "mean_calls": round(sum(calls) / n, 2), "min_calls": min(calls), "max_calls": max(calls)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cond", type=parse_cond, required=True, metavar="{0,1,2,3,4,4b}",
                    help="condition to run: 0, 1, 2, 3, 4 or 4b")
    ap.add_argument("--limit", type=int, default=None, help="only the first N rows")
    ap.add_argument("--model", default=None, help="provider/model or model (default: configs/models.yaml)")
    ap.add_argument("--sheet", type=Path, default=ANNOTATION_SHEET)
    ap.add_argument("--out-root", type=Path, default=RESULTS_DIR)
    ap.add_argument("--prompt", default=None,
                    help="diagnosis prompt template name in configs/prompts/ (cond 1-4b)")
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--max-repairs", type=int, default=None)
    ap.add_argument("--no-cache", action="store_true", help="bypass results/cache/")
    ap.add_argument("--mock", action="store_true", help="use a mock client that returns a fixed valid record")
    ap.add_argument("--run-id", default=None, help="override the generated run id")
    ap.add_argument("--k", type=int, default=None,
                    help="chunks retrieved per row, and per re-query in cond 4 (cond 2-4b; default 4)")
    ap.add_argument("--retrieval-backend", choices=("bm25", "dense"), default="bm25",
                    help="bm25 (default) or dense (needs an embedding model already installed in Ollama)")
    ap.add_argument("--corpus-dir", type=Path, default=None, help="corpus directory (default data/corpus/)")
    ap.add_argument("--exclude-chunk", action="append", default=[], metavar="CHUNK_ID",
                    help="withhold this chunk id from retrieval on every row (repeatable)")
    ap.add_argument("--keep-own-reference", action="store_true",
                    help="allow retrieval of the row's own instructor-answer chunk (already in the prompt)")
    ap.add_argument("--fewshot", default=None, help="few-shot file name in configs/prompts/ (cond 3, 4, 4b)")
    ap.add_argument("--max-rounds", type=int, default=None,
                    help="cond 4: refinement rounds allowed per row (default 2; 0 makes it equal to cond 3)")
    ap.add_argument("--critic-prompt", default=None, help="cond 4: Critic template name in configs/prompts/")
    ap.add_argument("--match-run", default=None, metavar="RUN",
                    help="cond 4b (required): the condition 4 run (id under results/, or a folder) whose "
                         "tokens per row set the number of samples N")
    args = ap.parse_args()
    if args.k is not None and args.k < 0:
        ap.error("--k must be >= 0")
    if args.max_rounds is not None and (args.cond != 4 or args.max_rounds < 0):
        ap.error("--max-rounds needs --cond 4 and a value >= 0")
    if args.critic_prompt is not None and args.cond != 4:
        ap.error("--critic-prompt needs --cond 4")
    if (args.match_run is not None) != (args.cond == "4b"):
        ap.error("--match-run is required with --cond 4b and only valid there")

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
        "tokens_per_row": None, "calls_per_row": None, "per_row": None,
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
            client = LLMClient("mock", transport=MockTransport(mock_content, model="mock"),
                               use_cache=not args.no_cache, models_cfg=models_cfg)
        else:
            client = LLMClient(args.model, use_cache=not args.no_cache, models_cfg=models_cfg)
        if not args.mock and not client.is_reachable():
            base = client.provider_cfg.get("base_url") or "the API"
            raise SystemExit(f"{client.provider}/{client.model}: endpoint {base} is not reachable. "
                             "For Ollama run `ollama serve` (or open the Ollama app), or pass --mock.")
        # conditions 4 and 4b diagnose with condition 3's template
        module = {1: direct, 2: rag, 3: taxonomy_fewshot, 4: taxonomy_fewshot, "4b": taxonomy_fewshot}[args.cond]
        template = direct.load_template(args.prompt or module.DEFAULT_TEMPLATE)
        sc_cfg = dict(models_cfg.get("self_consistency") or {})
        default_temperature = float(gen.get("temperature", 0.0))
        if args.cond == "4b":
            from src.baselines import self_consistency
            default_temperature = float(sc_cfg.get("temperature", self_consistency.DEFAULT_TEMPERATURE))
        settings = {
            "temperature": args.temperature if args.temperature is not None else default_temperature,
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
        if args.cond in RETRIEVAL_CONDITIONS:
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
        if args.cond in TAXONOMY_CONDITIONS:
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

        # For condition 4 these are the first-pass prompts (used for the context check only; the
        # loop renders its own, identical ones); for 4b they are the prompts that get sampled.
        prepared = [prepare(row) for row in rows]

        def report(i: int, row: dict, rec, err, hits: str, extra: str = "") -> None:
            if rec is not None:
                flag = "" if rec.citation_valid else "  [INVALID CITATION]"
                print(f"[{i}/{len(rows)}] {rec.id}\t{rec.label}\tconf={rec.confidence}"
                      f"\t{'cached' if rec.meta.get('cached') else 'live'}"
                      f"\ttokens={rec.meta['prompt_tokens']}+{rec.meta['completion_tokens']}"
                      f"{extra}{chr(9) + hits if hits else ''}{flag}", flush=True)
            else:
                print(f"[{i}/{len(rows)}] {row['id']}\tERROR ({err['stage']}): {err['error'][:120]}", flush=True)

        if args.cond == 4:
            from src.pipeline import loop
            from src.retrieval import Hit
            max_rounds = args.max_rounds if args.max_rounds is not None else loop.DEFAULT_MAX_ROUNDS
            critic_template = direct.load_template(args.critic_prompt or loop.DEFAULT_CRITIC_TEMPLATE)
            ctx = loop.Context(template=template, critic_template=critic_template, labels=labels,
                               retriever=retriever, taxonomy=taxonomy, fewshot=fewshot)
            # later rounds append up to max_rounds * k chunks to the first-pass prompt
            longest_chunk = max(len(rag.format_chunks([Hit(c, 0.0, 1)])) + 2 for c in retriever.corpus.chunks)
            manifest["context_window"] = check_context_window(
                client, prepared, settings, extra_chars=max_rounds * retrieve_args["k"] * longest_chunk,
                always=True)
            print(f"critic: template {critic_template.name} ({critic_template.sha256[:12]}), "
                  f"max_rounds={max_rounds}", flush=True)
            traces: list[dict] = []
            for i, row in enumerate(rows, 1):
                rec, err, trace = loop.run_row(row, client, ctx, max_rounds=max_rounds, **retrieve_args, **settings)
                traces.append(trace)
                if rec is not None:
                    predictions.append(loop.to_prediction(rec, trace))
                else:
                    errors.append(err)
                report(i, row, rec, err, " ".join(trace["rounds"][-1]["chunk_ids_shown"]),
                       f"\tstop={trace['stop_reason']} refinements={trace['n_refinements']} "
                       f"calls={trace['n_calls']}")
            n = len(traces)
            stop_reasons: dict[str, int] = {}
            for t in traces:
                stop_reasons[t["stop_reason"]] = stop_reasons.get(t["stop_reason"], 0) + 1
            manifest["critic"] = {
                "spec": "docs/CRITIC_SPEC.md",
                "template": {"name": critic_template.name,
                             "path": str(Path(critic_template.path).relative_to(REPO_ROOT)),
                             "sha256": critic_template.sha256},
                "max_rounds": max_rounds, "requery_k": retrieve_args["k"], "requery": "the Critic's query",
                "stop_reasons": stop_reasons,
                "n_rows_critic_called": sum(1 for t in traces if t["rounds"][0]["critic"] is not None),
                "n_rows_critic_triggered": sum(1 for t in traces if t["critic_triggered"]),
                "n_rows_refined": sum(1 for t in traces if t["n_refinements"] > 0),
                "n_rows_label_changed": sum(1 for t in traces if t["final_label"] is not None
                                            and t["final_label"] != t["first_pass_label"]),
                "mean_refinements": round(sum(t["n_refinements"] for t in traces) / n, 3) if n else None,
            }
            # What condition 4b matches: this run's mean tokens per row (T4) and the mean tokens of
            # one condition 3 call on the same rows (T3: the first attempt of the first pass).
            manifest["budget_reference"] = {
                "n_rows": n,
                "mean_total_tokens_per_row": round(sum(t["tokens"]["total_tokens"] for t in traces) / n, 1) if n else None,
                "mean_first_call_tokens_per_row": round(sum(t["first_call_tokens"] for t in traces) / n, 1) if n else None,
                "note": "N for condition 4b = max(3, ceil(mean_total_tokens_per_row / mean_first_call_tokens_per_row))",
            }
        elif args.cond == "4b":
            try:
                match = self_consistency.load_match_run(args.match_run, args.out_root)
            except ValueError as e:
                raise SystemExit(str(e))
            derived = self_consistency.derive_n_samples(
                match["mean_tokens_per_row"], match["mean_tokens_single_cond3_call"],
                floor=int(sc_cfg.get("min_samples", self_consistency.MIN_SAMPLES)))
            n_samples = derived["n_samples"]
            mm = match["manifest"]
            differences = [name for name, mine, theirs in (
                ("model", client.model, mm.get("model")),
                ("sheet", manifest["sheet"]["sha256"], (mm.get("sheet") or {}).get("sha256")),
                ("rows run", len(rows), (mm.get("sheet") or {}).get("n_rows_run")),
                ("prompt template", template.sha256, (mm.get("prompt_template") or {}).get("sha256")),
                ("k", retrieve_args["k"], (mm.get("retrieval") or {}).get("k")),
                ("corpus", manifest["retrieval"]["corpus_hash"], (mm.get("retrieval") or {}).get("corpus_hash")),
            ) if mine != theirs]
            if differences:
                print(f"WARNING: this run differs from the matched condition 4 run in: {', '.join(differences)}. "
                      "N was derived from that run's rows and settings.", flush=True)
            manifest["context_window"] = check_context_window(client, prepared, settings, always=True)
            print(f"self-consistency: N={n_samples} (floor applied: {derived['floor_applied']}), temperature "
                  f"{settings['temperature']}, matched to {match['run_id']}: T4={derived['mean_tokens_per_row_cond4']} "
                  f"T3={derived['mean_tokens_single_cond3_call']}", flush=True)
            for i, (row, prep) in enumerate(zip(rows, prepared), 1):
                rec, err = self_consistency.predict_row(row, client, prep, labels, n_samples=n_samples, **settings)
                if rec is not None:
                    predictions.append(rec.to_dict())
                else:
                    errors.append(err)
                extra = (f"\tvotes={rec.meta['votes']} tie_break={rec.meta['tie_break']} calls={rec.meta['n_calls']}"
                         if rec is not None else "")
                report(i, row, rec, err, "", extra)
            manifest["self_consistency"] = {
                **derived, "temperature": settings["temperature"],
                "seeds": self_consistency.sample_seeds(settings["seed"], n_samples),
                "vote": "plurality; ties: higher mean confidence, then earliest first sample; evidence and "
                        "confidence from the highest-confidence sample that voted for the winner",
                "match_run": {"run_id": match["run_id"], "path": match["path"], "n_rows": match["n_rows"],
                              "differs_in": differences},
                "mean_total_tokens_per_row_4b": None, "budget_ratio_4b_to_4_measured": None,
            }
        else:
            manifest["context_window"] = check_context_window(client, prepared, settings)
            for i, (row, prep) in enumerate(zip(rows, prepared), 1):
                rec, err = direct.complete_and_validate(
                    row, client, prep["messages"], labels, retrieved_chunks=prep["retrieved_chunks"],
                    taxonomy_text=prep["taxonomy_text"], extra_meta=prep["extra_meta"], **settings)
                if rec is not None:
                    predictions.append(rec.to_dict())
                else:
                    errors.append(err)
                report(i, row, rec, err, " ".join(h["id"] for h in prep["extra_meta"].get("retrieved", [])))
        manifest["tokens_per_row"] = tokens_per_row(predictions, errors)
        manifest["per_row"] = per_row_usage(predictions, errors)
        manifest["calls_per_row"] = calls_per_row(manifest["per_row"])
        if args.cond == "4b":
            measured = manifest["tokens_per_row"]["mean_total_tokens"]
            sc = manifest["self_consistency"]
            sc["mean_total_tokens_per_row_4b"] = measured
            sc["budget_ratio_4b_to_4_measured"] = (round(measured / sc["mean_tokens_per_row_cond4"], 4)
                                                   if measured else None)
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
    if args.cond in RETRIEVAL_CONDITIONS:
        extra = (f"; taxonomy spans {cv['taxonomy']['n_valid']}/{cv['taxonomy']['n_with_spans']}"
                 if args.cond in TAXONOMY_CONDITIONS else "")
        print(f"                   {cv['retrieved']['n_valid']}/{cv['retrieved']['n_with_spans']} records with "
              f"retrieved spans are verbatim{extra}")
    if manifest["model"] != "keyword":
        print(f"tokens: {manifest['tokens']}  calls: {manifest['calls']}  cost: {manifest['cost']['usd']}")
        print(f"tokens per row: {manifest['tokens_per_row']}")
        print(f"calls per row: {manifest['calls_per_row']}")
        if args.cond == 4:
            print(f"critic: {manifest['critic']['n_rows_critic_triggered']}/{manifest['critic']['n_rows_critic_called']} "
                  f"rows triggered a re-retrieval; stop reasons {manifest['critic']['stop_reasons']}")
            print(f"budget reference for 4b: {manifest['budget_reference']}")
        if args.cond == "4b":
            sc = manifest["self_consistency"]
            print(f"self-consistency: N={sc['n_samples']} floor_applied={sc['floor_applied']} "
                  f"budget ratio 4b/4 planned={sc['budget_ratio_4b_to_4_planned']} "
                  f"measured={sc['budget_ratio_4b_to_4_measured']}")
    print(f"next: make eval RUN={run_id}")


if __name__ == "__main__":
    main()
