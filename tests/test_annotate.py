"""Mechanics of scripts/annotate.py, on temporary copies only.

The labels typed here are synthetic and chosen to exercise prompts and saving;
they are not judgements about any answer and are never written to the pilot.
"""
import ast
import csv
import io
import itertools
import json
import random
import re
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts import annotate
from scripts import annotation_sheet as rules

PILOT_BYTES = annotate.SOURCE_SHEET.read_bytes()
TAXONOMY = yaml.safe_load(rules.TAXONOMY.read_text())
IDENTITY = json.loads(rules.IDENTITY.read_text())
IDS = annotate.FIRST_SESSION_IDS
REAL_OUTPUTS = [annotate.DEFAULT_SHEET, annotate.SESSION_LOG]

# Keystrokes for one row, one entry per prompt.
NONE = ['none', '', '', '']                # primary, secondary, notes, confirm (no evidence prompt)
UNJUDGEABLE = ['insufficient_evidence', '', '']  # primary, notes, confirm (no secondary or evidence prompt)


class Typist:
    """Injected stdin: strings are typed lines; a callable runs just before the next line is read."""

    def __init__(self, steps):
        self.steps = list(steps)

    def readline(self):
        while self.steps:
            step = self.steps.pop(0)
            if not callable(step):
                return step + '\n'
            step()
        return ''


@pytest.fixture
def env(tmp_path):
    source = tmp_path / 'source' / 'pilot_sheet.csv'
    source.parent.mkdir()
    shutil.copyfile(annotate.SOURCE_SHEET, source)
    existed = [path.exists() for path in REAL_OUTPUTS]
    yield SimpleNamespace(source=source, sheet=tmp_path / 'work' / 'my_pass.csv',
                          log=tmp_path / 'work' / 'session_log.md')
    assert source.read_bytes() == PILOT_BYTES                  # the temporary source copy
    assert annotate.SOURCE_SHEET.read_bytes() == PILOT_BYTES   # and the real pilot sheet stay untouched
    assert [path.exists() for path in REAL_OUTPUTS] == existed  # nothing appears in annotation/


def run(env, typed, *flags, sheet=None):
    out = io.StringIO()
    code = annotate.main(['--sheet', str(sheet or env.sheet), '--log', str(env.log), '--rater', 'Test Rater', *flags],
                         stdin=Typist(typed), stdout=out, source=env.source, width=80)
    return code, out.getvalue()


def labels(path):
    return {row['id']: [row[k] for k in rules.LABELS] for row in rules.read_sheet(path)}


def source_row(env, row_id):
    return next(row for row in rules.read_sheet(env.source) if row['id'] == row_id)


def errors(path):
    return rules.validate(rules.read_sheet(path), TAXONOMY, IDENTITY)


def shown(output):
    """Row ids in the order their screens were printed."""
    return re.findall(r'^(E\d+\.Q\d+\.A\d+) {4}', output, flags=re.M)


def records(data):
    return {cells[0]: raw for raw, cells in annotate.split_records(data.decode('utf-8')) if cells}


# ---- the working copy ------------------------------------------------------

def test_working_copy_is_an_exact_copy_and_the_source_is_untouched(env):
    code, out = run(env, ['quit'])
    assert code == 0
    assert env.sheet.read_bytes() == PILOT_BYTES
    assert env.source.read_bytes() == PILOT_BYTES
    assert 'Created working copy' in out
    assert 'OK: 63 rows, 0 completed' in out and 'Completed 0, remaining 63 of 63.' in out
    assert not env.log.exists()  # a session that saved nothing is not logged


def test_refuses_to_use_the_pilot_sheet_as_the_working_copy(env, tmp_path):
    link = tmp_path / 'link.csv'
    link.symlink_to(env.source)
    for target in (annotate.SOURCE_SHEET, env.source, link):
        code, out = run(env, NONE, sheet=target)
        assert code == 2 and 'Refusing to label' in out
        assert shown(out) == []
    assert not env.log.exists()  # the fixture then checks that both sheets are byte-identical


def test_a_copy_with_changed_source_cells_is_not_edited(env):
    env.sheet.parent.mkdir()
    env.sheet.write_bytes(PILOT_BYTES.replace(b'recursi', b'RECURSI', 1))
    damaged = env.sheet.read_bytes()
    code, out = run(env, NONE)
    assert code == 1 and 'immutable source cells changed' in out and shown(out) == []
    assert env.sheet.read_bytes() == damaged


# ---- a scripted session ----------------------------------------------------

