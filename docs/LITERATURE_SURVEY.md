# Literature & SOTA Survey

Reorganized after the professor's feedback into five required areas. The ten
original entries are kept. Each one now has a **Verification** line.

- **Verified (metadata)**: title, authors and venue were confirmed via a web
  search on 2026-10-15 (arXiv/DOI/publisher listings). The full paper has
  **not** been read. Claims that come only from our earlier summary are
  marked *TODO: verify*.
- **Verified (metadata and abstract)**: as above, and the abstract (arXiv
  page or publisher listing) was fetched and read.
- **Verified (full text)**: the full text was fetched and the cited details
  were read from it.
- **Partially verified**: the paper exists, but some details are unconfirmed.
- No paper was added from memory. The new candidate entries below were
  confirmed to exist by search but have not been read.
- Entries added on 2026-10-18 follow docs/REVIEW_2026-10-18.md (sections 3.1
  to 3.5 and 7). Each was re-confirmed by search or fetch on that date, and
  its Verification line says which.

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

**"Beyond Score Accuracy: Examining the Diagnostic Quality of LLM-Generated
Structured Assessment in Higher Education"** (Zhao, Jiao & Xu;
arXiv:2610.09460, submitted 7 October 2026)
Analyzes the JorGPT data: 3,041 responses to 50 open-ended CS questions,
scored by human instructors and three commercial LLMs. Per the abstract:
rubric sub-dimension scores are highly correlated (r = 0.82–0.99, VIF up to
45), so they add little diagnostic information; LLM feedback identified
student misconceptions in only 5–7% of responses versus 15–31% for teachers,
acting as a coverage checklist rather than a diagnostic tool; feedback tone
stays uniformly positive regardless of answer quality; and grading accuracy
varies by knowledge domain, with procedural topics most reliable.
**Relevance:** the best single motivation for our problem statement: LLM
grading can score reliably while failing to diagnose. It is the closest prior
work on *diagnostic* (vs. score) quality, but it only measures how often
feedback names a misconception; it does not classify against a taxonomy,
retrieve course material, or check grounding.
*Verification:* Verified (metadata and abstract). arXiv abstract page fetched
on 2026-10-18. Full text not read. Previously listed here as an unread
candidate.

