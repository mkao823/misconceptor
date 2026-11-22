# Critic specification: condition 4, its control 4b, and the positive control

Version 1, 2026-11-22, written before the code (review G5, section 6.5).
`src/pipeline/`, `src/baselines/self_consistency.py` and
`scripts/run_positive_control.py` implement it; a difference is a bug in the
code. Arbitrary choices are listed in section 8.

## 1. First pass

Condition 4 starts with condition 3, unchanged: the same retrieval (BM25,
query = question + student answer, k = 4, the row's own instructor-answer chunk
withheld), the same template (`taxonomy_fewshot_v1`), the same taxonomy text
and few-shot examples, temperature 0, the same seed, the same repair
round-trip, through the same functions. Its messages are byte-identical to
condition 3's, so the two share cache entries. The validated record it yields
is the **draft**. If the first pass fails validation the row goes to
`errors.jsonl` as in condition 3 and the Critic is not called.

## 2. The Critic

A separate call to the same base model, temperature 0, template `critic_v1`.

**Sees:** the question, the instructor's reference answer, the student answer,
every chunk shown so far (formatted as in the diagnosis prompt), the draft
record (label, evidence, confidence), and the catalogue entry or special-label
definition of the draft label, so that the label id can be read.
**Does not see:** the rest of the taxonomy, the few-shot examples, the
diagnoser's reasoning, its own earlier verdicts, or any grade.

**Returns** one JSON object: `{"sufficient": bool, "missing": string,
"query": string}`. `missing` names the specific information needed; `query` is
a search query for it. When `sufficient` is false both must be non-empty.
Invalid output gets the same repair round-trip as a diagnosis.

The Critic never changes the label. It can only cause more material to be
shown to the diagnoser.

## 3. What "insufficient" means

The shown material (reference answer plus chunks) is **insufficient** only if

1. it does not let a grader decide between the draft label and one specific
   alternative, which the Critic must name together with the fact that would
   decide; or
2. the draft, or a claim it cites, rests on course-specific information (a
   convention, a definition, which answers the course accepts as equivalent,
   which case a formula belongs to) that is not in the shown material.

It is **not** insufficient when

- the student answer itself is vague, short, garbled or blank. That is the
  `insufficient_evidence` label; no course material changes what the student
  wrote, so it must not trigger retrieval;
- the Critic would merely have chosen another label from the same material;
- the missing item is general computer-science knowledge, or is already shown;
- more material would be welcome but could not change the label.

## 4. The loop

A **refinement round** is: Critic verdict "insufficient", re-query,
re-diagnosis. At most `max_rounds` = 2 per row.

- **Re-query.** The Critic's `query` string, alone, goes to the same retriever
  with the same k. Excluded: every chunk id already shown for the row, the
  row's own instructor-answer chunk, and chunks excluded for the whole run.
  Fewer than k new chunks is accepted.
- **Re-diagnosis.** Condition 3's template and code again, at temperature 0,
  with the retrieved block holding all accumulated chunks in the order shown
  (first pass, then round 1, then round 2). Nothing else is added: not the old
  draft, not the Critic's verdict. The new record replaces the draft entirely.

**Stop rules.** The loop ends at the first of these; the draft at that moment
is the row's output.

| `stop_reason` | When |
|---|---|
| `round_limit` | `max_rounds` refinement rounds are done. The Critic is not called on the last draft (with `max_rounds` 0 it is never called and condition 4 equals condition 3). |
| `sufficient` | The Critic returns `sufficient: true`. |
| `no_new_chunks` | The re-query returns no chunk that was not already shown. No re-diagnosis is made; its prompt would be unchanged. |
| `critic_error` | The Critic's output is still invalid after repair. Treated as a stop, not as "insufficient". |
| `rediagnosis_error` | A re-diagnosis is still invalid after repair. The previous valid draft is kept. |

