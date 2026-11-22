# Misconceptor: Final Report (draft skeleton)

**Diagnosing specific recursion and Big-O misconceptions in open-ended CS exam
answers.** Michael Kao. CMPE 258, Fall 2026, Option 2 (LLMs + AI Agent System,
evaluation-first).

> **Status, 2026-11-22. This is a skeleton, not a report. There are no
> results.** The 63-row evaluation sheet has no human labels, so no condition
> has been scored. This draft describes the committed code (commit 944463f):
> conditions 0 and 1 are built; conditions 2, 3, 4 and 4b, the Critic and the
> controls are not. Conditions 2 and 3, a retrieval corpus and a terminal
> labeling tool were being built in uncommitted work on the same day. That
> work is named where it matters and is not described. The method
> sections below are written in full and describe what is built as built and
> what is planned as planned. Section 10 holds empty tables only.

How to read this draft:

- `TODO(Rn)` marks a place that needs a human decision, a missing piece of
  work, or a result. The index at the end lists all of them.
- `TBD` marks a table cell that a script will fill.
- Every statement about a paper is limited to what that paper's Verification
  line in [LITERATURE_SURVEY.md](LITERATURE_SURVEY.md) supports. The level is
  given in brackets: [full text], [abstract] for "metadata and abstract",
  [metadata], [site]. Papers the survey marks "Partially verified" are not
  cited.
- Every number comes from a file in this repository; the file is named.
- This skeleton was drafted by Claude (Anthropic) on 2026-11-22 from the
  repository's files, at Michael's request. TODO(R1): record that in
  [AI_NOVELTY_AUDIT.md](AI_NOVELTY_AUDIT.md) if the course requires it, and
  rewrite the prose in your own words before submission.

TODO(R2): abstract. Write it last, after section 10 is filled.

---

## 1. Introduction and mechanism claim

Graders and automated scorers report *whether* an open-ended answer is right.
They rarely report *which* misconception produced the error, and that is what
an instructor needs in order to change how a topic is taught. The clearest
evidence that LLM grading leaves this gap open is Zhao, Jiao & Xu (2026)
[abstract]. They analyze the JorGPT data, and per their abstract LLM feedback
identified student misconceptions in 5–7% of responses, against 15–31% for
teachers.

Misconceptor takes one student answer to one exam question about recursion or
Big-O and returns exactly one label from a closed set: the id of a specific
misconception from a taxonomy file, or `none`, `other_error`, or
`insufficient_evidence`. It also returns the spans it cites as evidence and a
confidence (section 3).

The project tests one mechanism claim:

> Critic-driven, insufficiency-triggered re-retrieval improves
> specific-misconception classification beyond single-pass retrieval that
> already includes the taxonomy.

The claim is about one mechanism, not about a system with many parts. It is
tested on an ablation ladder in which every condition uses the same eval set
and the same base model (section 7): a keyword baseline (0), a direct LLM (1),
course-material retrieval (2), a single-pass prompt that also contains the
taxonomy and few-shot examples (3), the Critic loop (4), and self-consistency
sampling on condition 3's prompt with a token budget matched to condition 4
(4b). Condition 3 is the baseline that could make the mechanism unnecessary:
the label set is small and closed, so a single pass that already holds the
taxonomy may capture most of what is achievable. Condition 4b separates
iterative refinement from extra compute.

The claim fails if condition 4 does not beat condition 3, or does not beat
condition 4b. That outcome is reportable. It would say that, for a narrow and
well-described misconception domain, a single-pass taxonomy-grounded
classifier is enough and the cost of a Critic is not justified for this scope
([RESEARCH_PLAN.md](RESEARCH_PLAN.md)).

What this report does not claim. It does not claim that detecting
misconceptions with LLMs is new; section 2 lists prior work. It does not claim
a validated instrument: 11 of the 28 taxonomy items are provisional, and the
four Big-O items are not yet confirmed against a published source (section 4).
It does not claim generality beyond 63 answers to seven questions from one
course (section 11).

TODO(R3): after section 10 is filled, add one paragraph stating what was
found, with the interval, and whether the claim held, failed, or could not be
tested at this sample size.

## 2. Related work

Organized by the five areas of the literature survey. The survey holds the
full entries and the Verification lines.

### 2.1 Automated short-answer assessment

The eval data comes from the pre-LLM line of automatic short-answer grading.
Mohler, Bunescu & Mihalcea (2011) [abstract] combine lexical semantic
similarity measures with dependency-graph alignment features in a supervised
grader, and introduce the University of North Texas data-structures answers
reused here. Their task is scoring, not diagnosis. Burrows, Gurevych & Stein
(2015) [metadata] is a survey of that field; only its bibliographic record has
been checked, so nothing is said here about its content. TODO(R4): read it,
or drop it.

The JorGPT dataset paper (2026) [abstract; authors not verified] describes,
per its abstract, 3,041 student answers to 50 open-ended CS questions from 79
anonymized students, with instructor ideal answers, human grades and feedback,
and evaluations by several LLMs. It contains no misconception labels. Zhao,
Jiao & Xu (2026) [abstract] analyze the same data. Per their abstract, rubric
sub-dimension scores are highly correlated (r = 0.82–0.99), and LLM feedback
named a student misconception far less often than teachers did (the figures
are in section 1). This is the motivation for treating diagnosis as a task
separate from scoring.

### 2.2 Misconception diagnosis

