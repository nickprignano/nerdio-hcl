"""Tests for the feature checks (app.*, attach.*, ins.*, sa.*, auto.*), policy evaluation, the URL
check, the Nerdio data tier and the probe tier.

Run: python3 -m unittest discover -s scripts/nerdio
Every az, Graph, Nerdio and HTTPS call is answered from fixtures; nothing reaches the network.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from readiness import nerdio_api, probe, standalone  # noqa: E402
from readiness.context import NOT_AZ, is_read_only  # noqa: E402
from test_readiness_post import ALL, HOST_POOL, RESOURCES, RG, SUB, ZERO, by_id, role_rows, run  # noqa: E402

INSIGHTS_WEB = {"name": "nmw-intune-insights-abc", "type": "Microsoft.Web/sites", "id": f"{SUB}/Microsoft.Web/sites/ii"}
VM = f"/subscriptions/{ZERO}/resourceGroups/rg-avd/providers/Microsoft.Compute/virtualMachines/host-0"


class FakeNerdio:
    """Nerdio's REST API: answers by path, records what was asked."""

    def __init__(self, answers):
        self.answers, self.paths = answers, []

    def get(self, path):
        self.paths.append(path)
        return self.answers.get(path, (404, None))


class AppTests(unittest.TestCase):
    def test_intune_repository(self):
        _, r = run(features=["app-mgmt"])
        self.assertEqual(by_id(r)["app.intune_repo"], ["pass"])
        _, r = run(overrides={("rest", "/subscribedSkus"): {"value": []}, ("rest", "/appRoleAssignments"): {"value": []}},
                   features=["app-mgmt"])
        self.assertEqual(by_id(r)["app.intune_repo"], ["fail", "fail"])

    def test_private_winget_before_the_install(self):
        _, r = run("pre-install", features=["app-mgmt"])
        self.assertEqual(by_id(r)["app.private_winget"], ["manual"])
        _, r = run("pre-install", {("rest", "Microsoft.DocumentDB/locations"): {"value": []}}, features=["app-mgmt"])
        self.assertEqual(by_id(r)["app.private_winget"], ["fail", "manual"])

    def test_winget_reach_flags_a_deny(self):
        nsg = [{"name": "nsg-hosts", "rules": [{"port": "443", "to": "Internet"}]}]
        _, r = run(overrides={("network", "nsg", "list"): nsg}, features=["app-mgmt"])
        self.assertEqual(by_id(r)["app.winget_reach"], ["warn"])


class AppAttachTests(unittest.TestCase):
    def test_storage_must_be_here(self):
        _, r = run(features=["app-attach"], app_attach_storage="stattach")
        self.assertEqual(by_id(r)["attach.storage_sub"], ["pass"])
        _, r = run(overrides={("storage", "account", "list"): []}, features=["app-attach"], app_attach_storage="stattach")
        self.assertEqual(by_id(r)["attach.storage_sub"], ["fail"])

    def test_entra_hosts_need_both_service_principals(self):
        def one(args):
            if "Reader and Data Access" in args:
                return [{"id": "avd-sp", "name": "Azure Virtual Desktop"}]
            return role_rows(args)
        _, r = run(features=["app-attach"], app_attach_storage="stattach", identity_model="entra_joined")
        self.assertEqual(by_id(r)["attach.entra_hosts"], ["pass"])
        _, r = run(overrides={("role", "assignment", "list"): one}, features=["app-attach"], app_attach_storage="stattach",
                   identity_model="entra_joined")
        self.assertEqual(by_id(r)["attach.entra_hosts"], ["fail"])

    def test_without_storage_input_attach_checks_skip(self):
        _, r = run(features=["app-attach"])
        self.assertEqual(by_id(r)["attach.storage_sub"], ["skipped"])

    def test_server_hosts_warn(self):
        hosts = {"value": [{"name": "hp1/h", "properties": {"status": "Available", "osVersion": "10.0.20348.1"}}]}
        _, r = run(overrides={("rest", "/sessionHosts"): hosts}, features=["app-attach"])
        self.assertEqual(by_id(r)["attach.host_pools"], ["warn"])