def test_scripted_session_labels_three_rows_and_validates(env):
    span = ' '.join(source_row(env, IDS[1])['student_answer'].split()[:3])
    assert span in source_row(env, IDS[1])['student_answer']
    other_error = next(label.number for label in annotate.build_catalog(TAXONOMY) if label.id == 'other_error')
    note = 'synthetic note, with a comma and "quotes"\nCandidate: synthetic candidate'
    typed = (NONE
             + ['infiniteexecution', '', span, '', '']                     # id in the wrong case
             + [str(other_error), '', '', *note.splitlines(), '', '']      # by number; two note lines
             + ['quit'])
    code, out = run(env, typed, '--first-session')

    assert code == 0
    assert errors(env.sheet) == []
    after = labels(env.sheet)
    assert after[IDS[0]] == ['none', '', '', '']
    assert after[IDS[1]] == ['InfiniteExecution', '', span, '']  # the exact id is stored
    assert after[IDS[2]] == ['other_error', '', '', note]
    assert all(row == ['', '', '', ''] for row_id, row in after.items() if row_id not in IDS[:3])
    assert shown(out) == list(IDS[:4])

    report = rules.report(rules.read_sheet(env.sheet), TAXONOMY)
    assert (report['completed'], report['remaining']) == (3, 60)
    assert report['candidate_counts'] == {'synthetic candidate': 1}
    assert 'OK: 63 rows, 3 completed' in out and 'Completed 3, remaining 60 of 63.' in out
    assert 'score_avg' not in out  # never shown unless asked for

    # Every untouched record is byte-identical, and the edited ones keep their six source cells raw.
    before, saved = records(PILOT_BYTES), records(env.sheet.read_bytes())
    assert list(saved) == list(before)
    for row_id in before:
        if row_id in IDS[:3]:
            assert annotate.split_raw_fields(saved[row_id])[0][:6] == annotate.split_raw_fields(before[row_id])[0][:6]
        else:
            assert saved[row_id] == before[row_id]
    assert not list(env.sheet.parent.glob('.*.tmp'))

    log = env.log.read_text().splitlines()
    entries = [line for line in log if line.startswith('- ')]
    assert len(entries) == 1
    assert 'rater: Test Rater' in entries[0] and 'schema v0.3' in entries[0]
    assert f'labeled 3: {", ".join(IDS[:3])}' in entries[0]
    assert re.match(r'- \d{4}-\d\d-\d\d \|', entries[0])


def test_first_session_presents_the_fourteen_ids_in_readme_order_then_stops(env):
    code, out = run(env, UNJUDGEABLE * len(IDS), '--first-session')  # no "quit": the batch ends by itself
    assert code == 0
    assert shown(out) == list(IDS)
    assert 'First-session batch complete (14 of 14)' in out and 'OK: 63 rows, 14 completed' in out
    assert errors(env.sheet) == []

    code, out = run(env, ['quit'], '--first-session')
    order = [row['id'] for row in rules.read_sheet(env.source)]
    assert 'already labeled' in out
    assert shown(out) == [next(i for i in order if i not in IDS)]
    assert len([line for line in env.log.read_text().splitlines() if line.startswith('- ')]) == 1


def test_first_session_ids_match_the_readme_table():
    text = (annotate.ROOT / 'annotation/README.md').read_text()
    table = [line for line in text.splitlines() if re.match(r'\s*\| E\d+\.Q\d+ \|', line)]
    assert tuple(re.findall(r'E\d+\.Q\d+\.A\d+', '\n'.join(table))) == IDS


# ---- order, resume and navigation -----------------------------------------

def test_resume_starts_at_the_first_unlabeled_row(env):
    _, out = run(env, NONE + ['skip'] + NONE + ['quit'], '--first-session')
    assert shown(out) == list(IDS[:4])
    assert {i for i, row in labels(env.sheet).items() if row[0]} == {IDS[0], IDS[2]}

    _, out = run(env, ['quit'], '--first-session')
    assert shown(out) == [IDS[1]]  # the skipped row is the first one without a primary label

    _, out = run(env, ['quit'])  # without --first-session: sheet order, grouped by question
    order = [row['id'] for row in rules.read_sheet(env.source)]
    assert shown(out) == [next(i for i in order if i not in (IDS[0], IDS[2]))]


