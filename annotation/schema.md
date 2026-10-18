# Annotation schema (v0.1, 2026-10-18)

How to label a student answer in `annotation/pilot_sheet.csv` against
`taxonomy/recursion_bigO.yaml`. The pilot's purpose (docs/REVIEW_2026-10-18.md,
section 5 step 3) is to find out whether the taxonomy can be applied to Mohler
answers at all, and how many wrong answers fall outside it. Label honestly;
a high `other_error` count is a finding, not a failure.

## 1. Files

| File | Role |
|---|---|
| `taxonomy/recursion_bigO.yaml` | The label definitions. Read every `description`, `observable_in` and `notes` before labelling. |
| `annotation/pilot_sheet.csv` | 63 rows: all 43 answers with `score_avg < 3.5` on the seven in-scope questions, plus the 20 highest-scoring answers (ties broken by length). Built by `scripts/build_pilot_sheet.py`. |
| `annotation/pilot_sheet_rater2.csv` | Same columns, filled by the second rater on the agreement subset (section 7). Not created yet. |
| `scripts/validate_taxonomy.py` | Checks the taxonomy loads and every id is unique. |

Text in the sheet is normalized from Mohler's tokenized `cleaned` split:
`-LRB-`/`-RRB-` became parentheses, `<STOP>` was dropped, whitespace collapsed.
Other tokenization artifacts remain ("n to the power of 2", "n minus 1",
"m sort", "plus"); read through them.

## 2. Label set

Closed set: every `id` under `items` in the taxonomy plus the three
`special_labels`. Nothing else is a valid label; if an answer needs a label
that does not exist, use `other_error` and describe the candidate item in
`annotator_notes`.

| Group | Ids | Can Mohler recall answers show it? |
|---|---|---|
| Hamouda 2017, backward flow | `BFneverExecute`, `BFexecuteBefore` | No (needs a code trace) |
| Hamouda 2017, infinite recursion | `InfiniteExecution` | Weakly, E03.Q06 only |
| Hamouda 2017, recursive call | `RCwrite`, `RCnoReturnRequired`, `RCreturnIsRequired` | `RCreturnIsRequired` if stated; others need code |
| Hamouda 2017, base case | `BCbeforeRecursiveCase`, `BCactionReturnConstant`, `BCcheckAganistConstant`, `BCwrite`, `BCevaluation` | If the student states the belief; `BCwrite` narrowly on E05.Q04 |
| Hamouda 2017, updating variables | `GlobalVariable` | Only if stated |
| ProgMiscon | `BaseCaseNotNeeded`, `RecursiveActivationsShareFrame`, `RecursiveMethodImpliesRecursiveType`, `RecursiveMethodNeedsIfElse`, `RecursiveFunctionNeedsIfElse` | If stated |
| Götschi et al. 2003 mental models | `MMcopies` (viable), `MMlooping`, `MMactive`, `MMstep`, `MMmagic`, `MMreturnValue`, `MModd` | Yes, when the answer describes how recursion runs |
| Big-O (provisional) | `BOsearchLinearScan`, `BOsearchVsSort`, `BObestCaseSmallestInput`, `BObestWorstSwapped` | Yes; E05.Q03, E10.Q07, E12.Q10 |
| Special | `none`, `other_error`, `insufficient_evidence` | Always available |

Definitions of the special labels (from the taxonomy file):

- `none`: correct or acceptable for the question as asked; no incorrect claim. May be incomplete.
- `other_error`: wrong, off-topic, or answers a different question, but matches no catalogued item.
- `insufficient_evidence`: too short, vague, garbled or blank to judge.

## 3. Columns to fill

| Column | Rule |
|---|---|
| `primary_label` | Exactly one label from the set. Never empty once the row is done. |
| `secondary_label` | Optional. One further label when the answer clearly exhibits a second item, or a mental-model id that explains the primary item-level label. Never `none` or `insufficient_evidence`. Leave empty if in doubt. |
| `evidence_span` | Required whenever `primary_label` is a taxonomy id. Optional but encouraged for `other_error`. Empty for `none` and `insufficient_evidence`. |
| `annotator_notes` | Free text: why, what the error is for `other_error`, candidate new items, low confidence, anything a second rater should see after the fact. |

## 4. Core rules

1. **One primary label per answer.** If two taxonomy items fit, pick the one the
   student's words support most directly (section 6 gives precedence), put the
   other in `secondary_label`.
2. **Evidence span is a verbatim substring** of the `student_answer` cell: copy
   and paste, no paraphrase, no ellipsis, no added quotes. The shortest span that
   carries the claim. If two separate spans are needed, join them with ` || `.
   An automatic check will test `evidence_span in student_answer` for each part;
   a failing span invalidates the row.
3. **Label what the text says, not what it omits.** An answer that is correct but
   incomplete is `none` (add "incomplete" to notes). Do not infer a misconception
   from a missing element.
4. **The grade is not the label.** `score_avg` measures rubric match, not
   misconceptions. A 5.0 answer can carry a misconception in an aside; a 2.0
   answer can be `none` if it was penalized for incompleteness. Decide from the
   text, then look at the score only to catch misreadings.