**Pre-LLM ASAG lineage (our dataset's source paper).** Mohler, Bunescu &
Mihalcea, "Learning to Grade Short Answer Questions using Semantic Similarity
Measures and Dependency Graph Alignments," *Proceedings of ACL-HLT 2011*,
Portland, pp. 752–762 (ACL Anthology P11-1076).
Combines lexical semantic similarity measures with dependency-graph alignment
features in a supervised grader and shows the combination grades short
answers more accurately than the semantic measures alone. It introduces the
data we now use: short answers from a University of North Texas data
structures course (81 open-ended questions in the public release), each
graded by two instructors.
**Relevance:** the source paper for our fallback eval data (Mohler ASAG) and
the pre-LLM baseline lineage for automated short-answer grading. Its task is
scoring, not misconception diagnosis.
*Verification:* Verified (metadata and abstract) via the ACL Anthology
listing found by search on 2026-10-18. Full text not read.

**Pre-LLM ASAG survey.** Burrows, Gurevych & Stein, "The Eras and Trends of
Automatic Short Answer Grading," *International Journal of Artificial
Intelligence in Education*, 25(1), 60–117, 2015 (online 2014).
doi:10.1007/s40593-014-0026-8.
Surveys the automatic short answer grading (ASAG) literature, defined as the
computational assessment of short natural-language responses to objective
questions; search snippets say over 80 papers fitting that definition had
appeared by then.
**Relevance:** the standard foundational survey for ASAG, which gives the
LLM-era work in this area a lineage.
*Verification:* Verified (metadata) via Crossref on 2026-10-18 (title,
authors, journal, volume, issue, pages). The abstract and full text were not
read; the scope description above comes from search snippets.

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
"A basic recursion concept inventory," *Computer Science Education*, 27(2),
120–147, 2017. doi:10.1080/08993408.2017.1414728. Open PDF:
https://people.cs.vt.edu/~shaffer/Papers/RecurTutorCIPublished.pdf
The misconception list came from instructor input, the literature and an
analysis of approximately 8,000 responses to recursion exam questions over
three semesters (section 4.2). It defines twelve tagged items in five
groups: backward flow (`BFneverExecute`, `BFexecuteBefore`); infinite
recursion (`InfiniteExecution`); recursive call (`RCwrite`,
`RCnoReturnRequired`, `RCreturnIsRequired`); base case
(`BCbeforeRecursiveCase`, `BCactionReturnConstant`,
`BCcheckAganistConstant` [sic], `BCwrite`, `BCevaluation`); and updating
variables (`GlobalVariable`). Nine are labelled misconceptions and three
(`RCwrite`, `BCwrite`, `BCevaluation`) are labelled difficulties. The paper
reports per-item prevalence for each administration (for example `BCwrite`
42% and `BFneverExecute` about 28% in one administration).
**Relevance:** the published source for the recursion taxonomy items and
their tags. Nine of the twelve items require seeing the student reason about
code (tracing or writing), so only a few can be evidenced by recall answers
like Mohler's; see docs/REVIEW_2026-10-18.md, section 3.2.
*Verification:* Verified (full text). The open PDF was fetched and its text
extracted on 2026-10-18; the twelve tags, the five groups, the
misconception/difficulty labels, the ~8,000-response figure and the two
prevalence figures above were read from it. Use these tags, not invented
codes such as "MR1".

**Taxonomy source: data structures & algorithms (systematic review).**
Tilanterä & Korhonen, "Data structures and algorithms misconceptions in
concept inventories: a systematic literature review," *Computer Science
Education*, 2026 (online 8 March 2026), pp. 1–31.
doi:10.1080/08993408.2026.2633989.
This is the "92-item DSA misconception systematic review" that the research
plan cites and that the 2026-10-15 search could not find. Per the search
snippets quoted in docs/REVIEW_2026-10-18.md (section 3.1), it reviews seven
DSA concept inventories across nine reports and extracts 92 misconceptions
or difficulties, mapped onto the CS Curricula 2023 knowledge areas.
Tilanterä's earlier Aalto doctoral dissertation describes a 70-item
catalogue covering DSA subtopics and recursion, so the two counts refer to
different versions.
**Relevance:** the external, peer-reviewed catalogue the research plan relies
on for both recursion and basic algorithm analysis items.
*Verification:* Verified (metadata) via Crossref on 2026-10-18 (title,
authors, journal, year, pages). The publisher page returned 403 on fetch, so
the abstract was **not** read: the 92-item count and the seven-inventory /
nine-report figures rest on search snippets, and the C1/C2 category codes
remain unverified. TODO: obtain the PDF and the supplementary catalogue
through the SJSU library and confirm the counts and codes.
Related works found by search (not read): Danielsiek, Paul & Vahrenhold (2012,
doi:10.1145/2157136.2157148), a DSA concept-inventory effort, and an ICER 2023
systematic review of computing concept inventories.

**Taxonomy source: algorithm analysis (Big-O).** Farghally, Koh, Ernst &
Shaffer, "Towards a Concept Inventory for Algorithm Analysis Topics,"
*Proceedings of the 2017 ACM SIGCSE Technical Symposium on Computer Science
Education (SIGCSE '17)*, Seattle, pp. 207–212. doi:10.1145/3017680.3017756.
A concept inventory for introductory algorithm analysis from the same
Virginia Tech group as the recursion inventory. A Virginia Tech thesis record
(hdl:10919/73539) describes a pilot Algorithm Analysis Concept Inventory
built by a Delphi process with DSA instructors; whether it is the same
instrument is not confirmed.
**Relevance:** the candidate published source for the Big-O taxonomy items.
The Mohler low scorers suggest at least four candidate items (BST search
confused with linear scan; search confused with sort; "best case" confused
with smallest input; best and worst case swapped); confirm the wording
against this paper before use.
*Verification:* Verified (metadata) via Crossref on 2026-10-18. The item list
is behind the ACM paywall and has not been read. TODO: obtain the full text
through the SJSU library.

**"Can LLMs Identify Gaps and Misconceptions in Students' Code
Explanations?"** (Oli, Banjade, Olney & Rus; arXiv:2501.10365, submitted
December 2024)
The closest prior work to ours in CS. Free-text student explanations of code
examples (topics include loops, arrays, recursion, binary search and
sorting) are checked for gaps and misconceptions with GPT-4, Llama-3-8B and
Mistral-7B under zero-shot and few-shot prompting, supervised fine-tuning
(SFT) and ORPO preference alignment. GPT-4 is best with simple prompting;
fine-tuned models find gaps better than prompting; ORPO beats SFT. Two
details matter for us: the "student" data is simulated (2,888 explanations
made by perturbing expert explanations, deleting sentences from them, or
writing explanations for code with injected errors), and in the qualitative
analysis the models fabricated problems in 27% of correct explanations and
34% of typo-only ones.
**Relevance:** the same task framing (misconceptions in free-text CS
explanations) and a precedent for a human-verified synthetic supplement. The
fabrication rates are exactly the `none`-class precision risk in our eval,
and the reason to add a citation-validity check.
*Verification:* Verified (metadata and abstract) from the arXiv abstract page
on 2026-10-18. The dataset size, topic list and the 27% / 34% figures were
additionally read from the arXiv HTML full text on the same date; the rest
of the paper has not been read.

**"McMining: Automated Discovery of Misconceptions in Student Code"**
(Al-Hossami & Bunescu; arXiv:2510.08827, October 2025)
Defines McMining, the task of discovering a student's programming
misconceptions from samples of their code, builds an extensible benchmark of
misconceptions paired with code samples that exhibit them, and proposes two
LLM-based approaches. Per the abstract, Gemini, Claude and GPT family models
are effective at the task.
**Relevance:** misconception discovery from *code* rather than free-text
explanations, so adjacent rather than directly comparable; its benchmark is
a possible source of misconception definitions and of synthetic-example
methodology.
*Verification:* Verified (metadata and abstract) from the arXiv abstract page
on 2026-10-18. Full text not read; benchmark size and metrics unknown.

**"Can LLMs Simulate Novice Programmers' Misconceptions?"** (Yeltekin &
Bauer; arXiv:2610.10656, submitted 7 October 2026)
Evaluates 13 LLMs on generating, solving, simulating and diagnosing novice
misconceptions in code-tracing problems. Per the abstract: frontier models
do these reliably; models of 14B parameters or fewer struggle with dynamic
code execution; code-tuned models often fail at simulation because they
revert to correct execution; and diagnosis is much easier in a true/false
format than as open-ended generation.
**Relevance:** sets expectations for a small local base model, and supports
a closed-set (taxonomy-constrained) output format over free generation. Also
a precedent for LLM-simulated misconception-bearing answers.
*Verification:* Verified (metadata and abstract) from the arXiv abstract page
on 2026-10-18. Full text not read.

**Taxonomy source: programming misconceptions (ProgMiscon).** Chiodini,
Moreno Santos, Gallidabino, Tafliovich, Santos & Hauswirth, "A Curated
Inventory of Programming Language Misconceptions," *ITiCSE '21*; the live
inventory is at https://progmiscon.org/misconceptions/.
A curated, community-maintained inventory of programming-language
misconceptions, browsable by concept, language and notional machine. On
2026-10-18 the "any language" listing held 104 entries (our count), five of
them about recursion: `BaseCaseNotNeeded`, `RecursiveActivationsShareFrame`,
`RecursiveMethodImpliesRecursiveType`, `RecursiveMethodNeedsIfElse` and
`RecursiveFunctionNeedsIfElse`. None cover Big-O.
**Relevance:** a second published source for recursion items, complementary
to Hamouda et al.; no help on the complexity side.
*Verification:* Verified (site fetched 2026-10-18). The listing and the
site's About page (which gives the ITiCSE '21 citation and credits the
Lugano Computing Education Research Lab) were fetched. The ITiCSE '21 paper
itself was not separately searched or read; the entry count is our own
tally of the listing.

