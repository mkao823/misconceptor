# Course-specific facts in the corpus, per in-scope question

For each of the seven in-scope questions this file lists the facts in the retrieval corpus
that are **course-specific**: a competent grader who did not have them could reasonably
judge some answer to that question differently. It exists for review gap G7
(docs/REVIEW_2026-10-18.md): conditions 2, 3 and 4 can only differ from condition 1 on
items where retrieved content changes the right label, so those items, and the chunks that
carry the deciding fact, have to be known in advance.

Scope: this file is about questions and corpus facts only. It does not assess, label or
quote any student answer, and nothing in it was derived from model output. Where it says
"an answer that ..." it describes a kind of answer the question invites, not a row of the
sheet. This file has no front matter, so it is never indexed or retrieved.

## How to read the tables

**Origin** says where a fact comes from:

- `Mohler` — stated in the Mohler instructor answer for that question (quoted exactly in the notes).
- `Mohler (other question)` — stated in the instructor answer to a different Mohler question.
- `authored` — an elaboration written for this corpus (2026-11-22). It is consistent with the
  instructor answers but is not in the dataset. Treat these as the project's own reading of
  the course, and review them: see "Authored statements to review" at the end.

**In the prompt anyway?** matters for the experiment. Every LLM condition, including
condition 1, shows the instructor's reference answer for the row's own question. A fact
that is in that reference answer cannot separate condition 2 from condition 1. Only facts
marked **no** reach the model through retrieval alone; those are the ones that make an
item retrieval-dependent, and their chunks are the candidates to withhold in the
positive control (`Retriever.retrieve(..., exclude=[...])`, or `--exclude-chunk`).

Chunk ids refer to data/corpus/chunks.jsonl. The row's own instructor-answer chunk
(`ia.<question id>`) is withheld from retrieval by default because its content is the
reference answer already in the prompt.

## E03.Q06
When defining a recursive function, what are possible causes for infinite recursion?

| # | Course-specific fact | Chunks | Origin | In the prompt anyway? | Why a grader without it could judge differently |
|---|---|---|---|---|---|
| 1 | The course names two causes: the recursion step is defined incorrectly, or the base case is not included. | `rec.infinite-recursion` | Mohler | yes | Other courses phrase the causes differently (no termination condition, unbounded recursion); the wording decides what counts as naming a cause. |
| 2 | "Defined incorrectly" means the calls do not converge on the base case: the argument is not reduced, moves the wrong way, or jumps past the base case. | `rec.infinite-recursion`, `rec.convergence` | authored | no | An answer that describes non-convergence in its own words has to be recognised as the first cause; without this reading it can look like a third, unlisted cause or like a vague answer. |
| 3 | A base case that exists but cannot be reached is as good as no base case; having a base case is not enough. | `rec.convergence` | authored | no | Separates the belief that a base case guarantees termination (taxonomy item `InfiniteExecution`) from correct recall of the two causes. |
| 4 | In C++ an infinite recursion ends in a stack overflow rather than running forever. | `rec.infinite-recursion`, `rec.call-stack` | authored | no | An answer about running out of stack memory describes a consequence, not a cause; a grader may or may not count it as addressing the question. |

Retrieval dependence: low to medium. The two causes are in the reference answer. Fact 2 is
the one retrieval adds. Candidate chunk to withhold: `rec.convergence` (with
`rec.infinite-recursion`, which repeats part of it).

## E03.Q07
What are the similarities between iteration and recursion?

| # | Course-specific fact | Chunks | Origin | In the prompt anyway? | Why a grader without it could judge differently |
|---|---|---|---|---|---|
| 1 | Three similarities are expected: both involve repetition, both have termination tests, both can occur infinitely. | `rec.iteration-similarities` | Mohler | yes | Other sources list different similarities (both use control statements, both approach termination gradually). |
| 2 | The termination test of a loop is the loop-continuation condition failing; that of a recursion is a base case being recognised. | `rec.iteration-similarities` | authored | no | An answer that speaks of a "stopping condition" or uses the word for one mechanism when describing the other is naming the second similarity; a strict grader could read loose wording as an error. |
| 3 | Approaching termination step by step is treated as part of the termination-test similarity, not as a separate one. | `rec.iteration-similarities` | authored | no | Decides whether such an answer adds a similarity or restates one. |
| 4 | The two are equally powerful: whatever can be solved recursively can be solved iteratively, and the reverse. This is true in the course but it is not one of the three expected similarities. | `rec.iteration-similarities`, `rec.definition`, `ia.E11.Q06` | Mohler (other question: E11.Q06) and authored | no | Without it, an equivalence answer can be judged wrong, or judged a complete answer. With it, the claim is known to be true and known to be beside the expected list. |
| 5 | Differences (call overhead, one stack frame per call, loop state updated in place) are a separate topic. | `rec.iteration-differences` | authored | no | An answer that lists differences is answering another question. |

