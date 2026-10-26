import sys
import unittest
from datetime import date
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from depreciation import Asset, Valuation, depreciate, months_in_service, revalue  # noqa: E402

YE = date(2025, 12, 31)


class MonthsInService(unittest.TestCase):
    def test_start_month_counts_in_full(self):
        self.assertEqual(months_in_service(date(2025, 3, 31), date(2025, 3, 31)), 1)

    def test_across_years(self):
        self.assertEqual(months_in_service(date(2020, 7, 15), YE), 66)

    def test_not_yet_in_service(self):
        self.assertEqual(months_in_service(date(2026, 1, 1), YE), 0)


class Depreciate(unittest.TestCase):
    def test_building_land_is_excluded_and_not_counted_twice(self):
        # Golden values worked out by hand: base 1,000,000 over 600 months.
        a = Asset("B-1", "building", D("1200000"), date(2020, 7, 15),
                  land_value=D("200000"), residual=D("50000"), useful_life=50)
        r = depreciate(a, YE)
        self.assertEqual(r.accumulated, D("110000.00"))      # 66 months
        self.assertEqual(r.charge_for_year, D("20000.00"))   # 66 - 54 months
        self.assertEqual(r.net_book_value, D("1090000.00"))
        self.assertIn("land acts as residual", r.memo["base_rule"])

    def test_half_up_to_the_cent(self):
        # 12.30 / 12 = 1.025 -> 1.03 half up; banker's rounding would give 1.02,
        # and float round(1.025, 2) gives 1.02 too (1.025 is 1.02499... in binary).
        a = Asset("V-1", "vehicle", D("12.30"), date(2025, 3, 10), useful_life=1)
        self.assertEqual(depreciate(a, date(2025, 3, 31)).accumulated, D("1.03"))
        self.assertEqual(round(1.025, 2), 1.02)

    def test_fully_depreciated_stops_at_residual(self):
        a = Asset("V-2", "vehicle", D("30000"), date(2010, 1, 1), residual=D("3000"))
        r = depreciate(a, YE)
        self.assertEqual((r.accumulated, r.charge_for_year, r.net_book_value),
                         (D("27000.00"), D("0.00"), D("3000.00")))

    def test_accounting_rule_beats_data_gap(self):
        r = depreciate(Asset("H-1", "heritage", D("5000"), None), YE)
        self.assertFalse(r.depreciable)
        self.assertIn("heritage", r.memo["rule"])

    def test_not_owned(self):
        r = depreciate(Asset("C-1", "building", D("1000"), date(2020, 1, 1), owned=False), YE)
        self.assertFalse(r.depreciable)

    def test_memo_records_where_useful_life_came_from(self):
        a = Asset("F-1", "furniture", D("1200"), date(2025, 1, 1))
        self.assertEqual(depreciate(a, YE).memo["useful_life_source"], "default by category")
        r = depreciate(a, YE, tenant_lives={"furniture": 5})
        self.assertEqual(r.memo["useful_life_source"], "tenant table")
        self.assertEqual(r.accumulated, D("240.00"))

    def test_loaded_balance_from_approved_closing_is_respected(self):
        a = Asset("M-1", "equipment", D("1000"), date(2020, 1, 1),
                  loaded_accumulated=D("612.34"))
        r = depreciate(a, YE)
        self.assertEqual((r.accumulated, r.net_book_value), (D("612.34"), D("387.66")))
        self.assertEqual(r.memo["balance_source"], "loaded from approved closing")


class Revalue(unittest.TestCase):
    COEF = {2024: D("1.02"), 2025: D("1.03")}
    START = Valuation(D("100000"), D("20000"), 50, 2023)

    def test_one_year_revalues_accumulated_before_adding_the_charge(self):
        v = revalue(self.START, self.COEF, 2024)
        # 20,000 x 1.02 + 102,000 / 50 = 20,400 + 2,040. Forgetting to revalue
        # the accumulated balance would give 22,040: 400 off on one asset.
        self.assertEqual((v.replacement_cost, v.accumulated), (D("102000.00"), D("22440.00")))

    def test_applies_each_missing_year_once(self):
        v = revalue(self.START, self.COEF, 2025)
        self.assertEqual((v.replacement_cost, v.accumulated, v.net, v.revalued_through),
                         (D("105060.00"), D("25214.40"), D("79845.60"), 2025))

    def test_running_twice_does_not_compound(self):
        once = revalue(self.START, self.COEF, 2025)
        self.assertEqual(revalue(once, self.COEF, 2025), once)

    def test_accumulated_never_exceeds_cost(self):
        v = revalue(Valuation(D("1000"), D("995"), 10, 2023), self.COEF, 2024)
        self.assertEqual(v.accumulated, v.replacement_cost)

    def test_missing_coefficient_is_an_error_not_a_skip(self):
        with self.assertRaises(KeyError):
            revalue(Valuation(D("100000"), D("0"), 50, 2022), self.COEF, 2025)


if __name__ == "__main__":
    unittest.main()
