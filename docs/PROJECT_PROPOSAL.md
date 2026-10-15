# Misconceptor: Project Proposal

*The original proposal text is not in this repo. This file was started fresh
after the professor's feedback. Per class instructions it is **not a
resubmission**: changes are documented here for our own clarity and will be
reported in the Project Progress Check after the midterm.*

## Changes after feedback

| # | Feedback | What changed |
|---|---|---|
| 1 | Label mismatch: JorGPT has student answers, a 0–10 human score, free-text feedback and multi-LLM evaluations, but **no misconception labels**. | Macro-F1 is now computed against a **small, human-annotated eval subset that we build**, labeled with an explicit taxonomy taken from published CS misconception literature. The pilot first checks how many JorGPT questions are in scope, and the subset may be supplemented with self-collected answers if coverage is thin. |
| 2 | Output categories (misconception / partial / none) were too coarse. | Scope is narrowed to **recursion** and **Big-O / complexity analysis**. The system now outputs a **specific taxonomy ID**, `none`, or `insufficient_evidence`. |
| 3 | The Planner–Executor–Critic architecture must be justified by controlled baselines. | Added an ablation ladder (conditions 0–4b), including a token-matched self-consistency control (4b) and a positive control for the Critic. See [RESEARCH_PLAN.md](RESEARCH_PLAN.md). |
| 4 | Grounding must measure whether evidence *supports* the diagnosis, not whether a citation exists. | Added a **grounding-support metric**: human ratings of supports / partially supports / unrelated on a sampled subset. An LLM judge is optional, and only if validated against those ratings. |
| 5 | The literature survey must cover five areas substantively. | The survey is reorganized under: automated short-answer assessment, misconception diagnosis, LLM educational feedback, RAG tutoring, knowledge tracing. Gaps are marked TODO. |
| — | Class-wide: listing components is not a contribution. | The contribution is restated as one testable mechanism claim (below). Dropped from the core scope: the instructor dashboard, longitudinal tracking, and a comparison of 3+ LLMs as a goal in itself. |

## Problem

Graders and automated scorers report *whether* an answer is right. They do not
report *which* misconception caused an error. Instructors need the specific
misconception to adjust their teaching.

## Scope

- **Concepts:** recursion; Big-O / algorithmic complexity analysis.
- **Taxonomy:** taken from published CS misconception literature only; no items
  are invented. TODO: verify the exact source papers and item lists (see
  [LITERATURE_SURVEY.md](LITERATURE_SURVEY.md), Area 2).

## Mechanism claim

> Critic-driven, insufficiency-triggered re-retrieval improves
> specific-misconception classification beyond single-pass retrieval that
> already includes the taxonomy.

The claim fails if condition 4 does not beat condition 3 or 4b (below). That
null result is reportable.

## Output specification

For each `(response_id, question_id)` the system returns:

| Field | Values |
|---|---|
| `label` | one taxonomy ID from `taxonomy/recursion_bigO.yaml`, or `none` (no misconception), or `insufficient_evidence` (the answer does not contain enough to diagnose) |
| `evidence` | cited spans: from the student answer, and from retrieved course material or taxonomy entries |
| `confidence` | model-reported confidence (used for analysis, not as a metric of correctness) |

Partial-credit style labels ("partial misconception") are no longer outputs.

## Ablation ladder

Same eval set and same base model for every condition. Full rationale is in
[RESEARCH_PLAN.md](RESEARCH_PLAN.md).

| ID | Condition |
|---|---|
| 0 | Keyword/heuristic baseline |
| 1 | Direct LLM (zero-shot, no retrieval, no taxonomy) |
| 2 | + course-material RAG (static top-k) |
| 3 | + taxonomy / few-shot (single pass) |
| 4 | + Critic iterative re-retrieval |
| 4b | Self-consistency on condition 3's prompt, majority vote, total token budget matched to condition 4 |

Additional controls: a positive control for the Critic (cases with the
supporting chunk deliberately withheld from the first retrieval), and a
paraphrase check for keyword shortcutting.

## Metrics

1. **Macro-F1 per condition** over the label set (taxonomy IDs + `none` +
   `insufficient_evidence`) on the human-annotated eval subset. Report a
   **95% bootstrap confidence interval** (resample responses with replacement).
   Compare conditions with a **paired bootstrap** on the macro-F1 difference
   (e.g. 4 − 3, 4 − 4b). Also report per-class F1 and the confusion matrix, so a
   good aggregate cannot hide weak classes.
   TODO: decide the number of bootstrap resamples, and whether
   `insufficient_evidence` is also reported as a separate abstention rate.
2. **Grounding support.** On a sampled subset of diagnoses, a human rates each
   cited piece of evidence as **supports / partially supports / unrelated**
   with respect to the predicted label. Report the distribution per condition.
   Optional: an LLM judge applying the same rubric, used only after its
   agreement with the human ratings (e.g. Cohen's kappa) has been measured and
   reported.
   TODO: sample size and sampling procedure.
3. **Inter-annotator agreement** on the eval labels: Cohen's kappa between two
   raters on a subset. TODO: subset size.
4. **Cost**: tokens and LLM calls per response, per condition (needed to
   interpret 4 vs 4b).

## Data

- **JorGPT** (Data 2026, 11(3), 59; doi:10.3390/data11030059). Its abstract
  describes 3,041 student answers to 50 open-ended CS questions, in Spanish
  with English translations, with ideal answers, 0–10 human grades and
  feedback, and DeepSeek/Qwen/Gemini evaluations. **It has no misconception
  labels.** TODO: confirm counts from our local copy (feasibility pilot).
- **Feasibility pilot (first experiment):** count the in-scope questions and
  responses for recursion and Big-O. Based on the counts, either use JorGPT,
  supplement it, or collect a small self-made set.
- **Annotation:** a human-labeled subset against the taxonomy, with a second
  rater on part of it. TODO: target size once the pilot counts are known.

## Timeline

TODO: fill in against the course calendar. Order: feasibility pilot →
taxonomy + annotation (pilot of 10–15 cases) → conditions 0–3 → conditions
4/4b → controls → write-up.

## Stretch goals (not required deliverables)

Instructor dashboard; longitudinal per-student tracking; comparing multiple
LLMs, including a local open-weight model.
