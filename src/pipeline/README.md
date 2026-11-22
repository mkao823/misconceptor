# src/pipeline/

Condition 4: Critic-driven, insufficiency-triggered re-retrieval, and the Critic's positive
control. The specification is `docs/CRITIC_SPEC.md`; this code implements it.

| Module | Role |
|---|---|
| `loop.py` | Condition 4 for one row (`run_row`). Round 0 is condition 3, unchanged: same retrieval, template, taxonomy text, few-shot examples, temperature 0, through `taxonomy_fewshot.render_messages` and `direct.complete_and_validate`. Then at most `max_rounds` (default 2) refinement rounds: Critic verdict, re-query with the Critic's query (never re-showing a chunk), re-diagnosis with all accumulated chunks. Stop reasons: `round_limit`, `sufficient`, `no_new_chunks`, `critic_error`, `rediagnosis_error`. Returns the validated record and a `trace` (per round: query, new and cumulative chunk ids, draft, Critic verdict, tokens; and every model call). With `max_rounds=0` it equals condition 3. |
| `critic.py` | The Critic: one call that sees the question, reference answer, student answer, chunks shown so far, the draft record and the draft label's catalogue entry, and returns `{"sufficient", "missing", "query"}`. Template `configs/prompts/critic_v1.txt`. It never changes a label. |
| `controls.py` | Positive control: loads the authored cases in `configs/controls/` (refuses a file not marked as authored), runs an arm (first pass + one Critic call, with the supporting chunks withheld from or forced into the first retrieval), and computes the trigger and recovery rates. |

Run:

    .venv/bin/python scripts/run_condition.py --cond 4 [--max-rounds 2] [--limit N]
    .venv/bin/python scripts/run_condition.py --cond 4b --match-run <condition 4 run id>
    .venv/bin/python scripts/run_positive_control.py

A row's tokens are the sum over every model call made for it: first pass, Critic calls,
re-diagnoses and repairs. The condition 4 manifest carries `critic` (template hash, max rounds,
stop reasons, how many rows triggered) and `budget_reference` (mean tokens per row, and the
mean tokens of one condition 3 call on the same rows), which is what condition 4b
(`src/baselines/self_consistency.py`) derives its number of samples from.

Worst case per row at the defaults: 3 diagnoses and 2 Critic calls, each with at most one
repair, and a last prompt holding 12 chunks. That fits a 16,384-token context window
(`OLLAMA_CONTEXT_LENGTH=16384 ollama serve`); the run checks the window before the first call.

Tests: `tests/test_condition_4.py`, `tests/test_self_consistency.py`,
`tests/test_positive_control.py` (mock client, no network).
