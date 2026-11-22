"""Validate human pilot annotations and report progress (no label inference)."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / 'annotation/pilot_sheet.csv'
IDENTITY = ROOT / 'annotation/pilot_identity.json'
TAXONOMY = ROOT / 'taxonomy/recursion_bigO.yaml'
FIXED = ['id', 'question_id', 'question', 'instructor_answer', 'student_answer', 'score_avg']
LABELS = ['primary_label', 'secondary_label', 'evidence_span', 'annotator_notes']


def digest(row):
    return hashlib.sha256(json.dumps([row[k] for k in FIXED], ensure_ascii=False).encode()).hexdigest()


def read_sheet(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIXED + LABELS:
            raise ValueError('columns must be exactly: ' + ', '.join(FIXED + LABELS))
        rows = list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError('ragged CSV row (missing or extra cells)')
    return rows


def validate(rows, taxonomy, identity, complete=False):
    errors = []
    items = {i['id'] for i in taxonomy['items']}
    recall = {i['id'] for i in taxonomy['items'] if 'conceptual_recall' in i['observable_in']}
    labels = items | {i['id'] for i in taxonomy['special_labels']}
    counts = Counter(r['id'] for r in rows)
    if set(counts) != set(identity['rows']):
        errors.append('row ids differ from frozen pilot (missing or unknown ids)')
    for rid, count in counts.items():
        if count != 1:
            errors.append(f'{rid}: duplicate id')
    for r in rows:
        rid = r['id']
        def error(message):
            errors.append(f'{rid}: {message}')
        if rid in identity['rows'] and digest(r) != identity['rows'][rid]:
            error('immutable source cells changed')
        p, s, evidence, notes = (r[k] for k in LABELS)
        if not p:
            if complete:
                error('primary_label required in complete mode')
            if s or evidence:
                error('secondary/evidence requires primary_label; notes-only drafts are allowed')
            continue
        if p not in labels or (s and s not in labels):
            error('unknown label (labels are case sensitive single ids)')
        if s in {'none', 'insufficient_evidence'} or (s and s == p):
            error('invalid secondary label or duplicate primary')
        if ({p, s} & items) - recall:
            error('code-only taxonomy label is ineligible for this recall pilot')
        if 'BCwrite' in {p, s} and r['question_id'] != 'E05.Q04':
            error('BCwrite recall exception is restricted to E05.Q04')
        if p == 'MMcopies':
            error('MMcopies is secondary only')
        if p == 'insufficient_evidence' and s:
            error('insufficient_evidence cannot have a secondary label')
        if p == 'none' and s and s != 'MMcopies':
            error('none permits only MMcopies as secondary')
        if (p == 'other_error' or s == 'other_error') and not notes.strip():
            error('other_error requires explanatory notes')
        if {p, s} >= {'RecursiveMethodNeedsIfElse', 'RecursiveFunctionNeedsIfElse'}:
            error('if-else twins cannot co-occur')
        needs = p in items or s in items
        if needs and not evidence.strip():
            error('taxonomy label in either column requires evidence')
        if p in {'none', 'insufficient_evidence'} and not needs and evidence:
            error('evidence must be empty for this special label')
        if evidence:
            for span in evidence.split('||'):
                span = span.strip()
                if not span or span not in r['student_answer']:
                    error('evidence part is empty or not verbatim in student_answer')
    return errors


def report(rows, taxonomy):
    done = [r for r in rows if r['primary_label']]
    low = [r for r in rows if float(r['score_avg']) < 3.5]
    low_done = [r for r in low if r['primary_label']]
    other = sum(r['primary_label'] == 'other_error' for r in low_done)
    primary = Counter(r['primary_label'] for r in done)
    secondary = Counter(r['secondary_label'] for r in done if r['secondary_label'])
    ids = [i['id'] for i in taxonomy['items']]
    provisional = {i['id'] for i in taxonomy['items'] if i['concept'] == 'big_o' and i['status'] == 'provisional'}
    candidates = Counter()
    for r in done:
        for line in r['annotator_notes'].splitlines():
            if line.lower().startswith('candidate:') and line[10:].strip():
                candidates[line[10:].strip()] += 1
    return {
        'schema_version': '0.2', 'total': len(rows), 'completed': len(done),
        'remaining': len(rows) - len(done),
        'primary_counts': {k: primary[k] for k in ids + [i['id'] for i in taxonomy['special_labels']]},
        'secondary_counts': dict(sorted(secondary.items())),
        'by_question': {q: {'total': sum(r['question_id'] == q for r in rows),
                            'completed': sum(r['question_id'] == q for r in done)}
                        for q in sorted({r['question_id'] for r in rows})},
        'low_scorers': {'total': len(low), 'completed': len(low_done), 'other_error': other,
                        'other_error_share_all_43': other / len(low) if low else None,
                        'other_error_share_completed': other / len(low_done) if low_done else None,
                        'possible_final_share': [other / len(low), (other + len(low) - len(low_done)) / len(low)] if low else None,
                        'decision': ('supplement required' if other > len(low) / 2 else
                                     'pending' if len(low_done) < len(low) else 'threshold not exceeded')},
        'zero_primary_taxonomy_ids': [k for k in ids if not primary[k]],
        'zero_any_taxonomy_ids': [k for k in ids if not primary[k] and not secondary[k]],
        'zero_count_caution': 'Zero observed labels is not proof of unobservability, especially during a partial pass.',
        'provisional_big_o_rows': [r['id'] for r in done if {r['primary_label'], r['secondary_label']} & provisional],
        'candidate_counts': dict(sorted(candidates.items())),
        'notes_for_review': [{'id': r['id'], 'notes': r['annotator_notes']} for r in rows if r['annotator_notes'].strip()],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sheet', nargs='?', type=Path, default=SHEET)
    parser.add_argument('--complete', action='store_true', help='require all 63 primary labels')
    parser.add_argument('--report', action='store_true', help='emit JSON progress after validation')
    args = parser.parse_args()
    try:
        rows = read_sheet(args.sheet)
        taxonomy = yaml.safe_load(TAXONOMY.read_text())
        identity = json.loads(IDENTITY.read_text())
        errors = validate(rows, taxonomy, identity, args.complete)
        if errors:
            raise ValueError('\n'.join(errors))
    except (OSError, ValueError, csv.Error, yaml.YAMLError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(report(rows, taxonomy), indent=2) if args.report else
          f'OK: {len(rows)} rows, {sum(bool(r["primary_label"]) for r in rows)} completed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
