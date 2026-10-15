# Literature & SOTA Survey

Reorganized after the professor's feedback into five required areas. The ten
original entries are kept. Each one now has a **Verification** line.

- **Verified (metadata)**: title, authors and venue were confirmed via a web
  search on 2026-10-15 (arXiv/DOI/publisher listings). The full paper has
  **not** been read. Claims that come only from our earlier summary are
  marked *TODO: verify*.
- **Partially verified**: the paper exists, but some details are unconfirmed.
- No paper was added from memory. The new candidate entries below were
  confirmed to exist by search but have not been read.

---

## Area 1: Automated short-answer assessment

**JorGPT dataset**: "A Multilingual Dataset of Student Answers, Human Grading,
and Multi-LLM Evaluations for Automated Assessment Research Using JorGPT."
*Data* (MDPI), 2026, 11(3), 59. doi:10.3390/data11030059. Also on Zenodo
(records/18981627) and Kaggle.
Per its abstract: 3,041 authentic student answers to 50 open-ended CS
questions from 2025–2026 university assessments, from 79 anonymized students.
Includes original Spanish answers with English translations, instructor ideal
answers, 0–10 human grades with qualitative feedback, and DeepSeek/Qwen/Gemini
evaluations under a shared JSON schema. **It contains no misconception labels.**
**Relevance:** our candidate source data. Any misconception labels have to be
added by us as an annotation layer, and in-scope coverage for recursion/Big-O
is not yet known (feasibility pilot).
*Verification:* Verified (metadata and abstract). Authors: TODO: verify.
*Correction:* earlier drafts called this "ground-truth-adjacent" data for
diagnosis. That overstated it; the human ground truth is scores and feedback,
not misconception categories.

**"AI-Based Automated Scoring Layer Using Large Language Models and Semantic
Analysis"** (Vangelova & Gancheva)
Combines LLMs, RAG and analytic rubrics for criterion-based scoring of
open-ended answers, integrated with Moodle and tested on a university exam.
**Relevance:** a RAG + rubric grounding pattern for *scoring*, which we adapt
to diagnosis.
*Verification:* Partially verified. Title and authors were found in a
university repository listing. **The venue ("MDPI Applied Sciences, 2026")
and year are not confirmed. TODO: verify.**

**Candidate (found by search, not yet read):** "Beyond Score Accuracy:
Examining the Diagnostic Quality of LLM-Generated Structured Assessment in
Higher Education," arXiv:2610.09460. A search snippet says it analyzes the
JorGPT data. TODO: read; potentially the closest prior work on diagnostic
(vs. score) quality for this dataset.

TODO: find paper for this area. We need a foundational or survey reference
for automated short-answer grading (pre-LLM ASAG), so that LLM-based work has
a baseline lineage.

## Area 2: Misconception diagnosis

**"The Correct Answer Trap: Pedagogically-Grounded Detection and Feedback for
Hidden Misconceptions"** (Imran & Bulathwela; arXiv:2606.23205; PEAF 2026
workshop)
Uses about 21,000 (20,964 per the abstract) real Eedi math-platform responses.
It shows that correctness-only systems miss students who reach the right
answer through flawed reasoning, and it proposes a graduated rubric that
separates correctness from reasoning quality.
**Relevance:** motivates diagnosing reasoning, not correctness.
*Verification:* Verified (metadata). *TODO: verify* our earlier specifics:
"fine-tuned BERT vs. Gemini 3 Flash vs. Gemma" and "requests follow-up
evidence". The abstract snippets mention fine-tuned classifiers and an
open-weight reasoning model, but not those exact model names. A companion
paper by the same authors (arXiv:2605.23925, AIED'26) reports overlapping
figures; check which paper each figure comes from before citing it.

**"Misconception Diagnosis From Student-Tutor Dialogue: Generate, Retrieve,
Rerank"** (Mitton, Bhattacharyya, Smith, Christie, Abboud & Woodhead;
arXiv:2602.02414, 2026)
A fine-tuned LLM generates misconception hypotheses, embedding similarity
retrieves tutor-defined labels, and a second fine-tuned LLM reranks them.
Tested on 922 dialogues with LLaMA, Qwen and Claude. Fine-tuning can beat
larger closed models.
**Relevance:** a strong alternative to our Critic loop, and a candidate
additional baseline.
*Verification:* Verified (metadata and abstract). *TODO: verify* that the
fine-tuning is LoRA.

**"Learning to Make MISTAKEs: Modeling Incorrect Student Thinking And Key
Errors"** (Ross & Andreas; arXiv:2510.11502, 2025)
Generates synthetic student-error data by enforcing cycle consistency between
incorrect answers and their misconceptions, then trains models to simulate
students, infer misconceptions, and generate distractors.
**Relevance:** misconception inference from wrong answers, the same task
framing as ours, but in math.
*Verification:* Verified (metadata). Authors are taken from the arXiv HTML
version, because the PDF metadata disagrees. *Correction:* our earlier
summary called this a survey and said it shows "LLMs are better at judging
correctness than at identifying incorrect reasoning". That does not match the
abstract. That claim is removed until it is sourced.