class InsightsTests(unittest.TestCase):
    def with_insights(self, over=None):
        return {("resource", "list"): RESOURCES + [INSIGHTS_WEB], **(over or {})}

    def test_sql_tier_by_device_count(self):
        _, r = run("pre-install", features=["insights"], intune_devices=30000)
        found = [x for x in r if x.id == "ins.capacity"]
        self.assertEqual(found[0].status, "fail")  # the fixture region offers S1 only
        self.assertIn("S2", found[0].detail)
        _, r = run("pre-install", features=["insights"], intune_devices=500)
        self.assertEqual(by_id(r)["ins.capacity"], ["pass"])
        _, r = run("pre-install", features=["insights"], intune_devices=200000)
        self.assertEqual(by_id(r)["ins.capacity"], ["manual"])

    def test_enabler_rights(self):
        _, r = run("pre-install", features=["insights"])
        self.assertEqual(by_id(r)["ins.enabler_rights"], ["pass"])
        _, r = run("pre-install", {("role", "assignment", "list"): ["Contributor"],
                                   ("rest", "directoryRole"): {"value": []}}, features=["insights"])
        self.assertEqual(by_id(r)["ins.enabler_rights"], ["fail", "warn"])

    def test_reusing_stores_fails(self):
        _, r = run("pre-install", features=["insights"], rti_reuse_existing=True)
        self.assertEqual(by_id(r)["ins.rti_new_kv_sql"], ["fail"])
        _, r = run("pre-install", features=["insights"])
        self.assertEqual(by_id(r)["ins.rti_new_kv_sql"], ["manual"])

    def test_identities(self):
        _, r = run(overrides=self.with_insights(), features=["insights"])
        found = by_id(r)
        self.assertEqual(found["ins.identity_roles"], ["pass"])
        self.assertEqual(found["ins.intune_graph"], ["pass"])
        self.assertEqual(found["ins.avd_insights"], ["manual"])

        def missing(args):
            return [{"role": "Monitoring Reader", "scope": f"/subscriptions/{ZERO}"}] if "pid-intune" in args else role_rows(args)
        _, r = run(overrides=self.with_insights({("role", "assignment", "list"): missing,
                                                 ("rest", "/appRoleAssignments"): {"value": []}}), features=["insights"])
        found = by_id(r)
        self.assertEqual(found["ins.identity_roles"], ["fail", "warn"])
        self.assertEqual(found["ins.intune_graph"], ["fail"])

    def test_no_avd_insights_rule(self):
        _, r = run(overrides={("rest", "dataCollectionRules"): {"value": []}}, features=["insights"])
        self.assertEqual(by_id(r)["ins.avd_insights"], ["warn"])


class AutomationTests(unittest.TestCase):
    def test_scripted_actions(self):
        _, r = run(features=["scripted-actions"])
        found = by_id(r)
        self.assertEqual(found["sa.modules"], ["pass"])
        self.assertEqual(found["sa.hybrid_worker"], ["manual"])
        self.assertEqual(found["sa.runbooks_enabled"], ["manual"])

    def test_failed_module_and_offline_worker(self):
        mods = {"value": [{"name": "Az.Accounts", "properties": {"provisioningState": "Failed"}}]}
        workers = {"value": [{"properties": {"lastSeenDateTime": "2020-01-01T00:00:00Z"}}]}
        _, r = run(overrides={("rest", "/modules?"): mods, ("rest", "/hybridRunbookWorkers?"): workers},
                   features=["scripted-actions"])
        found = by_id(r)
        self.assertEqual(found["sa.modules"], ["fail"])
        self.assertEqual(found["sa.hybrid_worker"], ["fail", "manual"])

    def test_backup_vault_and_provider(self):
        _, r = run(features=["automation"])
        self.assertEqual(by_id(r)["auto.backup"], ["pass"])
        _, r = run(overrides={("backup", "vault", "list"): []}, features=["automation"])
        self.assertEqual(by_id(r)["auto.backup"], ["warn"])
        _, r = run("pre-install", {("provider", "show"): "NotRegistered"}, features=["automation"])
        self.assertEqual(by_id(r)["auto.backup"], ["fail"])

    def test_image_build_quota(self):
        usage = [{"name": {"value": "standardDSv5Family"}, "limit": 10, "currentValue": 10},
                 {"name": {"value": "cores"}, "limit": 100, "currentValue": 0}]
        _, r = run("pre-install", {("vm", "list-usage"): usage}, features=["automation"])
        self.assertIn("fail", by_id(r)["auto.image_mgmt"])


