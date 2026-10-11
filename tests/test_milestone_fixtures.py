import csv
import hashlib
import json
from pathlib import Path
import unittest

from local_ai_appliance.release_bootstrap import permitted

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'tests/fixtures/silo-milestone'


class MilestoneFixtureTests(unittest.TestCase):
    def test_frozen_inputs_and_independent_expected_result(self):
        expected=json.loads((FIXTURES/'expected.json').read_text())
        self.assertEqual(expected['expected_capacity_kg'],108)
        rows=list(csv.DictReader((FIXTURES/'inventory.csv').read_text().splitlines()))
        self.assertEqual([(r['quantity'],r['capacity_kg']) for r in rows if r['status']=='eligible'],[('4','12'),('3','20')])
        self.assertEqual([r['asset_id'] for r in rows if r['status']!='eligible'],expected['excluded_assets'])
        self.assertFalse(expected['execution_implemented'])
        pins=json.loads((FIXTURES/'fixture-manifest.json').read_text())
        for pin in pins['files']:
            self.assertEqual(hashlib.sha256((FIXTURES/pin['path']).read_bytes()).hexdigest(),pin['sha256'])

    def test_only_reviewed_csv_fixtures_enter_source_release(self):
        for name in ('inventory.csv','missing-capacity.csv','invalid-quantity.csv','malformed.csv'):
            permitted('tests/fixtures/silo-milestone/'+name)
        for name in ('tests/private.csv','data/inventory.csv','tests/fixtures/silo-milestone/operational.csv'):
            with self.assertRaises(ValueError): permitted(name)


if __name__=='__main__': unittest.main()
