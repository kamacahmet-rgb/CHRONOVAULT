"""
TURKDAMGA duman testleri — stdlib unittest, ek paket gerekmez.

Çalıştırma (repo kökü):  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import compileall
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestBackendPackage(unittest.TestCase):
    def test_app_package_compiles(self) -> None:
        app_dir = REPO_ROOT / "backend" / "app"
        self.assertTrue(app_dir.is_dir(), f"Eksik: {app_dir}")
        ok = compileall.compile_dir(str(app_dir), quiet=1)
        self.assertTrue(ok, "backend/app/*.py derlenemedi")


class TestAlembicPython(unittest.TestCase):
    def test_alembic_versions_compile(self) -> None:
        versions = REPO_ROOT / "backend" / "alembic" / "versions"
        self.assertTrue(versions.is_dir(), f"Eksik: {versions}")
        ok = compileall.compile_dir(str(versions), quiet=1)
        self.assertTrue(ok, "Alembic versions/*.py derlenemedi")

    def test_alembic_env_compiles(self) -> None:
        env_py = REPO_ROOT / "backend" / "alembic" / "env.py"
        self.assertTrue(env_py.is_file())
        src = env_py.read_text(encoding="utf-8")
        compile(src, str(env_py), "exec")


class TestFrontend(unittest.TestCase):
    def test_key_html_files(self) -> None:
        names = [
            "turkdamga-landing.html",
            "turkdamga-arsiv-ui.html",
            "turkdamga-user-panel.html",
            "turkdamga-image-verify.html",
        ]
        fe = REPO_ROOT / "frontend"
        for n in names:
            p = fe / n
            self.assertTrue(p.is_file(), f"Eksik: {p}")
            head = p.read_text(encoding="utf-8", errors="replace")[:800]
            self.assertIn("<!DOCTYPE html>", head, f"{n}: DOCTYPE yok")
            self.assertIn("html", head.lower(), f"{n}: html içeriği şüpheli")


class TestDocs(unittest.TestCase):
    def test_core_docs_exist(self) -> None:
        docs = REPO_ROOT / "docs"
        for name in (
            "Arsiv-Mimari.md",
            "Arama-ve-TC-Erisim-Mimarisi.md",
            "Toptan-Satis-Kredi-Kontrat.md",
            "KVKK-Vertical-Damgalama.md",
            "Medya-Damga-Sertifikasi.md",
            "Kullanici-Saklama-Yukumlulugu.md",
        ):
            p = docs / name
            self.assertTrue(p.is_file(), f"Eksik: {p}")
            self.assertGreater(p.stat().st_size, 50, f"{name} çok kısa")


if __name__ == "__main__":
    unittest.main()
