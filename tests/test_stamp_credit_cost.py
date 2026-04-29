"""Damga kredi maliyeti: Polygon GAS tahmini (cent) × çarpan."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"


class TestStampCreditCost(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["TURKDAMGA_TESTING"] = "1"
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))

    def setUp(self) -> None:
        from app.config import get_settings

        get_settings.cache_clear()

    def tearDown(self) -> None:
        from app.config import get_settings

        get_settings.cache_clear()

    def test_default_one_cent_times_ten(self) -> None:
        from app.config import Settings

        s = Settings()
        self.assertEqual(s.stamp_credit_cost(), 10)

    def test_gas_times_ten(self) -> None:
        from app.config import Settings

        s = Settings(polygon_gas_cost_cents_estimate=2)
        self.assertEqual(s.stamp_credit_cost(), 20)

    def test_gas_three_cents(self) -> None:
        from app.config import Settings

        s = Settings(polygon_gas_cost_cents_estimate=3)
        self.assertEqual(s.stamp_credit_cost(), 30)


if __name__ == "__main__":
    unittest.main()
