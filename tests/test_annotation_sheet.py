"""Synthetic annotation fixtures exercise mechanics; these are not human gold."""
import copy
import json
import tempfile
from pathlib import Path
import unittest

import yaml
from scripts import annotation_sheet as a


class SheetTests(unittest.TestCase):
    def setUp(self):
        self.rows = a.read_sheet(a.SHEET)
        self.tax = yaml.safe_load(a.TAXONOMY.read_text())
        self.identity = json.loads(a.IDENTITY.read_text())

    def errors(self, complete=False):
        return a.validate(self.rows, self.tax, self.identity, complete)

    def label(self, p, s='', evidence='', notes=''):
        self.rows[0].update(zip(a.LABELS, [p, s, evidence, notes]))

    def test_original_pilot(self):
        self.assertEqual(self.errors(), [])
        self.assertEqual(len(self.rows), 63)
        self.assertEqual(sum(float(r['score_avg']) < 3.5 for r in self.rows), 43)
        self.assertEqual(len(self.errors(True)), 63)

    def test_completed_sheet(self):
        for r in self.rows:
            r['primary_label'] = 'none'
        self.assertEqual(self.errors(True), [])

    def test_closed_labels_and_secondary_rules(self):
        for p, s in [('typo', ''), ('none', 'none'), ('other_error', 'insufficient_evidence'),
                     ('MMcopies', ''), ('none', 'MMlooping'), ('insufficient_evidence', 'MMcopies'),
                     ('RecursiveMethodNeedsIfElse', 'RecursiveFunctionNeedsIfElse')]:
            with self.subTest(p=p, s=s):
                self.label(p, s, self.rows[0]['student_answer'], 'explanation')
                self.assertTrue(self.errors())

    def test_required_evidence_and_notes(self):
        self.label('InfiniteExecution')
        self.assertTrue(self.errors())
        self.label('other_error')
        self.assertTrue(self.errors())
        self.label('other_error', notes='wrong cause')
        self.assertEqual(self.errors(), [])
        self.label('none', 'MMcopies')
        self.assertTrue(self.errors())
        self.label('none', 'MMcopies', self.rows[0]['student_answer'])
        self.assertEqual(self.errors(), [])

    def test_verbatim_multiple_spans(self):
        answer = self.rows[0]['student_answer']
        self.label('InfiniteExecution', evidence=answer[:20] + ' || ' + answer[-20:])
        self.assertEqual(self.errors(), [])
        for span in ['fabricated words', answer[:20] + ' || ', '||', answer.upper()]:
            self.label('InfiniteExecution', evidence=span)
            self.assertTrue(self.errors())
        self.label('none', evidence=answer)
        self.assertTrue(self.errors())

    def test_recall_eligibility(self):
        for p in ['GlobalVariable', 'BFneverExecute', 'BCwrite']:
            self.label(p, evidence=self.rows[0]['student_answer'])
            self.assertTrue(self.errors())

    def test_drafts(self):
        self.label('', notes='revisit this answer')
        self.assertEqual(self.errors(), [])
        self.label('', evidence='anything')
        self.assertTrue(self.errors())

    def test_identity_changes_duplicates_missing_unknown(self):
        original = copy.deepcopy(self.rows)
        self.rows.reverse()
        self.assertEqual(self.errors(), [])
        for field in a.FIXED:
            self.rows = copy.deepcopy(original)
            self.rows[0][field] += 'changed'
            self.assertTrue(self.errors(), field)
        self.rows = original + [original[0]]
        self.assertTrue(self.errors())
        self.rows = original[1:]
        self.assertTrue(self.errors())

    def test_csv_structure(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'sheet.csv'
            for contents in ['id\nx\n', ','.join(a.FIXED + a.LABELS) + '\nx\n',
                             ','.join(a.FIXED + a.LABELS) + '\n' + ','.join(['x'] * 11)]:
                path.write_text(contents)
                with self.assertRaises(ValueError):
                    a.read_sheet(path)

    def test_blank_report(self):
        report = a.report(self.rows, self.tax)
        self.assertEqual((report['completed'], report['remaining']), (0, 63))
        low = report['low_scorers']
        self.assertEqual(low['other_error_share_all_43'], 0)
        self.assertIsNone(low['other_error_share_completed'])
        self.assertEqual(low['possible_final_share'], [0, 1])
        self.assertEqual(low['decision'], 'pending')
        self.assertEqual(len(report['zero_any_taxonomy_ids']), 28)

    def test_distribution_and_threshold(self):
        low = [r for r in self.rows if float(r['score_avg']) < 3.5]
        for r in low[:21]:
            r['primary_label'] = 'other_error'
            r['annotator_notes'] = 'Candidate: new issue\nneeds review'
        high = next(r for r in self.rows if float(r['score_avg']) >= 3.5)
        high.update(primary_label='none', secondary_label='MMcopies', evidence_span=high['student_answer'])
        self.assertEqual(self.errors(), [])
        report = a.report(self.rows, self.tax)
        self.assertEqual(report['completed'], 22)
        self.assertEqual(report['candidate_counts'], {'new issue': 21})
        self.assertEqual(report['secondary_counts'], {'MMcopies': 1})
        self.assertNotIn('MMcopies', report['zero_any_taxonomy_ids'])
        self.assertEqual(report['low_scorers']['decision'], 'pending')
        low[21].update(primary_label='other_error', annotator_notes='wrong claim')
        report = a.report(self.rows, self.tax)
        self.assertEqual(report['low_scorers']['decision'], 'supplement required')
        self.assertAlmostEqual(report['low_scorers']['other_error_share_all_43'], 22 / 43)
        self.assertEqual(report['low_scorers']['other_error_share_completed'], 1)
        low[-1].update(primary_label='BOsearchLinearScan', evidence_span=low[-1]['student_answer'])
        self.assertIn(low[-1]['id'], a.report(self.rows, self.tax)['provisional_big_o_rows'])
        for r in low:
            r.update(primary_label='none', annotator_notes='', evidence_span='')
        self.assertEqual(a.report(self.rows, self.tax)['low_scorers']['decision'], 'threshold not exceeded')


if __name__ == '__main__':
    unittest.main()
