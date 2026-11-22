# Misconceptor: Project Proposal

*The original proposal text is not in this repo. This file was started fresh
after the professor's feedback. Per class instructions it is **not a
resubmission**: changes are documented here for our own clarity and will be
reported in the Project Progress Check after the midterm.*

*Status as of 2026-11-22: **no results exist.** The 63-row evaluation sheet
(`annotation/pilot_sheet.csv`) has no human labels yet, so no condition has
been scored. Passages updated on that date are marked.*

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
| — | Project review of 2026-10-18 ([REVIEW_2026-10-18.md](REVIEW_2026-10-18.md), gaps G1, G2, G9) | Added a fourth outcome, `other_error` (wrong, but not a catalogued misconception), next to the three in row 2. The label set is now the file `taxonomy/recursion_bigO.yaml`: 28 items, 11 of them provisional, plus three special labels. The Data section now records the Mohler grading scales, the tokenization of the `cleaned` split, and a per-question table of low scorers. The eval sheet is 63 Mohler answers and is still unlabeled. |
| — | Harness and conditions 0 and 1 built (2026-11-01; commit 9c7f59f) | The Metrics TODOs on bootstrap resamples and abstention reporting are resolved with what `src/eval/metrics.py` and `scripts/evaluate.py` implement. An automatic citation-validity check was added. Conditions 2, 3, 4 and 4b were not part of that commit. |
| — | Annotation schema v0.2 (2026-11-01; `annotation/schema.md`, `annotation/README.md`) | Annotation is human-only (no model pre-labels), with a validator and a stated rule for deciding whether Mohler alone is enough. There is one rater so far; the second rater is planned, not recruited. |

## Problem

Graders and automated scorers report *whether* an answer is right. They do not
report *which* misconception caused an error. Instructors need the specific
misconception to adjust their teaching.

## Scope

- **Concepts:** recursion; Big-O / algorithmic complexity analysis.
- **Taxonomy** (updated 2026-11-22): the intent is that every item comes from
  published CS misconception literature. That is true today for 17 of the 28
  items in `taxonomy/recursion_bigO.yaml`. The other 11 are marked
  `provisional` in the file and must not be cited as published: see Output
  specification for which ones and why.

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
| `label` | exactly one of: a taxonomy ID from `taxonomy/recursion_bigO.yaml`; `none` (no misconception); `other_error` (the answer is wrong, off-topic, or answers a different question, but the error matches no catalogued item); `insufficient_evidence` (the answer does not contain enough to diagnose) |
| `evidence` | cited spans, each tagged with its source: the student answer, retrieved course material, or a taxonomy entry |
| `confidence` | model-reported confidence in [0, 1] (used for analysis, not as a metric of correctness) |

Partial-credit style labels ("partial misconception") are no longer outputs.

**Label set (updated 2026-11-22).** The label set is closed and is defined by
`taxonomy/recursion_bigO.yaml` (version 0.1): 28 item ids plus the three
special labels `none`, `other_error` and `insufficient_evidence`, 31 labels in
all. `src/schema.py` rejects any other label.

| Source of items | Items | `status` in the file |
|---|---|---|
| Hamouda et al. 2017, recursion concept inventory | 12 | verified (wording checked against the paper) |
| ProgMiscon inventory (Chiodini et al. 2021), recursion entries | 5 | verified (wording checked against the site) |
| Götschi, Sanders & Galpin 2003, mental models of recursion | 7 | provisional: the list of model names comes from the published abstract, but the per-model descriptions are our paraphrase and were not checked against the full text |
| Big-O candidates | 4 | provisional: **not yet confirmed against a published source** |
| **Total** | **28** | **17 verified, 11 provisional** |

The four Big-O items (`BOsearchLinearScan`, `BOsearchVsSort`,
`BObestCaseSmallestInput`, `BObestWorstSwapped`) were written from patterns in
low-scoring Mohler answers. Their names and wording are ours. The intended
source is Farghally et al., SIGCSE 2017, whose item list is behind a paywall
and has not been read (see [LITERATURE_SURVEY.md](LITERATURE_SURVEY.md),
Area 2). TODO(P1): read Farghally et al. 2017 (and Tilanterä & Korhonen 2026)
and then confirm, reword or drop the four Big-O items. TODO(P2): check the
seven mental-model descriptions against the full text of Götschi et al. 2003.

`other_error` exists so that wrong answers that match no item are not forced
into the nearest taxonomy id. Its share among the low scorers is also the
pilot's decision statistic (see Data plan).

## Ablation ladder

Same eval set and same base model for every condition. Full rationale is in
[RESEARCH_PLAN.md](RESEARCH_PLAN.md).

