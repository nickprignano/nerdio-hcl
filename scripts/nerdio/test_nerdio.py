"""Tests for the ./nerdio engine. Run: python3 -m unittest discover -s scripts/nerdio"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine  # noqa: E402
import form  # noqa: E402
import nerdio  # noqa: E402
import preflight  # noqa: E402
import tfcheck  # noqa: E402

ZERO = "00000000-0000-0000-0000-000000000000"
SOURCES = {"tenant": ZERO, "subscription": ZERO}


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = engine.load_schema()
        self.params = engine.params_by_id(self.schema)

    def test_schema_is_clean(self):
        self.assertEqual(engine.check_schema(self.schema), [])

    def test_every_tfvar_target_is_a_declared_variable(self):
        declared = {s: tfcheck.declared_variables(engine.stage_dir(self.schema, s, "example")) for s in self.schema["stages"]}
        modules = tfcheck.declared_variables(engine.ROOT / "modules" / "nerdio-config")
        for p in self.schema["parameters"]:
            for t in p.get("tfvars", []):
                top, *rest = t["path"].split(".")
                self.assertIn(top, declared[t["stage"]], f"{p['id']} -> {t['stage']}.{top}")
                # Terraform drops unknown nested attributes silently, so check those names here.
                # Stage variables typed `any` pass through to a module, so check the module's type instead.
                block = declared[t["stage"]][top]
                if re.search(r"type\s*=\s*any\b", block):
                    block = modules[top]
                for attr in rest:
                    if not attr.startswith("{") and top != "tags":
                        self.assertTrue(tfcheck.attribute_declared(block, attr), f"{p['id']} -> {t['path']}")

    def test_defaults_resolve_cleanly(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12"}, SOURCES)
        self.assertEqual(resolved.errors, {})
        self.assertEqual(resolved.values["prefix"], "nme-sandbox-ab12")
        self.assertEqual(resolved.values["fslogix_storage_account_name"], "stnmesandboxab12fslogix")
        self.assertEqual(resolved.values["fslogix_share_quota_gb"], 100)

    def test_workload_and_users_drive_sizing(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12", "workload": "heavy", "user_count": 33}, SOURCES)
        self.assertEqual(resolved.values["vm_size"], "Standard_D8s_v5")
        self.assertEqual(resolved.values["max_sessions_per_host"], 8)
        self.assertEqual(resolved.values["host_pool_capacity"], 5)

    def test_subnets_follow_the_address_space(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12", "address_space": "172.20.0.0/22"}, SOURCES)
        self.assertEqual(resolved.errors, {})
        self.assertEqual(resolved.values["session_hosts_subnet"], "172.20.0.0/24")
        self.assertEqual(resolved.values["private_endpoints_subnet"], "172.20.1.0/27")
        self.assertEqual(resolved.values["app_integration_subnet"], "172.20.1.32/27")

    def test_overlapping_subnet_is_rejected(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12", "private_endpoints_subnet": "10.50.0.0/27"}, SOURCES)
        self.assertIn("private_endpoints_subnet", resolved.errors)

    def test_subnet_outside_range_is_rejected(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12", "app_integration_subnet": "10.99.0.0/27"}, SOURCES)
        self.assertIn("app_integration_subnet", resolved.errors)

    def test_secret_hand_off_defaults_to_key_vault(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12"}, SOURCES)
        rendered, _ = engine.render(self.schema, resolved, placeholders=True)
        self.assertEqual(rendered["platform"]["nme_secret_store"], "key_vault")
        self.assertIsNone(rendered["platform"]["openbao"])

    def test_openbao_gets_its_own_subnet(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12", "address_space": "172.20.0.0/22",
                                                "nme_secret_store": "openbao"}, SOURCES)
        self.assertEqual(resolved.errors, {})
        rendered, _ = engine.render(self.schema, resolved, placeholders=True)
        self.assertEqual(rendered["platform"]["openbao"],
                         {"subnet_cidr": "172.20.1.64/28", "allowed_source_addresses": ["Internet"]})

    def test_openbao_subnet_overlap_is_rejected(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12", "nme_secret_store": "openbao",
                                                "openbao_subnet": "10.50.4.32/28"}, SOURCES)
        self.assertIn("openbao_subnet", resolved.errors)

    def test_public_or_wrong_size_ranges_are_rejected(self):
        p = self.params["address_space"]
        for bad in ("8.8.0.0/20", "10.0.0.0/8", "10.50.0.0/24", "10.50.0.1/20", "nope"):
            with self.assertRaises(engine.AnswerError, msg=bad):
                engine.validate(p, bad)

    def test_unsupported_choice_explains_why(self):
        with self.assertRaises(engine.AnswerError) as ctx:
            engine.validate(self.params["identity_model"], "ad_ds")
        self.assertIn("AD DS", str(ctx.exception))

    def test_domain_models_need_dns_servers(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12", "identity_model": "entra_ds"}, SOURCES)
        self.assertIn("dns_servers", resolved.errors)
        self.assertEqual(resolved.values["fslogix_identity_source"], "AADDS")
        self.assertFalse(resolved.values["fslogix_entra_kerberos"])

    def test_terraform_install_needs_the_entra_app(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12", "create_entra_app": False}, SOURCES)
        self.assertIn("create_entra_app", resolved.errors)
        resolved = engine.resolve(self.schema, {"_random4": "ab12", "create_entra_app": False,
                                                "nerdio_install": "marketplace"}, SOURCES)
        self.assertEqual(resolved.errors, {})

    def test_missing_sign_in_is_an_error_not_a_crash(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12"}, {"tenant": None, "subscription": None})
        self.assertIn("tenant_id", resolved.errors)

    def test_disabled_features_render_null(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12", "fslogix_enabled": False, "image_gallery_enabled": False}, SOURCES)
        rendered, problems = engine.render(self.schema, resolved, placeholders=True)
        self.assertEqual(problems, [])
        self.assertIsNone(rendered["platform"]["fslogix"])
        self.assertIsNone(rendered["platform"]["image_gallery"])

    def test_render_maps_onto_nested_variables(self):
        resolved = engine.resolve(self.schema, {"_random4": "ab12", "host_pool_name": "hp-x"}, SOURCES)
        rendered, _ = engine.render(self.schema, resolved, placeholders=True)
        self.assertEqual(rendered["platform"]["resource_groups"]["storage"], "rg-nme-sandbox-ab12-storage")
        self.assertEqual(rendered["platform"]["network"]["address_space"], ["10.50.0.0/20"])
        self.assertNotIn("hub_vnet_id", rendered["platform"]["network"])
        self.assertEqual(rendered["config"]["host_pools"]["hp-x"]["max_session_limit"], 16)
        self.assertEqual(rendered["config"]["workspace"]["name"], "ws-nme-sandbox-ab12")

    def test_group_names_are_looked_up(self):
        def fake(args):
            if args[:3] == ["ad", "group", "list"]:
                return ["11111111-2222-3333-4444-555555555555"] if "'AVD Users'" in args[4] else []
            if args[:3] == ["ad", "signed-in-user", "show"]:
                return "66666666-7777-8888-9999-000000000000"
            return None
        with mock.patch.object(engine, "az_json", side_effect=fake):
            ids, problems = engine.resolve_principals(["AVD Users", "me", "Missing"])
        self.assertEqual(ids, ["11111111-2222-3333-4444-555555555555", "66666666-7777-8888-9999-000000000000"])
        self.assertEqual(len(problems), 1)

    def test_sources_prefer_arm_env(self):
        with mock.patch.dict(os.environ, {"ARM_TENANT_ID": "t", "ARM_SUBSCRIPTION_ID": "s"}), \
             mock.patch.object(engine, "az_json", side_effect=AssertionError("az should not run")):
            self.assertEqual(engine.read_sources(), {"tenant": "t", "subscription": "s"})


class CliTests(unittest.TestCase):
    def setUp(self):
        self.schema = engine.load_schema()

    def test_set_parses_types_and_blank_means_default(self):
        answers = {"workload": "heavy"}
        problems = nerdio.apply_sets(self.schema, answers, ["user_count=42", "fslogix_enabled=no", "workload="])
        self.assertEqual(problems, [])
        self.assertEqual(answers, {"user_count": 42, "fslogix_enabled": False})

    def test_set_refuses_sourced_and_unknown(self):
        problems = nerdio.apply_sets(self.schema, {}, ["tenant_id=x", "nope=1", "user_count=many"])
        self.assertEqual(len(problems), 3)

    def test_mask_hides_real_ids_only(self):
        self.assertEqual(nerdio.mask("a 12345678-1234-1234-1234-123456789abc b"), "a 1234… b")
        self.assertEqual(nerdio.mask(ZERO), ZERO)

    def test_form_matches_schema(self):
        self.assertTrue(form.in_sync(self.schema))

    def test_form_hides_unsupported_choices(self):
        block = form.inputs_block(self.schema)
        self.assertIn("- entra_joined", block)
        self.assertNotIn("- ad_ds", block)

    def test_init_with_form_inputs_end_to_end(self):
        env = {"FORM_INPUTS": json.dumps({"environment": "dev", "user_count": 20, "fslogix_enabled": True, "prefix": ""})}
        tmp_answers = engine.ROOT / ".nerdio" / "test-answers.json"
        stage_files = [engine.stage_dir(self.schema, s, "example") / self.schema["output_file"] for s in self.schema["stages"]]
        backups = {f: f.read_bytes() for f in stage_files if f.exists()}
        try:
            with mock.patch.object(engine, "ANSWERS_PATH", tmp_answers), \
                 mock.patch.object(engine.load_answers, "__defaults__", (tmp_answers,)), \
                 mock.patch.object(engine.save_answers, "__defaults__", (tmp_answers,)), \
                 mock.patch.dict(os.environ, env), redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
                code = nerdio.main(["init", "--non-interactive", "--placeholder-ids", "--inputs-env", "FORM_INPUTS"])
            self.assertEqual(code, 0, out.getvalue())
            platform = json.loads(stage_files[0].read_text())
            self.assertEqual(platform["tags"]["environment"], "dev")
            self.assertEqual(platform["fslogix"]["share_quota_gb"], 256)
        finally:
            tmp_answers.unlink(missing_ok=True)
            for f in stage_files:
                if f in backups:
                    f.write_bytes(backups[f])
                else:
                    f.unlink(missing_ok=True)


class TfcheckTests(unittest.TestCase):
    def test_extracts_blocks_with_nested_braces_and_heredocs(self):
        text = 'variable "a" {\n  type = object({ b = string })\n  description = "x { y"\n}\n\nvariable "c" {\n  description = <<-EOT\n    hi\n  EOT\n}\n'
        blocks = tfcheck.variable_blocks(text)
        self.assertEqual(set(blocks), {"a", "c"})
        self.assertTrue(blocks["a"].endswith("}"))

    def test_unknown_variable_is_reported_without_terraform(self):
        schema = engine.load_schema()
        ok, msg = tfcheck.check_stage(engine.stage_dir(schema, "platform", "example"), {"not_a_var": 1})
        self.assertFalse(ok)
        self.assertIn("not_a_var", msg)

    @unittest.skipUnless(shutil.which("terraform"), "terraform not installed")
    def test_terraform_rejects_bad_values(self):
        schema = engine.load_schema()
        ok, msg = tfcheck.check_stage(engine.stage_dir(schema, "platform", "example"), {"create_entra_app": "maybe"})
        self.assertFalse(ok, msg)


class PreflightTests(unittest.TestCase):
    def fake_az(self, overrides=None):
        data = {
            ("account", "show"): {"id": ZERO, "name": "sandbox", "user": {"type": "user", "name": "admin"}},
            ("ad", "signed-in-user"): "66666666-7777-8888-9999-000000000000",
            ("role", "assignment"): ["Owner"],
            ("rest", "directoryRole"): {"value": [{"displayName": "Global Administrator"}]},
            ("rest", "authorizationPolicy"): {"defaultUserRolePermissions": {"allowedToCreateApps": False}},
            ("rest", "Microsoft.Web"): {"value": [{"name": {"value": "B3 VMs", "localizedValue": "B3 VMs"},
                                                    "limit": 10, "currentValue": 0}]},
            ("appservice", "list-locations"): ["East US 2", "West Europe"],
            ("rest", "Microsoft.Sql"): {"status": "Default", "supportedServerVersions": [
                {"supportedEditions": [{"supportedServiceLevelObjectives": [{"name": "S1"}]}]}]},
            ("network", "vnet", "list"): [],
            ("group", "list"): [],
            ("network", "private-dns"): [],
            ("policy", "assignment"): [],
            ("provider", "list"): [{"ns": ns, "state": "Registered"} for ns in preflight.PROVIDERS],
            ("account", "list-locations"): ["eastus2", "westeurope"],
            ("vm", "list-skus"): [{"name": "Standard_D8s_v5", "family": "standardDSv5Family", "restrictions": [],
                                   "capabilities": [{"name": "vCPUs", "value": "8"}]}],
            ("vm", "list-usage"): [{"name": {"value": "standardDSv5Family"}, "limit": 100, "currentValue": 0},
                                   {"name": {"value": "cores"}, "limit": 100, "currentValue": 10}],
        }
        data.update(overrides or {})
        def fake(args):
            if args[0] == "rest":
                url = args[args.index("--url") + 1]
                return next((v for (k, frag), v in data.items() if k == "rest" and frag in url), None)
            return data[tuple(args[:3])] if tuple(args[:3]) in data else data.get(tuple(args[:2]))
        return fake

    def values(self):
        schema = engine.load_schema()
        return engine.resolve(schema, {"_random4": "ab12"}, SOURCES).values

    def test_ready_subscription_passes(self):
        with mock.patch.object(preflight, "az_json", side_effect=self.fake_az()), \
             mock.patch.object(preflight, "check_tools", return_value=[]):
            results = preflight.run(self.values())
        self.assertFalse([r for r in results if r.status == "fail"], results)

    def test_missing_owner_quota_and_provider_fail_with_fixes(self):
        overrides = {
            ("role", "assignment"): ["Contributor"],
            ("provider", "list"): [{"ns": "Microsoft.Compute", "state": "Registered"}],
            ("vm", "list-usage"): [{"name": {"value": "standardDSv5Family"}, "limit": 4, "currentValue": 0},
                                   {"name": {"value": "cores"}, "limit": 100, "currentValue": 0}],
        }
        with mock.patch.object(preflight, "az_json", side_effect=self.fake_az(overrides)), \
             mock.patch.object(preflight, "check_tools", return_value=[]):
            results = preflight.run(self.values())
        failed = {r.check for r in results if r.status == "fail"}
        self.assertEqual(failed, {"Subscription Owner", "Resource providers", "vCPU quota"})
        for r in results:
            if r.status == "fail":
                self.assertTrue(r.fix, r.check)

    def test_consent_needs_the_role_pair_or_global_admin(self):
        overrides = {("rest", "directoryRole"): {"value": [{"displayName": "Cloud Application Administrator"}]}}
        with mock.patch.object(preflight, "az_json", side_effect=self.fake_az(overrides)), \
             mock.patch.object(preflight, "check_tools", return_value=[]):
            results = preflight.run(self.values())
        self.assertIn("Entra admin role", {r.check for r in results if r.status == "fail"})

    def test_app_service_quota_of_zero_fails_with_the_fix_command(self):
        overrides = {("rest", "Microsoft.Web"): {"value": [{"name": {"value": "B3 VMs", "localizedValue": "B3 VMs"},
                                                             "limit": 0, "currentValue": 0}]}}
        with mock.patch.object(preflight, "az_json", side_effect=self.fake_az(overrides)), \
             mock.patch.object(preflight, "check_tools", return_value=[]):
            results = preflight.run(self.values())
        quota = [r for r in results if r.check == "App Service quota"]
        self.assertEqual([r.status for r in quota], ["fail"])
        self.assertIn("./nerdio fix quota", quota[0].fix)

    def test_app_service_quota_unreadable_warns(self):
        overrides = {("rest", "Microsoft.Web"): None}
        with mock.patch.object(preflight, "az_json", side_effect=self.fake_az(overrides)), \
             mock.patch.object(preflight, "check_tools", return_value=[]):
            results = preflight.run(self.values())
        self.assertEqual([r.status for r in results if r.check == "App Service quota"], ["warn"])

    def test_app_registration_blocked_without_a_role_fails(self):
        overrides = {("rest", "directoryRole"): {"value": []}}
        with mock.patch.object(preflight, "az_json", side_effect=self.fake_az(overrides)), \
             mock.patch.object(preflight, "check_tools", return_value=[]):
            results = preflight.run(self.values())
        self.assertIn("App registration", {r.check for r in results if r.status == "fail"})

    def run_with(self, overrides=None, **values):
        vals = self.values()
        vals.update(values)
        with mock.patch.object(preflight, "az_json", side_effect=self.fake_az(overrides)), \
             mock.patch.object(preflight, "check_tools", return_value=[]), \
             mock.patch.object(preflight, "check_cloud_shell", return_value=[]):
            return {r.check: r for r in preflight.run(vals)}

    def test_contributor_plus_access_admin_counts_as_owner(self):
        results = self.run_with({("role", "assignment"): ["Contributor", "User Access Administrator"]})
        self.assertEqual(results["Subscription Owner"].status, "pass")

    def test_overlapping_vnet_warns(self):
        results = self.run_with({("network", "vnet", "list"): [
            {"name": "vnet-other", "id": "/x/vnet-other", "prefixes": ["10.50.8.0/24"]}]})
        self.assertEqual(results["Address range"].status, "warn")

    def test_the_kits_own_earlier_resources_are_not_flagged(self):
        results = self.run_with({
            ("group", "list"): ["rg-nme-sbx-ab12-network"],
            ("network", "vnet", "list"): [{"name": "vnet-nme-sbx-ab12-avd", "id": "/x/v", "rg": "rg-nme-sbx-ab12-network",
                                           "prefixes": ["10.50.0.0/20"]}],
            ("network", "private-dns"): [{"name": "privatelink.blob.core.windows.net", "rg": "rg-nme-sbx-ab12-network"}]})
        self.assertEqual(results["Address range"].status, "pass")
        self.assertNotIn("Private DNS", results)

    def test_policy_names_hide_ids(self):
        results = self.run_with({("policy", "assignment"): ["ASC Default (subscription: 11111111-2222-3333-4444-555555555555)"]})
        self.assertNotIn("11111111", results["Azure Policy"].detail)

    def test_region_scan_reports_each_region(self):
        overrides = {("account", "list-locations"): [{"name": "eastus2", "group": "US"}, {"name": "centralus", "group": "US"}, {"name": "eastus2euap", "group": "US"},
                                                     {"name": "westeurope", "group": "Europe"}]}
        with mock.patch.object(preflight, "az_json", side_effect=self.fake_az(overrides)):
            regions = preflight.nearby_regions("eastus2")
            found = preflight.scan_regions(self.values(), ZERO, regions)
        self.assertEqual(regions, ["centralus", "eastus2"])
        self.assertEqual(set(found), {"centralus", "eastus2"})
        self.assertIn("Azure SQL region", {r.check for r in found["centralus"]})

    def test_hub_overlap_and_missing_rights_fail(self):
        hub = "/subscriptions/x/resourceGroups/hub/providers/Microsoft.Network/virtualNetworks/hub"
        results = self.run_with({("network", "vnet", "show"): {"prefixes": ["10.50.0.0/16"]},
                                 ("role", "assignment"): ["Reader"]}, hub_vnet_id=hub)
        self.assertEqual(results["Hub network"].status, "fail")
        self.assertEqual(results["Hub peering rights"].status, "fail")

    def test_unreadable_hub_fails(self):
        results = self.run_with({("network", "vnet", "show"): None}, hub_vnet_id="/subscriptions/x/hub")
        self.assertEqual(results["Hub network"].status, "fail")

    def test_sql_region_closed_fails(self):
        results = self.run_with({("rest", "Microsoft.Sql"): {"status": "Disabled", "reason": "RegionDoesNotAllowProvisioning"}})
        self.assertEqual(results["Azure SQL region"].status, "fail")

    def test_enforced_policies_are_listed_for_review(self):
        results = self.run_with({("policy", "assignment"): ["Allowed locations", "Require a tag"]})
        self.assertEqual(results["Azure Policy"].status, "manual")
        self.assertIn("Allowed locations", results["Azure Policy"].detail)

    def test_ephemeral_cloud_shell_fails(self):
        with mock.patch.dict(os.environ, {"AZUREPS_HOST_ENVIRONMENT": "cloud-shell/1.0"}), \
             mock.patch.object(os.path, "isdir", return_value=False):
            results = preflight.check_cloud_shell()
        self.assertEqual(results[0].status, "fail")

    def test_not_signed_in_stops_early(self):
        with mock.patch.object(preflight, "az_json", return_value=None), \
             mock.patch.object(preflight, "check_tools", return_value=[]):
            results = preflight.run(self.values())
        self.assertEqual(results[0].check, "Azure sign-in")
        self.assertEqual(results[0].status, "fail")


if __name__ == "__main__":
    unittest.main()