Retrieval dependence: medium, through fact 4. Candidate chunk to withhold:
`rec.iteration-similarities`.

## E05.Q03
What is the number of operations for insertion sort under a best-case scenario, and what is the best-case scenario?

| # | Course-specific fact | Chunks | Origin | In the prompt anyway? | Why a grader without it could judge differently |
|---|---|---|---|---|---|
| 1 | The count is stated as N operations, N being the length of the array, and the scenario is an array that is already sorted. | `ana.insertion-sort`, `ana.best-case-arrangement` | Mohler | yes | Sets both the expected count and the expected scenario. |
| 2 | Strictly the best case is N - 1 comparisons; the course states it as N, and both are O(n). | `ana.insertion-sort` | authored | no | A grader who counts exactly could mark N wrong, and one who goes by the reference alone could mark N - 1 wrong. |
| 3 | "Operations" means the basic operations we count: comparisons, sometimes also moves. | `ana.counting-operations`, `ana.insertion-sort` | authored | no | An answer in comparisons, in shifts or in Big-O is in the same currency as the reference answer. |
| 4 | Best case is the most favourable arrangement of n elements, not the smallest input; a count of exactly 1 is not a best case for a sort. | `ana.best-case-arrangement`, `ana.cases` | authored | no | Separates a smallest-input reading of "best case" (taxonomy item `BObestCaseSmallestInput`) from a correct answer; without it, "one element, one operation" can look like a defensible reading of the question. |
| 5 | N(N - 1)/2, or O(n^2), is the worst case (reverse order), and about N^2/4 the average case. | `ana.insertion-sort`, `ana.cases` | authored | no | Needed to tell that a quadratic count offered as the best case is the worst-case formula (taxonomy item `BObestWorstSwapped`) rather than an arithmetic slip. |

Retrieval dependence: medium to high, through facts 2, 4 and 5. Candidate chunks to
withhold: `ana.insertion-sort`, `ana.best-case-arrangement`.

## E05.Q04
What is the base case for a recursive implementation of merge sort?

| # | Course-specific fact | Chunks | Origin | In the prompt anyway? | Why a grader without it could judge differently |
|---|---|---|---|---|---|
| 1 | The base case is an array of size 1 (or 2). | `rec.merge-sort-base-case` | Mohler | yes | The usual textbook base case is size 1 (or at most 1); size 2 is this course's convention. |
| 2 | Size 2 is accepted because two elements can be sorted directly with one comparison and at most one swap; a base case stated as one element, as two elements, or as one or two is correct. | `rec.merge-sort-base-case` | authored | no | The reference answer puts "(or 2)" in parentheses. Without the explanation a grader can read 2 as a grudging alternative and mark an answer of two elements alone as wrong. |
| 3 | The base case is a test on the size of the piece handed to the current call. It is a different thing from the result (the whole array in order, produced by the last merge) and from the running time. | `rec.merge-sort-base-case`, `rec.merge-sort-structure` | authored | no | Decides whether an answer that names the end result, or a running time, has stated a base case at all. |
| 4 | O(n log n) is the cost of merge sort in the best, average and worst case. | `ana.merge-sort-cost` | authored | no | Identifies a bound given here as a true statement about cost, hence an answer to a different question, not a wrong base case. |

Retrieval dependence: medium. Fact 1 is in the reference answer; facts 2 and 3 are what
retrieval adds. This is the question the review uses as its example of a course
convention. Candidate chunk to withhold: `rec.merge-sort-base-case`.

## E10.Q07
How many comparisons does it take to find an element in a binary search tree?