*Sources of the taxonomy.* Hamouda, Edwards, Elmongui, Ernst & Shaffer (2017)
[full text] built a recursion concept inventory. Their list of misconceptions
came from instructor input, the literature, and an analysis of approximately
8,000 responses to recursion exam questions over three semesters. It defines
twelve tagged items in five groups; nine are labelled misconceptions and three
are labelled difficulties. ProgMiscon (Chiodini et al.) [site, fetched
2026-10-18; the ITiCSE '21 paper itself was not read] is a curated inventory
of programming-language misconceptions. On that date its "any language"
listing held 104 entries by our own count, five of them about recursion and
none about Big-O. Götschi, Sanders & Galpin (2003) [abstract] studied
first-year students' mental models of recursion. Per the abstract, most
students built the viable "copies" model, and many built non-viable ones:
looping, active, step, magic, return-value and various odd models.

Three further sources are known by bibliographic record only, and nothing is
claimed about their content: Farghally, Koh, Ernst & Shaffer (2017)
[metadata], the intended source for the Big-O items, whose item list has not
been read; Tilanterä & Korhonen (2026) [metadata], a systematic review of
data-structures-and-algorithms misconceptions in concept inventories, whose
item count rests on search snippets; and Haberman & Averbuch (2002)
[metadata], on students' difficulties with base cases. TODO(R5): obtain the
full texts of Farghally et al. and Tilanterä & Korhonen through the SJSU
library.

*Diagnosis with LLMs.* The closest prior work in CS is Oli, Banjade, Olney &
Rus (arXiv:2501.10365) [abstract, plus the figures below from the HTML full
text]. They
check free-text student explanations of code for gaps and misconceptions with
GPT-4, Llama-3-8B and Mistral-7B, under zero-shot and few-shot prompting,
supervised fine-tuning, and preference alignment. Their student data is
simulated: 2,888 explanations made by perturbing expert explanations, deleting
sentences from them, or writing explanations for code with injected errors. In
their qualitative analysis the models fabricated problems in 27% of correct
explanations and in 34% of typo-only ones. That failure mode is the reason
this project scores the `none` class separately and checks every cited span
automatically (section 8).

Mitton et al. (2026) [abstract] diagnose misconceptions from student–tutor
dialogue with a generate, retrieve, rerank pipeline, tested on 922 dialogues.
It is an alternative architecture to a Critic loop and is not a baseline here.
Yeltekin & Bauer (2026) [abstract] evaluate 13 LLMs on novice misconceptions
in code-tracing problems. Per their abstract, models of 14B parameters or
fewer struggle with dynamic code execution, and diagnosis is much easier in a
true/false format than as open-ended generation, which supports a closed label
set. Al-Hossami & Bunescu (2025) [abstract] define the task of discovering
misconceptions from student code and build a benchmark for it; that is
adjacent to free-text diagnosis, not the same task. Liu et al. (2026)
[abstract] report that instruction-tuning on misconception-laden data can
degrade reasoning, which is one reason this project prompts and retrieves
and does not fine-tune.

Two further papers are related by title and are known by bibliographic record
only: Imran & Bulathwela (2026), "The Correct Answer Trap", and Ross & Andreas
(2025), "Learning to Make MISTAKEs" [both metadata]. TODO(R6): read their
abstracts and either describe them or drop them.

### 2.3 LLM educational feedback

Korthals et al. (2026) [abstract] prompt an LLM grader repeatedly and use low
certainty (high output diversity) to flag grades for human regrading; per the
abstract this cut manual grading time by 40–90%. It motivates condition 4b as
the compute-matched control. Kiesler, Lohr & Keuning (2023) [abstract] fed
student programs from a CS1 dataset to ChatGPT and categorized the feedback;
per the abstract the feedback can contain information that misleads novices.
Herklotz, Ippisch & Haensch (2025, preprint) [abstract] reviewed all 2,389
GPT-4 feedback instances from a mock exam in an introductory statistics
course; per the abstract about 7% contained errors. A wrong misconception
label is the same kind of risk.

### 2.4 Retrieval-augmented generation for tutoring

Levonian et al. (2023) [abstract] ground answers to middle-school math
questions in a vetted textbook. Per the abstract, people preferred the
retrieval-augmented answers, but preference fell when answers stayed too close
to the textbook text, which the authors frame as a trade-off between
groundedness and preference. Dinh, Schumacher & Niehues (2025) [abstract] ask
whether lecture slides and transcripts help LLMs answer questions in
university CS courses. Per the abstract, retrieval was more effective and
efficient than continual pre-training at the small scale of course materials.
That is the setting of condition 2. Neither abstract reports retrieval quality
directly, and the survey still lacks such an entry. TODO(R7): find one before
the final report, or say that none was found.

### 2.5 Knowledge tracing

Knowledge tracing is background for longitudinal tracking of a student's
misconceptions, which is a stretch goal and outside this report. Norris, Gal &
Bulathwela (2025) [abstract] frame it as next-token prediction over text
histories with fine-tuned LLMs. Scarlatos, Baker & Lan (2025) and Wang, Zhou
et al. (2025) are known by bibliographic record only [both metadata].
TODO(R8): decide which version of the Wang, Zhou et al. paper to cite; the
survey notes a revised version under a different title.

### 2.6 The gap this project targets

Stated relative to the two closest works, and only as far as their abstracts
and the parts of Oli et al. that were read show. Zhao, Jiao & Xu measure how
often feedback names any misconception; they do not classify against a
taxonomy. Oli et al. work on simulated student text. This project uses real
student answers on recursion and Big-O; a closed label set taken from
published catalogues where one has been verified (17 of 28 items); and a
controlled test of one mechanism against single-pass baselines, one of them
matched on compute, with a check on the cited evidence. The caveat is in the
survey already: the eval data is small and mostly recall questions, so the
honest version of the gap may narrow to the Big-O side and to the few
recursion items that recall answers can show.

## 3. Task and output specification

**Input.** One row of the eval sheet: an answer id such as `E05.Q03.A02`, the
question id, the question text, the instructor's reference answer, and the
student's answer. The sheet also carries the human grade (`score_avg`). No
condition sees it: the keyword baseline never reads it, and the condition 1
prompt contains only the three text fields.

**Output.** One record per answer, defined and validated in `src/schema.py`:

| Field | Content |
|---|---|
| `label` | exactly one label from the closed set of 31 (section 4) |
| `evidence` | a list of spans, each tagged with its source: `student_answer`, `retrieved`, or `taxonomy` |
| `confidence` | a number in [0, 1], reported by the model |
| `citation_valid` | computed by the validator, not by the model: true when every cited `student_answer` span is a verbatim substring of the answer after whitespace normalization |

The three labels that are not taxonomy items are defined in the taxonomy file:

- `none`: the answer is correct or acceptable for the question as asked and
  contains no incorrect claim. It may be incomplete.
- `other_error`: the answer is wrong, off-topic, or answers a different
  question, and the error matches no catalogued item.
- `insufficient_evidence`: the answer is too short, vague, garbled or blank
  to judge. The evaluation treats this label as an abstention.

**Validation.** A label outside the closed set is an error; a label that
differs only in letter case is normalized and a warning is recorded. Evidence
must be a list of source-tagged spans; a bare string is accepted as a
`student_answer` span with a warning. A confidence outside [0, 1] is an error.
In an LLM condition, output that fails to parse or validate triggers up to one
repair round-trip (`max_repairs: 1`), in which the error is sent back and a
corrected JSON object is requested. A row that still fails is written to
`errors.jsonl` and is scored as wrong.

**One label per answer.** The annotation sheet allows an optional secondary
label, but the system predicts one label and the evaluation joins on the
primary label only.

**Confidence** is used for analysis, not as a measure of correctness.
TODO(R9): decide whether to include a calibration analysis (a reliability
diagram per condition, review section 6.7). Nothing computes one yet.

## 4. Taxonomy

### 4.1 Sources and counts

The label definitions live in `taxonomy/recursion_bigO.yaml` (version 0.1,
created 2026-10-18). `scripts/validate_taxonomy.py` checks its structure:
28 items, 24 for recursion and 4 for Big-O, plus the three special labels.
Each item has an id, a concept, a source citation with a locator, a
description in our own words, a kind, the answer types that can show it
(`observable_in`), trigger phrases for condition 0, and a status.

| Source | Items | Kind | Status in the file | Survey verification of the source |
|---|---|---|---|---|
| Hamouda et al. 2017, recursion concept inventory | 12 | 9 misconception, 3 difficulty | 12 verified | full text |
| ProgMiscon (Chiodini et al.), recursion entries | 5 | 5 misconception | 5 verified | site fetched; paper not read |
| Götschi, Sanders & Galpin 2003, mental models | 7 | 7 mental model (1 viable, 6 non-viable) | 7 provisional | abstract; full text not read |
| Big-O candidates, to be confirmed against Farghally et al. 2017 | 4 | 4 misconception | 4 provisional | metadata only; item list not read |
| **Total** | **28** | 18 misconception, 3 difficulty, 7 mental model | **17 verified, 11 provisional** | |

For the Hamouda and ProgMiscon items, the id is the source's own tag, kept
verbatim, including the paper's spelling `BCcheckAganistConstant`. For the
Hamouda items the file also stores the paper's wording and the prevalence the
paper reports for each item.

"Verified" in the file means that the item's wording was checked against its
source. It does not mean that the item has been observed in this project's
data.

### 4.2 The provisional items

The seven mental-model labels (`MMcopies`, `MMlooping`, `MMactive`, `MMstep`,
`MMmagic`, `MMreturnValue`, `MModd`) take their names from the abstract of
Götschi, Sanders & Galpin (2003). The description of each model in the file is
our paraphrase and was not checked against the full text. `MMcopies` is the
viable model, so it is never the primary label of an answer; the schema allows
it only as a secondary label.

The four Big-O labels (`BOsearchLinearScan`, `BOsearchVsSort`,
`BObestCaseSmallestInput`, `BObestWorstSwapped`) were written from patterns
seen in low-scoring Mohler answers. Their names and wording are ours. They are
not items from a published inventory, and they must not be described as such
until they have been confirmed. TODO(R10): after reading Farghally et al. 2017
(TODO(R5)), confirm, reword or drop each one, and re-check every gold row that
carries one. TODO(R11): check the seven mental-model descriptions against the
full text of Götschi et al. 2003.

### 4.3 The observability problem

The inventories behind the recursion items were built from students tracing
and writing code. The eval data is recall-style: none of the seven in-scope
questions asks the student to trace or write code (section 5). So the first
question about each item is whether a recall answer can show it at all.

The taxonomy records this per item in `observable_in`. The annotation schema
(v0.2, section 2) then says what to expect from Mohler answers specifically.

| Group | Items | Marked observable in conceptual recall | What the schema expects of Mohler answers |
|---|---|---|---|
| Hamouda, backward flow | 2 | 0 | No; needs a code trace |
| Hamouda, infinite recursion | 1 | 1 | Weakly, on E03.Q06 only |
| Hamouda, recursive call | 3 | 1 (`RCreturnIsRequired`) | Only if the student states the belief; the other two need code |
| Hamouda, base case | 5 | 4 (all but `BCevaluation`) | Only if the student states the belief; `BCwrite` narrowly, on E05.Q04 |
| Hamouda, updating variables | 1 | 0 | No |
| ProgMiscon | 5 | 5 | Only if stated |
| Götschi mental models | 7 | 7 | Yes, when the answer describes how recursion runs |
| Big-O (provisional) | 4 | 4 | Yes, on E05.Q03, E10.Q07 and E12.Q10 |
| **Total** | **28** | **22** | |

Six items cannot be shown by a recall answer under the taxonomy's own
marking: `BFneverExecute`, `BFexecuteBefore`, `RCwrite`, `RCnoReturnRequired`,
`BCevaluation` and `GlobalVariable`. The schema makes these ineligible as gold
labels in this pilot, and the sheet validator rejects them. With `MMcopies`
barred as a primary label, gold can hold at most 21 of the 28 item ids, plus
the three special labels. The models still choose among all 31 labels, so a
prediction of one of the other seven ids can never be correct on this data.

"Marked observable" is weaker than "likely to be observed". Most recursion
items in the table are observable only if a student volunteers a belief that
the question did not ask about. The project review (section 3.2) reads the
situation more strictly than the taxonomy file: it says that nine of the
twelve Hamouda items require seeing the student reason about code, and that
only two or three can appear in Mohler answers. The file marks six of the
twelve as code-only. TODO(R12): reconcile the two readings, in the taxonomy's
`observable_in` field or in the text, before the final report.

The items the Mohler questions ask about most directly are the four Big-O
items, on three of the seven questions, and those are the provisional ones.
Among the recursion items the schema expects a direct match only narrowly:
`BCwrite` on E05.Q04 and, weakly, `InfiniteExecution` on E03.Q06. Which items
receive gold labels is an empirical question that the annotation answers:
TBD (TODO(R13): after annotation, list the ids with zero gold labels).

### 4.4 Consequences for scoring

An item with no gold rows is reported as having "zero observed primary
labels", not as proven unobservable (schema section 8). It is left out of the
macro-F1 average and named, not averaged in as a zero (section 8).

## 5. Data

### 5.1 JorGPT is out of scope

The project was proposed on the JorGPT dataset. The feasibility pilot of
2026-10-15 (`scripts/inspect_jorgpt.py`, `scripts/filter_scope.py`, and a
manual read of every flagged question; table in
`data/processed/scope_report.md`) found that the local copy matches the
paper's description (3,041 rows, 50 questions, 79 anonymized students, English
and Spanish files) and that **0 of the 50 questions are about recursion or
Big-O**. All of them are software-engineering topics. JorGPT therefore
supplies no eval data. The pilot also found that the English file's
`question_text` often holds answer-like text instead of the translated
question; the Spanish file has the original questions.

