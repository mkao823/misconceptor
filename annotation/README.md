# Human annotation pilot

Read [schema v0.2](schema.md) and every taxonomy description and note before
labeling. The pilot CSV remains entirely unlabeled. Only humans assign labels;
validation checks mechanics, not whether evidence actually supports a belief.
No baselines, model pre-labels, or critic outputs belong in this pass.

## Commands (from repository root)

Use Python 3 with the existing PyYAML dependency installed; the new workflow
otherwise uses the standard library. No new packages are required.

```bash
python3 scripts/validate_taxonomy.py
python3 scripts/annotation_sheet.py                         # partial pass
python3 scripts/annotation_sheet.py annotation/my_pass.csv  # full sheet copy
python3 scripts/annotation_sheet.py --report > /tmp/progress.json
python3 scripts/annotation_sheet.py --complete               # all 63 required
python3 -m unittest discover -s tests -v
```

Reports are JSON; omit `--report` for concise validation. Invalid input exits 1
and emits errors to stderr, with no report. Partial completion means blank rows
within the full 63-row sheet, not deleting rows. These commands do not yet
support the future second-rater subset. You can label a copy using the same
columns; pass that path to each command. The frozen `pilot_identity.json`
protects all six source cells, independently of which CSV you edit. Treat the
manifest as immutable and review any intentional source correction separately.
Do not rebuild the pilot over human work: `scripts/build_pilot_sheet.py` writes
blank annotations and requires the original local parquet.

## First session: 14 answers, then pause

1. Make a working copy of the entire CSV and record rater name, date, and schema
   v0.2 in a local session log. Keep text columns as text in your spreadsheet;
   preserve exact source values and export UTF-8 CSV. Hide `score_avg` while
   deciding; inspect it afterward only to catch misreadings.
2. Label these 14 IDs (two per question). They were selected by row identity
   and score pool, without predicting any labels. Some questions have no high
   scorer in the selected top 20, so their two examples are both low scorers.

   | Question | IDs |
   |---|---|
   | E03.Q06 | E03.Q06.A01, E03.Q06.A00 |
   | E05.Q04 | E05.Q04.A03, E05.Q04.A06 |
   | E05.Q03 | E05.Q03.A02, E05.Q03.A08 |
   | E10.Q07 | E10.Q07.A02, E10.Q07.A08 |
   | E12.Q10 | E12.Q10.A04, E12.Q10.A13 |
   | E03.Q07 | E03.Q07.A01, E03.Q07.A03 |
   | E11.Q09 | E11.Q09.A25, E11.Q09.A12 |

3. Read question, instructor answer, then student answer. Judge explicit claims,
   not grade or omissions. Pick one primary; add secondary only with clear
   support. Paste exact evidence for either taxonomy label, joining disjoint
   spans with ` || `. Explain `other_error`; record uncertainty in notes rather
   than forcing a catalogued misconception. For candidate items use one line
   each: `Candidate: stable short description`. All notes also appear verbatim
   in the report for human review; untagged prose is not automatically classified.
4. Run partial validation and the report after 10–15 answers. Fix CSV/evidence
   errors. Review ambiguous cases and candidate notes without looking at model
   output. If a rule must change, version the schema, record the reason, and
   re-check these answers under the new version before continuing. This small
   convenience batch is for calibration, not a representative prevalence estimate.
5. Finish the remaining 49 in batches of roughly 10–15. Re-run partial checks
   after every batch and complete validation at the end. Retain a dated copy
   before adjudication. These are first-rater annotations, not yet gold.

## Reading progress and making the pilot decision

`progress.json` is the initial, reproducible snapshot: 0/63 completed and 0/43
low scorers completed. Refresh a report against the actual human working copy.
`primary_counts` includes zeros for every valid label; secondary counts are
separate. Per-question completion exposes coverage gaps. Provisional Big-O row
IDs and notes identify cases needing review.

The report gives the observed `other_error` count divided by **all 43** low
scorers, the share among completed low scorers (`null` before any are labeled),
and the possible final range if all pending answers are or are not
`other_error`. A current 0/43 is a lower bound, not a finding of no errors.
Only primary `other_error` contributes to this decision. More than half means
**at least 22/43**: the report marks a supplement required even if other rows
are pending. Otherwise the decision stays pending until all 43 are labeled.
Do not interpret zero observed taxonomy counts as proof an item is unobservable.
No labels have been invented to populate the initial report.

## Remaining human work

- Complete and review the first 14, then all 63 under the current schema.
- Review candidate-item counts and provisional Big-O cases against original
  literature before confirming or expanding the taxonomy.
- Recruit an independent second human; follow schema section 7 for the 30–50
  row subset. Record actual selected IDs, seed, rater and schema version here
  once chosen. Do not expose first-rater annotations or notes to that rater.
  If taxonomy-labeled rows exceed the planned subset capacity, revise and
  document the sampling plan rather than silently dropping them.
- Preserve both independent sheets, compute pre-adjudication agreement, discuss
  disagreements, and produce adjudicated gold with provenance. Agreement and
  subset tooling are deferred; this validator targets the full pilot only.
- Decide the supplement after the low-scorer result. Model baselines and the
  critic loop remain later work.

## Validation record and limits (2026-11-01)

The existing taxonomy passes its validator: 28 items (17 verified, 11
provisional), plus three special labels. This checks structure, not source
verification. The existing CSV has 63 unique IDs, seven questions, 43 scores
below 3.5, 20 high scorers, and all four annotation columns blank. Source-cell
fingerprints were frozen from this original sheet. The local raw parquet is
absent, so the original selection's completeness and top-20 ranking could not
be independently rebuilt; no dataset was downloaded or sheet regenerated.
The tests use synthetic assignments only and do not write to the pilot.

Dataset attribution is retained from the repository: Mohler, Bunescu &
Mihalcea (2011), dataset `nkazi/MohlerASAG`, CC-BY-4.0. Source URL:
https://huggingface.co/datasets/nkazi/MohlerASAG — **unverified (from memory /
existing repository attribution); not checked this run**. Published-source
verification statuses in the taxonomy are inherited, not re-verified here.