**Recursion mental models.** Götschi, Sanders & Galpin, "Mental models of
recursion," *Proceedings of the SIGCSE 2003 Technical Symposium on Computer
Science Education*, Reno, pp. 346–350.
A study of first-year students' mental models of recursion at the University
of the Witwatersrand over 2000–2002. Per the abstract, most students built
the viable "copies" model, but many built non-viable models: looping,
active, step, magic, return-value and various odd models. A follow-up by
Sanders, Galpin & Götschi, "Mental models of recursion revisited" (2006,
pp. 138–142), extends the study to the 2003–2005 cohorts.
**Relevance:** mental-model categories rather than item-level
misconceptions, and therefore the natural labels for conceptual (non-code)
answers like Mohler's, where Hamouda's code-tracing items cannot be
evidenced.
*Verification:* Verified (metadata and abstract) via the author's
publication page (homepages.inf.ed.ac.uk/vgalpin1/pubs/GSG03.html) fetched
on 2026-10-18. Full text not read. The 2006 follow-up was seen only in
search snippets; its venue is not confirmed here.

**Base-case difficulties.** Haberman & Averbuch, "The case of base cases:
why are they so difficult to recognize? Student difficulties with
recursion," *Proceedings of the 7th Annual Conference on Innovation and
Technology in Computer Science Education (ITiCSE '02)*, Aarhus, pp. 84–88.
doi:10.1145/544414.544441.
Per the abstract (search snippet): students struggle to identify base cases,
including handling redundant base cases, overlooking boundary and degenerate
values, and sometimes defining none at all, and they struggle to evaluate
recursive algorithms whose base cases are hard to perceive.
**Relevance:** base-case difficulties at a finer grain than Hamouda's
`BCwrite`/`BCevaluation`, and the recursion source most likely to match
Mohler's recall questions (E03.Q06 on infinite recursion, E05.Q04 on the
merge sort base case).
*Verification:* Verified (metadata) via Crossref on 2026-10-18; the abstract
is summarized from search snippets only. Full text behind the ACM paywall
and not read.

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

