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
| — | Feasibility pilot (our own first experiment) | JorGPT has **no** recursion/Big-O questions. Mohler ASAG is the proposed primary source, supplemented by self-collected answers. See Data. |
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

### Feasibility pilot results (2026-10-15)

Produced by `scripts/inspect_jorgpt.py` and `scripts/filter_scope.py` using a
keyword filter (`configs/scope_keywords.yaml`). Every flagged question was
then reviewed by reading its text. Full table:
[data/processed/scope_report.md](../data/processed/scope_report.md).

- **JorGPT** (Data 2026, 11(3), 59; doi:10.3390/data11030059). Our local copy
  matches the paper: 3,041 rows, 50 questions, 79 anonymized students, in EN
  and ES files. **0 of the 50 questions are about recursion or Big-O.** All of
  them are software engineering (TDD and testing, Docker Compose and
  Kubernetes, Spring Boot and JPA, Vaadin and REST, GitFlow). In student
  answers, "recursive" appears only 3 times, all incidental; Big-O terms never
  appear. **JorGPT cannot provide the eval set for this scope.** It could still
  serve as a pipeline smoke test or a source of out-of-scope negatives.
  *Data-quality issue:* in `dataset_en.csv`, `question_text` often contains
  answer-like text instead of the translated question (e.g. Q327838357 starts
  mid-sentence). The original questions are in `dataset_es.csv`. Do not use the
  English `question_text` as-is.
- **Mohler ASAG** (Mohler, Bunescu & Mihalcea 2011; University of North Texas
  data structures course, C++; Hugging Face `nkazi/MohlerASAG`, cleaned
  open-ended split, CC-BY-4.0). 2,273 answers to 81 open-ended questions, with
  two human grades on a 0–5 scale. No misconception labels.
  **The filter flags 11 of 81 questions (314 responses).** On manual review:
  - Strong fits (5 questions, 139 responses): E03.Q06 causes of infinite
    recursion (31); E05.Q04 base case of recursive merge sort (28); E05.Q03
    best-case operations of insertion sort (28); E10.Q07 comparisons to find an
    element in a BST (24); E12.Q10 steps to search a node in a BST (28).
  - Medium fits: E03.Q07 iteration vs. recursion (31); E11.Q09
    divide-and-conquer (30).
  - Weak or false positives: E11.Q05 and E11.Q06 (definitional), E12.Q02
    (experimental running-time measurement), E07.Q06 (matched only because the
    instructor answer says "constant time").
  - Borderline, not flagged: E11.Q10 (how merge sort works), E10.Q06 (inorder
    traversal).
  - Across all 11 flagged questions, 90 answers score below 4/5 and 40 below
    3/5. This is the pool most likely to contain misconceptions. The answers
    are short (median roughly 10–24 words) and the questions are mostly factual
    recall.
  - Caveats: the data is from around 2009–2011, and the dataset is widely
    used, so LLM training contamination is possible.

### Data plan (proposed, pending decision)

- Use Mohler's in-scope questions for the 10–15 case annotation pilot and as
  part of the eval set.
- Supplement with self-collected recursion and Big-O short answers. TODO:
  check consent/IRB requirements.
- Optionally, ask the authors of the recursion concept inventory / RecurTutor
  work (Hamouda, Shaffer et al.) whether their recursion exam responses can be
  shared. TODO: no public release found.
- **Annotation:** a human-labeled subset against the taxonomy, with a second
  rater on part of it. TODO: target size. With about 40–90 low-scoring
  in-scope Mohler answers, per-class F1 will be noisy without extra data.

## Timeline

TODO: fill in against the course calendar. Order: feasibility pilot →
taxonomy + annotation (pilot of 10–15 cases) → conditions 0–3 → conditions
4/4b → controls → write-up.

## Stretch goals (not required deliverables)

Instructor dashboard; longitudinal per-student tracking; comparing multiple
LLMs, including a local open-weight model.
