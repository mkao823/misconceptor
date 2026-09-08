# misconceptor: An Agentic Diagnostic System for Open-Ended Exam Responses

**Team Members:** Michael Kao

**Course:** CMPE 258 — Deep Learning, Fall 2026 (Dr. Kaikai Liu)

**Selected Track:** Option 2 — LLMs + AI Agent System (Evaluation-First)

## Abstract

Automated grading tools tell an instructor *whether* a student's open-ended
answer was correct; they rarely tell the instructor *why* it was wrong.
Misconceptor is an agentic diagnostic system that reads open-ended exam
responses and identifies the specific conceptual misconception underlying an
incorrect (or superficially correct but poorly reasoned) answer, grounds that
diagnosis in the instructor's own course material via retrieval-augmented
generation, and aggregates per-student and per-class misconception patterns
into an actionable dashboard for the instructor. Unlike prior work that
optimizes for scoring accuracy, our system is evaluated on *diagnostic
accuracy* against human-labeled misconception categories, compares at least
three LLMs (including a locally-hosted open-weight model) on this task, and
tracks how a given student's misconception profile evolves across multiple
assessments over a semester. The target users are course instructors —
starting with STEM courses where reasoning errors are well-characterized —
who want formative, actionable insight into what their class collectively
misunderstands, rather than just a spreadsheet of scores.

## Repository Structure (planned)

```
/docs
  LITERATURE_SURVEY.md
  PROJECT_PROPOSAL.md
  AI_NOVELTY_AUDIT.md
/data
  (JorGPT dataset subset + misconception annotations)
/src
  planner/
  executor/
  critic/
  rag/
  dashboard/
/eval
  test_cases.jsonl   # 50+ labeled diagnostic cases
  results/
```