**"Misconception Acquisition Dynamics in Large Language Models"** (Liu, Chen,
Baraniuk, Sachan & Sonkar; arXiv:2604.00818; listed at AIED 2026, LNCS 16581)
Instruction-tuning on misconception-laden data can degrade reasoning.
Intermediate reasoning steps are needed for a model to acquire misconceptions.
**Relevance:** supports prompting/RAG over fine-tuning on raw misconception
data.
*Verification:* Verified (metadata and abstract).

**Taxonomy source: recursion.** Hamouda, Edwards, Elmongui, Ernst & Shaffer,
"A basic recursion concept inventory," *Computer Science Education*, 2017.
doi:10.1080/08993408.2017.1414728.
**Relevance:** a candidate published source for the recursion taxonomy items.
*Verification:* Verified (metadata) by search. Full text not yet read. TODO:
extract the misconception list and item IDs from the full text. Do not use
item codes (e.g. "MR1") until they are confirmed there.

**Taxonomy source: data structures & algorithms (systematic review).**
TODO: find paper for this area. The research plan refers to a "92-item DSA
misconception systematic review" with categories C1/C2 for recursion and
basic algorithm analysis. A search on 2026-10-15 did **not** locate it. TODO:
verify the title, authors, item count and category codes from your own copy.
Related works found by search (not read): Danielsiek, Paul & Vahrenhold (2012,
doi:10.1145/2157136.2157148), a DSA concept-inventory effort, and an ICER 2023
systematic review of computing concept inventories.

## Area 3: LLM educational feedback

**"Towards Reliable LLM Grading Through Self-Consistency and Selective Human
Review: Higher Accuracy, Less Work"** (Korthals et al.; *Machine Learning and
Knowledge Extraction* (MDPI), 2026, 8(3), 74; doi:10.3390/make8030074)
Repeated LLM prompting: low certainty (high output diversity) flags likely
incorrect grades for human regrading, reducing manual grading time by 40–90%
per the abstract.
**Relevance:** directly motivates our condition 4b (self-consistency) as the
compute-matched control, and confidence-based flagging.
*Verification:* Verified (metadata and abstract). *TODO: verify* the "SURE"
acronym used in our earlier draft. It was not found in the metadata.

TODO: find paper for this area. We need work on LLM-generated formative
feedback to students (quality, correctness, pedagogical value), separate from
grading.

## Area 4: RAG for tutoring

TODO: find paper for this area. We need RAG grounded in course material for
tutoring or feedback, ideally with an evaluation of retrieval quality and
whether the evidence supports the output (feedback item 4). The Vangelova &
Gancheva scoring layer (Area 1) uses RAG for scoring, not tutoring.

## Area 5: Knowledge tracing

**"Exploring Knowledge Tracing in Tutor-Student Dialogues using LLMs"**
(Scarlatos, Baker & Lan; LAK 2025; arXiv:2409.16490)
LLMKT: an LLM tags knowledge components and correctness per dialogue turn,
validated against expert annotation, then applies KT. It beats KT baselines on
two tutoring datasets.
**Relevance:** LLM-produced labels validated against humans, the same
validation pattern we need for an LLM judge.
*Verification:* Verified (metadata). Baker appears on the LAK version but not
on arXiv v1.

**"Next Token Knowledge Tracing: Exploiting Pretrained LLM Representations to
Decode Student Behaviour"** (Norris, Gal & Bulathwela; arXiv:2511.02599,
2025/2026)
Frames KT as next-token prediction over text histories using fine-tuned LLaMA
models. Improves over neural KT and handles cold-start better.
**Relevance:** background for longitudinal tracking, which is now a stretch
goal.
*Verification:* Verified (metadata and abstract).

**"LLM-KT: Aligning Large Language Models with Knowledge Tracing using a
Plug-and-Play Instruction"** (Wang, Zhou et al.; arXiv:2502.02945, 2025)
Aligns LLMs with traditional KT sequence models via instruction and
context/sequence plug-ins.
**Relevance:** background for longitudinal tracking (stretch goal).
*Verification:* Verified (metadata). A revised version appears in ACL
Findings 2026 under a different title and author list. TODO: decide which
version to cite.

---

## Gap our project targets (revised)

The earlier gap statement said the contribution was an "instructor-facing,
longitudinally-tracked, RAG-grounded diagnostic system." That describes a
combination of components, not a contribution, and it has been withdrawn.

Revised: prior misconception-diagnosis work (Area 2) is mostly in math (Eedi)
and does not isolate whether **iterative, critic-triggered retrieval** adds
anything over a single-pass prompt that already contains the taxonomy. We
test that one mechanism on CS concepts (recursion, Big-O), using a taxonomy
from published CS misconception literature, against compute-matched baselines.
TODO: re-check this gap after reading arXiv:2610.09460 and filling Areas 3–4.