class PolicyAndUrlTests(unittest.TestCase):
    def test_policy_eval_stays_manual(self):
        _, r = run("pre-install")
        found = [x for x in r if x.id == "sub.policy_eval"]
        self.assertEqual([x.status for x in found], ["manual"])
        self.assertIn("NME-SE", found[0].detail)

    def test_url_check(self):
        _, r = run()
        self.assertEqual(by_id(r)["net.url_check"], ["manual"])  # no host reports the check: never a pass
        ok = {"value": [{"name": "hp1/h", "properties": {"sessionHostHealthCheckResults": [
            {"healthCheckName": "UrlsAccessibleCheck", "healthCheckResult": "HealthCheckSucceeded"}]}}]}
        _, r = run(overrides={("rest", "/sessionHosts"): ok})
        self.assertEqual(by_id(r)["net.url_check"], ["pass"])
        bad = {"value": [{"name": "hp1/h", "properties": {"sessionHostHealthCheckResults": [
            {"healthCheckName": "UrlsAccessibleCheck", "healthCheckResult": "HealthCheckFailed"}]}}]}
        _, r = run(overrides={("rest", "/sessionHosts"): bad})
        self.assertEqual(by_id(r)["net.url_check"], ["fail"])


class NerdioDataTests(unittest.TestCase):
    def test_off_by_default(self):
        _, r = run()
        self.assertEqual(by_id(r)["nme.wizard"], ["skipped"])

    def test_wizard_and_rest_reads(self):
        api = FakeNerdio({"/api/v1/ad/config": (200, {"type": "EntraId"})})
        ctx, r = run(nerdio_data=True, nerdio_client=api)
        found = by_id(r)
        self.assertEqual(found["nme.wizard"], ["pass", "manual"])
        self.assertEqual(found["nme.rest_api"], ["pass"])
        self.assertEqual(api.paths, ["/api/v1/ad/config", "/api/v1/ad/config"])
        for call in ctx.calls:
            self.assertTrue(call[0] in NOT_AZ or is_read_only(call), call)

    def test_no_directory_profile_and_refused_client(self):
        _, r = run(nerdio_data=True, nerdio_client=FakeNerdio({}))
        self.assertEqual(by_id(r)["nme.wizard"], ["fail", "manual"])
        _, r = run(nerdio_data=True, nerdio_client=FakeNerdio({"/api/v1/ad/config": (403, None)}))
        found = by_id(r)
        self.assertEqual(found["nme.wizard"], ["no-access"])
        self.assertEqual(found["nme.rest_api"], ["fail"])

    def test_standalone_settings_need_every_value_and_never_show_the_secret(self):
        with self.assertRaises(nerdio_api.NotConfigured) as err:
            nerdio_api.settings("standalone", {"NME_CLIENT_ID": "c"}, "example", "t", "nmw.example.net")
        self.assertIn("NME_CLIENT_SECRET", str(err.exception))
        cfg, secret = nerdio_api.settings("standalone", {"NME_CLIENT_ID": "c", "NME_SCOPE": "api://x/.default",
                                                         "NME_CLIENT_SECRET": "s3cret"}, "example", "t", "nmw.example.net")
        self.assertEqual(cfg["base_url"], "https://nmw.example.net")
        self.assertNotIn("s3cret", json.dumps(cfg))
        self.assertEqual(secret, "s3cret")

    def test_kit_settings_read_platform_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "platform.auto.tfvars.json").write_text(json.dumps({
                "nme_base_url": "https://nmw.example.net", "nme_tenant_id": ZERO, "nme_client_id": "c",
                "nme_scope": "api://x/.default", "nme_key_vault": {"id": "/x/vaults/kv", "secret_name": "nme"}}))
            with mock.patch("engine.stage_dir", return_value=Path(d)), \
                    mock.patch.object(nerdio_api, "vault_secret", return_value="from-vault") as vault:
                cfg, secret = nerdio_api.settings("kit", {}, "example", "", "")
        self.assertEqual(secret, "from-vault")
        vault.assert_called_once_with({"id": "/x/vaults/kv", "secret_name": "nme"})
        self.assertEqual(cfg["client_id"], "c")

    def test_failed_sign_in_is_its_own_result(self):
        client = nerdio_api.Client({"base_url": "https://n", "tenant": ZERO, "client_id": "c", "scope": "s"}, "bad",
                                   "https://login.microsoftonline.com", post=lambda u, f: (401, {}), get=None)
        with self.assertRaises(nerdio_api.SignInFailed):
            client.get("/api/v1/ad/config")
        _, r = run(nerdio_data=True, nerdio_client=client)
        found = [x for x in r if x.id in ("nme.wizard", "nme.rest_api")]
        self.assertEqual([x.status for x in found], ["warn", "warn"])
        self.assertTrue(all("sign in" in x.detail for x in found))

    def test_hybrid_worker_with_arm_timestamp(self):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.1234567+00:00")
        workers = {"value": [{"properties": {"lastSeenDateTime": now}}]}
        _, r = run(overrides={("rest", "/hybridRunbookWorkers?"): workers}, features=["scripted-actions"])
        self.assertEqual(by_id(r)["sa.hybrid_worker"], ["manual"])

    def test_client_signs_in_once_and_only_gets(self):
        posts, gets = [], []

        def post(url, form):
            posts.append((url, form["grant_type"], form["scope"]))
            return 200, {"access_token": "tok"}

        def get(url, token):
            gets.append((url, token))
            return 200, {}
        client = nerdio_api.Client({"base_url": "https://nmw.example.net/", "tenant": ZERO, "client_id": "c",
                                    "scope": "api://x/.default"}, "s", "https://login.microsoftonline.com/",
                                   post=post, get=get)
        client.get("/api/v1/ad/config")
        client.get("/api/v1/image")
        self.assertEqual(posts, [(f"https://login.microsoftonline.com/{ZERO}/oauth2/v2.0/token", "client_credentials",
                                  "api://x/.default")])
        self.assertEqual([g[0] for g in gets], ["https://nmw.example.net/api/v1/ad/config",
                                                "https://nmw.example.net/api/v1/image"])
        with self.assertRaises(ValueError):
            client.get("https://elsewhere/")