def test_rows_are_grouped_by_question_and_can_be_limited_to_one(env):
    rows = rules.read_sheet(env.source)
    random.Random(7).shuffle(rows)
    calibration, grouped = annotate.build_queues(rows, None)
    assert [row['id'] for row in calibration] == list(IDS)
    questions = [q for q, _ in itertools.groupby(row['question_id'] for row in grouped)]
    assert len(grouped) == 63 and len(questions) == len(set(questions)) == 7

    _, out = run(env, ['quit'], '--question', 'E05.Q03', '--first-session')
    assert shown(out) == ['E05.Q03.A02']
    _, out = run(env, ['skip'] * 10, '--question', 'E05.Q03')
    assert len(shown(out)) == 10 and all(i.startswith('E05.Q03.') for i in shown(out))
    with pytest.raises(SystemExit):
        run(env, [], '--question', 'E99.Q99')


def test_back_reedits_the_previous_row(env):
    code, out = run(env, NONE + ['back', *UNJUDGEABLE, 'quit'], '--first-session')
    assert shown(out) == [IDS[0], IDS[1], IDS[0], IDS[1]]
    assert labels(env.sheet)[IDS[0]] == ['insufficient_evidence', '', '', '']
    assert errors(env.sheet) == []
    assert f'labeled 1: {IDS[0]}' in env.log.read_text()

    # A later session can step back to a row labeled earlier; Enter keeps what is there.
    code, out = run(env, ['back', '', 'second look', '', '', 'quit'], '--first-session')
    assert shown(out) == [IDS[1], IDS[0], IDS[1]]
    assert labels(env.sheet)[IDS[0]] == ['insufficient_evidence', '', '', 'second look']
    assert f'labeled 0: - | re-edited 1: {IDS[0]}' in env.log.read_text().splitlines()[-1]


def test_skip_and_redo_do_not_save_and_edit_again_keeps_the_draft(env):
    span = source_row(env, IDS[1])['student_answer'].split()[0]
    typed = (['none', 'redo', 'skip']                           # first row: abandoned twice
             + ['InfiniteExecution', '', span, '', 'e']        # second row: finished, then edited again
             + ['', '', '', 'changed my mind', '', '', 'quit'])  # Enter keeps label, secondary and evidence
    code, out = run(env, typed, '--first-session')
    after = labels(env.sheet)
    assert after[IDS[0]] == ['', '', '', '']
    assert after[IDS[1]] == ['InfiniteExecution', '', span, 'changed my mind']
    assert shown(out) == [IDS[0], IDS[0], IDS[1], IDS[1], IDS[2]]
    assert errors(env.sheet) == []


# ---- labels ---------------------------------------------------------------

def test_menu_numbers_every_label_in_groups_and_marks_provisional_items(env):
    catalog = annotate.build_catalog(TAXONOMY)
    items = TAXONOMY['items']
    assert [label.number for label in catalog] == list(range(1, 32))
    assert {label.id for label in catalog} == {i['id'] for i in items + TAXONOMY['special_labels']}
    assert [g for g, _ in itertools.groupby(label.group for label in catalog)] == list(annotate.GROUPS[:5])
    assert [label.id for label in catalog[:3]] == ['none', 'other_error', 'insufficient_evidence']
    assert {label.id for label in catalog if label.provisional} == {
        i['id'] for i in items if i['status'] == 'provisional'}

    bcwrite = next(i for i in items if i['id'] == 'BCwrite')
    code, out = run(env, ['?', '? bcwrite', '? 1', '? nonsense', 'quit'], '--first-session')
    menu = out.split('Labels', 1)[1].split('primary label', 1)[0]
    for label in catalog:
        star = re.search(rf'(?<!\d){label.number} {label.id}(\*?)(?!\w)', menu).group(1)
        assert star == ('*' if label.provisional else '')
    assert 'provisional' in menu
    assert ' '.join(bcwrite['description'].split())[:60] in out   # "? bcwrite": description ...
    assert ' '.join(bcwrite['notes'].split())[:60] in out         # ... and notes
    assert ' '.join(TAXONOMY['special_labels'][0]['definition'].split())[:60] in out
    assert '"nonsense" is not a label number or id' in out
    listing = out.split('primary label (number or id) > ?\n', 1)[1].splitlines()[:31]
    assert [line.split()[1] for line in listing] == [label.id for label in catalog]
    assert env.sheet.read_bytes() == PILOT_BYTES


