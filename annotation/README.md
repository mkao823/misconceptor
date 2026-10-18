# annotation/

Annotation schema, templates and completed human labels for the evaluation subset, plus inter-annotator agreement notes.

- `schema.md`: label set, column rules, decision rules for the recurring Mohler confusions, two-rater plan.
- `pilot_sheet.csv`: the 63-row annotation pilot (43 low scorers plus 20 top scorers on the seven in-scope questions), label columns empty. Rebuild with `python scripts/build_pilot_sheet.py`.
- Student answers in `pilot_sheet.csv` come from the Mohler ASAG dataset (Mohler, Bunescu & Mihalcea 2011; Hugging Face `nkazi/MohlerASAG`, CC-BY-4.0).