| ID | Condition | Status 2026-11-22 |
|---|---|---|
| 0 | Keyword/heuristic baseline | built (`src/baselines/keyword.py`) |
| 1 | Direct LLM (zero-shot, no retrieval, no taxonomy) | built (`src/baselines/direct.py`, prompt `configs/prompts/direct_v1.txt`). As built, the prompt lists the 28 item ids by name, with no descriptions. |
| 2 | + course-material RAG (static top-k) | not in the committed code; a corpus of course notes (`data/corpus/`), a retrieval module (`src/retrieval.py`) and a runner (`src/baselines/rag.py`) were being written on 2026-11-22, uncommitted and unreviewed |
| 3 | + taxonomy / few-shot (single pass) | not in the committed code; a runner (`src/baselines/taxonomy_fewshot.py`) and authored few-shot examples were being written on 2026-11-22, uncommitted and unreviewed |
| 4 | + Critic iterative re-retrieval | not built; Critic not specified |
| 4b | Self-consistency on condition 3's prompt, majority vote, total token budget matched to condition 4 | not built; `n_samples` unset in `configs/models.yaml` |

The base model configured for every condition is `gpt-oss:20b`, served
locally through Ollama (`configs/models.yaml`).

Additional controls: a positive control for the Critic (cases with the
supporting chunk deliberately withheld from the first retrieval), and a
paraphrase check for keyword shortcutting. Neither is built.

## Metrics

Items 1 and 2 are implemented in `src/eval/metrics.py` and
`scripts/evaluate.py` (resolved 2026-11-22 from the code). Nothing has been
computed on labeled data.

1. **Macro-F1 per condition** on the human-annotated eval sheet.
   - *Classes.* Macro-F1 is the unweighted mean of per-class F1 over the
     labels that occur in the gold column. A label with no gold rows is left
     out of the average and listed as such; it is not averaged in as a zero
     (`annotation/schema.md`, section 8). A predicted label that never occurs
     in gold adds no class; it counts against the gold class of that row.
   - *Interval.* A **95% percentile bootstrap confidence interval** from
     **2,000 resamples** of rows with replacement, fixed seed 0. Macro-F1 is
     recomputed over the classes present in each resample. The count and the
     seed can be changed with `--n-resamples` and `--seed`.
   - *Comparisons.* A **paired bootstrap** on the macro-F1 difference (planned
     for 4 − 3 and 4 − 4b), using the same resample indices for both runs,
     with a two-sided p-value. An exact McNemar test on per-row correctness is
     reported next to it.
   - *Breakdowns.* Per-class precision, recall and F1 with support and
     predicted counts; the confusion matrix; accuracy; and macro-F1 on a
     four-way collapse (any taxonomy id / `none` / `other_error` /
     `insufficient_evidence`), so a good aggregate cannot hide weak classes.
   - *Abstention.* `insufficient_evidence` is treated as the abstain label.
     It stays in the headline macro-F1 as a class when it occurs in gold, and
     it is also reported separately: **coverage** (the share of predictions
     that are not `insufficient_evidence`), **accuracy on the covered rows**,
     the number of abstentions and of gold-abstain rows, and **macro-F1 with
     `insufficient_evidence` removed** from the averaged classes, so that
     abstaining cannot raise the average. No field is named "abstention rate";
     it is 1 − coverage.
   - *Failures.* A row whose model output still fails validation after the
     repair attempt is written to `errors.jsonl` and scored as wrong, not
     dropped.
   - *Caveat.* The 63 rows come from 7 questions, so a row-level bootstrap
     understates variance. `scripts/evaluate.py` prints this caveat with every
     report. TODO(P3): decide whether to add a question-level (cluster)
     resampling as a sensitivity check.
2. **Citation validity** (automatic, every record; added 2026-11-01). A
   record is valid when every span it cites from the student answer is a
   verbatim substring of that answer after whitespace normalization. The
   metric is the share of valid records among those that cite at least one
   student-answer span. It catches fabricated quotes. It does not measure
   whether a real quote supports the label; item 3 does.
3. **Grounding support.** On a sampled subset of diagnoses, a human rates each
   cited piece of evidence as **supports / partially supports / unrelated**
   with respect to the predicted label. Report the distribution per condition.
   Optional: an LLM judge applying the same rubric, used only after its
   agreement with the human ratings (e.g. Cohen's kappa) has been measured and
   reported. Not implemented.
   TODO(P4): sample size and sampling procedure.
4. **Inter-annotator agreement** on the eval labels: unweighted Cohen's kappa
   on the primary label between two raters, on a subset of 30 to 50 of the 63
   rows chosen after the first rater's pass, reported over the full label set
   and over the four-way collapse, with raw percent agreement
   (`annotation/schema.md` v0.2, section 7). The kappa function exists in
   `src/eval/metrics.py`; no script computes agreement yet.
   TODO(P5): recruit the second rater; record the chosen row ids and seed.
5. **Cost**: tokens and LLM calls per response, per condition (needed to
   interpret 4 vs 4b). Each run's `manifest.json` records prompt, completion
   and total tokens, cached and uncached calls, a cost figure and wall time;
   each LLM prediction record carries its own token counts.

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
  open-ended split, CC-BY-4.0). 2,273 answers to 81 open-ended questions, each
  with two human grades and their average (`score_avg`); the grading scale
  differs by exam, see "Mohler data facts" below. No misconception labels.
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
    3/5 on `score_avg`. This is the pool most likely to contain
    misconceptions. The answers are short (median roughly 10–24 words) and the
    questions are mostly factual recall.
  - Caveats: the data is from around 2009–2011, and the dataset is widely
    used, so LLM training contamination is possible.