def test_labels_the_validator_rejects_are_refused_with_its_message(env):
    typed = ['MMcopies', 'GlobalVariable', '99', 'BCwrite',   # all refused as primary on an E03.Q06 row
             'none', 'MMlooping', 'none', '',                 # secondary refused twice, then left empty
             '', '',                                          # notes, confirm
             'other_error', 'other_error', '',                # second row: duplicate secondary refused
             '', '', 'explained', '', '',                     # evidence optional; notes required
             'quit']
    code, out = run(env, typed, '--first-session')
    for message in ('MMcopies is secondary only', 'code-only taxonomy label is ineligible',
                    '"99" is not a label', 'BCwrite recall exception is restricted to E05.Q04',
                    'none permits only MMcopies as secondary', 'invalid secondary label or duplicate primary',
                    'other_error requires explanatory notes'):
        assert message in out, message
    after = labels(env.sheet)
    assert after[IDS[0]] == ['none', '', '', '']
    assert after[IDS[1]] == ['other_error', '', '', 'explained']
    assert errors(env.sheet) == []
    first_row_screen = out.split(IDS[1] + '    ')[0]
    assert 'evidence span' not in first_row_screen  # evidence must be empty for none: never asked


def test_evidence_is_required_when_only_the_secondary_is_a_taxonomy_id(env):
    first = ' '.join(source_row(env, IDS[0])['student_answer'].split()[:2])
    second = ' '.join(source_row(env, IDS[1])['student_answer'].split()[-2:])
    typed = (['none', 'mmcopies', '', first, '', '']                    # Enter alone is refused first
             + ['other_error', 'MMlooping', '-', second, 'why', '', '']  # so is clearing it
             + ['quit'])
    code, out = run(env, typed, '--first-session')
    assert out.count('taxonomy label in either column requires evidence') == 2
    after = labels(env.sheet)
    assert after[IDS[0]] == ['none', 'MMcopies', first, '']
    assert after[IDS[1]] == ['other_error', 'MMlooping', second, 'why']
    assert errors(env.sheet) == []


def test_score_is_hidden_until_a_primary_label_is_entered(env):
    score = source_row(env, IDS[0])['score_avg']
    code, out = run(env, ['s', 'none', 's', 'quit'], '--first-session')
    before, after = out.split('-> primary: none')
    assert 'score_avg' not in before and 'stays hidden' in before
    assert f'score_avg: {score}' in after
    assert env.sheet.read_bytes() == PILOT_BYTES


# ---- evidence -------------------------------------------------------------

INVENTED = 'the function calls itself until the stack overflows because the base case never matches'


def test_non_verbatim_evidence_is_rejected(env):
    answer = source_row(env, IDS[0])['student_answer']
    assert answer.upper() != answer
    typed = ['InfiniteExecution', '', 'words the student never wrote', answer.upper(), '', 'quit']
    code, out = run(env, typed, '--first-session')
    assert out.count('Not accepted: not verbatim in the student answer') == 2
    assert 'taxonomy label in either column requires evidence' in out  # Enter alone is refused too
    assert out.count('Student answer\n') == 4  # shown with the row, then again after each refusal
    assert env.sheet.read_bytes() == PILOT_BYTES  # nothing was saved

    for typed in ('a paraphrase', 'calls itself || ', '||', INVENTED.upper()):
        with pytest.raises(annotate.SpanError):
            annotate.resolve_evidence(typed, INVENTED)


def test_span_shortcut_expands_a_unique_match():
    assert annotate.expand_span('calls itself ... overflows', INVENTED) == 'calls itself until the stack overflows'
    assert annotate.expand_span('calls itself…overflows', INVENTED) == 'calls itself until the stack overflows'
    assert annotate.expand_span('base case', INVENTED) == 'base case'  # verbatim text is stored as typed
    assert (annotate.resolve_evidence('calls itself ... overflows||base case', INVENTED)
            == 'calls itself until the stack overflows || base case')
    assert annotate.expand_span('wait ... what', 'he said wait ... what now') == 'wait ... what'  # literal dots


def test_span_shortcut_refuses_an_ambiguous_match():
    with pytest.raises(annotate.SpanError, match='ambiguous'):
        annotate.expand_span('the ... case', INVENTED)  # "the" starts three possible spans
    with pytest.raises(annotate.SpanError, match='ambiguous'):
        annotate.expand_span('calls ... s', INVENTED)   # and "s" ends several
    with pytest.raises(annotate.SpanError, match='no part of the student answer'):
        annotate.expand_span('zebra ... case', INVENTED)
    with pytest.raises(annotate.SpanError, match='no part of the student answer'):
        annotate.expand_span('overflows ... calls', INVENTED)  # wrong order
    with pytest.raises(annotate.SpanError, match='not verbatim'):
        annotate.expand_span('the ... stack ... case', INVENTED)


def test_span_shortcut_in_a_session_stores_the_exact_substring(env):
    answer = source_row(env, IDS[0])['student_answer']
    words = answer.split()
    typed = f'{" ".join(words[:3])} ... {" ".join(words[-3:])}'
    assert annotate.expand_span(typed, answer) == answer and typed not in answer
    code, out = run(env, ['InfiniteExecution', '', typed, '', '', 'quit'], '--first-session')
    assert labels(env.sheet)[IDS[0]] == ['InfiniteExecution', '', answer, '']
    assert errors(env.sheet) == []


