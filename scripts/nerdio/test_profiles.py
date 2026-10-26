"""Tests for ./nerdio use and the tenant guard. Run: python3 -m unittest discover -s scripts/nerdio"""

from __future__ import annotations

import io
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine
import nerdio
import profiles

TRIAL = {"tenantId": "t-trial", "id": "s-trial", "name": "Personal sandbox", "tenantDefaultDomain": "trial.example"}


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = {"XDG_CONFIG_HOME": self.tmp.name}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        for var in ("ARM_SUBSCRIPTION_ID", "GITHUB_ACTIONS"):
            os.environ.pop(var, None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = nerdio.main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def test_first_use_saves_private_profile_and_sets_current(self):
        with mock.patch.object(engine, "az_json", return_value=TRIAL):
            code, out = self.run_cli("use", "trial", "--yes")
        self.assertEqual(code, 0, out)
        self.assertEqual(profiles.load("trial")["subscription_id"], "s-trial")
        self.assertEqual(profiles.current(), "trial")
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(profiles.path("trial").stat().st_mode), 0o600)
        self.assertNotIn("s-trial", out)

    def test_first_use_needs_a_yes(self):
        with mock.patch.object(engine, "az_json", return_value=TRIAL), mock.patch("builtins.input", return_value="no"):
            code, _ = self.run_cli("use", "trial")
        self.assertEqual(code, 1)
        self.assertIsNone(profiles.load("trial"))

    def test_other_subscription_in_same_tenant_switches(self):
        profiles.save("trial", TRIAL)
        other = dict(TRIAL, id="s-other")
        with mock.patch.object(profiles.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            ok, message = profiles.ensure("trial", other)
        self.assertTrue(ok)
        self.assertIn("Switched", message)
        self.assertIn("s-trial", run.call_args.args[0])

    def test_wrong_tenant_stops_with_cloud_shell_link(self):
        profiles.save("trial", TRIAL)
        with mock.patch.object(profiles.subprocess, "run", side_effect=AssertionError("must not switch")):
            ok, message = profiles.ensure("trial", {"tenantId": "t-work", "id": "s-work"})
        self.assertFalse(ok)
        self.assertIn("https://shell.azure.com/trial.example", message)

    def test_guard_blocks_commands_in_wrong_tenant(self):
        profiles.save("trial", TRIAL)
        profiles.set_current("trial")
        with mock.patch.object(engine, "az_json", return_value={"tenantId": "t-work", "id": "s-work"}):
            code, out = self.run_cli("preflight")
        self.assertEqual(code, 1)
        self.assertIn("different tenant", out)

    def test_guard_skips_in_pipelines_and_without_profiles(self):
        self.assertEqual(profiles.guard(), (True, ""))
        profiles.save("trial", TRIAL)
        profiles.set_current("trial")
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            self.assertEqual(profiles.guard(), (True, ""))

    def test_bad_names_and_forget(self):
        code, _ = self.run_cli("use", "../x")
        self.assertEqual(code, 1)
        profiles.save("trial", TRIAL)
        profiles.set_current("trial")
        code, _ = self.run_cli("use", "trial", "--forget")
        self.assertEqual(code, 0)
        self.assertIsNone(profiles.load("trial"))
        self.assertIsNone(profiles.current())


if __name__ == "__main__":
    unittest.main()
