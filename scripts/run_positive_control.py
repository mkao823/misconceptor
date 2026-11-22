"""Positive control for the Critic of condition 4. Needs no gold labels.

Runs the authored cases in configs/controls/<name>.yaml (docs/CRITIC_SPEC.md, section 7):

  * each dependent case twice: once with its supporting chunks withheld from the first
    retrieval, once with them forced into the first-pass k;
  * each non-dependent case once, with condition 3's ordinary retrieval.

Every arm is condition 3's first pass plus one Critic call. When the Critic triggers, the
re-query is run (no model call) to see whether it brings back a withheld chunk. Nothing is
compared with a gold label, and the eval sheet is not read.

Outputs in results/<run_id>/ (run_id = pc_<model>_<timestamp>):
  manifest.json   model, templates and their hashes, controls file + hash, corpus hash,
                  generation settings, the rates with counts, tokens and calls
  arms.jsonl      one line per arm: chunks shown, draft, Critic verdict, re-query, recovery,
                  tokens and every model call
  summary.md      the rates and a table of the arms

Usage:
    python scripts/run_positive_control.py [--model ollama/gpt-oss:20b] [--k 4] [--mock] [--limit-pairs N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_condition import check_context_window, git_info, mock_content, slug, write_jsonl  # noqa: E402
from src.baselines import direct, taxonomy_fewshot  # noqa: E402
from src.config import RESULTS_DIR, TAXONOMY_PATH, load_config, sha256_file, sha256_text  # noqa: E402
from src.pipeline import controls as C  # noqa: E402
from src.pipeline import loop  # noqa: E402
from src.retrieval import CORPUS_DIR, DEFAULT_K, make_retriever  # noqa: E402
from src.schema import label_set, load_taxonomy  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--controls", default=C.DEFAULT_CONTROLS, help="control file name in configs/controls/")
    ap.add_argument("--model", default=None, help="provider/model or model (default: configs/models.yaml)")
    ap.add_argument("--k", type=int, default=DEFAULT_K, help="chunks in the first pass and per re-query")
    ap.add_argument("--prompt", default=None, help="diagnosis template (default: condition 3's)")
    ap.add_argument("--critic-prompt", default=None, help="Critic template in configs/prompts/")
    ap.add_argument("--fewshot", default=None, help="few-shot file name in configs/prompts/")
    ap.add_argument("--corpus-dir", type=Path, default=None)
    ap.add_argument("--limit-pairs", type=int, default=None, help="only the first N pairs (smoke runs)")
    ap.add_argument("--no-cache", action="store_true", help="bypass results/cache/")
    ap.add_argument("--mock", action="store_true", help="mock client: fixed record, Critic always 'sufficient'")
    ap.add_argument("--out-root", type=Path, default=RESULTS_DIR)
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    from src.llm import LLMClient, MockTransport

    taxonomy = load_taxonomy()
    labels = label_set(taxonomy)
    models_cfg = load_config("models")
    gen = dict(models_cfg.get("generation") or {})
    retriever = make_retriever("bm25", corpus_dir=args.corpus_dir or CORPUS_DIR)
    controls = C.load_controls(args.controls, corpus=retriever.corpus)
    cases = controls.cases
    if args.limit_pairs:
        keep = list(dict.fromkeys(c["pair"] for c in cases))[: args.limit_pairs]
        cases = [c for c in cases if c["pair"] in keep]

    if args.mock:
        models_cfg = {"default_model": "mock", "default_provider": "mock", "generation": gen,
                      "providers": {"mock": {"base_url": None, "api_key_env": "MOCK_API_KEY",
                                             "api_key_required": False, "models": ["mock"]}}}
        client = LLMClient("mock", transport=MockTransport(mock_content, model="mock"),
                           use_cache=not args.no_cache, models_cfg=models_cfg)
    else:
        client = LLMClient(args.model, use_cache=not args.no_cache, models_cfg=models_cfg)
        if not client.is_reachable():
            base = client.provider_cfg.get("base_url") or "the API"
            raise SystemExit(f"{client.provider}/{client.model}: endpoint {base} is not reachable. "
                             "For Ollama run `OLLAMA_CONTEXT_LENGTH=16384 ollama serve`, or pass --mock.")

    template = direct.load_template(args.prompt or loop.DEFAULT_TEMPLATE)
    critic_template = direct.load_template(args.critic_prompt or loop.DEFAULT_CRITIC_TEMPLATE)
    fewshot = taxonomy_fewshot.load_fewshot(args.fewshot or taxonomy_fewshot.DEFAULT_FEWSHOT, labels=labels)
    ctx = loop.Context(template=template, critic_template=critic_template, labels=labels, retriever=retriever,
                       taxonomy=taxonomy, fewshot=fewshot)
    settings = {"temperature": float(gen.get("temperature", 0.0)), "seed": gen.get("seed", 0),
                "max_tokens": int(gen.get("max_output_tokens", 1024)), "json_mode": bool(gen.get("json_mode", True)),
                "max_repairs": int(gen.get("max_repairs", 1))}

    plan = [(case, arm) for case in cases for arm in C.ARMS[case["kind"]]]
    # the Critic prompt is shorter than the diagnosis prompt, so the first-pass prompts bound the need
    prepared = []
    for case, arm in plan:
        hits, _, _ = loop.first_pass_retrieval(C.case_row(case, controls), retriever, k=args.k,
                                               **C.arm_retrieval_args(case, arm))
        prepared.append({"messages": taxonomy_fewshot.render_messages(template, C.case_row(case, controls), hits,
                                                                     taxonomy, fewshot)})
    context_window = check_context_window(client, prepared, settings, always=True)

    started = datetime.now().astimezone()
    t0 = time.time()
    n_dep = sum(1 for c in cases if c["kind"] == "dependent")
    print(f"positive control: {client.provider}/{client.model}, {len(cases)} cases ({n_dep} dependent, "
          f"{len(cases) - n_dep} non-dependent), {len(plan)} arms, k={args.k}, critic {critic_template.name}", flush=True)
    arms: list[dict] = []
    for i, (case, arm) in enumerate(plan, 1):
        result = C.run_arm(case, arm, controls, client, ctx, k=args.k, **settings)
        arms.append(result)
        if result["error"]:
            status = f"ERROR ({result['error']['where']}): {str(result['error']['error'])[:100]}"
        else:
            status = f"draft={result['draft']['label']}\ttriggered={result['triggered']}"
            if result["recovered"] is not None:
                status += f"\trecovered={result['recovered']['chunk_ids'] or 'no'}"
        print(f"[{i}/{len(plan)}] {case['id']}\t{arm}\t{status}\ttokens={result['tokens']['total_tokens']}", flush=True)

    summary = C.summarize(arms)
    model_slug = slug(client.model)
    run_id = args.run_id or f"pc_{model_slug}_{started.strftime('%Y%m%d-%H%M%S')}"
    out = args.out_root / run_id
    out.mkdir(parents=True, exist_ok=False)
    stats = client.stats()
    desc = retriever.describe()

    def rel(path: str) -> str:
        p = Path(path)
        return str(p.relative_to(REPO_ROOT)) if p.is_relative_to(REPO_ROOT) else str(p)

    manifest = {
        "run_id": run_id, "kind": "critic_positive_control", "spec": "docs/CRITIC_SPEC.md",
        "timestamp": started.isoformat(timespec="seconds"), "git": git_info(),
        "controls": {"name": controls.name, "path": rel(controls.path), "sha256": controls.sha256,
                     "provenance": controls.provenance, "n_cases": len(cases), "n_dependent": n_dep,
                     "n_independent": len(cases) - n_dep, "limit_pairs": args.limit_pairs},
        "model": client.model, "provider": client.provider,
        "transport": "mock" if args.mock else "openai-compatible",
        "base_url": client.provider_cfg.get("base_url"),
        "prompt_template": {"name": template.name, "path": rel(template.path), "sha256": template.sha256},
        "critic_template": {"name": critic_template.name, "path": rel(critic_template.path),
                            "sha256": critic_template.sha256},
        "fewshot": {"name": fewshot.name, "sha256": fewshot.sha256},
        "taxonomy": {"path": str(TAXONOMY_PATH.relative_to(REPO_ROOT)), "sha256": sha256_file(TAXONOMY_PATH),
                     "rendered_sha256": sha256_text(ctx.taxonomy_text)},
        "retrieval": {"backend": desc["backend"], "k": args.k, "corpus_hash": desc["corpus_hash"],
                      "n_chunks": desc["n_chunks"], "query": "question + student_answer",
                      "own_instructor_answer_withheld": True},
        **settings, "cache_used": client.use_cache, "context_window": context_window,
        "arms": {"withheld": "supporting chunks excluded from the first retrieval only",
                 "present": "supporting chunks forced into the first-pass k",
                 "natural": "condition 3's ordinary retrieval (non-dependent cases)"},
        "summary": summary,
        "tokens": stats["tokens_total"], "tokens_uncached": stats["tokens_uncached"],
        "calls": {"uncached": stats["calls_uncached"], "cached": stats["calls_cached"]},
        "wall_seconds": round(time.time() - t0, 1),
    }
    write_jsonl(out / "arms.jsonl", arms)
    with open(out / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    header = {"run_id": run_id, "model": client.model, "controls": controls.name, "n_cases": len(cases),
              "n_dependent": n_dep, "n_independent": len(cases) - n_dep, "critic_template": critic_template.name,
              "k": args.k, "timestamp": manifest["timestamp"]}
    (out / "summary.md").write_text(C.summary_markdown(summary, arms, header), encoding="utf-8")

    a = summary["arms"]
    try:
        shown = out.resolve().relative_to(REPO_ROOT)
    except ValueError:
        shown = out
    print(f"\nrun_id: {run_id}\nwrote {shown}/  (manifest.json, arms.jsonl, summary.md)")
    for arm in ("withheld", "present", "natural"):
        print(f"triggered, {arm}: {a[arm]['n_triggered']}/{a[arm]['n_judged']}  (errors {a[arm]['n_errors']})")
    rec = summary["recovery"]
    print(f"withheld arms that triggered and whose re-query recovered a withheld chunk: "
          f"{rec['n_recovered_any']}/{rec['n_withheld_triggered']}")
    print(f"tokens: {manifest['tokens']}  calls: {manifest['calls']}")


if __name__ == "__main__":
    main()
