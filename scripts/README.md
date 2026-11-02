# scripts/

Runnable entry-point scripts (data inspection, scope filtering, experiment runs).

Human annotation: `python3 scripts/annotation_sheet.py [sheet.csv]` validates a
partially filled full pilot; add `--complete` to require all primary labels or
`--report` to emit JSON progress and label counts. See
[annotation workflow](../annotation/README.md) for commands and scope.
