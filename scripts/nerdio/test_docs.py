"""Tests for scripts/nerdio/docs.py and ./nerdio docs."""

from __future__ import annotations

import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import docs  # noqa: E402
import nerdio  # noqa: E402


class DocsTests(unittest.TestCase):
    def test_repo_docs_are_clean_and_in_sync(self):
        self.assertEqual(docs.check(), [])

    def test_cli_docs_check_succeeds(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = nerdio.main(["docs", "--check"])
        self.assertEqual(code, 0)
        self.assertIn("in sync", out.getvalue())

    def test_inventory_flags_unlisted_module_stage_and_doc(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        for m in list(docs.MODULES) + ["new-module"]:
            (tmp / "modules" / m).mkdir(parents=True)
        for s in list(docs.STAGES) + ["03-extra"]:
            (tmp / "environments" / "example" / s).mkdir(parents=True)
        (tmp / "docs").mkdir(parents=True)
        for d in list(docs.DOCS) + ["extra.md"]:
            (tmp / "docs" / d).write_text("# Extra\n", encoding="utf-8")

        problems = docs.check_inventory(tmp)
        self.assertIn("modules/new-module is not listed in scripts/nerdio/docs.py MODULES", problems)
        self.assertIn("environments/example/03-extra is not listed in scripts/nerdio/docs.py STAGES", problems)
        self.assertIn("docs/extra.md is not listed in scripts/nerdio/docs.py DOCS", problems)

    def test_links_anchors_and_leaks_are_checked(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        target = tmp / "target.md"
        target.write_text("# Target Heading\n", encoding="utf-8")
        doc = tmp / "README.md"
        doc.write_text(
            "# Doc\n\n"
            "Good [link](target.md#target-heading).\n"
            "Missing [file](nope.md) and bad [anchor](target.md#wrong).\n"
            "Leak email alice@realcorp.io and public IP 8.8.8.8, but user@contoso.com and 10.50.0.1 are fine.\n",
            encoding="utf-8",
        )
        problems = docs.check_links_and_leaks([doc], root=tmp)
        self.assertTrue(any("broken link 'nope.md'" in p for p in problems), problems)
        self.assertTrue(any("no heading #wrong" in p for p in problems), problems)
        self.assertTrue(any("non-placeholder email" in p for p in problems), problems)
        self.assertTrue(any("public IP 8.8.8.8" in p for p in problems), problems)
        self.assertEqual(len(problems), 4)

    def test_superseded_decision_and_architecture_checks(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        dec_dir = tmp / "docs" / "knowledge" / "decisions"
        dec_dir.mkdir(parents=True)
        (dec_dir / "0003-marketplace-template.md").write_text(
            "---\nstatus: superseded by 0011\ndate: 2026-10-16\n---\n# 0003. Old\n",
            encoding="utf-8",
        )
        (tmp / "README.md").write_text("See 0003-marketplace-template.md for details.\n", encoding="utf-8")
        (tmp / "docs" / "architecture.md").write_text("# Architecture\nOnly modules/nerdio-manager here.\n", encoding="utf-8")

        problems = docs.check_decisions_and_architecture(tmp)
        self.assertTrue(any("cites superseded decision 0003-marketplace-template.md" in p for p in problems), problems)
        self.assertTrue(any("missing reference to active module modules/nerdio-core" in p for p in problems), problems)
        self.assertTrue(any("missing reference to active module modules/nerdio-config" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