### 5.2 Mohler ASAG

The fallback is the Mohler ASAG dataset (Mohler, Bunescu & Mihalcea 2011):
short answers from a University of North Texas data-structures course, taken
from the Hugging Face dataset `nkazi/MohlerASAG`, `cleaned/open_ended`,
license CC-BY-4.0. The local file holds 2,273 answers to 81 open-ended
questions with the columns `id`, `question`, `instructor_answer`,
`student_answer`, `score_grader_1`, `score_grader_2` and `score_avg`. It has
no misconception labels.

*Grading scale.* Exams E01 to E10 are graded 0 to 5. Exams E11 and E12 are
graded 0 to 10 by each grader. `score_avg` is rescaled to 0 to 5 for every
exam, so it is the only score that is comparable across exams, and it is the
only one used here.

*Tokenization.* The `cleaned` split is Penn-Treebank tokenized (`-LRB-` and
`-RRB-` for parentheses, "n to the power of 2" for exponents, `<STOP>` at
sentence ends). A `raw` config with untokenized answers exists on Hugging Face
according to the review's reading of the dataset card; this project has not
used it. The eval sheet is built from `cleaned` with a light normalization
(section 5.3). TODO(R14): decide whether to rebuild from `raw`; this must
happen before labeling starts, because the sheet's source cells are frozen by
fingerprint once annotation begins.

*In-scope questions.* A keyword filter flagged 11 of the 81 questions (314
answers). On manual review, five are strong fits (139 answers) and two are
medium fits; the other four are weak or false positives. The seven strong and
medium questions hold 200 answers:

| Question | Topic | Answers | `score_avg` < 3.5 | `score_avg` <= 2.5 |
|---|---|---|---|---|
| E03.Q06 | causes of infinite recursion | 31 | 2 | 1 |
| E05.Q04 | base case of recursive merge sort | 28 | 7 | 7 |
| E05.Q03 | best-case operations of insertion sort | 28 | 8 | 4 |
| E10.Q07 | comparisons to find an element in a BST | 24 | 8 | 7 |
| E12.Q10 | steps to search a node in a BST | 28 | 9 | 9 |
| E03.Q07 | similarities of iteration and recursion | 31 | 6 | 3 |
| E11.Q09 | divide and conquer | 30 | 3 | 0 |
| **Total** | | **200** | **43** | **31** |

These counts describe the source data, not an outcome. They are from the
project review (section 2.4) and were re-derived from the local parquet on
2026-11-22. A low grade is not a misconception: the grade measures match to
the rubric, and the annotation decides what, if anything, is wrong with an
answer.

### 5.3 Construction of the eval sheet

`scripts/build_pilot_sheet.py` builds `annotation/pilot_sheet.csv` from the
seven questions. It takes every answer with `score_avg` below 3.5 (43 rows),
the pool most likely to contain misconceptions, and adds the 20
highest-scoring answers to populate the `none` class. All 20 are scored 5.0;
99 answers on these questions have that score (counted in the local parquet
on 2026-11-22), so the tie-break, longest answer first, decided the
selection. The sheet has 63 rows:

| Question | Low scorers | High scorers | Rows |
|---|---|---|---|
| E03.Q06 | 2 | 3 | 5 |
| E05.Q04 | 7 | 0 | 7 |
| E05.Q03 | 8 | 2 | 10 |
| E10.Q07 | 8 | 0 | 8 |
| E12.Q10 | 9 | 2 | 11 |
| E03.Q07 | 6 | 8 | 14 |
| E11.Q09 | 3 | 5 | 8 |
| **Total** | **43** | **20** | **63** |

