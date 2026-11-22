# Critic positive control: pc_gpt-oss-20b_20261122-025526

Model `gpt-oss:20b`, controls `critic_positive_control_v1` (16 authored cases: 8 dependent, 8 non-dependent), Critic template `critic_v1`, k = 4, 2026-11-22T02:55:26-08:00.

The cases are authored control material, not eval rows, and carry no gold label. The rates below describe how the Critic behaved on these constructed cases. They are not evidence for or against the mechanism claim.

"Triggered" means the Critic returned `sufficient: false` on the first-pass draft. Rates are over arms that produced a verdict.

| Arm | Triggered | Errors |
|---|---|---|
| Dependent case, supporting chunk withheld from the first retrieval | 0/7 (0%) | 1 |
| Dependent case, supporting chunk present in the first retrieval | 0/7 (0%) | 1 |
| Non-dependent case, ordinary retrieval | 0/7 (0%) | 1 |

Non-dependent cases by kind (triggered / judged): matches_reference 0/5, vague 0/1, plainly_wrong 0/1.

Recovery: of the 0 withheld arms that triggered, the re-query's k chunks contained a withheld supporting chunk in 0 (all of the withheld chunks in 0). Over all 7 judged withheld arms that is 0/7 (0%).

Paired view over the 7 dependent cases judged in both arms: triggered only when withheld 0, in both arms 0, in neither 7, only when present 0.

Cost: 24 arms, 45 model calls, 171768 tokens (7157.0 tokens and 1.88 calls per arm, cache hits included).

## Arms

| Case | Question | Arm | Draft label | Triggered | Critic's query | Re-query chunks | Recovered |
|---|---|---|---|---|---|---|---|
| pc01d | E03.Q06 | withheld | none | no |  |  |  |
| pc01d | E03.Q06 | present | none | no |  |  |  |
| pc01i | E03.Q06 | natural | none | no |  |  |  |
| pc02d | E03.Q07 | withheld | none | no |  |  |  |
| pc02d | E03.Q07 | present | none | no |  |  |  |
| pc02i | E03.Q07 | natural | insufficient_evidence | no |  |  |  |
| pc03d | E05.Q03 | withheld | other_error | no |  |  |  |
| pc03d | E05.Q03 | present | none | no |  |  |  |
| pc03i | E05.Q03 | natural | none | no |  |  |  |
| pc04d | E05.Q04 | withheld | none | no |  |  |  |
| pc04d | E05.Q04 | present | none | no |  |  |  |
| pc04i | E05.Q04 | natural | none | no |  |  |  |
| pc05d | E10.Q07 | withheld | BOsearchLinearScan | no |  |  |  |
| pc05d | E10.Q07 | present | none | no |  |  |  |
| pc05i | E10.Q07 | natural | none | no |  |  |  |
| pc06d | E10.Q07 | withheld | other_error | no |  |  |  |
| pc06d | E10.Q07 | present | other_error | no |  |  |  |
| pc06i | E10.Q07 | natural | other_error | no |  |  |  |
| pc07d | E12.Q10 | withheld | other_error | no |  |  |  |
| pc07d | E12.Q10 | present | other_error | no |  |  |  |
| pc07i | E12.Q10 | natural | none | no |  |  |  |
| pc08d | E11.Q09 | withheld | other_error | ERROR (critic) | | | |
| pc08d | E11.Q09 | present |  | ERROR (first_pass) | | | |
| pc08i | E11.Q09 | natural |  | ERROR (first_pass) | | | |

## What the Critic said was missing

No arm triggered.

Withheld chunks per dependent case (and whether ordinary retrieval would have shown them):

- pc01d: `rec.infinite-recursion` (in the ordinary top k), `rec.convergence` (in the ordinary top k)
- pc02d: `rec.iteration-similarities` (in the ordinary top k), `rec.definition` (in the ordinary top k), `ia.E11.Q06` (not in the ordinary top k)
- pc03d: `ana.insertion-sort` (in the ordinary top k)
- pc04d: `rec.merge-sort-base-case` (in the ordinary top k)
- pc05d: `ana.balanced-vs-degenerate` (in the ordinary top k)
- pc06d: `ana.bst-search-height` (in the ordinary top k)
- pc07d: `ia.E10.Q07` (in the ordinary top k), `ana.bst-search-height` (in the ordinary top k)
- pc08d: `rec.divide-and-conquer` (in the ordinary top k)
