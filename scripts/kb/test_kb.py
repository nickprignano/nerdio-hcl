"""Tests for the knowledge base scripts. Run: python3 -m unittest discover -s scripts/kb"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
import feedback  # noqa: E402
import freshness  # noqa: E402
import kblib  # noqa: E402

SAFE = "### Public-safe\n\n- [X] I removed tenant and subscription IDs, names, domains, emails, IP addresses and secrets.\n"

FEEDBACK_BODY = """### Outcome

Broke or gave the wrong result

### Page

docs/knowledge/terraform/azurerm-5.md

### What happened

The subnet fix needed a different block name.

### Versions

_No response_

### Evidence

_No response_

""" + SAFE

KNOWN_ERROR_BODY = """### Symptom

`Error: Unsupported argument` on `azurerm_example`

### Cause

Renamed in a provider release.

### Fix

Use the new argument name.

### Source

https://example.com/changelog

### Versions

azurerm 5.11.0

### Confidence

Fix worked once; the cause is a guess

""" + SAFE


class TempData(unittest.TestCase):
    """Point the data files at temporary copies so tests never touch the real KB."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.patches = []
        for name in ("KNOWN_ERRORS", "FIELD_REPORTS"):
            src = getattr(kblib, name)
            dst = self.tmp / src.name
            shutil.copy(src, dst)
            p = mock.patch.object(kblib, name, dst)
            p.start()
            self.patches.append(p)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)


class FeedbackTests(TempData):
    def test_parse_form(self):
        fields = feedback.parse_form(FEEDBACK_BODY)
        self.assertEqual(fields["Outcome"], "Broke or gave the wrong result")
        self.assertEqual(fields["Versions"], "")

    def test_field_report(self):
        issue = {"number": 7, "body": FEEDBACK_BODY, "labels": [{"name": "kb-feedback"}]}
        title, _ = feedback.handle(issue, "2026-10-16")
        self.assertIn("broke on terraform/azurerm-5.md", title)
        report = kblib.load_yaml(kblib.FIELD_REPORTS)["reports"][-1]
        self.assertEqual(report["page"], "terraform/azurerm-5.md")
        self.assertNotIn("versions", report)
        with self.assertRaises(feedback.FeedbackError):
            feedback.handle(issue, "2026-10-16")  # same issue twice

    def test_known_error(self):
        issue = {"number": 8, "body": KNOWN_ERROR_BODY, "labels": [{"name": "kb-known-error"}]}
        feedback.handle(issue, "2026-10-16")
        entry = kblib.load_yaml(kblib.KNOWN_ERRORS)["errors"][-1]
        self.assertEqual(entry["status"], "unverified")
        self.assertEqual(entry["source"], "https://example.com/changelog")
        self.assertTrue(kblib.KNOWN_ERRORS.read_text().startswith("# Known errors catalog"))

    def test_rejects_unticked_and_missing_page(self):
        unticked = FEEDBACK_BODY.replace("- [X]", "- [ ]")
        with self.assertRaises(feedback.FeedbackError):
            feedback.handle({"number": 9, "body": unticked, "labels": ["kb-feedback"]}, "2026-10-16")
        bad_page = FEEDBACK_BODY.replace("terraform/azurerm-5.md", "../../etc/passwd")
        with self.assertRaises(feedback.FeedbackError):
            feedback.handle({"number": 10, "body": bad_page, "labels": ["kb-feedback"]}, "2026-10-16")


class FreshnessTests(TempData):
    def test_stale_and_reported(self):
        issue = {"number": 11, "body": FEEDBACK_BODY, "labels": ["kb-feedback"]}
        feedback.handle(issue, "2026-10-16")
        sections = freshness.collect(90, date(2027, 6, 1))
        self.assertTrue(any("azurerm-5.md" in i for i in sections["Reported broken or outdated"]))
        self.assertTrue(sections["Stale"])
        self.assertFalse(any("stack-options.md" in i for i in sections["Stale"]))  # plan pages skip


class BuildTests(unittest.TestCase):
    def test_generated_files_up_to_date(self):
        stale = [p for p, c in build.targets().items() if p.read_text(encoding="utf-8") != c]
        self.assertEqual(stale, [], "run python3 scripts/kb/build.py")

    def test_link_from(self):
        page_dir = kblib.KB_DIR / "troubleshooting"
        self.assertEqual(build.link_from(page_dir, "nerdio/platform.md#x"), "../nerdio/platform.md#x")
        self.assertEqual(build.link_from(page_dir, "https://example.com"), "https://example.com")


class AnchorTests(unittest.TestCase):
    def test_github_slugs(self):
        body = "# A\n## Post-deployment checks with Playwright\n## 8. Deployment troubleshooting\n## A\n"
        self.assertEqual(kblib.anchors(body), {
            "a", "post-deployment-checks-with-playwright", "8-deployment-troubleshooting", "a-1"})


if __name__ == "__main__":
    unittest.main()
