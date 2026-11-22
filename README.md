# Misconceptor: Diagnosing Specific Recursion and Big-O Misconceptions in Open-Ended CS Exam Answers

**Team Members:** Michael Kao

**Course:** CMPE 258 — Deep Learning, Fall 2026 (Dr. Kaikai Liu)

**Selected Track:** Option 2 — LLMs + AI Agent System (Evaluation-First)

## Status (2026-11-22): no results yet

**There are no results of any kind.** The evaluation set
(`annotation/pilot_sheet.csv`, 63 student answers) has no human labels, so
nothing can be scored: `scripts/evaluate.py` reports "Gold labels are all
empty" for every run.

- Built: the taxonomy, the annotation schema and sheet, the experiment
  harness, the metrics, and ablation conditions 0 (keyword baseline) and 1
  (direct LLM).
- Not in the committed code: conditions 2, 3, 4 and 4b, the Critic, and the
  controls. Conditions 2 and 3 (with a retrieval corpus under `data/corpus/`)
  and a terminal labeling tool (`scripts/annotate.py`) were being built on
  2026-11-22 in uncommitted work. This README describes the committed code
  and does not cover that work yet.
- Conditions 0 and 1 have only been smoke-run to check the plumbing. Those
  runs are unscored and are not results.

The remaining order of work is in
[docs/PROJECT_PROPOSAL.md](docs/PROJECT_PROPOSAL.md) (Timeline).

## Abstract

Automated grading tells an instructor *whether* an open-ended answer is
correct, but rarely *which* misconception produced the error. Misconceptor
classifies student answers about **recursion** and **Big-O / algorithmic
complexity analysis** into a specific misconception id from a taxonomy built
from published CS misconception literature (11 of its 28 items are still
provisional), or into `none`, `other_error` or `insufficient_evidence`. The
project tests one mechanism claim:
**critic-driven, insufficiency-triggered re-retrieval improves
specific-misconception classification beyond a single-pass prompt that already
includes the taxonomy and few-shot examples.** We test this against an ablation
ladder: a keyword baseline, a direct LLM, course-material RAG, single-pass
taxonomy grounding, the critic loop, and a self-consistency baseline matched on
token budget, so a win from extra compute is not mistaken for a win from the
mechanism. Evaluation uses a small, human-annotated set that is still being
built: 63 answers to seven questions from the Mohler ASAG dataset. (The
dataset first proposed, JorGPT, turned out to have no recursion or Big-O
questions.) Neither dataset carries misconception labels. The plan is to
report macro-F1 with bootstrap confidence intervals, plus a human-rated
measure of whether cited evidence actually supports each diagnosis. A null
result, where the critic loop does not beat the single-pass or
self-consistency baselines, is a possible and reportable outcome.

## Documents

- [docs/PROJECT_PROPOSAL.md](docs/PROJECT_PROPOSAL.md): proposal, with changes after feedback, metrics, data facts and the timeline checklist
- [docs/RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md): internal research plan (mechanism, baselines, controls)
- [docs/LITERATURE_SURVEY.md](docs/LITERATURE_SURVEY.md): literature survey (five areas), with a Verification line per entry
- [docs/REVIEW_2026-10-18.md](docs/REVIEW_2026-10-18.md): project review (inventory, verified sources, gaps, order of work)
- [docs/REPORT_DRAFT.md](docs/REPORT_DRAFT.md): skeleton of the final report; methods written, results empty
- [docs/AI_NOVELTY_AUDIT.md](docs/AI_NOVELTY_AUDIT.md): novelty & feasibility audit, with post-feedback addendum
- [annotation/README.md](annotation/README.md) and [annotation/schema.md](annotation/schema.md): human annotation workflow and labeling rules (schema v0.2)

## Repository Structure