| # | Course-specific fact | Chunks | Origin | In the prompt anyway? | Why a grader without it could judge differently |
|---|---|---|---|---|---|
| 1 | The expected answer is the height of the tree; the log of the number of elements is accepted as the same answer. | `ana.bst-search-height` | Mohler | yes | A grader could insist on one of the two, or on a worst-case statement. |
| 2 | Log n equals the height only when the tree is balanced; when the course quotes log n it assumes a balanced tree. | `ana.bst-search-height`, `ana.balanced-vs-degenerate` | authored | no | Without it, log n can be marked wrong for an arbitrary tree, or the height marked wrong because it is not a formula in n. |
| 3 | Height is the length of the longest path from the root to any leaf; the course ignores the difference between the height and the height plus one. | `ia.E10.Q02`, `ana.bst-search-height` | Mohler (other question: E10.Q02) and authored | no | Answers in levels, depth or height plus one are off by one from the reference answer and are still the same answer here. |
| 4 | A cost of n (or n - 1) is the cost in a degenerate tree only. | `ana.balanced-vs-degenerate` | authored | no | An answer of n with the degenerate case named is a correct worst case; the same number without it describes a linear scan. A grader without this cannot tell which reading the course takes. |
| 5 | n, n - 1 and n/2 are linear-scan counts, and n log n is the cost of sorting, not of one search. | `ana.linear-vs-tree-search` | authored | no | Ties such counts to scanning a list (taxonomy item `BOsearchLinearScan`) or to sorting (`BOsearchVsSort`) rather than leaving them as unexplained wrong numbers. |
| 6 | The course's definition of a binary search tree: the left child is smaller than the parent, which is smaller than the right child. | `ia.E10.Q05`, `ana.bst-search-height` | Mohler (other question: E10.Q05) | no | Fixes what kind of tree the question is about; no balance condition is part of the definition. |

Retrieval dependence: high, through facts 2, 4 and 5. Candidate chunks to withhold:
`ana.bst-search-height`, `ana.balanced-vs-degenerate`. The instructor answer to E12.Q10
(`ia.E12.Q10`) is usually retrieved for this question and repeats "the height of the tree".

## E12.Q10
How many steps does it take to search a node in a binary search tree?

| # | Course-specific fact | Chunks | Origin | In the prompt anyway? | Why a grader without it could judge differently |
|---|---|---|---|---|---|
| 1 | The expected answer is the height of the tree. | `ana.bst-search-height` | Mohler | yes | As for E10.Q07. |
| 2 | The log of the number of elements is accepted as the same answer. The reference answer to this question does not say so; the reference answer to E10.Q07 does. | `ia.E10.Q07`, `ana.bst-search-height` | Mohler (other question: E10.Q07) | **no** | With only this question's reference answer, an answer of log n is not obviously the expected one. This is the clearest case in the set of a fact that the course states and that only retrieval supplies. |
| 3 | A "step" is one comparison, which moves the search one level down a single path from the root. | `ana.bst-search-height` | authored | no | Steps could otherwise be read as the cases of the comparison or as operations of some other kind. |
| 4 | Log n assumes a balanced tree; n (or n - 1) is the cost in a degenerate tree only. | `ana.balanced-vs-degenerate` | authored | no | As facts 2 and 4 of E10.Q07. |
| 5 | n, n - 1 and n/2 are linear-scan counts, and n log n is the cost of sorting. | `ana.linear-vs-tree-search` | authored | no | As fact 5 of E10.Q07. |
| 6 | Height is the length of the longest path from the root to any leaf; height versus height plus one is ignored. | `ia.E10.Q02`, `ana.bst-search-height` | Mohler (other question: E10.Q02) and authored | no | As fact 3 of E10.Q07. |

Retrieval dependence: high, and higher than E10.Q07 because of fact 2. Candidate chunks to
withhold: `ia.E10.Q07` together with `ana.bst-search-height` (both state fact 2; withholding
only one leaves the other in the top k).

## E11.Q09
Briefly describe the divide-and-conquer paradigm.

| # | Course-specific fact | Chunks | Origin | In the prompt anyway? | Why a grader without it could judge differently |
|---|---|---|---|---|---|
| 1 | Three steps: divide a problem into smaller subproblems, solve them recursively, combine the solutions into a solution for the original problem. | `rec.divide-and-conquer` | Mohler | yes | Fixes that recursion and a combine step are part of the definition. |
| 2 | In this course the term means that recursive pattern. Splitting a program into functions, classes or files is modular design, not this paradigm. | `rec.divide-and-conquer` | authored | no | "Divide and conquer" is also used informally for breaking a programming task into manageable pieces, and a grader could accept that as a loose description. This sentence takes a side. |
| 3 | The subproblems are smaller instances of the same problem, which is why the same function is called on them. | `rec.divide-and-conquer` | authored | no | Distinguishes "smaller subproblems" from "smaller, different tasks". |
| 4 | Merge sort is the standard instance: it splits the array into two, sorts each half, and merges the sorted halves. | `rec.merge-sort-structure`, `ia.E11.Q10` | Mohler (other question: E11.Q10) | no | An answer that describes merge sort describes an instance of the paradigm; a grader needs this to see it as on topic rather than as a different algorithm. |

Retrieval dependence: medium, through facts 2 and 4. Candidate chunk to withhold:
`rec.divide-and-conquer`.

## Summary