The script normalizes the question, the instructor answer and the student
answer in the same way: `-LRB-` and `-RRB-` become parentheses, `<STOP>` is
dropped, whitespace is collapsed. Other tokenization artifacts stay ("n to the
power of 2", "n minus 1", "C plus plus"). Re-running the script on 2026-11-22
reproduced the committed sheet byte for byte.

The sheet is not a random sample of anything. It over-represents low-scoring
answers by design, and its correct answers are the longest ones. Label
frequencies in it do not estimate how common a misconception is.

### 5.4 Contamination

The Mohler data dates from around 2009 to 2011 and is widely used, so the
base model may have seen the questions, the answers, or both during training.
This cannot be ruled out with the data in hand. The mitigation in the research
plan, comparing against freshly collected answers, has no collection plan.
TODO(R15): either add a supplement of new answers and report it separately,
or state plainly that contamination is uncontrolled.

### 5.5 What the data does not yet include

There is no supplement to the 63 rows; whether one is needed is decided by the
annotation (section 6). There are no labeled student answers outside the eval
sheet, so condition 3's few-shot examples cannot be real answers; section 7.4
says what is being used instead. No eval
item has been tagged as retrieval-dependent, meaning that retrieved course
content could change its correct label; without such items conditions 2 to 4
cannot differ by construction (review gap G7). TODO(R16): build or tag that
subset when the retrieval corpus exists.

## 6. Annotation protocol

This section describes schema v0.2 (`annotation/schema.md`, 2026-11-01) and
the workflow in `annotation/README.md`. **No row is labeled as of
2026-11-22.** Schema v0.2 was written before any label existed.

**Who labels.** Only humans assign labels. For this pilot there is no model
pre-labeling, and model-generated labels are never gold. The annotator does
not look at the output of any condition before labeling and does not revise a
label after seeing one. The grade is hidden while deciding and consulted
afterwards only to catch a misreading.

**What is recorded.** Four columns per row. `primary_label` holds exactly one
label. `secondary_label` is optional and restricted: never `none` or
`insufficient_evidence`, never a repeat of the primary; with primary `none`
only `MMcopies` is allowed, and with primary `insufficient_evidence` nothing
is. `evidence_span` is required whenever either label is a taxonomy id. It
must be a verbatim, case-sensitive substring of the student answer, with
disjoint spans joined by ` || `. `annotator_notes` is required whenever
either label is `other_error`, and it is where candidate new items are
recorded, one per line in the form `Candidate: short description`.

**Core rules.** One primary label per answer. Label what the text says, not
what it omits: a correct but incomplete answer is `none`. The grade is not the
label: a top-scoring answer can carry a misconception in an aside, and a
low-scoring answer can be `none`. An explicit incorrect aside prevents `none`;
if it matches no item it is `other_error`. The three difficulty items need an
attempt at code, with one exception: an answer to E05.Q04 that states a wrong
base case for merge sort may be `BCwrite`. A wrong answer to a different
question, such as a running time given when a base case was asked for, is
`other_error` unless it matches a Big-O item on a search or best-case
question. `insufficient_evidence` is for text that cannot be judged, not for
answers that are merely short. Provisional Big-O items are used exactly like
verified ones during the pilot, with loose fits noted. For this recall pilot
a taxonomy label is eligible only if the taxonomy marks it observable in
conceptual recall.

**Decision rules.** Section 5 of the schema gives a table of rules for each of
the seven questions, written from the recurring patterns in the low scorers:
for example, "O(n log n)" in answer to the merge-sort base-case question is
`other_error`, and "n/2" for the cost of a BST search is `BOsearchLinearScan`.
Section 6 of the schema gives precedence between overlapping ids.

**Workflow and checks.** The first session covers 14 answers, two per
question, chosen by row identity and score pool without predicting labels.
After validation and a review of ambiguous cases, the remaining 49 are
labeled in batches of about 10 to 15, with validation after each batch.
`scripts/annotation_sheet.py` checks the mechanics: valid labels, the
secondary-label restrictions, eligibility for a recall pilot, the `BCwrite`
restriction, required notes, and that every evidence part is verbatim. It
also checks each row's six source cells against SHA-256 fingerprints frozen in
`annotation/pilot_identity.json`, so the source text cannot change under the
labels. Passing validation means the sheet is structurally complete. It does
not mean that the evidence supports the label; that is the human's judgment.
If a rule has to change, the schema version is bumped and earlier labels are
re-checked under the new rule.

**The pilot's decision.** The progress report counts primary `other_error`
labels among the 43 low scorers. If more than half, that is at least 22 of 43,
are `other_error`, Mohler alone cannot support the evaluation and a supplement
is required. TODO(R17): report the count and the decision; choose the
supplement if one is required.

**Raters.** There is one rater so far, the project's author, and first-rater
labels are not gold. A second rater is planned and not recruited (schema
section 7): a
classmate or the course TA, briefed with the schema and the taxonomy and not
shown the first rater's labels or notes. The second rater labels 30 to 50 of
the 63 rows: every row to which the first rater gave a taxonomy id, topped up
with a random sample of the other rows, stratified so that every question
appears. Agreement is unweighted Cohen's kappa on the primary label, computed
on the labels before adjudication and reported twice, over the full label set
and over a four-way collapse (taxonomy id, `none`, `other_error`,
`insufficient_evidence`), together with raw percent agreement, the pairwise
confusion table, and the share of doubly-labeled taxonomy rows whose evidence
spans overlap by at least one token. Disagreements are then discussed and
the adjudicated labels become gold. The schema's own threshold: a kappa below
0.4 on the four-way collapse means the schema needs work before any model is
evaluated.

TODO(R18): recruit the second rater; record the selected row ids, the random
seed, the rater and the schema version in `annotation/README.md`. TODO(R19):
write the agreement script; the kappa function exists in
`src/eval/metrics.py`, and the tooling for the subset and for agreement is
deferred. TODO(R20): if no second rater can be found, say so here and treat
every score in section 10 as measured against single-rater labels.

## 7. Conditions

Every condition runs on the same 63-row sheet and, for conditions 1 to 4b,
the same base model. Conditions 0 and 1 are built. The rest are planned, and
their descriptions below are design intentions, not descriptions of code.

### 7.0 Shared harness (built)

`scripts/run_condition.py` reads the sheet, runs one condition, and writes a
run folder `results/<run_id>/` with a manifest, one validated prediction
record per answer, and a file of rows that failed validation. LLM calls go
through `src/llm.py`, a thin client for any OpenAI-compatible chat endpoint.
It requests JSON output, captures token usage, and caches every response on
disk under a key made of the model, the messages, the temperature, the seed,
the token limit and the JSON-mode flag, so a re-run with unchanged settings
costs nothing and returns the same outputs.

The base model configured for all conditions is `gpt-oss:20b`, served locally
through Ollama (`configs/models.yaml`). Generation settings for single-pass
conditions: temperature 0.0, seed 0, at most 2,048 output tokens, JSON mode
on, one repair round-trip. TODO(R21): confirm this model as the base model
after condition 1 has been scored on labeled data. The review (section 6.1)
recommends also running condition 1 on one hosted model before committing;
that has not been done.

### 7.1 Condition 0: keyword baseline (built)

`src/baselines/keyword.py`. Each taxonomy item's trigger phrases are matched,
case-insensitively and as plain substrings, against the whitespace-normalized
student answer. The prediction is the item with the most distinct matched
phrases; ties go to the item that comes first in the taxonomy file; the
prediction is `none` when nothing matches. The evidence is the matched text,
copied from the answer. The confidence is the winner's share of all matched
phrases, and 0.5 for `none`.

Its limits follow from the design. It can output only an item id or `none`,
never `other_error` or `insufficient_evidence`, so it never abstains. Matching
has no word boundaries. `MModd` has no trigger phrases and can never be
predicted. The trigger phrases of the four Big-O items were written from the
same Mohler answers that make up the eval sheet, so this baseline is fitted to
the eval data and is a floor, not a fair competitor (section 11).

### 7.2 Condition 1: direct LLM (built)

`src/baselines/direct.py` with the prompt template
`configs/prompts/direct_v1.txt`. One zero-shot call per answer. The system
message sets the role of an instructor diagnosing misconceptions and asks for
a single JSON object. The user message gives the question, the instructor's
reference answer and the student's answer, then the closed list of the 28
item ids, then one-line definitions of the three special labels, then four
rules: judge only what the student wrote; the grade is unknown; evidence spans
must be verbatim, at least one for an item id or `other_error` and none for
`none` or `insufficient_evidence`; confidence is the probability that the
label is correct.

There is no retrieval, there are no examples, and there are no item
descriptions. The ids themselves are given, and some of them are descriptive
(`BObestWorstSwapped`), so condition 1 is not entirely free of taxonomy
content. The proposal describes condition 1 as "no taxonomy". TODO(R22):
either reword that description or accept the leak and say so; the step from
condition 1 to condition 3 adds descriptions and examples, not the label
names.

Prompt templates are versioned files that are not edited once a run has used
them, and the manifest records the template's name and SHA-256.

### 7.3 Condition 2: course-material retrieval (planned)

Condition 1 plus static top-k retrieval of course material relevant to the
question, in a single pass. Not in the committed code. The review (section
6.2) lists three
candidate sources: course notes written for the purpose, OpenDSA chapters on
recursion and algorithm analysis, and Mohler's own instructor answers.

On 2026-11-22 a corpus of the first kind was being drafted under
`data/corpus/`: two files of course notes, one on recursion and one on
algorithm analysis, with chunk markers in the text. Their headers say they
were written for this project on that date, in the voice of the course
instructor, as original text, with course conventions that follow the Mohler
instructor answers. A retrieval module (`src/retrieval.py`), a condition 2
runner (`src/baselines/rag.py`) and its prompt were being written on the same
date. All of it is uncommitted and unreviewed, so it is not described further
here. Section 11 states what follows from a corpus written with the eval
questions in view. TODO(R23): finish and commit the corpus and the retrieval
code; then describe the chunking, the retrieval method, k and the query here,
from the code.

### 7.4 Condition 3: taxonomy and few-shot grounding (planned)

Condition 2 plus the taxonomy items' descriptions and a few labeled examples
in the prompt, still in a single pass. Not in the committed code. This is the
baseline the mechanism claim is measured against.

The few-shot examples cannot be eval rows, and no other labeled student
answers exist. On 2026-11-22 a runner (`src/baselines/taxonomy_fewshot.py`),
a prompt and a file of examples (`configs/prompts/fewshot_v1.yaml`) were being
written, uncommitted. The header of the examples file says that every
question and answer in it was written from scratch for the prompt, that none
is taken from the Mohler data or the eval sheet, and that none of the seven
in-scope questions is used. TODO(R24): review those examples and confirm that
claim before relying on them. Authored examples are not real student answers,
and that belongs in section 11 once they are adopted. TODO(R25): decide
whether the prompt holds all 28 items or only the items observable in recall.

### 7.5 Condition 4: Critic-driven re-retrieval (planned)

Condition 3 plus a Critic that judges whether the retrieved evidence is
sufficient for a diagnosis and, when it is not, triggers another retrieval
before the final answer. Not built, and not specified: what "insufficient"
means operationally, what pool and query the re-retrieval uses, how many
rounds are allowed and what stops the loop are all open. The review (section
6.5) proposes the contents of a one-page specification (a sufficiency prompt
with a `sufficient` flag and a `missing` field, a re-query built from
`missing`, at most two refinement rounds, per-round logging); none of it has
been adopted. The Critic uses the same base model as every other condition.
TODO(R26): write the Critic specification before writing code, and copy the
adopted version here.

### 7.6 Condition 4b: compute-matched self-consistency (planned)

Condition 3's prompt sampled several times, with a majority vote over the
labels, at a total token budget matched to condition 4. Not built.
`configs/models.yaml` reserves a sampling temperature of 0.7 and leaves the
number of samples unset, because it depends on condition 4's measured cost.
TODO(R27): set the number of samples from condition 4's mean tokens per
answer; state the tie-break rule for the vote.

## 8. Metrics and statistics

Everything in 8.1 to 8.4 is implemented in `src/eval/metrics.py` and
`scripts/evaluate.py` and covered by unit tests. None of it has been computed
on labeled data. 8.5 and 8.6 are planned.

### 8.1 Headline metric

Macro-F1 on the primary label: the unweighted mean of per-class F1 over the
labels that occur in gold. A label with no gold rows is not a class in the
average. A prediction of a label that does not occur in gold adds no class;
it counts as a miss for the gold class of that row. The reports also give
per-class precision, recall and F1 with each class's support and predicted
count, the confusion matrix, accuracy, and macro-F1 on a four-way collapse of
the labels (any taxonomy id, `none`, `other_error`, `insufficient_evidence`).
The four-way figure answers a coarser question and is less exposed to
taxonomy classes that have only one or two rows.

Rows whose model output failed validation have no prediction. They are scored
as wrong, not dropped, and they count as covered in 8.2.

### 8.2 Abstention

`insufficient_evidence` is the system's way to abstain. It remains a class in
the headline macro-F1 when it occurs in gold. So that abstaining cannot raise
a score unnoticed, four more figures are reported: coverage, the share of
predictions that are not `insufficient_evidence`; accuracy on the covered
rows; the number of abstentions next to the number of gold rows labeled
`insufficient_evidence`; and macro-F1 with `insufficient_evidence` removed
from the averaged classes. There is no separate "abstention rate"; it is one
minus coverage.

### 8.3 Uncertainty and comparisons

The interval on macro-F1 is a 95% percentile bootstrap: 2,000 resamples of
rows with replacement, seed 0, with macro-F1 recomputed over the classes
present in each resample. Two runs are compared with a paired bootstrap on the
difference in macro-F1, using the same resample indices for both runs, which
gives an interval and a two-sided p-value; and with an exact McNemar test on
per-row correctness. The planned comparisons are condition 4 minus condition 3
and condition 4 minus condition 4b.

The rows are not independent: 63 answers come from 7 questions. Resampling
rows therefore understates the variance, and every report prints that caveat.
TODO(R28): decide whether to add a question-level resampling as a sensitivity
check, and whether the two planned comparisons need a correction for
multiplicity.

### 8.4 Citation validity (automatic)

For every record, each cited `student_answer` span is checked to be a
verbatim substring of the answer after whitespace normalization. The reported
rate is the share of valid records among those that cite at least one student
span. The same check runs on the gold evidence spans. This catches fabricated
quotes, the failure Oli et al. describe. It says nothing about whether a
genuine quote supports the label. In the committed code it does not check
spans cited from retrieved material or from the taxonomy, which conditions 0
and 1 never produce. TODO(R29): extend the check to `retrieved` and `taxonomy`
spans for conditions 2 to 4 (an extension was being written on 2026-11-22,
uncommitted), then update the columns of section 10.3 to match.

### 8.5 Grounding support (planned, human)

On a sample of diagnoses, a human rates each cited piece of evidence as
supports, partially supports, or unrelated with respect to the predicted
label, and the distribution is reported per condition. An LLM judge may apply
the same rubric only after its agreement with the human ratings has been
measured and reported. Not implemented. TODO(R30): sample size, sampling
procedure, and who rates; with one rater this measure has no agreement figure.

### 8.6 Agreement and cost

Inter-annotator agreement is described in section 6. Cost per condition comes
from each run's manifest: prompt, completion and total tokens, with and
without cache hits; the number of live and cached calls; a dollar figure; and
wall time. The base model runs locally, and its configured cost per token is
zero, so tokens and calls are the cost measures that matter for comparing
condition 4 with 4b.

## 9. Controls

**Compute-matched control (planned).** Condition 4 makes more calls and uses
more tokens than condition 3. Condition 4b spends a matched budget on
sampling condition 3's prompt. If 4b matches 4, the gain comes from compute,
not from the Critic.

**Positive control for the Critic (planned).** End-to-end accuracy on a set
this small cannot show whether the Critic's judgment works. The direct test is
a small set of cases in which the supporting chunk is deliberately withheld
from the first retrieval, so the first-pass evidence is known to be
insufficient, paired with cases in which it is present. The Critic should
trigger a second retrieval on the first kind and not on the second.
TODO(R31): build these cases once the corpus is chunked and indexed; fix
their number.

**Paraphrase check for shortcut learning (planned).** A model can match
surface words from the taxonomy descriptions without reasoning about the
answer. A handful of answers with known labels are paraphrased to remove
trigger words while keeping the same error; a collapse in accuracy on the
paraphrases would mean keyword matching. TODO(R32): choose the answers and
who writes the paraphrases. The review suggests cutting this control first if
time is short.

**Controls already in place.** The same sheet and base model for every
condition. No condition sees the grade. Labels are assigned without sight of
any model output, and a model never pre-labels. Citation validity is checked
automatically for every record. Runs are deterministic on re-run through the
response cache, and each manifest pins the sheet, the taxonomy and the prompt
by SHA-256. Mock runs, which return a canned record, are named `mock` in their
run id and are never reported.

## 10. Results

**No results exist.** Every cell below is TBD. The tables mirror the fields
that `scripts/evaluate.py` (as committed in 944463f) writes to `metrics.json`;
field paths are given in
the column heads. TODO(R33): fill every table from the run folders, and name
the `run_id` of each run used.

### 10.1 Gold labels (`gold.*`)

| `gold.n_rows` | `gold.n_labeled` | `gold.n_unlabeled` | `gold.invalid_gold_labels` (count) | `gold.citation_validity.rate` (`n_valid` / `n_with_spans`) |
|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD |

Gold label distribution, from the annotation progress report
(`scripts/annotation_sheet.py --report`, `primary_counts`):

| Label | Gold rows |
|---|---|
| (one row per label with at least one gold row) | TBD |

Pilot decision (`low_scorers.*` in the same report):

| `low_scorers.completed` | `low_scorers.other_error` | `low_scorers.other_error_share_all_43` | `low_scorers.decision` |
|---|---|---|---|
| TBD | TBD | TBD | TBD |

### 10.2 Scores per condition (`scores.*`)

| Condition | `run_id` | `n_scored` | `n_missing_predictions` | `macro_f1` | `macro_f1_ci.lower` | `macro_f1_ci.upper` | `macro_f1_excluding_abstain` | `four_way.macro_f1` | `accuracy` |
|---|---|---|---|---|---|---|---|---|---|
| 0 keyword | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 1 direct LLM | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 2 + retrieval | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 3 + taxonomy, few-shot | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 4 + Critic | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 4b self-consistency | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

Bootstrap settings used (`scores.macro_f1_ci.n_resamples`, `.seed`, `.alpha`,
`.n_rows`): TBD. Labels averaged (`scores.labels_in_gold`): TBD.

### 10.3 Abstention and citation validity

| Condition | `scores.coverage` | `scores.covered_accuracy` | `scores.abstention.n_abstained` | `scores.abstention.n_gold_abstain` | `predictions.n` | `predictions.n_errors` | `predictions.citation_validity.rate` (`n_valid` / `n_with_student_spans`) | `predictions.citation_validity.rate_all` |
|---|---|---|---|---|---|---|---|---|
| 0 keyword | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 1 direct LLM | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 2 + retrieval | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 3 + taxonomy, few-shot | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 4 + Critic | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 4b self-consistency | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### 10.4 Per-class scores (`scores.per_class`), one table per condition

| Label (from `scores.labels_in_gold`) | `precision` | `recall` | `f1` | `support` | `predicted` |
|---|---|---|---|---|---|
| (one row per label with at least one gold row) | TBD | TBD | TBD | TBD | TBD |

### 10.5 Confusion matrix (`scores.confusion`), one per condition

Rows are gold, columns are predicted, labels in the order of
`scores.confusion.labels`.

| gold \ predicted | (label 1) | (label 2) | ... |
|---|---|---|---|
| (label 1) | TBD | TBD | TBD |
| (label 2) | TBD | TBD | TBD |
| ... | TBD | TBD | TBD |

### 10.6 Predicted label distribution (`predictions.label_distribution`)

| Label | 0 | 1 | 2 | 3 | 4 | 4b |
|---|---|---|---|---|---|---|
| (one row per predicted label) | TBD | TBD | TBD | TBD | TBD | TBD |

### 10.7 Paired comparisons (`comparison.*`, from `--compare`)

"This" is the run passed to `--run`; "other" is the run passed to `--compare`.

| This minus other | `macro_f1_this` | `macro_f1_other` | `paired_bootstrap_this_minus_other.diff` | `.lower` | `.upper` | `.p_value` | `mcnemar.b` | `mcnemar.c` | `mcnemar.p_value` |
|---|---|---|---|---|---|---|---|---|---|
| 4 minus 3 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 4 minus 4b | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

TODO(R34): decide whether to report the other rungs of the ladder (1 minus 0,
2 minus 1, 3 minus 2) as well.

### 10.8 Cost per condition (from each run's `manifest.json`, written by `scripts/run_condition.py`)

| Condition | `n_predictions` | `calls.uncached` | `calls.cached` | `tokens.prompt_tokens` | `tokens.completion_tokens` | `tokens.total_tokens` | `cost.usd` | `wall_seconds` |
|---|---|---|---|---|---|---|---|---|
| 0 keyword | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 1 direct LLM | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 2 + retrieval | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 3 + taxonomy, few-shot | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 4 + Critic | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| 4b self-consistency | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### 10.9 Tables with no script behind them yet

No code writes the fields for these three tables. Their columns follow the
written plans (schema section 7; sections 8.5 and 9 above) and may change when
the code exists. TODO(R35): implement the scripts, then fix the columns.

Inter-annotator agreement:

| Rows doubly labeled | Kappa, full label set | Kappa, four-way collapse | Raw agreement | Evidence-span overlap |
|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD |

Grounding support (human ratings):

| Condition | Evidence items rated | Supports | Partially supports | Unrelated |
|---|---|---|---|---|
| (one row per condition rated) | TBD | TBD | TBD | TBD |

Controls:

| Control | Cases | Measure | Value |
|---|---|---|---|
| Critic positive control, evidence withheld | TBD | Critic triggered a second retrieval | TBD |
| Critic positive control, evidence present | TBD | Critic triggered a second retrieval | TBD |
| Paraphrase check, original answers | TBD | Accuracy | TBD |
| Paraphrase check, paraphrased answers | TBD | Accuracy | TBD |

### 10.10 Discussion

TODO(R36): write after the tables are filled. State what the intervals allow
and what they do not.

## 11. Limitations and threats to validity

These hold whatever the results turn out to be.

**Small sample, low power.** The eval set is 63 answers to 7 questions. With
up to 24 possible gold labels and 43 low-scoring answers, most classes will
have very few rows, and the intervals on macro-F1 will be wide. If condition 4
does not beat condition 3 or 4b, that may be because there is no effect or
because a set this small could not have shown one. A null result here does not
establish that the mechanism is useless, and the report must not word it that
way.

**Rows cluster by question.** The 63 rows are not independent draws. Answers
to one question share a topic, a reference answer and typical errors, and one
question supplies 14 of the 63 rows. The bootstrap resamples rows, so its
intervals are narrower than the real uncertainty. Seven questions are also too
few to support any statement about question types.

**One annotator.** Until a second rater has labeled the agreement subset,
gold is one person's reading, and that person also wrote the decision rules
and built the system. There is no agreement figure. Even with a second rater,
agreement is measured on 30 to 50 rows, and kappa over a sparse label set is
unstable at that size, which is why the schema also reports a four-way
collapse.

**Most recursion items cannot be seen in this data.** The recursion
inventories describe students tracing and writing code. The Mohler questions
are recall questions. Six of the 24 recursion items cannot be shown by a
recall answer at all, and most of the rest would appear only if a student
volunteered a belief the question did not ask about (section 4.3). Whatever
the system scores on recursion items, it is scored on a small subset of them,
and nothing can be concluded about the items that never occur.

**The Big-O items are provisional and were written from the eval data.** The
four Big-O labels are not confirmed against any published source. They were
defined by reading the low-scoring Mohler answers, and those same answers make
up most of the eval sheet. So were their trigger phrases, which condition 0
uses, and the per-question decision rules the annotator follows. The labels
most likely to be frequent in gold are therefore fitted to this data. Scores
on them say how well a system reproduces a categorization designed for these
63 answers, not how well it recognizes an established misconception.

**One base model.** Every condition uses one model, a 20B model served
locally. A difference between conditions, or the lack of one, may not
hold for a stronger or a weaker model. No second model has been run.

**An old, public dataset.** The answers are from around 2009 to 2011 and the
dataset is widely used. The model may have seen them in training. The data is
from one course at one university, in C++, and the text carries tokenization
artifacts that a model would not meet in real answers.

**The eval sheet is a constructed sample.** Low scorers are included
wholesale and correct answers are represented by the 20 longest top-scoring
ones. Class proportions in the sheet do not estimate prevalence, and precision
on `none` is measured on unusually thorough correct answers.

**Retrieval may have nothing to add.** For a ten-word recall answer, what
limits the diagnosis may be the information in the answer, not the retrieved
context. Unless some eval items are retrieval-dependent (section 5.5),
conditions 2, 3 and 4 cannot differ, and the mechanism claim is untestable on
this data by construction.

**The retrieval corpus is written for this project.** The course notes being
drafted for condition 2 are not the course's own material. They are written
after the eval questions were chosen and follow the instructor answers that
the eval rows are judged against (section 7.3). A gain from retrieval would
then show that notes written to cover these seven questions help on these
seven questions. It would not show that retrieval over ordinary course
material helps. TODO(R43): decide how to guard against this, for example by
adding a source written without sight of the eval questions, and say which
was done.

**Condition 1 is not taxonomy-free.** Its prompt lists the item ids, and some
ids describe their item (section 7.2).

**Grounding is only partly measured.** Citation validity checks that a quote
exists, not that it supports the label. The human support rating is planned
on a sample, by one rater.

TODO(R37): after the results, add the threats that the data reveals (for
example classes with no gold rows, or a supplement that had to be synthetic)
and remove any that no longer apply.

## 12. Reproducibility

**Code and state.** Everything described as built is in the repository as of
commit 944463f (2026-11-22). Conditions 0 and 1 and the evaluation need no
raw data: they read the tracked sheet `annotation/pilot_sheet.csv`.

**Environment.** Python 3.10 or newer; development used 3.12. Dependencies are
in `requirements.txt`, without pinned versions. The base model is
`gpt-oss:20b` under Ollama at `http://localhost:11434/v1`; no API key is
needed. TODO(R38): pin the dependency versions, and record the Ollama version
and the model's digest, none of which the manifest captures.

**Commands.**

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q                                   # unit tests
python scripts/validate_taxonomy.py                   # taxonomy structure
python scripts/annotation_sheet.py --complete         # all 63 rows labeled and valid
ollama serve                                          # before any LLM run
python scripts/run_condition.py --cond 0
python scripts/run_condition.py --cond 1
python scripts/evaluate.py --run <run_id>
python scripts/evaluate.py --run <run_id> --compare <other_run_id>
```

TODO(R39): add the commands for conditions 2, 3, 4 and 4b when they exist;
the committed `scripts/run_condition.py` accepts only `--cond 0` and
`--cond 1`.

**What each run records.** `results/<run_id>/manifest.json` holds the
condition, the model and provider, the prompt template's name and SHA-256, the
temperature, seed, token limit, JSON mode and repair limit, the git commit and
whether the tree was dirty, the SHA-256 of the sheet and of the taxonomy file,
token and call counts, cost and wall time. `predictions.jsonl` holds the
validated records with the model's raw text. `errors.jsonl` holds the rows
that failed. `scripts/evaluate.py` adds `metrics.json` and `metrics.md`, with
the SHA-256 of the gold sheet it scored against.

**Determinism.** With the response cache in place, re-running a condition
with the same settings reproduces the same outputs without calling the model.
The cache is gitignored, so on another machine the model is called again;
whether a fresh call at temperature 0 and seed 0 reproduces the cached output
is not covered by any test or record in the repository. The bootstrap uses a
fixed seed.
TODO(R40): decide whether to commit the run folders, the cache, or neither,
so that the reported numbers can be regenerated from the repository alone. No
run folder is committed today.

**Data.** The eval sheet is tracked and its source cells are fingerprinted.
The Mohler parquet and the JorGPT files are gitignored. With the Mohler
parquet in place, `scripts/build_pilot_sheet.py` rebuilds the unlabeled sheet
exactly. TODO(R41): record the exact download steps for both datasets; they
are not written down in the repository.

**Use of AI.** The repository records AI assistance in
[AI_NOVELTY_AUDIT.md](AI_NOVELTY_AUDIT.md). The project review of 2026-10-18
and this skeleton were written by Claude, and the commit that adds the
harness names Claude as co-author. Labels are assigned by humans only.

## References

Bibliographic details are copied from [LITERATURE_SURVEY.md](LITERATURE_SURVEY.md),
which also holds the Verification line for each entry. TODO(R42): format to the
course's citation style; resolve the open items noted in brackets.

- Al-Hossami & Bunescu. McMining: Automated Discovery of Misconceptions in
  Student Code. arXiv:2510.08827, 2025.
- Burrows, Gurevych & Stein. The Eras and Trends of Automatic Short Answer
  Grading. *International Journal of Artificial Intelligence in Education*
  25(1), 60–117, 2015. doi:10.1007/s40593-014-0026-8.
- Chiodini, Moreno Santos, Gallidabino, Tafliovich, Santos & Hauswirth. A
  Curated Inventory of Programming Language Misconceptions. ITiCSE '21,
  pp. 380–386, 2021. doi:10.1145/3430665.3456343.
  Inventory: https://progmiscon.org/misconceptions/
- Dinh, Schumacher & Niehues. From Slides to Chatbots: Enhancing Large
  Language Models with University Course Materials. arXiv:2510.22272.
- Farghally, Koh, Ernst & Shaffer. Towards a Concept Inventory for Algorithm
  Analysis Topics. SIGCSE '17, pp. 207–212. doi:10.1145/3017680.3017756.
- Götschi, Sanders & Galpin. Mental models of recursion. SIGCSE 2003,
  pp. 346–350. doi:10.1145/611892.612004.
- Haberman & Averbuch. The case of base cases: why are they so difficult to
  recognize? Student difficulties with recursion. ITiCSE '02, pp. 84–88.
  doi:10.1145/544414.544441.
- Hamouda, Edwards, Elmongui, Ernst & Shaffer. A basic recursion concept
  inventory. *Computer Science Education* 27(2), 121–148, 2017.
  doi:10.1080/08993408.2017.1414728.
- Herklotz, Ippisch & Haensch. Can we trust LLMs as a tutor for our students?
  Evaluating the Quality of LLM-generated Feedback in Statistics Exams.
  arXiv:2511.04213, 2025 (preprint).
- Imran & Bulathwela. The Correct Answer Trap: Pedagogically-Grounded
  Detection and Feedback for Hidden Misconceptions. arXiv:2606.23205.
- JorGPT dataset. A Multilingual Dataset of Student Answers, Human Grading,
  and Multi-LLM Evaluations for Automated Assessment Research Using JorGPT.
  *Data* 11(3), 59, 2026. doi:10.3390/data11030059. [Authors not verified.]
- Kiesler, Lohr & Keuning. Exploring the Potential of Large Language Models to
  Generate Formative Programming Feedback. FIE 2023. arXiv:2309.00029.
- Korthals et al. Towards Reliable LLM Grading Through Self-Consistency and
  Selective Human Review: Higher Accuracy, Less Work. *Machine Learning and
  Knowledge Extraction* 8(3), 74, 2026. doi:10.3390/make8030074.
- Levonian, Li, Zhu, Gade, Henkel, Postle & Xing. Retrieval-augmented
  Generation to Improve Math Question-Answering: Trade-offs Between
  Groundedness and Human Preference. arXiv:2310.03184.
- Liu, Chen, Baraniuk, Sachan & Sonkar. Misconception Acquisition Dynamics in
  Large Language Models. arXiv:2604.00818.
- Mitton, Bhattacharyya, Smith, Christie, Abboud & Woodhead. Misconception
  Diagnosis From Student-Tutor Dialogue: Generate, Retrieve, Rerank.
  arXiv:2602.02414, 2026.
- Mohler, Bunescu & Mihalcea. Learning to Grade Short Answer Questions using
  Semantic Similarity Measures and Dependency Graph Alignments. ACL-HLT 2011,
  pp. 752–762.
- Norris, Gal & Bulathwela. Next Token Knowledge Tracing: Exploiting
  Pretrained LLM Representations to Decode Student Behaviour.
  arXiv:2511.02599.
- Oli, Banjade, Olney & Rus. Can LLMs Identify Gaps and Misconceptions in
  Students' Code Explanations? arXiv:2501.10365.
- Ross & Andreas. Learning to Make MISTAKEs: Modeling Incorrect Student
  Thinking And Key Errors. arXiv:2510.11502, 2025.
- Scarlatos, Baker & Lan. Exploring Knowledge Tracing in Tutor-Student
  Dialogues using LLMs. LAK 2025. arXiv:2409.16490.
- Tilanterä & Korhonen. Data structures and algorithms misconceptions in
  concept inventories: a systematic literature review. *Computer Science
  Education*, 2026. doi:10.1080/08993408.2026.2633989.
- Wang, Zhou et al. LLM-KT: Aligning Large Language Models with Knowledge
  Tracing using a Plug-and-Play Instruction. arXiv:2502.02945, 2025.
  [Which version to cite is open.]
- Yeltekin & Bauer. Can LLMs Simulate Novice Programmers' Misconceptions?
  arXiv:2610.10656, 2026.
- Zhao, Jiao & Xu. Beyond Score Accuracy: Examining the Diagnostic Quality of
  LLM-Generated Structured Assessment in Higher Education. arXiv:2610.09460,
  2026.

## TODO index

| Id | Section | What is needed |
|---|---|---|
| R1 | front | Record AI drafting in the audit; rewrite prose in your own words |
| R2 | front | Abstract |
| R3 | 1 | Findings paragraph, after results |
| R4 | 2.1 | Read Burrows et al. 2015 or drop it |
| R5 | 2.2 | Get Farghally et al. 2017 and Tilanterä & Korhonen 2026 full texts |
| R6 | 2.2 | Read abstracts of Imran & Bulathwela and Ross & Andreas, or drop them |
| R7 | 2.4 | A tutoring-RAG paper that reports retrieval quality |
| R8 | 2.5 | Which version of Wang, Zhou et al. to cite |
| R9 | 3 | Calibration analysis: yes or no |
| R10 | 4.2 | Confirm, reword or drop the four Big-O items |
| R11 | 4.2 | Check mental-model descriptions against Götschi et al. full text |
| R12 | 4.3 | Reconcile "nine of twelve need code" with `observable_in` (six of twelve) |
| R13 | 4.3 | List ids with zero gold labels, after annotation |
| R14 | 5.2 | Rebuild the sheet from the `raw` config, or not; before labeling |
| R15 | 5.4 | Contamination: supplement, or state it is uncontrolled |
| R16 | 5.5 | Retrieval-dependent subset of eval items |
| R17 | 6 | `other_error` count among the 43; supplement decision |
| R18 | 6 | Recruit second rater; record subset ids, seed, rater |
| R19 | 6 | Agreement script |
| R20 | 6 | Fallback wording if no second rater |
| R21 | 7.0 | Confirm the base model |
| R22 | 7.2 | Condition 1 lists label ids: reword "no taxonomy" or accept |
| R23 | 7.3 | Finish and commit the retrieval corpus and code; describe chunking, method, k, query |
| R24 | 7.4 | Review the authored few-shot examples; confirm none overlaps the eval data |
| R25 | 7.4 | All 28 items in the prompt, or only recall-observable ones |
| R26 | 7.5 | Critic specification |
| R27 | 7.6 | Number of samples and tie-break for 4b |
| R28 | 8.3 | Question-level resampling; multiplicity correction |
| R29 | 8.4 | Citation check for retrieved and taxonomy spans; then update 10.3's columns |
| R30 | 8.5 | Grounding-support sample size, procedure, rater |
| R31 | 9 | Positive-control cases for the Critic |
| R32 | 9 | Paraphrase-check answers and author |
| R33 | 10 | Fill every results table; name the runs |
| R34 | 10.7 | Report the other rungs of the ladder, or not |
| R35 | 10.9 | Scripts for agreement, grounding support and controls; fix the columns |
| R36 | 10.10 | Discussion |
| R37 | 11 | Update limitations after results |
| R38 | 12 | Pin dependencies; record Ollama version and model digest |
| R39 | 12 | Commands for conditions 2 to 4b |
| R40 | 12 | Commit run folders, cache, or neither |
| R41 | 12 | Dataset download steps |
| R42 | References | Citation style; open bibliographic items |
| R43 | 11 | Guard against a retrieval corpus written with the eval questions in view |