```
docs/                   # proposal, research plan, literature survey, project review, report draft, novelty audit
data/
  raw/                  # gitignored, never committed (see Data):
                        #   dataset_en.csv, dataset_es.csv      JorGPT
                        #   mohler/cleaned-oe-00001.parquet     Mohler ASAG
  processed/            # scope_report.md (tracked); derived CSV/JSONL/parquet (gitignored)
  corpus/               # course notes for the condition 2 retrieval corpus (draft in progress, uncommitted)
taxonomy/
  recursion_bigO.yaml   # the label definitions: 28 items + 3 special labels (version 0.1)
annotation/
  README.md             # human annotation workflow
  schema.md             # labeling rules (v0.2)
  pilot_sheet.csv       # the 63-row eval sheet; label columns still empty
  pilot_identity.json   # frozen SHA-256 fingerprints of the sheet's source cells
  progress.json         # initial progress snapshot (0 of 63 labeled)
configs/
  models.yaml           # base model, providers, generation settings (no keys)
  datasets.yaml         # where the raw datasets live, for the pilot scripts
  scope_keywords.yaml   # keyword filter used in the feasibility pilot
  prompts/              # versioned prompt templates; direct_v1.txt is condition 1
src/
  config.py             # paths, YAML loading, API-key and model resolution
  llm.py                # OpenAI-compatible chat client with an on-disk response cache
  schema.py             # prediction record, closed label set, validators, citation check
  baselines/            # keyword.py (condition 0), direct.py (condition 1); 2, 3, 4b not built
  pipeline/             # condition 4, Critic-driven re-retrieval; not built
  eval/metrics.py       # macro-F1, bootstrap CI, paired bootstrap, McNemar, coverage, kappa
scripts/
  inspect_jorgpt.py     # feasibility pilot: schema and samples of data/raw/
  filter_scope.py       # feasibility pilot: flag in-scope questions
  build_pilot_sheet.py  # rebuild annotation/pilot_sheet.csv from the Mohler parquet
  validate_taxonomy.py  # check the taxonomy file
  annotation_sheet.py   # validate human labels and report progress
  run_condition.py      # run condition 0 or 1 -> results/<run_id>/
  evaluate.py           # score a run -> metrics.json, metrics.md
tests/                  # unit tests for the schema, LLM cache, metrics, conditions 0 and 1, sheet validator
results/
  <run_id>/             # one folder per run; run_id = <cond>_<model>_<YYYYMMDD-HHMMSS>
    manifest.json       #   condition, model, prompt hash, settings, git commit, tokens, cost
    predictions.jsonl   #   one validated record per answer
    errors.jsonl        #   answers whose model output failed validation
    metrics.json        #   written by scripts/evaluate.py
    metrics.md          #   the same report, readable
  cache/                # LLM response cache (gitignored)
notebooks/              # exploration only
Makefile                # shortcuts for the commands below; `make help` lists them
requirements.txt
.env.example            # template for API-key variables; not needed for the local default model
```

No run folders are committed so far.

## Data

`data/raw/` is gitignored and holds two datasets. Neither is needed to run
conditions 0 and 1 or the evaluation, which read the tracked sheet
`annotation/pilot_sheet.csv`. The raw files are needed only to re-run the
feasibility pilot (`scripts/inspect_jorgpt.py`, `scripts/filter_scope.py`) or
to rebuild the sheet (`scripts/build_pilot_sheet.py`).

| Dataset | Local path | Source | Used for |
|---|---|---|---|
| Mohler ASAG (Mohler, Bunescu & Mihalcea 2011) | `data/raw/mohler/cleaned-oe-00001.parquet` | Hugging Face dataset `nkazi/MohlerASAG`, `cleaned/open_ended`, license CC-BY-4.0 | The eval set: 63 of its 2,273 answers, from 7 of its 81 questions |
| JorGPT | `data/raw/dataset_en.csv`, `data/raw/dataset_es.csv` | *Data* 2026, 11(3), 59, doi:10.3390/data11030059 | Feasibility pilot only: 0 of its 50 questions are in scope |

The Mohler `cleaned` split is Penn-Treebank tokenized, and its grading scale
differs by exam; see the Data section of the proposal before using it.

TODO(M1): record the exact download commands for both datasets. They are not
written down anywhere in this repo.

## Setup

Requires Python 3.10 or newer (developed on 3.12).

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q          # unit tests; no model or raw data needed
```

Condition 0 (keyword baseline) needs no model:

```bash
python scripts/run_condition.py --cond 0
```

Condition 1 (direct LLM) calls the base model set in `configs/models.yaml`:
`gpt-oss:20b`, served locally by [Ollama](https://ollama.com) at
`http://localhost:11434/v1`. No API key is needed for it. Pull the model once,
and start Ollama **before** any LLM run (in a second terminal, or open the
Ollama app):

```bash
ollama pull gpt-oss:20b
ollama serve
```

Then:

```bash
python scripts/run_condition.py --cond 1 --limit 5    # smoke test on the first 5 answers
python scripts/run_condition.py --cond 1              # all 63 answers
```

Each run prints its `run_id` and writes `results/<run_id>/`. Useful options:
`--model <provider>/<model>` to override the configured model, `--mock` to
test the plumbing with a canned response and no model (mock runs must never be
reported), `--no-cache` to bypass the response cache. `--help` lists the rest.
If Ollama is not running, the script stops with a message saying so.

Score a run, and optionally compare it with another:

```bash
python scripts/evaluate.py --run <run_id>
python scripts/evaluate.py --run <run_id> --compare <other_run_id>
```

This writes `metrics.json` and `metrics.md` into the run folder. Until
`primary_label` is filled in `annotation/pilot_sheet.csv`, it reports only the
predicted label distribution and citation validity, and says that gold is
empty.

Other entry points:

```bash
python scripts/validate_taxonomy.py          # check the taxonomy file
python scripts/annotation_sheet.py           # validate the (partially) labeled sheet
python scripts/annotation_sheet.py --report  # JSON progress and label counts
```

The Makefile wraps the same commands: `make test`,
`make baselines COND=1 ARGS='--limit 5'`, `make eval RUN=<run_id>`,
`make annotation-check`, `make annotation-report`.

To use a hosted model instead of Ollama, uncomment a provider in
`configs/models.yaml`, then `cp .env.example .env` and set the variable that
the provider's `api_key_env` names. `.env` is gitignored.