| Question | Deciding facts that only retrieval supplies | Chunks to withhold for the positive control |
|---|---|---|
| E03.Q06 | non-convergence is the first cause | `rec.convergence`, `rec.infinite-recursion` |
| E03.Q07 | equal expressive power is true but not an expected similarity | `rec.iteration-similarities` |
| E05.Q03 | N versus N - 1; best case is an arrangement, not a size; which formula is the worst case | `ana.insertion-sort`, `ana.best-case-arrangement` |
| E05.Q04 | size 2 alone is a correct base case; base case versus result versus running time | `rec.merge-sort-base-case` |
| E10.Q07 | log n assumes balance; n only for a degenerate tree; linear-scan and sorting counts | `ana.bst-search-height`, `ana.balanced-vs-degenerate` |
| E12.Q10 | log n is accepted although this question's reference answer does not say so | `ia.E10.Q07`, `ana.bst-search-height` |
| E11.Q09 | the paradigm versus modular design; merge sort as an instance | `rec.divide-and-conquer` |

Withholding a chunk only removes the fact if no other retrieved chunk repeats it. Several
facts are deliberately stated in two places (a notes chunk and an instructor-answer
chunk); the last column lists every chunk that has to go.

### How often the supporting chunk is actually retrieved

Counts of sheet rows whose top 4 contain the chunk, for the default retrieval (BM25, k = 4,
query = question + student answer, own instructor-answer chunk withheld), on the 63-row
pilot sheet with corpus hash `17795a06407c…` (2026-11-22). These are retrieval counts per
question only; they say nothing about whether any answer is right. Every row received
four chunks; 209 of the 252 retrieved places went to notes chunks and 43 to
instructor-answer chunks.

| Question | Rows | Supporting chunks in the top 4 |
|---|---|---|
| E03.Q06 | 5 | `rec.infinite-recursion` 5, `rec.convergence` 2 |
| E03.Q07 | 14 | `rec.iteration-similarities` 14, `rec.iteration-differences` 14 |
| E05.Q03 | 10 | `ana.insertion-sort` 10, `ana.best-case-arrangement` 7, `ana.cases` 5 |
| E05.Q04 | 7 | `rec.merge-sort-base-case` 6, `rec.merge-sort-structure` 5, `ana.merge-sort-cost` 6 |
| E10.Q07 | 8 | `ana.bst-search-height` 8, `ana.linear-vs-tree-search` 8, `ia.E12.Q10` 8, `ana.balanced-vs-degenerate` 7 |
| E12.Q10 | 11 | `ana.bst-search-height` 11, `ana.balanced-vs-degenerate` 10, `ia.E10.Q07` 8, `ana.linear-vs-tree-search` 6 |
| E11.Q09 | 8 | `rec.divide-and-conquer` 8, `rec.merge-sort-structure` 6, `ia.E11.Q10` 6 |

Two things follow for the experiment. Fact 3 of E03.Q06 (an unreachable base case is as
good as none) is stated only in `rec.convergence`, which is retrieved for 2 of 5 rows at
k = 4, so that fact often does not reach the model; fact 2 is also in
`rec.infinite-recursion`, which is always retrieved. And on one E05.Q04 row the base-case
chunk is not retrieved at all. Recompute these counts after any change to the corpus, to k or to the backend.

## Authored statements to review

These sentences in the notes go beyond what the Mohler instructor answers say and take a
position that affects how an answer would be judged. They were written to match the
instructor answers, not to match any labelling decision, but they overlap with the
decision rules in annotation/schema.md, so the corpus should not be treated as independent
evidence for those rules. Edit or delete them in the notes (then run
`python scripts/build_corpus.py`; the corpus hash changes) if they claim more than the
course material should.

| Chunk | Statement |
|---|---|
| `rec.merge-sort-base-case` | A base case stated as one element, as two elements, or as one or two elements is correct in this course. The base case is different from the result of the algorithm and from its running time. |
| `rec.divide-and-conquer` | Splitting a program into functions, classes or files is modular design, not the divide-and-conquer paradigm. |
| `rec.iteration-similarities` | "These are the three similarities expected in this course", followed by the statement that the two are equally powerful. |
| `ana.insertion-sort` | Strictly N - 1 comparisons; "in this course we state the count as N operations". |
| `ana.best-case-arrangement` | A count of exactly 1 operation is a best case only for an algorithm that can stop after one step on an arbitrarily large input. |
| `ana.bst-search-height` | "We ignore that difference" (the height versus the height plus one). Log n "is the height when the tree is balanced". |
| `ana.balanced-vs-degenerate` | "When we quote log n for a binary search tree we are assuming that the tree is balanced. A cost of n belongs only to the degenerate tree." |
| `ana.linear-vs-tree-search` | Counts such as n, n - 1 or n/2 are linear-scan counts; n log n is not the cost of a search. |
