"""Tests for the standalone readiness check and its zipapp build."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from readiness import standalone  # noqa: E402
from test_readiness import TOOLS, fake_az  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_pyz", REPO / "scripts" / "build-preflight-pyz.py")
build_pyz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_pyz)


def run(*argv, answers=(), **kw):
    out, err = io.StringIO(), io.StringIO()
    replies = iter(answers)
    code = standalone.run(list(argv), az=kw.pop("az", fake_az()), ask=lambda q: next(replies, ""), stdout=out,
                          stderr=err, interactive=kw.pop("interactive", False), **dict(TOOLS, **kw))
    return code, out.getvalue(), err.getvalue()


class StandaloneTests(unittest.TestCase):
    def test_runs_without_the_kit_and_reports_standalone_mode(self):
        code, out, _ = run("--json", "--location", "eastus2", "--users", "40")
        doc = json.loads(out)
        self.assertEqual(doc["mode"], "standalone")
        self.assertEqual(code, 0, out)
        ids = {r["id"] for r in doc["results"]}
        self.assertNotIn("op.cloudshell_storage", ids)
        tools = [r["title"] for r in doc["results"] if r["id"] == "op.tools"]
        self.assertEqual(sorted(tools), ["az", "git", "python3"])

    def test_no_address_space_means_no_invented_network_check(self):
        _, out, _ = run("--json")
        overlap = [r for r in json.loads(out)["results"] if r["id"] == "net.overlap"]
        self.assertEqual(overlap[0]["status"], "skipped")
        _, out, _ = run("--json", "--set", "address_space=10.60.0.0/20")
        overlap = [r for r in json.loads(out)["results"] if r["id"] == "net.overlap"]
        self.assertEqual(overlap[0]["status"], "pass")

    def test_interview_asks_only_discover_questions_and_retries_bad_answers(self):
        asked = []

        def ask(q):
            asked.append(q)
            return {1: "entra", 2: "entra_ds"}.get(len(asked), "")
        out, err = io.StringIO(), io.StringIO()
        standalone.run(["--json"], az=fake_az(), ask=ask, stdout=out, stderr=err, interactive=True, **TOOLS)
        self.assertEqual(len(asked), 5)  # identity (bad, then good), users, workload, region
        self.assertIn("pick one of", err.getvalue())
        results = {r["id"]: r for r in json.loads(out.getvalue())["results"]}
        self.assertEqual(results["id.domain_join_account"]["status"], "manual")

    def test_answers_file_and_bad_values(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"location": "westeurope", "user_count": 5}, f)
        code, out, _ = run("--json", "--answers", f.name)
        self.assertIn("westeurope", out)
        code, _, err = run("--set", "user_count=lots")
        self.assertEqual(code, 2)
        code, _, err = run("--set", "user_count=0")
        self.assertEqual(code, 2)
        self.assertIn("user_count", err)

    def test_list_and_usage(self):
        code, out, _ = run("--list")
        self.assertEqual(code, 0)
        self.assertIn("sub.providers", out)
        self.assertEqual(run("--no-redact")[0], 2)
        self.assertEqual(run("--features", "nope")[0], 2)

    def test_identity_alias(self):
        _, out, _ = run("--json", "--identity-model", "ad_ds")
        results = {r["id"]: r for r in json.loads(out)["results"]}
        self.assertEqual(results["id.domain_join_account"]["status"], "manual")


class ZipappTests(unittest.TestCase):
    def test_build_is_reproducible_and_runs_isolated(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.pyz", Path(d) / "b.pyz"
            self.assertEqual(build_pyz.build(a), build_pyz.build(b))
            self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(), build_pyz.build(a))
            res = subprocess.run([sys.executable, "-I", str(a), "--version"], capture_output=True, text=True, cwd=d)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("0.1.0", res.stdout)
            res = subprocess.run([sys.executable, "-I", str(a), "--list", "--format", "json"], capture_output=True,
                                 text=True, cwd=d)
            self.assertIn("op.signin", {e["id"] for e in json.loads(res.stdout)})

    def test_bundles_the_schema_license_and_notice(self):
        names = [n for n, _ in build_pyz.members()]
        for want in ("readiness/parameters.json", "LICENSE", "NOTICE", "engine.py", "redact.py", "__main__.py"):
            self.assertIn(want, names)
        self.assertFalse([n for n in names if "test_" in n or "__pycache__" in n])


if __name__ == "__main__":
    unittest.main()
