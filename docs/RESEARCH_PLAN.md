# Misconceptor — Research Plan (Internal, Post-Proposal)

*Not for resubmission. Written to internalize the professor's feedback and the
class-wide announcement before starting implementation.*

## What the announcement is actually asking for

Listing RAG + Planner + Executor + Critic + Memory + 3 LLMs is not a
contribution. The contribution has to be a **specific mechanism** with a
**precise claim**, tested against the **strongest baseline that could make it
unnecessary**, with **controls** that rule out confounds, and an honest
account of **what a null result would mean**. Everything below is organized
around that, not around "what components does the system have."

## Scope decision

**Concepts:** Recursion and Big-O / algorithmic complexity analysis.
Rationale: both have published, validated misconception catalogs (recursion
via a dedicated CS2 concept inventory; both via the 92-item DSA misconception
systematic review, which explicitly flags recursion and "basic algorithm
analysis" — categories C1/C2 — as well-represented). This gives us an
external, peer-reviewed taxonomy instead of one we invent ourselves.

Example taxonomy entries we can draw on directly: `MR1 = "Recursive call
requires a return"` (recursion), plus the C1/C2 complexity-analysis items
from the same catalog. Exact item list to be pulled from the source paper
before annotation begins.

> **TODO: verify (added 2026-10-15).** The "92-item" count, the C1/C2 category
> codes, and the `MR1` item ID/wording above are not yet confirmed against the
> source papers. A web search did not locate the DSA systematic review. The
> recursion inventory was found: Hamouda et al., *Computer Science Education*
> 2017, doi:10.1080/08993408.2017.1414728. Do not use these codes in the
> taxonomy file until they are checked. See docs/LITERATURE_SURVEY.md, Area 2.

## The actual mechanism claim (not "we built an agentic system")

**Claim to test:** *Critic-driven, insufficiency-triggered re-retrieval
improves specific-misconception classification accuracy beyond what a
single-pass retrieval, even when that single pass already includes the full
taxonomy as grounding context.*

This isolates the thing we're actually proposing — iterative refinement
driven by a grounding-sufficiency judgment — from "having RAG at all" or
"having a taxonomy at all," both of which a simpler system could also have.

## Strongest baseline we were avoiding

The honest risk: if we simply give the model the full 92-item taxonomy
(filtered to recursion/Big-O items) as few-shot context and ask for one-shot
classification, that alone might already capture most of the achievable
accuracy — because the taxonomy is small, well-defined, and closed-set. The
agentic loop may be solving a problem that's already solved by condition 3
below. We should expect this to be a real possibility, not design the
experiment to avoid finding it.

A second, cheaper baseline we were also avoiding: simple keyword/pattern
matching. Several taxonomy items (e.g., "recursive call requires a return")
have recognizable linguistic signatures. A regex/heuristic classifier is a
near-zero-cost floor; if it performs comparably to the LLM pipeline on some
items, that's worth knowing before claiming an LLM-based system is needed at
all for those cases.

## Ablation / baseline ladder (same eval set, same model, per condition)

0. **Heuristic/keyword baseline** — pattern match against known trigger
   phrases per taxonomy item. Cost: ~free. Purpose: sanity floor.
1. **Direct LLM diagnosis** — zero-shot, no retrieval, no taxonomy.
2. **+ course-material RAG** — static top-k retrieval of lecture/textbook
   content relevant to the question.
3. **+ taxonomy/few-shot grounding** — full recursion/Big-O taxonomy subset
   plus a few labeled examples injected into the prompt, still single-pass.
4. **+ Critic-based iterative retrieval** — the full agentic loop.

**Confound control to add:** condition 4 uses more LLM calls / more tokens
than condition 3. To separate "iterative *refinement*" from "just more
compute," add **4b: self-consistency baseline** — condition 3's prompt,
sampled N times with majority vote, using a similar total token budget to
condition 4. If 4b matches condition 4, the win isn't from the Critic
mechanism — it's from spending more compute, and that's the honest
conclusion to report.

## Positive control for the Critic specifically

End-to-end accuracy is noisy on a ~50-case set and doesn't cleanly tell us
whether the Critic mechanism itself works. Direct test: construct a small
set of cases where we deliberately withhold the correct supporting chunk
from the *first* retrieval pass (known ground truth: insufficient evidence).
Check whether the Critic reliably (a) triggers a refine step on exactly
these cases and (b) does *not* trigger one when the first pass was already
sufficient. This isolates the Critic's core judgment from the rest of the
pipeline's noise.

## Construct validity check (are we measuring what we claim?)

Risk: the model could be pattern-matching surface keywords from the
taxonomy descriptions rather than actually reasoning about the student's
answer (shortcut learning) — this would inflate accuracy without reflecting
real diagnostic capability. Control: take a handful of known-misconception
responses and paraphrase them to remove taxonomy-adjacent trigger words
while preserving the same underlying conceptual error. If accuracy collapses
on the paraphrased set, the system was keyword-matching, not diagnosing —
an important thing to know before claiming diagnostic capability.

## Early feasibility pilot (do this before building anything else)

1. JorGPT is already downloaded to `data/raw/` (gitignored). Filter for recursion/Big-O
   questions. Record how many of the 50 questions and how many of the 3,041
   responses actually fall in scope.
2. If coverage is thin (open risk — not yet verified), fall back to a small
   self-collected set of recursion/Big-O short-answer responses.
3. Hand-label ~10–15 real responses against the taxonomy subset. Check two
   things before scaling to 50+: (a) can a human actually apply these
   labels with reasonable agreement, i.e., is the taxonomy usable on real
   free-text answers, not just concept-inventory distractors; (b) does
   condition 1 (direct LLM) get anywhere close, which tells us whether the
   full ladder is worth building out.
4. Only after this pilot succeeds, scale annotation to the full 50+ case
   eval set and build out conditions 0–4b.

## Metrics (added after feedback)

- Macro-F1 per condition with 95% bootstrap CIs, plus paired-bootstrap
  differences (4 − 3, 4 − 4b). Also per-class F1 and the confusion matrix.
- Grounding support: on a sampled subset, a human rates each cited piece of
  evidence as supports / partially supports / unrelated. An LLM judge is
  optional, and only after its agreement with the human ratings is measured.
- Details: docs/PROJECT_PROPOSAL.md.

## What a null result would still tell us

If the agentic loop (condition 4) does not beat condition 3 or 4b: that is
a legitimate, reportable finding — for a narrow, well-characterized
misconception domain like recursion/Big-O, a single-pass taxonomy-grounded
classifier may be sufficient, and the added complexity/cost of an agentic
critic is not justified *for this scope*. That's a real contribution to
report, not a failed project — it tells future work where agentic
complexity is and isn't worth it.

## Self-check against the professor's eight questions

| Question | Answer for this project |
|---|---|
| Closest recent work? | DSA misconception concept-inventory literature (published taxonomy); LLM misconception-diagnosis papers (Correct Answer Trap, Generate-Retrieve-Rerank) — none combine a validated CS taxonomy with agentic grounding and an explicit ablation against simpler baselines. |
| What would make the contribution unnecessary? | If condition 3 (static taxonomy + few-shot) matches condition 4, the agentic loop adds nothing for this scope. |
| Strongest baseline being avoided? | Keyword/heuristic matching (condition 0) and self-consistency sampling (condition 4b) — both now added. |
| Confound in an expected win? | More compute/more calls in the agentic condition — controlled for via 4b. |
| Positive control? | Deliberately-withheld-evidence cases to test the Critic's sufficiency judgment directly. |
| Experiment before heavy compute? | The 10–15 case hand-labeling pilot, run before scaling to 50+ and before building conditions 0–4b in full. |
| If null, what do we learn? | That narrow, well-documented misconception domains may not need agentic complexity — a real, reportable finding. |
| Are we measuring the claimed capability? | Paraphrase/shortcut-learning check against taxonomy-keyword overfitting. |