# ---- saving ---------------------------------------------------------------

def test_save_changes_only_the_edited_cells_of_a_spreadsheet_export(env):
    rows = list(csv.reader(io.StringIO(PILOT_BYTES.decode('utf-8'), newline='')))
    exported = io.StringIO(newline='')
    csv.writer(exported, quoting=csv.QUOTE_ALL, lineterminator='\r\n').writerows(rows)
    env.sheet.parent.mkdir()
    env.sheet.write_bytes(b'\xef\xbb\xbf' + exported.getvalue().encode('utf-8'))  # BOM, CRLF, all quoted
    before = env.sheet.read_bytes().split(b'\r\n')

    code, out = run(env, ['other_error', '', '', 'a comma, and "quotes"', '', '', 'quit'], '--first-session')
    after = env.sheet.read_bytes().split(b'\r\n')
    changed = [i for i, (old, new) in enumerate(zip(before, after)) if old != new]
    assert code == 0 and len(after) == len(before) and len(changed) == 1
    blank = b'"","","",""'
    assert before[changed[0]].endswith(blank)
    assert after[changed[0]] == (before[changed[0]][:-len(blank)]
                                 + b'"other_error","","","a comma, and ""quotes"""')
    assert errors(env.sheet) == []
    assert labels(env.sheet)[IDS[0]] == ['other_error', '', '', 'a comma, and "quotes"']


def write_sheet(path, rows, end='\n'):
    path.parent.mkdir(exist_ok=True)
    text = io.StringIO(newline='')
    writer = csv.DictWriter(text, fieldnames=annotate.COLUMNS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    path.write_bytes((text.getvalue().rstrip('\n') + end).encode('utf-8'))


def test_reordered_copy_without_a_final_newline_keeps_its_shape(env):
    rows = rules.read_sheet(env.source)[::-1]
    write_sheet(env.sheet, rows, end='')
    before = env.sheet.read_bytes().split(b'\n')
    assert before[-1].startswith(b'E03.Q06.A00,')

    # E03.Q06 comes last in this copy; its five rows are offered in the copy's own order.
    code, out = run(env, ['skip'] * 4 + UNJUDGEABLE, '--question', 'E03.Q06')
    assert shown(out) == [row['id'] for row in rows if row['question_id'] == 'E03.Q06']
    after = env.sheet.read_bytes().split(b'\n')
    assert after[:-1] == before[:-1]
    assert after[-1] == before[-1][:-len(b',,,')] + b'insufficient_evidence,,,'
    assert code == 0 and errors(env.sheet) == []


def test_a_row_labeled_elsewhere_that_fails_validation_is_offered_again(env):
    rows = rules.read_sheet(env.source)
    broken = next(row for row in rows if row['id'] == IDS[2])
    broken.update(primary_label='InfiniteExecution', evidence_span='words the student never wrote')
    write_sheet(env.sheet, rows)
    span = broken['student_answer'].split()[0]

    typed = ['skip', 'skip', '', '', '', span, '', '', 'quit']  # keep the label; Enter cannot keep bad evidence
    code, out = run(env, typed, '--first-session')
    assert f'Note: {IDS[2]} is labeled but fails validation' in out
    assert '! fails validation: evidence part is empty or not verbatim in student_answer' in out
    assert shown(out) == list(IDS[:4])
    assert labels(env.sheet)[IDS[2]] == ['InfiniteExecution', '', span, '']
    assert code == 0 and errors(env.sheet) == []
    assert f'labeled 0: - | re-edited 1: {IDS[2]}' in env.log.read_text()


def test_a_sheet_changed_on_disk_is_not_overwritten(env):
    def another_program_saves():
        env.sheet.write_bytes(env.sheet.read_bytes() + b'\n')

    code, out = run(env, ['none', '', '', another_program_saves, ''], '--first-session')
    assert code == 1 and 'NOT SAVED' in out and 'changed on disk' in out
    assert env.sheet.read_bytes() == PILOT_BYTES + b'\n'
    assert not env.log.exists()
    assert not list(env.sheet.parent.glob('.*.tmp'))


# ---- no model in the loop --------------------------------------------------

def test_tool_imports_only_the_standard_library_yaml_and_the_validator():
    tree = ast.parse(Path(annotate.__file__).read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split('.')[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or '').split('.')[0])
    assert imported - set(sys.stdlib_module_names) == {'yaml', 'scripts', 'annotation_sheet'}