Most calls per row: 1 + `max_rounds` diagnoses and `max_rounds` Critic calls
(5 at the default), each plus at most one repair.

## 5. What is logged

Each prediction is the usual validated record plus `trace`: `max_rounds`, `k`,
`stop_reason`, `n_refinements` (re-diagnoses that gave a valid draft),
`n_calls`, `tokens`, `first_pass_label`, and one entry per round (round 0 is
the first pass) with the query and its source (row or Critic), the new chunk
ids with scores, the cumulative chunk ids shown, the draft label and
confidence, the Critic's verdict on that draft (null if it was not called), and
the round's tokens and calls. A re-query that returns nothing is logged as a
round with no new chunks and no diagnosis. `trace.calls` lists every model call
(round, role, attempt, prompt and completion tokens, cache hit).

## 6. Tokens

A row's tokens are prompt plus completion tokens, as reported by the server,
summed over **every** model call made for it: first pass, Critic calls,
re-diagnoses, and every repair round-trip of any of them. Completion tokens
include hidden reasoning. A call served from the disk cache counts at its
recorded usage, so a re-run reports what a cold run costs. Retrieval costs no
model tokens. Rows in `errors.jsonl` count. The manifest gives total tokens and
number of calls for every row.

## 7. Condition 4b and the positive control

**4b (compute-matched self-consistency).** Condition 3's exact prompt, sampled
N times at temperature 0.7 with seeds `seed`, `seed + 1`, ...; each sample is
validated and repaired as in condition 3. An invalid sample is dropped from the
vote; its tokens count. The label is the plurality vote; a tie goes to the
label with the higher mean confidence, then to the label whose first sample
came earliest. Evidence and confidence are those of the highest-confidence
sample that voted for the winner (the earliest on a tie).

N comes from a named condition 4 run: **N = max(3, ceil(T4 / T3))**. T4 is that
run's mean total tokens per row; T3 is the mean tokens of one condition 3 call
on the same rows (the first attempt of that run's first pass). The 4b manifest
records N, T4, T3, the planned budget ratio N·T3 / T4 and the measured one (4b's
mean tokens per row / T4). Because of the rounding up, and above all the floor
of 3, **4b can receive more tokens than condition 4**: when the Critic rarely
triggers, T4 / T3 is below 2 and the floor applies. That favours the baseline.
It is the safe direction for the claim, and it must be stated next to any 4
versus 4b comparison.

**Positive control.** `configs/controls/critic_positive_control_v1.yaml` holds
authored cases, none from the eval sheet or Mohler: per in-scope question, at
least one *dependent* answer whose judgement turns on a course-specific fact
held in named chunks, paired with a *non-dependent* answer on the same
question. A dependent case is run twice (first pass, then one Critic call):
with its supporting chunks withheld from the first retrieval only, and with
them forced into the first-pass k. A non-dependent case is run once with
ordinary retrieval. "Triggered" means `sufficient: false`. Reported: the
trigger rate in each of the three arms and, for triggered withheld arms,
whether the re-query's k chunks contain a withheld chunk. This tests the
Critic's judgement on constructed cases. It says nothing about the claim.

## 8. Arbitrary choices that could be varied

- `max_rounds` = 2; re-query k = first-pass k (4); chunks accumulate and are
  never dropped or re-ranked; the re-query is the Critic's string alone.
- The Critic sees one catalogue entry, not the taxonomy; keeps no memory across
  rounds; is not called after the last round; cannot relabel; and a broken
  Critic output stops the loop instead of counting as "insufficient".
- The re-diagnosis sees neither the old draft nor the Critic's `missing`.
- Critic temperature 0 and the diagnoser's output-token limit.
- 4b: temperature 0.7, consecutive seeds, the floor of 3, rounding N up, the
  tie-break order, and taking T3 from the condition 4 run's own first pass.
- Positive control: 16 cases; forcing replaces the lowest-ranked chunks; one
  Critic call per arm.