5. **Difficulties need an attempt.** `RCwrite`, `BCwrite` and `BCevaluation` are
   observed inabilities to write or trace code. A recall answer cannot show them,
   with one exception: an answer to E05.Q04 that attempts to state merge sort's
   base case and gets it wrong may be `BCwrite`.
6. **Answered a different question** (gives a running time when asked for a base
   case, describes a procedure when asked for a count) is `other_error` unless the
   wrong answer itself matches a Big-O item on a *search or best-case* question.
7. **`insufficient_evidence` is for unjudgeable text**, not for short correct or
   short wrong answers. "n/2" is short and judgeable; "not answered" is not.
8. **`MMcopies` is never the primary label of a wrong answer.** Correct
   mechanism descriptions are `none`.
9. **Provisional Big-O items are used exactly like verified ones** during the
   pilot; the pilot is how they get confirmed or dropped. Note any answer that
   fits a Big-O item only loosely.
10. **Do not look at model outputs** (conditions 0 to 4) before labelling, and do
    not revise labels after seeing them. Pre-labelling with a model from another
    family (review section 6.9) is allowed only if it is done before this pass and
    recorded.

## 5. Decision rules for confusions seen in the data

These cover the recurring patterns in the 43 low scorers. They are rules, not
labels: apply them row by row and record exceptions in notes.

### E05.Q04, base case of merge sort (instructor: size 1 or 2)