### Mohler data facts (added 2026-11-22, from review sections 2.3 and 2.4)

**Grading scale.** Exams E01 to E10 are graded 0 to 5. Exams E11 and E12 are
graded 0 to 10 by each grader. `score_avg` is rescaled to 0 to 5 for every
exam. So only `score_avg` is comparable across exams, and every threshold in
this project uses `score_avg`. The review took this from the per-exam maxima
and the dataset card; the per-exam maxima were re-checked in the local parquet
on 2026-11-22 (grader maxima are 5 for E01 to E10 and 10 for E11 and E12;
the `score_avg` maximum is 5 for every exam).

**Tokenization.** The `cleaned` split is Penn-Treebank tokenized: parentheses
appear as `-LRB-` and `-RRB-`, "C++" as "C plus plus", exponents as "n to the
power of 2", and sentences end in `<STOP>`. Per the review's reading of the
dataset card, a `raw` config with the original, untokenized answers also
exists on Hugging Face. The project still uses `cleaned`:
`scripts/build_pilot_sheet.py` turns `-LRB-`/`-RRB-` back into parentheses,
drops `<STOP>` and collapses whitespace, and the other artifacts remain in the
eval sheet. TODO(P6): decide whether to rebuild the sheet from `raw` before
any labeling starts; after labeling, a rebuild would invalidate the frozen
source-cell fingerprints in `annotation/pilot_identity.json`.

**Low scorers per in-scope question.** Counts are on `score_avg` over the
seven strong and medium questions; they were re-derived from the local parquet
on 2026-11-22 and match the review. The last column is the reviewer's informal
reading of the answers on 2026-10-18. It is **not** an annotation and not a
result.

| Question | n | score < 3.5 | score <= 2.5 | What the low scorers look like (informal reading) |
|---|---|---|---|---|
| E03.Q06 infinite recursion causes | 31 | 2 | 1 | Almost all correct. Little diagnostic signal. |
| E05.Q04 base case of merge sort | 28 | 7 | 7 | Five answer "O(n log n)", one pastes code, one is vague. These are not base-case misconceptions; they are answers to a different question. |
| E05.Q03 insertion sort best case | 28 | 8 | 4 | Swapped best/worst, "best case is 1 operation", "worst case N factorial", "n(n-1)/2 in the best case". |
| E10.Q07 BST comparisons | 24 | 8 | 7 | "n-1", "n/2", "n log n", "at most 3", "(n^k)-1". |
| E12.Q10 BST search steps | 28 | 9 | 9 | "n/2", "2n-1", "2^n", "n(n-1)/2", "3 steps, there are 3 cases". |
| E03.Q07 iteration vs recursion | 31 | 6 | 3 | Mostly incomplete rather than wrong. |
| E11.Q09 divide and conquer | 30 | 3 | 0 | Confuses it with modular decomposition into files or classes. Not in any catalogue. |
| **Total** | **200** | **43** | **31** | |

This table and the "90 below 4, 40 below 3" figure above describe different
pools: the table covers the 7 strong and medium questions (200 answers), the
earlier figure all 11 flagged questions (314 answers).

The review's reading is that the Big-O questions carry more candidate
misconceptions than the recursion questions, which are mostly correct recall
or off-topic answers. That would invert the emphasis of the original plan,
which leans on the recursion inventory. It is a hypothesis until the sheet is
labeled.

### Eval sheet (added 2026-11-22)

`annotation/pilot_sheet.csv` has 63 rows from the seven questions above: all
43 answers with `score_avg` below 3.5, plus the 20 highest-scoring answers
(all scored 5.0; ties broken by answer length, longest first), included to
populate `none`. Rows per question, low / high: E03.Q06 2 / 3, E05.Q04 7 / 0,
E05.Q03 8 / 2, E10.Q07 8 / 0, E12.Q10 9 / 2, E03.Q07 6 / 8, E11.Q09 3 / 5.
As of 2026-11-22, 0 of the 63 rows are labeled.

### Data plan (updated 2026-11-22; decisions still pending)

