import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reconcile import Row, reconcile, totals  # noqa: E402

LEGACY = [
    Row("A-1", "211", D("1000.00"), D("400.00")),
    Row("A-2", "211", D("500.00"), D("100.00")),
    Row("V-1", "218", D("20000.00"), D("8000.00")),
]


class Reconcile(unittest.TestCase):
    def setUp(self):
        self.legacy_totals = totals(LEGACY)
        self.legacy_rows = {r.asset_id: r for r in LEGACY}

    def test_identical_migration_reconciles(self):
        self.assertEqual(reconcile(list(LEGACY), self.legacy_totals, self.legacy_rows), [])

    def test_one_cent_is_a_mismatch_and_names_the_asset(self):
        ours = [LEGACY[0], Row("A-2", "211", D("500.00"), D("100.01")), LEGACY[2]]
        issues = reconcile(ours, self.legacy_totals, self.legacy_rows)
        self.assertEqual({(i.account, i.metric) for i in issues},
                         {("211", "accumulated"), ("211", "net")})
        self.assertEqual(issues[0].delta, D("0.01"))
        self.assertEqual(issues[0].suspects, ["A-2"])

    def test_asset_loaded_twice(self):
        ours = list(LEGACY) + [Row("A-1b", "211", D("1000.00"), D("400.00"))]
        issues = reconcile(ours, self.legacy_totals, self.legacy_rows)
        self.assertTrue(all(i.suspects == ["A-1b"] for i in issues))

    def test_missing_account_is_reported(self):
        issues = reconcile(LEGACY[:2], self.legacy_totals, self.legacy_rows)
        self.assertEqual({i.account for i in issues}, {"218"})


if __name__ == "__main__":
    unittest.main()
