# src/baselines/

Ablation conditions 0-3 and 4b: keyword heuristic, direct LLM, +RAG, +taxonomy/few-shot, self-consistency.

| Module | Condition | Status |
|---|---|---|
| `keyword.py` | 0, trigger-phrase matching against the taxonomy (no grade feature; ties by taxonomy order) | done |
| `direct.py` | 1, zero-shot LLM with question + instructor answer + student answer; label ids only, no taxonomy text, no retrieval; prompt in `configs/prompts/direct_v1.txt` | done |
| rag / taxonomy_fewshot / self_consistency | 2, 3, 4b | not started |

Run with `make baselines COND=<n>`; see `scripts/run_condition.py`.
