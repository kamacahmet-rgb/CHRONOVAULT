"""HMAC(TC) parmak izi — stdlib + app.services."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"


class TestSubjectFingerprint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))

    def test_tc_fingerprint_hex_length(self) -> None:
        from app.services.subject_fingerprint import tc_fingerprint

        fp = tc_fingerprint("test-secret-at-least-used", "12345678901")
        self.assertEqual(len(fp), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in fp))

    def test_tc_fingerprint_invalid(self) -> None:
        from app.services.subject_fingerprint import tc_fingerprint

        with self.assertRaises(ValueError):
            tc_fingerprint("secret", "123")
        with self.assertRaises(ValueError):
            tc_fingerprint("secret", "abcdefghijk")
