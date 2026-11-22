#!/usr/bin/env python3
"""Label the annotation pilot by hand, one answer at a time, in the terminal.

    python scripts/annotate.py [--sheet annotation/my_pass.csv] [--first-session]
                               [--question E05.Q03] [--rater NAME]

A typing aid for one human rater. It calls no model and reads no model output:
its only inputs are the sheet, the taxonomy, the frozen identity manifest and
the schema heading. Every label rule is decided by `validate` in
scripts/annotation_sheet.py. This file asks that validator about a candidate
row instead of restating the rules, so the two cannot drift apart.

annotation/pilot_sheet.csv is never written. Labels go to a working copy
(created as an exact copy on first use) that is saved after every completed
row by writing a temporary file and renaming it over the copy. A save rewrites
only the four annotation cells of the edited row; every other byte, including
that row's six source cells, is carried over exactly as it was on disk.

Standard library only, apart from PyYAML, which the validator already needs to
read the taxonomy.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import datetime
import getpass
import io
import json
import os
import re
import shutil
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

import yaml

try:  # imported as scripts.annotate (tests) ...
    from scripts import annotation_sheet as rules
except ImportError:  # ... or run as `python scripts/annotate.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import annotation_sheet as rules

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHEET = rules.SHEET
DEFAULT_SHEET = ROOT / 'annotation/my_pass.csv'
SESSION_LOG = ROOT / 'annotation/session_log.md'
SCHEMA_DOC = ROOT / 'annotation/schema.md'
COLUMNS = rules.FIXED + rules.LABELS
SEPARATOR = ' || '
ELLIPSIS = re.compile(r'\.{3,}|…')

# annotation/README.md, "First session: 14 answers, then pause", in table order.
# tests/test_annotate.py fails if this list and that table ever disagree.
FIRST_SESSION_IDS = (
    'E03.Q06.A01', 'E03.Q06.A00', 'E05.Q04.A03', 'E05.Q04.A06', 'E05.Q03.A02',
    'E05.Q03.A08', 'E10.Q07.A02', 'E10.Q07.A08', 'E12.Q10.A04', 'E12.Q10.A13',
    'E03.Q07.A01', 'E03.Q07.A03', 'E11.Q09.A25', 'E11.Q09.A12',
)

GROUPS = ('Special labels', 'Big-O items', 'Mental models', 'Hamouda 2017 items',
          'ProgMiscon items', 'Other taxonomy items')

HELP = '''\
Commands (at any prompt)
  back     re-edit the previous row
  skip     leave this row as it is and move on
  redo     start this row's prompts again
  show     print the row and the label menu again
  s        show score_avg for this row (only once it has a primary label)
  ?        one line per label;  "? 12"  or  "? BCwrite"  prints description and notes
  help     this text
  quit     stop, validate the sheet, print completed and remaining counts
  \\text    take "text" literally when it would otherwise be read as a command
Labels     the menu number or the id (any capitalisation; the exact id is stored).
Evidence   exact words from the student answer; join separate spans with " || ".
           Shortcut: "first words ... last words" expands to the full span when
           exactly one span of the answer starts and ends that way.
Notes      free text, required for other_error. One line per candidate item:
           Candidate: stable short description
Editing    Enter keeps the value shown in [brackets]; "-" clears it.
Rules      annotation/schema.md, sections 4 to 6. Only you assign labels; this
           tool checks mechanics, not whether the evidence supports the label.'''

LOG_HEADER = '''\
# Annotation session log

One line per `scripts/annotate.py` session that saved at least one row (local
record of rater, date and schema version; see README, "First session", step 1).

'''


class SpanError(ValueError):
    """Typed evidence that cannot be stored as verbatim parts of the answer."""


class SheetChangedError(RuntimeError):
    """The working copy changed on disk behind this session."""


class Back(Exception):
    pass


class Skip(Exception):
    pass


class Redo(Exception):
    pass


class Quit(Exception):
    pass


# --------------------------------------------------------------------------
# Evidence spans
# --------------------------------------------------------------------------

def find_all(text, sub):
    """Every start index of `sub` in `text`, overlapping matches included."""
    i = text.find(sub)
    while i != -1:
        yield i
        i = text.find(sub, i + 1)


def expand_span(part, answer):
    """Return `part` as an exact substring of `answer`, or raise SpanError.

    A part that is already verbatim is returned unchanged. Otherwise
    "first words ... last words" expands to the substring that starts with the
    first words and ends with the last words, but only when exactly one
    substring of the answer does.
    """
    if part in answer:
        return part
    ends = [piece.strip() for piece in ELLIPSIS.split(part)]
    if len(ends) != 2 or not all(ends):
        raise SpanError(f'not verbatim in the student answer: "{part}"')
    first, last = ends
    spans = [(i, j + len(last)) for i in find_all(answer, first)
             for j in find_all(answer, last) if j >= i + len(first)]
    if not spans:
        raise SpanError(f'no part of the student answer starts with "{first}" and ends with "{last}"')
    if len(spans) > 1:
        loose = [name for name, n in (('first', len({i for i, _ in spans})),
                                      ('last', len({j for _, j in spans}))) if n > 1]
        raise SpanError(f'"{first} ... {last}" is ambiguous ({len(spans)} possible spans); '
                        f'type more of the {" and ".join(loose)} words')
    start, end = spans[0]
    return answer[start:end]


def resolve_evidence(text, answer):
    """Typed evidence -> the evidence_span cell: verbatim parts joined by ' || '."""
    parts = []
    for part in text.split('||'):
        part = part.strip()
        if not part:
            raise SpanError('empty span next to "||"')
        parts.append(expand_span(part, answer))
    return SEPARATOR.join(parts)


def sample_span(answer):
    """Some verbatim piece of the answer, used only to ask the validator
    whether evidence is allowed or required for a pair of labels."""
    return next((piece.strip() for piece in answer.split('||') if piece.strip()), '')


# --------------------------------------------------------------------------
# The working copy on disk
# --------------------------------------------------------------------------

def split_records(text):
    """[(raw text, cells)] for every CSV record; a quoted line break stays
    inside its record and each record keeps its own line terminator."""
    lines, taken, records = io.StringIO(text, newline=''), [], []

    def feed():
        for line in lines:
            taken.append(line)
            yield line

    for cells in csv.reader(feed()):
        records.append((''.join(taken), cells))
        taken.clear()
    return records


def split_raw_fields(record):
    """One raw record -> (its raw, still quoted fields, its line terminator)."""
    body = record.rstrip('\r\n')
    fields, start, quoted = [], 0, False
    for i, char in enumerate(body):
        if char == '"':
            quoted = not quoted
        elif char == ',' and not quoted:
            fields.append(body[start:i])
            start = i + 1
    fields.append(body[start:])
    return fields, record[len(body):]


def to_csv(cells, quoting=csv.QUOTE_MINIMAL):
    buffer = io.StringIO(newline='')
    csv.writer(buffer, quoting=quoting, lineterminator='\r\n').writerow(cells)
    return buffer.getvalue()[:-2]  # '\r\n' as terminator makes the writer quote both characters


def parse_csv(text):
    return list(csv.reader(io.StringIO(text, newline='')))


class SheetFile:
    """The working copy. `rows` are the validator's own row dicts; `save`
    writes them back, touching only the annotation cells of rows that changed."""

    def __init__(self, path):
        self.path = Path(path)
        self._bytes = self.path.read_bytes()
        self._records = split_records(self._bytes.decode('utf-8'))
        self.rows = rules.read_sheet(self.path)  # checks the columns and ragged rows
        if [cells for _, cells in self._data()] != self._cells():
            raise ValueError('cannot line up the CSV records with the rows read from the sheet')
        self._source = [[row[k] for k in rules.FIXED] for row in self.rows]

    def _data(self, records=None):
        """Records that are data rows: everything after the header that is not a blank line."""
        return [record for record in (records or self._records)[1:] if record[1]]

    def _cells(self):
        return [[row[k] for k in COLUMNS] for row in self.rows]

    def _render_row(self, raw, row):
        fixed, labels = [row[k] for k in rules.FIXED], [row[k] for k in rules.LABELS]
        fields, terminator = split_raw_fields(raw)
        kept = ','.join(fields[:len(fixed)])
        if len(fields) == len(COLUMNS) and parse_csv(kept) == [fixed]:
            # Keep the raw source cells; write the annotation cells in the row's own quoting style.
            style = csv.QUOTE_ALL if all(f.startswith('"') for f in fields) else csv.QUOTE_MINIMAL
            return kept + ',' + to_csv(labels, style) + terminator
        return to_csv(fixed + labels) + terminator  # unusual quoting: rewrite the whole row

    def render(self):
        rows, out = iter(self.rows), [self._records[0][0]]
        for raw, cells in self._records[1:]:
            row = next(rows) if cells else None
            changed = row is not None and [row[k] for k in rules.LABELS] != cells[len(rules.FIXED):]
            out.append(self._render_row(raw, row) if changed else raw)
        return ''.join(out)

    def save(self):
        """Write the rows to a temporary file and rename it over the working copy."""
        if self.path.read_bytes() != self._bytes:
            raise SheetChangedError(f'{self.path} changed on disk since it was read (is it open in '
                                    'another program?). Nothing was written; start the tool again.')
        text = self.render()
        records = split_records(text)
        if (records[0][0] != self._records[0][0] or [c for _, c in self._data(records)] != self._cells()
                or [[row[k] for k in rules.FIXED] for row in self.rows] != self._source):
            raise RuntimeError('refusing to save: the sheet would not read back as edited (this is a bug)')
        data = text.encode('utf-8')
        handle, temp = tempfile.mkstemp(dir=self.path.parent, prefix=f'.{self.path.name}.', suffix='.tmp')
        try:
            with os.fdopen(handle, 'wb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            shutil.copymode(self.path, temp)
            os.replace(temp, self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(temp)
            raise
        self._bytes, self._records = data, records


# --------------------------------------------------------------------------
# Labels
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Label:
    number: int
    id: str
    group: str
    provisional: bool
    description: str
    notes: str
    facts: str


def group_of(item):
    source = str(item.get('source', '')).lower()
    if item.get('concept') == 'big_o':
        return GROUPS[1]
    if item.get('kind') == 'mental_model':
        return GROUPS[2]
    if 'hamouda' in source:
        return GROUPS[3]
    if 'progmiscon' in source:
        return GROUPS[4]
    return GROUPS[5]


def build_catalog(taxonomy):
    """Every valid label, numbered in menu order."""
    entries = [(GROUPS[0], s['id'], False, s.get('definition', ''), '', 'special label')
               for s in taxonomy['special_labels']]
    for item in taxonomy['items']:
        facts = [item.get('kind', ''), item.get('status', ''),
                 'observable in ' + ', '.join(item.get('observable_in', []))]
        entries.append((group_of(item), item['id'], item.get('status') == 'provisional',
                        item.get('description', ''), item.get('notes', ''), '; '.join(filter(None, facts))))
    entries.sort(key=lambda entry: GROUPS.index(entry[0]))  # stable: taxonomy order inside a group
    return [Label(number, ident, group, provisional, ' '.join(description.split()), ' '.join(notes.split()), facts)
            for number, (group, ident, provisional, description, notes, facts) in enumerate(entries, 1)]


def in_columns(cells, width, indent=3, gap=2):
    cell = max(len(c) for c in cells) + gap
    per_line = max(1, (width - indent) // cell)
    return [(' ' * indent + ''.join(c.ljust(cell) for c in cells[i:i + per_line])).rstrip()
            for i in range(0, len(cells), per_line)]


# --------------------------------------------------------------------------
# The interactive session
# --------------------------------------------------------------------------

class Session:
    def __init__(self, sheet, taxonomy, identity, *, stdin, stdout, width):
        self.sheet, self.taxonomy, self.identity = sheet, taxonomy, identity
        self.stdin, self.stdout, self.width = stdin, stdout, width
        self.catalog = build_catalog(taxonomy)
        self.by_number = {label.number: label for label in self.catalog}
        self.by_name = {label.id.lower(): label for label in self.catalog}
        self.queue, self.batch = [], ''
        self.labeled_before = {row['id'] for row in sheet.rows if row['primary_label']}
        self.saved = []  # ids saved in this session, in order

    # ---- input and output -------------------------------------------------

    def say(self, text=''):
        try:
            self.stdout.write(text + '\n')
        except UnicodeEncodeError:
            encoding = getattr(self.stdout, 'encoding', None) or 'ascii'
            self.stdout.write(text.encode(encoding, 'replace').decode(encoding) + '\n')

    def read(self, prompt):
        if self.stdin is sys.stdin and self.stdout is sys.stdout:
            return input(prompt)  # line editing when the readline module is loaded
        self.stdout.write(prompt)
        self.stdout.flush()
        line = self.stdin.readline()
        if not line:
            raise EOFError
        line = line.rstrip('\r\n')
        self.say(line)  # echo, so a transcript of injected input reads like a terminal
        return line

    def block(self, title, text):
        self.say(title)
        self.say(textwrap.fill(text, self.width, initial_indent='  ', subsequent_indent='  ',
                               break_on_hyphens=False) or '  (empty)')

    def ask(self, prompt, row, draft, free_text=False):
        """Read one answer, handling the commands that work at every prompt."""
        while True:
            try:
                text = self.read(prompt).strip()
            except EOFError:
                self.say()
                raise Quit from None
            if text.startswith('\\'):
                return text[1:].strip()
            word = text.lower()
            if word in ('quit', 'exit'):
                raise Quit
            if word == 'back':
                raise Back
            if word == 'skip':
                raise Skip
            if word == 'redo':
                raise Redo
            if word == 'help':
                self.say(HELP)
            elif word == 'show':
                self.show(row)
            elif word == 's':
                self.show_score(row, draft)
            elif text.startswith('?') and (self.lookup(text[1:].strip(), quiet=free_text) or not free_text):
                pass
            else:
                return text

    # ---- what the validator says ------------------------------------------

    def problems(self, row, primary, secondary='', evidence='', notes=''):
        """The project validator's objections if this row carried these annotations."""
        trial = dict(row, primary_label=primary, secondary_label=secondary,
                     evidence_span=evidence, annotator_notes=notes)
        frozen = {'rows': {row['id']: self.identity['rows'][row['id']]}}
        prefix = row['id'] + ': '
        found = rules.validate([trial], self.taxonomy, frozen)
        return list(dict.fromkeys(e[len(prefix):] if e.startswith(prefix) else e for e in found))

    def label_problems(self, row, primary, secondary=''):
        """Objections to the labels themselves, with evidence and notes filled
        in whichever way the validator likes best."""
        span = sample_span(row['student_answer'])
        return min((self.problems(row, primary, secondary, evidence, 'x') for evidence in (span, '')), key=len)

    def evidence_rule(self, row, primary, secondary):
        span = sample_span(row['student_answer'])
        allowed = bool(span) and not self.problems(row, primary, secondary, span, 'x')
        required = bool(self.problems(row, primary, secondary, '', 'x'))
        return allowed, required

    def pending(self, row):
        """Unlabeled, or labeled outside this tool in a way the validator rejects."""
        return not row['primary_label'] or bool(self.problems(row, *(row[k] for k in rules.LABELS)))

    # ---- display ----------------------------------------------------------

    def tag(self, label_id):
        label = self.by_name.get(label_id.lower())
        return label_id + (' (provisional)' if label and label.provisional else '')

    def menu(self, row):
        self.say('Labels    * provisional    (n/a) not a valid primary for this row')
        for group in GROUPS:
            members = [label for label in self.catalog if label.group == group]
            if not members:
                continue
            self.say(f' {group}' + (' (all provisional)' if all(m.provisional for m in members) else ''))
            cells = [f'{m.number:>2} {m.id}{"*" if m.provisional else ""}'
                     f'{" (n/a)" if self.label_problems(row, m.id) else ""}' for m in members]
            for line in in_columns(cells, self.width):
                self.say(line)

    def values(self, values):
        primary, secondary, evidence, notes = (values[k] for k in rules.LABELS)
        self.say(f'  primary    {self.tag(primary) if primary else "-"}')
        self.say(f'  secondary  {self.tag(secondary) if secondary else "-"}')
        self.say(f'  evidence   {evidence or "-"}')
        self.say('  notes      ' + ('\n             '.join(notes.splitlines()) or '-'))

    def show(self, row):
        done = sum(bool(r['primary_label']) for r in self.sheet.rows)
        place = f'{self.batch} {self.queue.index(row) + 1}/{len(self.queue)}' if row in self.queue else ''
        self.say()
        self.say('-' * self.width)
        self.say(f'{row["id"]}    {place}    {done} of {len(self.sheet.rows)} labeled')
        self.block('Question', row['question'])
        self.block('Instructor answer', row['instructor_answer'])
        self.block('Student answer', row['student_answer'])
        if any(row[k] for k in rules.LABELS):
            self.say('Currently on this row')
            self.values(row)
            for problem in self.problems(row, *(row[k] for k in rules.LABELS)) if row['primary_label'] else ():
                self.say(f'  ! fails validation: {problem}')
        self.say()
        self.menu(row)

    def show_score(self, row, draft):
        if draft['primary_label']:
            self.say(f'  score_avg: {row["score_avg"]}   (rubric match, not a label; only to catch a misreading)')
        else:
            self.say('  The score stays hidden until this row has a primary label.')

    def lookup(self, query, quiet=False):
        """`?` lists every label; `? <number or id>` prints one. True if it printed."""
        if not query:
            pad = max(len(label.id) for label in self.catalog)
            room = max(20, self.width - pad - 5)
            for label in self.catalog:
                text = label.description
                if len(text) > room:
                    text = text[:room - 4].rsplit(' ', 1)[0] + ' ...'
                self.say(f'{label.number:>2} {label.id:<{pad}}  {text}')
            return True
        label = self.resolve(query)
        if label is None:
            if not quiet:
                self.say(f'  "{query}" is not a label number or id.')
            return False
        self.say(f'{label.number} {label.id}   [{label.group}; {label.facts}]')
        self.block(' Description', label.description)
        if label.notes:
            self.block(' Notes', label.notes)
        return True

    # ---- prompts ----------------------------------------------------------

    def resolve(self, text):
        if text.isdigit():
            return self.by_number.get(int(text))
        return self.by_name.get(text.lower())

    def ask_label(self, column, prompt, row, draft, check, optional):
        """Read a label for `column`; `check(label_id)` returns the validator's objections."""
        current = draft[column]
        while True:
            text = self.ask(prompt, row, draft)
            if text == '-' and optional:
                chosen = ''
            elif not text:
                chosen = current
            else:
                label = self.resolve(text)
                if label is None:
                    self.say(f'  "{text}" is not a label. Type a number from 1 to {len(self.catalog)} or an id.')
                    continue
                chosen = label.id
            if not chosen and not optional:
                self.say('  A primary label is required. Type a number or an id, or "skip" to leave this row.')
                continue
            if chosen and (objections := check(chosen)):
                self.say(f'  {chosen} cannot go here: {"; ".join(objections)}')
                continue
            draft[column] = chosen
            self.say(f'  -> {column.split("_")[0]}: {self.tag(chosen) if chosen else "-"}')
            return chosen

    def ask_primary(self, row, draft):
        current = draft['primary_label']
        prompt = f'primary label [{current}] > ' if current else 'primary label (number or id) > '
        self.ask_label('primary_label', prompt, row, draft, lambda p: self.label_problems(row, p), optional=False)

    def ask_secondary(self, row, draft):
        primary = draft['primary_label']
        allowed = [m.id for m in self.catalog if not self.label_problems(row, primary, m.id)]
        if draft['secondary_label'] not in allowed:
            draft['secondary_label'] = ''
        if not allowed:
            return
        current = draft['secondary_label']
        only = f'; only {", ".join(allowed)} allowed with {primary}' if len(allowed) <= 3 else ''
        prompt = (f'secondary label [{current}] (- clears{only}) > ' if current
                  else f'secondary label (Enter = none{only}) > ')
        self.ask_label('secondary_label', prompt, row, draft,
                       lambda s: self.label_problems(row, primary, s), optional=True)

    def ask_evidence(self, row, draft):
        primary, secondary, answer = draft['primary_label'], draft['secondary_label'], row['student_answer']
        allowed, required = self.evidence_rule(row, primary, secondary)
        if not allowed:
            draft['evidence_span'] = ''
            return
        current = draft['evidence_span']
        if current and self.problems(row, primary, secondary, current, 'x'):
            current = ''
        self.say('  Exact words from the answer; " || " joins spans; "first ... last" expands.')
        need = 'required' if required else 'optional, Enter = none'
        prompt = (f'evidence span [Enter keeps the current one{"" if required else "; - clears"}] > ' if current
                  else f'evidence span ({need}) > ')
        while True:
            text = self.ask(prompt, row, draft, free_text=True)
            try:
                evidence = current if not text else '' if text == '-' else resolve_evidence(text, answer)
            except SpanError as error:
                objections = [str(error)]
            else:
                objections = self.problems(row, primary, secondary, evidence, 'x')
            if objections:
                self.say(f'  Not accepted: {"; ".join(objections)}')
                self.block('Student answer', answer)
                continue
            draft['evidence_span'] = evidence
            self.say(f'  -> evidence: {evidence or "-"}')
            return

    def ask_notes(self, row, draft):
        labels = draft['primary_label'], draft['secondary_label'], draft['evidence_span']
        required = bool(self.problems(row, *labels, ''))
        current = draft['annotator_notes']
        need = 'required: say what the error is' if required else 'Enter = none'
        prompt = (f'notes [Enter keeps the current notes{"" if required else "; - clears"}] > ' if current
                  else f'notes ({need}) > ')
        while True:
            text = self.ask(prompt, row, draft, free_text=True)
            if text and text != '-':
                lines = [text]
                while more := self.ask('  next line of notes (Enter = done) > ', row, draft, free_text=True):
                    lines.append(more)
                notes = '\n'.join(lines)
            else:
                notes = '' if text == '-' else current
            if objections := self.problems(row, *labels, notes):
                self.say(f'  Not accepted: {"; ".join(objections)}')
                continue
            draft['annotator_notes'] = notes
            return

    def confirm(self, row, draft):
        """Show the finished row; save on Enter. False means edit it again."""
        self.say(f'{row["id"]} will be saved as')
        self.values(draft)
        while True:
            text = self.ask('Enter = save and go on, e = edit again, s = show score > ', row, draft).lower()
            if text in ('e', 'edit'):
                return False
            if text:
                self.say('  Press Enter to save, or type e, s, back, skip or quit.')
                continue
            if objections := self.problems(row, *(draft[k] for k in rules.LABELS)):
                self.say(f'  Not saved: {"; ".join(objections)}')
                return False
            before = {k: row[k] for k in rules.LABELS}
            row.update(draft)
            try:
                self.sheet.save()
            except BaseException:
                row.update(before)
                raise
            if row['id'] not in self.saved:
                self.saved.append(row['id'])
            done = sum(bool(r['primary_label']) for r in self.sheet.rows)
            self.say(f'  saved {row["id"]}   ({done} of {len(self.sheet.rows)} labeled)')
            return True

    # ---- the loop ---------------------------------------------------------

    def edit(self, row):
        draft = {k: row[k] for k in rules.LABELS}
        while True:
            self.show(row)
            try:
                self.ask_primary(row, draft)
                self.ask_secondary(row, draft)
                self.ask_evidence(row, draft)
                self.ask_notes(row, draft)
                if self.confirm(row, draft):
                    return
            except Redo:
                pass

    def next_pending(self, start):
        return next((i for i in range(start, len(self.queue)) if self.pending(self.queue[i])), None)

    def run(self, queue, batch):
        """Walk the queue from its first pending row. Returns True if the queue ran out."""
        self.queue, self.batch = queue, batch
        position, handled = self.next_pending(0), set()
        while position is not None:
            row = self.queue[position]
            try:
                self.edit(row)
            except Back:
                # The nearest earlier row handled in this session, else the row before in the queue.
                earlier = max((p for p in handled if p < position), default=position - 1)
                if earlier < 0:
                    self.say('  This is the first row; there is nothing to go back to.')
                else:
                    position = earlier
                continue
            except Skip:
                self.say(f'  skipped {row["id"]} (left as it was)')
            except Quit:
                return False
            handled.add(position)
            position = self.next_pending(position + 1)
        return True


