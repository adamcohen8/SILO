"""Developer-authored synthetic oracle; do not alter to hide a failing implementation."""
import unittest
from calculator import capacity


class CapacityTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(capacity([]), 0)

    def test_first_active_row_and_status_filter(self):
        rows = [{'quantity': 4, 'mass_kg': 12, 'status': 'active'},
                {'quantity': 3, 'mass_kg': 20, 'status': 'active'},
                {'quantity': 100, 'mass_kg': 100, 'status': 'retired'}]
        self.assertEqual(capacity(rows), 108)

    def test_negative_first_measurement(self):
        with self.assertRaises(ValueError):
            capacity([{'quantity': -1, 'mass_kg': 12, 'status': 'active'}])

    def test_missing_measurement(self):
        with self.assertRaises(KeyError):
            capacity([{'quantity': 1, 'status': 'active'}])


if __name__ == '__main__':
    unittest.main()