**"Exploring the Potential of Large Language Models to Generate Formative
Programming Feedback"** (Kiesler, Lohr & Keuning; IEEE Frontiers in
Education Conference (FIE) 2023; arXiv:2309.00029)
A work-in-progress study of how ChatGPT responds when CS1 students ask for
help: the authors fed it student programs from a CS1 dataset with prompts
asking for feedback and a correct solution, then categorized the feedback
types in the responses. Per the abstract, ChatGPT does reasonably well for
some introductory tasks and common student errors, but its feedback can
contain information that misleads novices, so educators should guide its
use.
**Relevance:** LLM formative feedback on CS work, evaluated for correctness
and feedback type, separate from grading; the "misleading to novices"
failure mode is the same risk as a wrong misconception label in our output.
*Verification:* Verified (metadata and abstract) from the arXiv abstract page
(comments line: "Accepted to FIE 2023") and a search on 2026-10-18. Full
text not read.

**"Can we trust LLMs as a tutor for our students? Evaluating the Quality of
LLM-generated Feedback in Statistics Exams"** (Herklotz, Ippisch & Haensch;
arXiv:2511.04213, November 2025, preprint)
An exploratory study in an introductory statistics course at the University
of Munich: during a mock exam, GPT-4 generated individualized feedback from
instructor-supplied correct solutions. The authors reviewed all 2,389
feedback instances for errors and classified their focus with a combined
feedback framework. Per the abstract, about 7% of the feedback contained
errors, from minor technical inaccuracies to conceptually misleading
explanations; most feedback explained why an answer was right or wrong, and
little offered deeper conceptual insight, learning strategies or
self-regulation advice.
**Relevance:** a systematic error-rate audit of LLM feedback at scale, and a
feedback-level framework we could reuse when rating our own explanations.
Not CS, and the feedback is tied to a reference solution rather than a
misconception taxonomy.
*Verification:* Verified (metadata and abstract) from the arXiv abstract page
on 2026-10-18. Preprint, not peer reviewed as of that date. Full text not
read.

## Area 4: RAG for tutoring

