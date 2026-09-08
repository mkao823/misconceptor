# Literature & SOTA Survey

Ten recent (2024–2026) papers relevant to LLM-based diagnosis of student
misconceptions, knowledge tracing, and grounded automated assessment.

---

## Theme 1: Misconception Detection Directly from Student Responses

**1. "The Correct Answer Trap: Pedagogically-Grounded Detection and Feedback
for Hidden Misconceptions"** (arXiv:2606.23205, 2026)
Studies ~21,000 real student responses from the Eedi math platform and shows
that systems relying on answer correctness alone miss students who reach the
right answer through flawed reasoning ("correct-answer misconceptions").
Compares a fine-tuned BERT classifier against Gemini 3 Flash and an
open-weight Gemma model, using a graduated rubric that lets the system
express uncertainty and request follow-up evidence instead of forcing a
binary call. **Relevance:** directly motivates why our system diagnoses
reasoning, not just correctness, and the graduated-uncertainty rubric is a
template for our Critic's confidence mechanism.

**2. "Misconception Diagnosis From Student-Tutor Dialogue: Generate,
Retrieve, Rerank"** (arXiv:2602.02414, 2026)
Proposes a generate → retrieve → rerank pipeline: a fine-tuned LLM proposes
candidate misconceptions, embedding similarity retrieves the most plausible
ones, and a second fine-tuned model reranks them. Evaluated on real tutoring
dialogues across LLaMA, Qwen, and Claude; LoRA fine-tuning outperformed much
larger closed models. **Relevance:** a strong architectural alternative to
our Planner–Executor–Critic loop.

**3. "Learning to Make MISTAKEs: Modeling Incorrect Student Thinking And Key
Errors"** (arXiv:2510.11502, 2025)
Surveys and extends work on modeling student misconceptions, summarizing
findings that LLMs are considerably better at judging whether an answer is
*correct* than at identifying the specific incorrect reasoning behind a wrong
one. **Relevance:** directly supports our project's premise — diagnosis is
the harder, less-solved problem compared to scoring.

**4. "Misconception Acquisition Dynamics in Large Language Models"**
(arXiv:2604.00818, 2026)
Shows that instruction-tuning an LLM directly on misconception-laden student
responses can degrade the model's own reasoning ability, creating a tension
between faithfully modeling misconceptions and preserving correctness.
**Relevance:** informs our decision to rely primarily on prompting/RAG-based
diagnosis rather than fine-tuning on raw misconception data, at least for the
frontier-model tier of our comparison.

## Theme 2: Knowledge Tracing with LLMs

**5. "Exploring Knowledge Tracing in Tutor-Student Dialogues using LLMs"**
(Scarlatos, Baker & Lan, LAK 2025; arXiv:2409.16490)
Introduces LLMKT: uses LLM prompting to extract knowledge components from
each dialogue turn, verifies correctness against human annotation, then
applies knowledge-tracing methods on the resulting labeled data.
Outperforms prior KT baselines on two real tutoring datasets. **Relevance:**
template for how we turn per-question misconception labels into a
longitudinal per-student knowledge/misconception state.

**6. "Next Token Knowledge Tracing: Exploiting Pretrained LLM Representations
to Decode Student Behaviour"** (Norris et al., arXiv:2511.02599, 2025/2026)
Represents student history and question text as token sequences and uses
pretrained LLM representations for knowledge tracing, improving on
state-of-the-art neural KT models and generalizing better to unseen
questions/students. **Relevance:** supports our choice to use LLM
representations (vs. hand-engineered skill tags) for tracking mastery over
multiple midterms.

**7. "LLM-KT: Aligning Large Language Models with Knowledge Tracing using a
Plug-and-Play Instruction"** (arXiv:2502.02945, 2025)
Combines the sequence-modeling strength of traditional KT models with the
world-knowledge/reasoning strength of LLMs via a plug-and-play instruction
layer. **Relevance:** an alternative longitudinal-memory design we can
compare against our simpler summarize-and-retrieve memory approach.

## Theme 3: Grounded / Reliable Automated Assessment (adjacent, not competing)

**8. "AI-Based Automated Scoring Layer Using Large Language Models and
Semantic Analysis"** (MDPI Applied Sciences, 2026)
Combines LLMs, retrieval-augmented generation, and analytic rubrics to
produce criterion-based, context-grounded scoring of open-ended responses in
a real university exam setting. **Relevance:** the RAG + rubric grounding
pattern we adapt for our Critic role, applied to diagnosis rather than
scoring.

**9. "Towards Reliable LLM Grading Through Self-Consistency and Selective
Human Review" (SURE)** (MDPI Machine Learning & Knowledge Extraction, 2026)
Proposes a human-in-the-loop pipeline that uses repeated LLM prompting and
uncertainty-based flagging to decide which graded responses need human
re-review, reducing human workload while preserving accuracy. **Relevance:**
directly informs the confidence-flagging mechanism in our Critic stage —
low-confidence diagnoses get surfaced to the instructor rather than silently
reported.

**10. "A Multilingual Dataset of Student Answers, Human Grading, and
Multi-LLM Evaluations for Automated Assessment Research (JorGPT)"**
(MDPI Data, 2026)
Releases 3,041 authentic student answers to 50 open-ended computer-science
exam questions, collected from real 2025–2026 university assessments, with
instructor-defined ideal answers, human grading, and baseline evaluations
from three LLMs. **Relevance:** our primary bootstrap dataset — gives us
real, ground-truth-adjacent data to build our 50+ case evaluation set on
without the FERPA/consent overhead of collecting fresh student data
mid-semester. Misconception-category labels are not included and will be
added by us as an annotation layer.

---

### Gap our project targets

Themes 1 and 2 show that misconception detection and knowledge tracing with
LLMs are active but still-open research problems — not solved, but also not
un-tackled ("no man's land" claims would be dishonest). What is missing
across all ten papers is an **instructor-facing, longitudinally-tracked,
RAG-grounded diagnostic system evaluated on real exam data end-to-end** —
most existing work stops at single-turn diagnosis (Theme 1) or is scoring-
rather than diagnosis-oriented (Theme 3). That end-to-end, instructor-facing
integration is our project's contribution.