# --------------------------------------------------------------------------
# Session bookkeeping
# --------------------------------------------------------------------------

def display(path):
    with contextlib.suppress(ValueError):
        return str(Path(path).relative_to(Path.cwd()))
    return str(path)


def is_same_file(a, b):
    a, b = Path(a), Path(b)
    if a.resolve() == b.resolve():
        return True
    with contextlib.suppress(OSError):
        return a.exists() and b.exists() and os.path.samefile(a, b)
    return False


def schema_version(rows, taxonomy):
    with contextlib.suppress(OSError, IndexError):
        heading = SCHEMA_DOC.read_text(encoding='utf-8').splitlines()[0]
        if match := re.search(r'\(v(\d+(?:\.\d+)*)', heading):
            return match.group(1)
    return rules.report(rows, taxonomy)['schema_version']


def last_rater(log):
    with contextlib.suppress(OSError):
        found = re.findall(r'^- .*?\| rater: (.+?) \|', Path(log).read_text(encoding='utf-8'), flags=re.M)
        return found[-1] if found else ''
    return ''


def append_log(log, rater, version, sheet_path, labeled, re_edited):
    """One line for this session: date, rater, schema version, ids."""
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    existing = log.read_text(encoding='utf-8') if log.exists() else None
    parts = [datetime.date.today().isoformat(), f'rater: {rater}', f'schema v{version}',
             f'sheet: {display(sheet_path)}', f'labeled {len(labeled)}: {", ".join(labeled) or "-"}']
    if re_edited:
        parts.append(f're-edited {len(re_edited)}: {", ".join(re_edited)}')
    with log.open('a', encoding='utf-8') as f:
        if existing is None:
            f.write(LOG_HEADER)
        elif existing and not existing.endswith('\n'):
            f.write('\n')
        f.write('- ' + ' | '.join(parts) + '\n')