- Mohler's in-scope questions supply the eval sheet. Annotation starts with a
  14-answer calibration session (two per question) and then covers all 63
  rows (`annotation/README.md`). This replaces the earlier "10–15 case
  annotation pilot".
- **Decision rule for a supplement** (`annotation/README.md`): if `other_error`
  is the primary label of more than half of the 43 low scorers, that is at
  least 22 of 43, Mohler alone is not enough and a supplement is required.
  TODO(P7): choose the supplement once the low scorers are labeled. The
  options on the table (review section 6.3) are synthetic answers verified by
  a human and reported separately from Mohler, new code-tracing questions, or
  re-scoping to make Big-O the primary concept.
- Self-collected recursion and Big-O short answers remain an option.
  TODO(P8): check consent/IRB requirements before collecting anything from
  people.
- Optionally, ask the authors of the recursion concept inventory / RecurTutor
  work (Hamouda, Shaffer et al.) whether their recursion exam responses can be
  shared. TODO(P9): no public release found.
- **Annotation:** one human rater labels all 63 rows; a second rater labels 30
  to 50 of them (Metrics, item 4). With 43 low-scoring answers spread over 7
  questions and 28 item ids, per-class F1 will be noisy without extra data.

## Timeline

TODO(P10, for Michael): **fill in the dates.** The project deadline and the
course calendar are not recorded anywhere in this repo, so no dates are given
here. The review of 2026-10-18 assumed the semester ends in mid-December; that
assumption has not been checked.

Order of work, with status as of 2026-11-22:

- [x] Feasibility pilot: JorGPT is out of scope, Mohler is the fallback
  (2026-10-15).
- [x] Taxonomy file v0.1 and its validator (2026-10-18).
- [x] Annotation schema (v0.1 on 2026-10-18, v0.2 on 2026-11-01), the 63-row
  sheet, and the sheet validator and progress report
  (`scripts/annotation_sheet.py`).
- [x] Literature survey in five areas with a Verification line per entry
  (2026-10-18). Open TODOs remain inside the survey.
- [x] Shared harness, metrics, unit tests, and conditions 0 and 1
  (built 2026-11-01, committed 2026-11-22).
- [x] Smoke runs of condition 0 (all 63 rows) and condition 1 (first 5 rows)
  to exercise the plumbing. They are unscored and are not results.
- [ ] **1. First-rater annotation.** The 14-answer calibration session, then
  the remaining 49 rows, then complete-mode validation. 0 of 63 done.
  Date: TODO.
- [ ] **2. Pilot decision.** Count `other_error` among the 43 low scorers and
  apply the supplement rule (TODO(P7)). Date: TODO.
- [ ] **3. Second rater.** Recruit; label the 30 to 50 row subset; compute
  kappa; adjudicate to gold (TODO(P5)). The agreement script is not written.
  Date: TODO.
- [ ] **4. Confirm the provisional items** (TODO(P1), TODO(P2)). Date: TODO.
- [ ] **5. Score conditions 0 and 1** on the labeled sheet. Condition 1 has
  not yet been run on all 63 rows. This is the check on whether the rest of
  the ladder is worth building. TODO(P11): confirm `gpt-oss:20b` as the base
  model for every condition, or pick another, before building further.
  Date: TODO.
- [ ] **6. Retrieval corpus** for condition 2: assemble, chunk, index; tag
  which eval items could change label given retrieved content (review gap
  G7). In progress: course notes under `data/corpus/` and a retrieval module
  `src/retrieval.py` were being written on 2026-11-22; both are uncommitted
  and unreviewed. Date: TODO.
- [ ] **7. Conditions 2 and 3.** Get condition 3's number with its interval
  before building anything agentic. In progress: runners, prompts and a file
  of authored few-shot examples were being written on 2026-11-22
  (uncommitted, unreviewed). TODO(P12): review those few-shot examples
  (`configs/prompts/fewshot_v1.yaml`). They must not overlap the eval rows,
  and because no other labeled answers exist they are written examples, not
  real student answers. Date: TODO.
- [ ] **8. Critic specification, then condition 4, then 4b** with `n_samples`
  set so its token budget matches condition 4's measured mean. Date: TODO.
- [ ] **9. Controls**: positive control (withheld chunk), paraphrase check,
  grounding-support ratings (TODO(P4)). Date: TODO.
- [ ] **10. Write-up**, from [REPORT_DRAFT.md](REPORT_DRAFT.md). Date: TODO.

If time runs short, the review recommends cutting from the bottom: the
paraphrase check, then the human grounding-support ratings (keeping the
automatic citation-validity check), then 4b; and not cutting condition 3 or
the annotation. TODO(P13, for Michael): accept or change this cut order once
the dates are known.

## Stretch goals (not required deliverables)

Instructor dashboard; longitudinal per-student tracking; comparing multiple
LLMs, including a local open-weight model.
