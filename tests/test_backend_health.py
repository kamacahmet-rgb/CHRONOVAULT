"""FastAPI iskeleti — /health uçları (backend/app)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"


class TestBackendHealth(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["TURKDAMGA_TESTING"] = "1"
        os.environ.pop("DATABASE_URL", None)
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))

    def test_health_paths(self) -> None:
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("Backend testleri için: pip install -r backend/requirements.txt")

        from app.config import get_settings

        get_settings.cache_clear()

        from app.main import app

        client = TestClient(app)
        for path in ("/health", "/api/v1/health"):
            r = client.get(path)
            self.assertEqual(r.status_code, 200, path)
            data = r.json()
            self.assertEqual(data.get("status"), "ok", path)
            self.assertEqual(data.get("db"), "skipped", path)

        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("docs", r.json())
