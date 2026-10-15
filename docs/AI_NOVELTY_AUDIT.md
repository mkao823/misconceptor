# AI Novelty & Feasibility Audit

*Prepared via iterative critique with Claude (Anthropic), September 2026.
Pasted per assignment requirement D.*

## Idea Evolution (for transparency)

The project went through three iterations before arriving at its current
form, each rejected or revised for a specific reason:

1. **"Agent harness for non-technical users."** Rejected as red ocean:
   current commercial products (e.g., Claude Cowork, Taskade Genesis) already
   explicitly target non-coders with a full agent harness (loop, tools,
   memory, guardrails), and 2026 industry coverage frames "which harness" as
   a converged, commoditized decision layer. A generic friendlier-interface
   pitch would not clear a graduate novelty bar and offers little to
   rigorously evaluate.
2. **"Personalized learning-style-based tutoring plans."** Rejected on
   scientific grounds, not just novelty grounds: the visual/auditory/
   kinesthetic "learning styles" framework has been repeatedly shown to lack
   evidence that matching instruction to a preferred style improves outcomes,
   and the American Psychological Association has warned the label can
   function as a proxy for lowered expectations of certain students. Building
   a diagnostic engine on a discredited premise would undermine both the
   academic rigor and the real-world utility of the system.
3. **"Hybrid local/cloud LLM agent routing" (home-lab infrastructure
   angle).** A legitimate technical exercise, but current in 2026: multiple
   vendor and engineering blogs already publish detailed three-tier
   local/cloud routing architectures (sensitivity → complexity → availability)
   as production-standard patterns. Implementing this alone would look like
   following an existing blueprint rather than a novel contribution, though
   the underlying infrastructure experience remains useful context for the
   team.

## Current Idea: Misconception Diagnosis from Open-Ended Exam Responses

### Novelty Assessment
This is **not virgin territory** — misconception detection with LLMs and
LLM-based knowledge tracing are active 2025–2026 research areas. Representing the idea as wholly unexplored would be inaccurate and is explicitly the kind of overclaiming this audit is meant to catch.

What appears to be a genuine, defensible gap: existing misconception-
detection work is evaluated as a standalone modeling task (single-turn
tutoring dialogue, or math-platform multiple-choice distractors), and
existing grounded-scoring work optimizes for score accuracy rather than
diagnostic labels. None of the surveyed papers combine (a) diagnosis grounded
in an instructor's own course material via agentic RAG, (b) an explicit
confidence-gated Critic that routes uncertain cases to the instructor rather
than silently reporting them, and (c) longitudinal tracking of a student's
misconception profile across multiple real assessments, packaged as an
instructor-facing tool rather than a benchmark paper. That combination —
not any single component — is the project's novelty claim, and it should be
stated that way in the final report rather than as a first-of-its-kind claim.

### Red Ocean Risks and Mitigations
| Risk | Mitigation |
|---|---|
| Overlaps with commodity "AI grading tools" | Explicitly scope out scoring; evaluate only on diagnostic-label accuracy, not grade agreement |
| Overlaps with student-facing AI tutors (crowded space) | Keep the user strictly the instructor; UI and eval design should reflect this, not a chat tutor |
| Risk of re-deriving basic learning-styles framing | Explicitly avoid; ground personalization/diagnosis language in knowledge-component/misconception taxonomies with citations, not sensory-style categories |
| Small eval set could overstate generality | 50+ case minimum is a floor, not a target; report per-question-type breakdowns rather than a single aggregate number to avoid hiding weak subcategories |

### Feasibility Assessment
- **Data:** feasible without new IRB/consent overhead — the JorGPT dataset
  provides real, ground-truth-adjacent open-ended CS exam responses
  immediately usable for annotation and evaluation.
- **Compute:** feasible given the team's existing access to a personal NVIDIA
  GPU workstation, a mini-PC, and NAS-hosted local model deployments,
  covering the "local tier" of the multi-model comparison without relying on
  university HPC availability (noted in lecture as not guaranteed).
- **Scope for one semester:** the core pipeline (Planner–Executor–Critic +
  Agentic RAG + 50-case eval across 3 models) is achievably scoped; the
  longitudinal multi-assessment tracking and any real-course pilot with a
  live instructor should be treated explicitly as stretch goals, not
  required deliverables, to protect the semester timeline.

### Recommendation
Proceed with this direction. Frame the contribution honestly as an
**integration and instructor-facing application of an active but unsolved
research problem**, not as inventing misconception detection from scratch,
and lead the final report's related-work section with the four
misconception-detection/knowledge-tracing papers identified above to
preempt reviewer concerns about novelty.
---

## Addendum (October 2026): after professor feedback

*The original audit above is preserved as written. This addendum records what
it missed and what changed. It is not a resubmission.*

### What the professor's feedback caught that this audit did not

1. **Label mismatch.** The Feasibility section called JorGPT
   "ground-truth-adjacent … immediately usable for annotation and evaluation."
   JorGPT provides 0–10 human scores, free-text feedback and multi-LLM
   evaluations, but **no misconception labels**. Diagnostic accuracy therefore
   cannot be measured against JorGPT as-is. We must define a taxonomy and build
   a human-annotated eval subset ourselves.
2. **Missing baselines.** The audit treated the Planner–Executor–Critic +
   agentic RAG pipeline as the core deliverable and never asked whether a
   simpler system would match it. No keyword baseline, no single-pass
   taxonomy baseline and no compute-matched control were planned.
3. **Coarse outputs.** The planned misconception / partial / none labels
   detect that a misconception exists without naming which one.
4. **Citation-presence grounding.** Nothing measured whether cited evidence
   actually supports the diagnosis.
5. **Novelty framed as a combination of components.** "(a) + (b) + (c)" is a
   combination of components, which the class-wide guidance explicitly says
   is not a contribution.
6. **Dangling reference.** The Recommendation cites "the four
   misconception-detection/knowledge-tracing papers identified above," but no
   papers are listed in this audit.

### What changed

| Area | Before | After |
|---|---|---|
| Scope | STEM courses generally | Recursion and Big-O / complexity analysis only |
| Labels | misconception / partial / none | Specific taxonomy ID from published CS misconception literature, plus `none` and `insufficient_evidence` |
| Ground truth | Assumed from JorGPT | Small human-annotated subset with a second rater (Cohen's kappa). Coverage to be checked in a feasibility pilot first |
| Contribution | Integration of RAG + Critic + longitudinal tracking | One mechanism claim: critic-driven, insufficiency-triggered re-retrieval beats single-pass taxonomy-grounded classification |
| Baselines | None | Ladder 0–4b: keyword, direct LLM, +RAG, +taxonomy/few-shot, +Critic loop, token-matched self-consistency |
| Controls | None | Positive control (withheld-evidence cases); paraphrase check for keyword shortcutting |
| Metrics | Accuracy on 50+ cases | Macro-F1 with bootstrap CIs per condition; human-rated grounding support (supports / partially / unrelated) |
| Null result | Not considered | Explicitly reportable: the agentic loop may not be needed for a narrow, well-catalogued domain |
| Dashboard, longitudinal tracking, 3+ LLM comparison | Core / near-core | Stretch goals |

Details: [PROJECT_PROPOSAL.md](PROJECT_PROPOSAL.md) (Changes after feedback),
[RESEARCH_PLAN.md](RESEARCH_PLAN.md).
