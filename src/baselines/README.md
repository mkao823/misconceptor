# src/baselines/

Ablation conditions 0-3 and 4b: keyword heuristic, direct LLM, +RAG, +taxonomy/few-shot, self-consistency.

| Module | Condition | Status |
|---|---|---|
| `keyword.py` | 0, trigger-phrase matching against the taxonomy (no grade feature; ties by taxonomy order) | done |
| `direct.py` | 1, zero-shot LLM with question + instructor answer + student answer; label ids only, no taxonomy text, no retrieval; prompt in `configs/prompts/direct_v1.txt` | done |
| `rag.py` | 2, condition 1 plus the top-k chunks retrieved from `data/corpus/` (BM25 by default, query = question + student answer); label ids only, no taxonomy text; may cite `retrieved` spans, which must be verbatim in a chunk shown for the row; prompt in `configs/prompts/rag_v1.txt` | done |
| `taxonomy_fewshot.py` | 3, condition 2 plus the full taxonomy text (id, description, notes, special-label definitions) and the authored examples in `configs/prompts/fewshot_v1.yaml`; one retrieval, one model call; prompt in `configs/prompts/taxonomy_fewshot_v1.txt` | done |
| self_consistency | 4b | not started |

Run with `.venv/bin/python scripts/run_condition.py --cond <n>` (`--k`, `--retrieval-backend bm25|dense`,
`--exclude-chunk ID`, `--keep-own-reference`, `--fewshot NAME` for conditions 2 and 3). Retrieval lives in
`src/retrieval.py`; the corpus and its documentation in `data/corpus/`.

Shared pieces: `direct.complete_and_validate` is the call / parse / validate / repair loop used by
conditions 1 to 3. Each record's `meta` holds prompt and completion tokens and, for conditions 2 and 3,
`retrieved` (chunk id, score, rank) and `withheld_chunk_ids`. The manifest gains `retrieval`
(backend, k, corpus hash, chunker and BM25 settings), `fewshot` (file and hash), `context_window`
and `tokens_per_row`.

Ollama context window: conditions 2 and 3 need more than Ollama's default 4096 tokens (condition 3
prompts are about 4,900 tokens), and Ollama truncates a longer prompt without an error. Start the
server with `OLLAMA_CONTEXT_LENGTH=16384 ollama serve`. `run_condition.py` checks the window the model
is loaded with before the first live call and stops if the longest prompt plus `max_tokens` cannot fit.
