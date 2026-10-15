# Misconceptor: Diagnosing Specific Recursion and Big-O Misconceptions in Open-Ended CS Exam Answers

**Team Members:** Michael Kao

**Course:** CMPE 258 — Deep Learning, Fall 2026 (Dr. Kaikai Liu)

**Selected Track:** Option 2 — LLMs + AI Agent System (Evaluation-First)

## Abstract

Automated grading tells an instructor *whether* an open-ended answer is
correct, but rarely *which* misconception produced the error. Misconceptor
classifies student answers about **recursion** and **Big-O / algorithmic
complexity analysis** into a specific misconception category drawn from
published CS misconception literature, or into "no misconception" or
"insufficient evidence". The project tests one mechanism claim:
**critic-driven, insufficiency-triggered re-retrieval improves
specific-misconception classification beyond a single-pass prompt that already
includes the taxonomy and few-shot examples.** We test this against an ablation
ladder: a keyword baseline, a direct LLM, course-material RAG, single-pass
taxonomy grounding, the critic loop, and a self-consistency baseline matched on
token budget, so a win from extra compute is not mistaken for a win from the
mechanism. Evaluation uses a small, human-annotated subset that we are
building. The source dataset (JorGPT) has scores and feedback but no
misconception labels. We report macro-F1 with bootstrap confidence intervals,
plus a human-rated measure of whether cited evidence actually supports each
diagnosis. A null result, where the critic loop does not beat the single-pass
or self-consistency baselines, is a possible and reportable outcome.

## Documents

- [docs/PROJECT_PROPOSAL.md](docs/PROJECT_PROPOSAL.md): proposal, with changes after feedback
- [docs/RESEARCH_PLAN.md](docs/RESEARCH_PLAN.md): internal research plan (mechanism, baselines, controls)
- [docs/LITERATURE_SURVEY.md](docs/LITERATURE_SURVEY.md): literature survey (five areas)
- [docs/AI_NOVELTY_AUDIT.md](docs/AI_NOVELTY_AUDIT.md): novelty & feasibility audit, with post-feedback addendum

## Repository Structure

```
docs/             # proposal, research plan, literature survey, novelty audit
data/
  raw/            # JorGPT CSVs, gitignored (never committed)
  processed/      # derived subsets (gitignored) and reports (tracked)
taxonomy/         # recursion + Big-O misconception taxonomy (from published sources)
annotation/       # annotation schema, templates, human labels
src/
  config.py       # loads configs/*.yaml; reads API keys from env vars
  baselines/      # conditions 0-3 and 4b
  pipeline/       # condition 4: Critic-driven re-retrieval
  eval/           # macro-F1 + bootstrap CIs, grounding support, kappa
configs/          # model/API settings and keyword lists (no keys)
results/          # experiment outputs
notebooks/        # exploration only
scripts/          # runnable entry points
Makefile          # make inspect / scope / ...
requirements.txt
.env.example      # env var names for API keys; copy to .env (gitignored)
```

## Setup

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env   # then fill in keys
```

Put the JorGPT CSVs in `data/raw/`.