| Answer pattern | Primary | Notes |
|---|---|---|
| "O(n log n)", "n log n", "n multiplied by log(n)", "best case is the same as worst case O(n log n)" | `other_error` | Running time given instead of a base case. Not `BOsearchVsSort` (no search, and n log n is merge sort's correct bound). Not `BCwrite` (no base case attempted). Note: "running time instead of base case". |
| Code paste of the recursive step with no base case | `other_error` | Do not infer `BaseCaseNotNeeded` from omission in a paste. Note: "pasted recursive step; base case not identified". |
| States a base case that amounts to size 1 or 2 in other words ("when a half has nothing left to sort") | `none` | Note "paraphrase of size 1" and low confidence if the wording is loose. |
| States a wrong base case ("when the array is sorted", "when n = 0 elements remain", a size other than 1 or 2) | `BCwrite` | Span = the stated base case. This is the only recall use of `BCwrite`. |

### E10.Q07 and E12.Q10, comparisons / steps to search a BST (instructor: height, or log n)

| Answer pattern | Primary | Notes |
|---|---|---|
| "n/2", "n divided by 2", "n-1", "(n-1)/2", "n", unqualified "O(n)" | `BOsearchLinearScan` | For unqualified "O(n)" note "could be degenerate-tree worst case" and mark low confidence. |
| "n log n", "O(nlog(n))", "nLog(n)" | `BOsearchVsSort` | |
| "log n", "height", "depth", "number of levels", "O(log n) balanced, O(n) degenerate" | `none` | Includes answers that give both best and worst case correctly. |
| Node-count formulas: "2^n where n is the levels", "(n^k)-1 where k is the height", "2n-1", "n(n-1)/2" | `BOsearchLinearScan` if the formula is the total node count expressed through height (the student equates cost with visiting all nodes); otherwise `other_error` | Note the formula. Candidate new item: "search cost given as a closed-form node count". |
| Fixed constant: "at most 3 comparisons", "3 steps, there are 3 cases", "2 way key comparison" | `other_error` | Candidate new item: "cost stated as a small constant independent of n" (possibly confusing the number of branches per step with the number of steps). |
| Describes the search procedure (compare, go left or right) without a count | `insufficient_evidence` | No cost claim to judge. If the description is itself wrong (visits root then whole right subtree then left subtree) use `other_error` and note "traversal confused with search". |

### E05.Q03, best case of insertion sort (instructor: N operations, already sorted input)

| Answer pattern | Primary | Notes |
|---|---|---|
| "1 operation", "best case 1", "1 where there is a list of two ints", "having only one item would be the easiest to sort" | `BObestCaseSmallestInput` | Even when the answer also says "already sorted": the count 1 shows the smallest-input reading. Note the extra correct part. |
| "best case n(n-1)/2", "best case O(n^2)", "worst case O(n) best case O(n^2)" | `BObestWorstSwapped` | If the same answer also states the correct best case elsewhere, keep `BObestWorstSwapped` and note "self-contradictory". |
| "Best case N, worst case N factorial" or any answer whose best-case claim is right but whose extra worst-case claim is wrong | `none` | The question asks for the best case. Put the wrong extra claim in notes; it is a wrong fact, not a catalogued item. |
| "best case N (sorted)" with or without the scenario | `none` | Missing scenario is incompleteness, not error. |

### E03.Q07, similarities between iteration and recursion

| Answer pattern | Primary | Notes |
|---|---|---|
| "anything you can do iteratively you can do recursively" or the converse | `none` | True claim about expressive power, not one of the rubric's similarities. Note "equivalence claim; incomplete". This is the clearest case where a low grade and `none` coexist. Do **not** label `MMlooping`: equating what the two can compute is not the belief that a recursive call *is* a loop jump. |
| "both repeat", "both have a stopping condition / base case", "both can run forever" | `none` | Calling the loop's termination test a "base case" is loose wording, not a misconception. |
| "recursion is used to process iterative actions", definitions of recursion with no similarity stated | `insufficient_evidence` | Nothing comparable to judge. |
| "not answered" | `insufficient_evidence` | |

### E03.Q06, causes of infinite recursion

| Answer pattern | Primary | Notes |
|---|---|---|
| "missing base case", "recursive step does not converge / reach the base case" | `none` | Correct recall; it is not evidence of `InfiniteExecution` (see taxonomy notes). |
| "badly designed algorithms", "using recursion for a non-recursive problem" | `other_error` | Vague or wrong cause. |
| Restates that infinite recursion means calling itself forever, gives no cause | `insufficient_evidence` | |
| Claims that having a base case is enough to stop, or that a base case "will be reached eventually" regardless of the step | `InfiniteExecution` | The one Hamouda item a recall answer here can show. |

### E11.Q09, divide and conquer

| Answer pattern | Primary | Notes |
|---|---|---|
| Split into files, classes, functions, "easily managed functions" (modular decomposition) | `other_error` | Candidate new item: "divide-and-conquer confused with modular decomposition". |
| Describes merge sort specifically (split in half, sort halves, combine) instead of the paradigm | `none` | Note "instance instead of paradigm". If the combine step is wrong ("sort them back together") still `none` with a note; it is imprecision. |
| Divide, solve subproblems (recursively), combine | `none` | |

## 6. Precedence between overlapping taxonomy ids

- `GlobalVariable` over `RecursiveActivationsShareFrame` when a variable "initialized once" or "keeps track across calls" is described; the ProgMiscon id when the student talks about frames, stack, or memory. Use the other as secondary.
- `BCbeforeRecursiveCase` over `RecursiveMethodNeedsIfElse` when ordering ("first") or tracing is involved; `RecursiveMethodNeedsIfElse` when the claim is only that an if-else is required. `RecursiveFunctionNeedsIfElse` only for answers explicitly about Python functions; never both twins on one row.
- `InfiniteExecution` (base case present but unreachable, expected to terminate) versus `BaseCaseNotNeeded` (no base case thought necessary).
- Item-level labels (Hamouda, ProgMiscon, Big-O) are primary; a mental model (`MM*`) is secondary when it explains the item, and primary only when the answer describes a wrong mechanism of recursion that matches no item. `MModd` is a last resort behind `other_error`.
- Verified over provisional when both genuinely fit, with the provisional id as secondary.

## 7. Two-rater plan and agreement

- **Second rater**: a classmate or the course TA, briefed with this file and the taxonomy, not with the first rater's labels.
- **Subset**: 30 to 50 rows of the 63, chosen after the first pass: every row the first rater gave a taxonomy id (expected 15 to 25), topped up with a random sample of `none`, `other_error` and `insufficient_evidence` rows to reach the target, stratified so every in-scope question appears. Record the row ids and the random seed in `annotation/README.md`.
- **Sheet**: the second rater receives a copy of `pilot_sheet.csv` restricted to the subset with the four label columns blank, saved back as `annotation/pilot_sheet_rater2.csv`. Both raters see the same columns, including `score_avg`.
- **Agreement**: Cohen's kappa (unweighted, `sklearn.metrics.cohen_kappa_score`) on `primary_label`, reported twice: over the full label set, and over the four-way collapse {taxonomy id, `none`, `other_error`, `insufficient_evidence`}, because sparse classes make the full-set kappa unstable at n = 30 to 50. Also report raw percent agreement and the pairwise confusion table. Secondary labels are not scored.
- **Evidence spans**: report the fraction of double-labelled taxonomy rows where the two spans overlap by at least one token.
- **Adjudication**: disagreements are discussed and resolved; the adjudicated labels become gold. Kappa is reported from the pre-adjudication labels. Any rule added during adjudication goes into section 5 with a version bump.
- **Interpretation**: kappa below 0.4 on the four-way collapse means the schema, not the raters, needs work before any model is evaluated.

## 8. What the pilot must record

1. Count of rows per primary label, and `other_error` as a share of the 43 low scorers. If more than half of the low scorers are `other_error`, the Mohler-only plan is dead and the supplement (review section 6.3) becomes mandatory.
2. The list of candidate new items collected in `annotator_notes` (section 5 names four), with counts.
3. Which taxonomy ids received zero labels. Those are reported as "not observable in this data" and excluded from per-class F1, not silently averaged in.
4. Rows labelled with a provisional Big-O id, so they can be re-checked once Farghally et al. 2017 is read.

## 9. Versioning

Bump the version in the heading and note the change whenever a rule in section 4 to 6 changes. Labels produced under an older version are re-checked against the new rule before being used as gold.