class ProbeTests(unittest.TestCase):
    def probe(self, *, env=None, interactive=True, answer="yes", vm=VM, message="Accessible URLs:\nrdweb.wvd.microsoft.com"):
        calls, out = [], io.StringIO()

        def az(args):
            calls.append(args)
            return {"value": [{"message": message}]}
        result = probe.run("url-check", vm=vm, env=env or {}, interactive=interactive, ask=lambda _: answer, out=out, az=az)
        return result, calls, out.getvalue()

    def test_says_what_it_does_and_runs_after_yes(self):
        result, calls, shown = self.probe()
        self.assertIn("SYSTEM", shown)
        self.assertIn("Virtual Machine Contributor", shown)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(calls[0][:3], ["vm", "run-command", "invoke"])

    def test_never_without_yes_a_terminal_or_in_the_pipeline(self):
        for kw in ({"answer": "y"}, {"interactive": False}, {"env": {"GITHUB_ACTIONS": "true"}}, {"vm": "host-0"}):
            with self.assertRaises(probe.ProbeRefused, msg=kw):
                self.probe(**kw)

    def test_reads_unreachable_urls(self):
        result, _, _ = self.probe(message="Not Accessible URLs:\nexample.wvd.microsoft.com")
        self.assertEqual(result["status"], "fail")

    def test_standalone_flag(self):
        out, err = io.StringIO(), io.StringIO()
        code = standalone.run(["--probe", "url-check", "--vm", VM], az=None, ask=lambda _: "no", stdout=out, stderr=err,
                              interactive=True, env={}, probe_az=lambda a: None)
        self.assertEqual(code, 2)
        self.assertIn("didn't type yes", err.getvalue())


class ExtraInputTests(unittest.TestCase):
    def test_extra_values(self):
        self.assertEqual(standalone.extra_value("rti_reuse_existing", "yes"), True)
        self.assertEqual(standalone.extra_value("intune_devices", "40"), 40)
        with self.assertRaises(ValueError):
            standalone.extra_value("rti_reuse_existing", "maybe")

    def test_every_feature_check_is_read_only(self):
        ctx, _ = run(features=ALL, app_attach_storage="stattach", intune_devices=100)
        ctx2, _ = run("pre-install", features=ALL, app_attach_storage="stattach", intune_devices=100)
        for call in ctx.calls + ctx2.calls:
            self.assertTrue(call[0] in NOT_AZ or is_read_only(call), call)
        self.assertTrue(any("Microsoft.DesktopVirtualization" in " ".join(c) for c in ctx.calls))
        self.assertEqual(HOST_POOL.split("/")[4], "rg-avd")
        self.assertNotEqual(RG, "rg-avd")


if __name__ == "__main__":
    unittest.main()
