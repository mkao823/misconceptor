# scripts/

Runnable entry-point scripts (data inspection, scope filtering, experiment runs).

| Script | Purpose |
|---|---|
| `inspect_jorgpt.py`, `filter_scope.py` | feasibility pilot (`make inspect`, `make scope`) |
| `build_pilot_sheet.py` | rebuild `annotation/pilot_sheet.csv` |
| `validate_taxonomy.py` | check `taxonomy/recursion_bigO.yaml` |
| `run_condition.py` | run one ablation condition -> `results/<run_id>/` (`make baselines COND=0|1 [ARGS=...]`); `--limit N`, `--model provider/model`, `--mock`, `--no-cache` |
| `evaluate.py` | score a run against the annotation sheet -> `metrics.json`, `metrics.md` (`make eval RUN=<run_id> [ARGS='--compare <other>']`) |
| `annotation_sheet.py` | validate the human-labeled pilot sheet and report progress (`make annotation-check`, `make annotation-report`) |

Human annotation: `python3 scripts/annotation_sheet.py [sheet.csv]` validates a
partially filled full pilot; add `--complete` to require all primary labels or
`--report` to emit JSON progress and label counts. See
[annotation workflow](../annotation/README.md) for commands and scope.