**"Retrieval-augmented Generation to Improve Math Question-Answering:
Trade-offs Between Groundedness and Human Preference"** (Levonian, Li, Zhu,
Gade, Henkel, Postle & Xing; arXiv:2310.03184; NeurIPS 2023 Workshop on
Generative AI for Education; also listed as an EDM 2024 short paper)
RAG for middle-school math question answering: passages retrieved from a
vetted open-source textbook (OpenStax Prealgebra, per search snippets) are
given to the LLM when it answers real student questions. A multi-condition
survey on algebra and geometry questions found that people preferred the
RAG answers, but preference fell when answers hewed too closely to the
textbook text; the authors frame this as a trade-off between groundedness
and preference. Code: github.com/levon003/llm-math-education.
**Relevance:** RAG grounded in course material for tutoring, with an explicit
groundedness-versus-usefulness evaluation; the closest published treatment
of "does the evidence actually support the output," which our
grounding-support rating needs.
*Verification:* Verified (metadata and abstract) from the arXiv abstract page
(comments line names the NeurIPS'23 GAIED workshop) and a search on
2026-10-18, where the EDM 2024 proceedings listing appeared. The textbook
name comes from a search snippet, and how groundedness was scored was not
visible in the abstract. Full text not read.

**"From Slides to Chatbots: Enhancing Large Language Models with University
Course Materials"** (Dinh, Schumacher & Niehues; arXiv:2510.22272; accepted
to NSLP @ LREC 2026)
Asks whether lecture slides and transcripts can help LLMs answer questions
in university-level CS courses. Compares retrieval-augmented generation with
continual pre-training (CPT) on the course materials, and tests a multimodal
RAG variant that passes retrieved slides to the generator as images. Per
the abstract, RAG is more effective and efficient than CPT at the small
scale of course materials, and slides as images beat text-only retrieval.
**Relevance:** the "course-material RAG" of our condition 2, on CS course
content specifically, with a comparison against the main alternative
(training on the material).
*Verification:* Verified (metadata and abstract) from the arXiv abstract page
on 2026-10-18. Full text not read; the course, data and evaluation metrics
were not visible in the abstract.

Still wanted for this area: a tutoring RAG paper that reports retrieval
quality directly (precision or relevance of the retrieved chunks), which
neither abstract above states. The Vangelova & Gancheva scoring layer
(Area 1) uses RAG for scoring, not tutoring.

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

Revised (2026-10-18), now that the closest prior work is identified. Zhao,
Jiao & Xu (Area 1) show on the JorGPT data that LLM grading feedback rarely
names a misconception (5–7% of responses vs. 15–31% for teachers) even when
scores are accurate: diagnosis is the missing piece. But they measure only
whether feedback names *any* misconception, with no taxonomy, no retrieval
and no grounding check. Oli, Banjade, Olney & Rus (Area 2) are the nearest
work in CS: they detect gaps and misconceptions in free-text code
explanations with prompted and fine-tuned LLMs, but on simulated student
data, without a published misconception catalogue as the label set, without
retrieval of course material, and with a reported tendency to fabricate
problems in correct explanations (27%). The other diagnosis work in Area 2 is
in math (Eedi) or starts from student code rather than prose. None of it
isolates whether **iterative, critic-triggered retrieval** adds anything over
a single-pass prompt that already contains the taxonomy.

Our gap, stated relative to those two: real (not simulated) student answers
on CS concepts (recursion, Big-O); labels drawn from published CS
misconception catalogues (Hamouda et al.; Tilanterä & Korhonen; Farghally et
al.; ProgMiscon) rather than free-form gap descriptions; and a controlled
test of one mechanism, critic-triggered re-retrieval, against
compute-matched single-pass baselines, with a grounding-support check on the
cited evidence. The Area 3 and Area 4 entries supply the feedback-quality and
course-material-RAG background but do not attempt misconception diagnosis.
Caveat: the eval data (Mohler ASAG) is small and mostly recall questions, so
the honest version of this gap may narrow to the Big-O side and to the few
recursion items that recall answers can evidence (docs/REVIEW_2026-10-18.md,
sections 1 and 4).
