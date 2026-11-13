from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from equitylab.storage import Database, ImportValidationError


CSV = """date,raw_close,adjusted_close,dividend
2024-01-02,296.52,286.41,0
2024-04-01,282.84,274.59,1.67
"""


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.database = Database(Path(self.temporary.name) / "equitylab.sqlite3")
        self.database.initialize()

    def tearDown(self):
        self.temporary.cleanup()

    def test_price_import_is_idempotent_and_updates_existing_rows(self):
        first = self.database.import_prices("mcd", "vendor export", CSV)
        self.assertEqual(first, {"imported": 2, "inserted": 2, "updated": 0})

        changed = CSV.replace("282.84", "283.00")
        second = self.database.import_prices("MCD", "vendor export", changed)
        self.assertEqual(second, {"imported": 2, "inserted": 0, "updated": 2})
        prices = self.database.list_prices("MCD", "vendor export")
        self.assertEqual(len(prices), 2)
        self.assertEqual(prices[1]["raw_close"], "283.00")

    def test_import_rejects_bad_rows_without_partial_writes(self):
        bad = CSV + "not-a-date,10,10,0\n"
        with self.assertRaisesRegex(ImportValidationError, "date must use"):
            self.database.import_prices("MCD", "vendor", bad)
        self.assertEqual(self.database.list_prices("MCD"), [])

    def test_scenario_save_updates_by_name(self):
        first = self.database.save_scenario(
            "Base case", "earnings_multiple", {"fair_pe": "20"}, {"value": "200"}
        )
        second = self.database.save_scenario(
            "Base case", "earnings_multiple", {"fair_pe": "22"}, {"value": "220"}
        )
        self.assertEqual(first["id"], second["id"])
        scenarios = self.database.list_scenarios()
        self.assertEqual(len(scenarios), 1)
        self.assertEqual(scenarios[0]["assumptions"]["fair_pe"], "22")


if __name__ == "__main__":
    unittest.main()