def build_queues(rows, question):
    """(the first-session rows in README order, all rows grouped by question)."""
    rows = [row for row in rows if not question or row['question_id'] == question]
    by_id = {row['id']: row for row in rows}
    questions = list(dict.fromkeys(row['question_id'] for row in rows))
    return ([by_id[i] for i in FIRST_SESSION_IDS if i in by_id],
            [row for q in questions for row in rows if row['question_id'] == q])


def validate_sheet(path, taxonomy, identity):
    """The checks `python scripts/annotation_sheet.py <path>` runs, as (ok, message, rows)."""
    try:
        rows = rules.read_sheet(path)
        errors = rules.validate(rows, taxonomy, identity)
        if errors:
            raise ValueError('\n'.join(errors))
    except (OSError, ValueError, csv.Error) as exc:
        return False, f'FAIL: {exc}', None
    return True, f'OK: {len(rows)} rows, {sum(bool(r["primary_label"]) for r in rows)} completed', rows


def main(argv=None, stdin=None, stdout=None, *, source=None, width=None):
    """Run one labeling session. Streams, the source sheet and the wrap width can be injected."""
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    source = Path(source or SOURCE_SHEET)
    parser = argparse.ArgumentParser(
        description='Label the annotation pilot by hand (no model calls, no model output).',
        epilog='Type "help" at any prompt for the commands. Rules: annotation/schema.md.')
    parser.add_argument('--sheet', type=Path, default=DEFAULT_SHEET,
                        help='working copy to label; created as an exact copy of the pilot sheet if missing '
                             '(default: annotation/my_pass.csv)')
    parser.add_argument('--first-session', action='store_true',
                        help='present the 14 calibration ids from annotation/README.md first, then stop')
    parser.add_argument('--question', metavar='ID', help='only rows of one question, e.g. E05.Q03')
    parser.add_argument('--rater', metavar='NAME', help='your name for the session log (asked if omitted)')
    parser.add_argument('--log', type=Path, default=SESSION_LOG,
                        help='session log to append to (default: annotation/session_log.md)')
    args = parser.parse_args(argv)

    def say(text=''):
        stdout.write(text + '\n')

    sheet_path = args.sheet.expanduser().resolve()
    if is_same_file(sheet_path, source) or is_same_file(sheet_path, SOURCE_SHEET):
        say(f'Refusing to label {display(sheet_path)}: the original pilot sheet is never written. '
            f'Use a working copy, e.g. --sheet {display(DEFAULT_SHEET)}')
        return 2
    try:
        if not sheet_path.exists():
            sheet_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, sheet_path)
            say(f'Created working copy {display(sheet_path)} (exact copy of {display(source)}).')
        taxonomy = yaml.safe_load(rules.TAXONOMY.read_text(encoding='utf-8'))
        identity = json.loads(rules.IDENTITY.read_text(encoding='utf-8'))
        sheet = SheetFile(sheet_path)
        blank = [dict(row, **dict.fromkeys(rules.LABELS, '')) for row in sheet.rows]
        if damage := rules.validate(blank, taxonomy, identity):
            raise ValueError('\n'.join(damage))
    except (OSError, ValueError, csv.Error, yaml.YAMLError) as exc:
        say(f'FAIL: {exc}')
        say(f'Not editing {display(sheet_path)}: it must hold the 63 frozen pilot rows with unchanged source cells.')
        return 1

    questions = list(dict.fromkeys(row['question_id'] for row in sheet.rows))
    if args.question and args.question not in questions:
        parser.error(f'--question must be one of: {", ".join(questions)}')

    if stdin is sys.stdin and stdout is sys.stdout:
        with contextlib.suppress(ImportError):
            import readline  # noqa: F401  (line editing for input())
    session = Session(sheet, taxonomy, identity, stdin=stdin, stdout=stdout,
                      width=max(40, min(width or shutil.get_terminal_size((80, 24)).columns, 100)))

    rater = ' '.join((args.rater or '').replace('|', '/').split())
    try:
        while not rater:
            suggestion = last_rater(args.log)
            with contextlib.suppress(Exception):
                suggestion = suggestion or getpass.getuser()
            typed = session.read(f'Rater name [{suggestion}] > ' if suggestion else 'Rater name > ')
            rater = ' '.join((typed or suggestion).replace('|', '/').split())
    except (EOFError, KeyboardInterrupt):
        say()
        return 1

    calibration, grouped = build_queues(sheet.rows, args.question)
    first = args.first_session and any(session.pending(row) for row in calibration)
    queue, batch = (calibration, 'first session') if first else (grouped, 'row')
    version = schema_version(sheet.rows, taxonomy)
    say(f'Pilot annotation, schema v{version}. Rater: {rater}. Sheet: {display(sheet_path)}')
    say('Human labels only: this tool calls no model and shows no model output.')
    for row in sheet.rows:
        if row['primary_label'] and session.pending(row):
            say(f'Note: {row["id"]} is labeled but fails validation; it is queued for re-editing.')
    if args.first_session and not first:
        say('The first-session ids are already labeled; continuing with the remaining rows by question.')
    waiting = sum(session.pending(row) for row in queue)
    say(f'{waiting} of {len(queue)} rows in this batch still need a label. Type "help" for commands.')

    failed = False
    try:
        finished = session.run(queue, batch)
    except KeyboardInterrupt:
        finished = False
        say('\nInterrupted.')
    except (SheetChangedError, OSError, RuntimeError) as exc:
        finished, failed = False, True
        say(f'\nNOT SAVED: {exc}')

    say()
    if finished and first and not any(session.pending(row) for row in calibration):
        say(f'First-session batch complete ({len(calibration)} of {len(calibration)}). Pause here (README step 4): '
            'review ambiguous rows and candidate notes before going on.')
        say(f'  python scripts/annotation_sheet.py {display(sheet_path)} --report')
    elif finished:
        say('End of this batch.' + ('' if not sum(session.pending(row) for row in queue)
                                    else ' Skipped rows come up first next time.'))
    labeled = [i for i in session.saved if i not in session.labeled_before]
    re_edited = [i for i in session.saved if i in session.labeled_before]
    say(f'Saved this session: {len(session.saved)}' + (f' ({", ".join(session.saved)})' if session.saved else ''))
    if session.saved:
        try:
            append_log(args.log, rater, version, sheet_path, labeled, re_edited)
            say(f'Session logged in {display(args.log)}')
        except OSError as exc:
            say(f'Could not write the session log {display(args.log)}: {exc}')
    ok, message, rows = validate_sheet(sheet_path, taxonomy, identity)
    say(f'Validation of {display(sheet_path)}: {message}')
    if rows is not None:
        progress = rules.report(rows, taxonomy)
        say(f'Completed {progress["completed"]}, remaining {progress["remaining"]} of {progress["total"]}.')
    return 0 if ok and not failed else 1


if __name__ == '__main__':
    sys.exit(main())
