"""Tests for the readiness engine (readiness/) and the preflight shim over it.

Run: python3 -m unittest discover -s scripts/nerdio
Every az call is answered from the fixtures below; nothing reaches the network.
"""

from __future__ import annotations

import io
import json
import os
import re
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine  # noqa: E402
import fix  # noqa: E402
import nerdio  # noqa: E402
import preflight  # noqa: E402
from readiness import SCHEMA_ID, catalogue, cloud, main, report, runner  # noqa: E402
from readiness.context import Ctx, WriteRefused, is_read_only  # noqa: E402
from readiness.model import REGISTRY, STAGES, Check, Result, check, contract_problems  # noqa: E402

ZERO = "00000000-0000-0000-0000-000000000000"
SOURCES = {"tenant": ZERO, "subscription": ZERO}
COMMERCIAL_CLOUD = {"name": "AzureCloud", "endpoints": {
    "resourceManager": "https://management.azure.com/", "microsoftGraphResourceId": "https://graph.microsoft.com/",
    "activeDirectory": "https://login.microsoftonline.com"}, "suffixes": {
    "storageEndpoint": "core.windows.net", "sqlServerHostname": ".database.windows.net", "keyvaultDns": ".vault.azure.net"}}
GOV_CLOUD = {"name": "AzureUSGovernment", "endpoints": {
    "resourceManager": "https://management.usgovcloudapi.net/", "microsoftGraphResourceId": "https://graph.microsoft.us/",
    "activeDirectory": "https://login.microsoftonline.us"}, "suffixes": {
    "storageEndpoint": "core.usgovcloudapi.net", "sqlServerHostname": ".database.usgovcloudapi.net",
    "keyvaultDns": ".vault.usgovcloudapi.net"}}
REPO = Path(__file__).resolve().parents[2]


def fake_az(overrides=None):
    """az answers for a subscription that's ready for the kit; overrides change one answer."""
    data = {
        # Specific URL fragments first: the fake answers the first fragment a URL contains.
        ("rest", "checkNameAvailability"): {"nameAvailable": True},
        ("rest", "checknameavailability"): {"nameAvailable": True},
        ("rest", "api-version=2022-12-01"): {"subscriptionPolicies": {"quotaId": "PayAsYouGo_2014-09-01",
                                                                       "spendingLimit": "Off"}},
        ("rest", "roleEligibilityScheduleInstances"): {"value": []},
        ("rest", "/me?$select=userType"): {"userType": "Member"},
        ("rest", "/applications"): {"value": []},
        ("cloud", "show"): COMMERCIAL_CLOUD,
        ("account", "show"): {"id": ZERO, "name": "sandbox", "user": {"type": "user", "name": "admin@contoso.onmicrosoft.com"}},
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
        ("keyvault", "list-deleted"): [],
        ("keyvault", "check-name"): {"nameAvailable": True},
        ("storage", "account", "check-name"): {"nameAvailable": True},
        ("resource", "list"): [],
        ("lock", "list"): [],
        ("group", "exists"): False,
        ("provider", "show"): "Registered",
        ("cognitiveservices", "model", "list"): ["GlobalStandard", "Standard"],
        ("cognitiveservices", "usage", "list"): [{"name": {"value": "OpenAI.GlobalStandard.gpt-4o"}, "limit": 50,
                                                  "currentValue": 0}],
        ("network", "vnet", "subnet"): {"addressPrefix": "10.60.1.0/24", "natGateway": {"id": "/x/nat"},
                                         "delegations": [{"serviceName": "Microsoft.Web/serverFarms"}]},
        ("network", "route-table"): [],
    }
    data.update(overrides or {})

    def fake(args):
        if args[0] == "rest":
            url = args[args.index("--url") + 1]
            return next((v for (k, frag), v in data.items() if k == "rest" and frag in url), None)
        return data[tuple(args[:3])] if tuple(args[:3]) in data else data.get(tuple(args[:2]))
    return fake


TOOLS = {"which": lambda t: f"/usr/bin/{t}", "run_tool": lambda cmd: '{"terraform_version": "1.16.6"}', "env": {}}


def values(**extra):
    vals = engine.resolve(engine.load_schema(), {"_random4": "ab12"}, SOURCES).values
    vals.update(extra)
    return vals


def run_all(overrides=None, vals=None, **kw):
    """Every pre-install result, skipped ones included, plus the context."""
    kw = dict(TOOLS, **kw)
    ctx, results, started = main.evaluate(vals or values(), az=fake_az(overrides), **kw)
    return ctx, results, started


def by_title(overrides=None, **vals):
    return {r.title: r for r in preflight.run(values(**vals), az=fake_az(overrides), **TOOLS)}


class PreflightShimTests(unittest.TestCase):
    """Today's checks, through the shim, behave as they did before the registry."""

    def test_ready_subscription_passes(self):
        results = preflight.run(values(), az=fake_az(), **TOOLS)
        self.assertFalse([r for r in results if r.status == "fail"], results)

    def test_missing_owner_quota_and_provider_fail_with_fixes(self):
        results = preflight.run(values(), az=fake_az({
            ("role", "assignment"): ["Contributor"],
            ("provider", "list"): [{"ns": "Microsoft.Compute", "state": "Registered"}],
            ("vm", "list-usage"): [{"name": {"value": "standardDSv5Family"}, "limit": 4, "currentValue": 0},
                                   {"name": {"value": "cores"}, "limit": 100, "currentValue": 0}],
        }), **TOOLS)
        failed = {r.check for r in results if r.status == "fail"}
        self.assertEqual(failed, {"Subscription Owner", "Resource providers", "vCPU quota"})
        for r in results:
            if r.status == "fail":
                self.assertTrue(r.fix, r.check)

    def test_consent_needs_the_role_pair_or_global_admin(self):
        results = by_title({("rest", "directoryRole"): {"value": [{"displayName": "Cloud Application Administrator"}]}})
        self.assertEqual(results["Entra admin role"].status, "fail")

    def test_app_service_quota_of_zero_fails_with_the_fix_command(self):
        results = preflight.run(values(), az=fake_az({("rest", "Microsoft.Web"): {"value": [
            {"name": {"value": "B3 VMs", "localizedValue": "B3 VMs"}, "limit": 0, "currentValue": 0}]}}), **TOOLS)
        quota = [r for r in results if r.check == "App Service quota"]
        self.assertEqual([r.status for r in quota], ["fail"])
        self.assertIn("./nerdio fix quota", quota[0].fix)

    def test_app_service_quota_unreadable_warns(self):
        results = preflight.run(values(), az=fake_az({("rest", "Microsoft.Web"): None}), **TOOLS)
        self.assertEqual([r.status for r in results if r.check == "App Service quota"], ["warn"])

    def test_app_registration_blocked_without_a_role_fails(self):
        results = by_title({("rest", "directoryRole"): {"value": []}})
        self.assertEqual(results["App registration"].status, "fail")

    def test_contributor_plus_access_admin_counts_as_owner(self):
        results = by_title({("role", "assignment"): ["Contributor", "User Access Administrator"]})
        self.assertEqual(results["Subscription Owner"].status, "pass")

    def test_overlapping_vnet_warns_and_masks_its_name(self):
        results = by_title({("network", "vnet", "list"): [
            {"name": "vnet-other", "id": "/x/vnet-other", "prefixes": ["10.50.8.0/24"]}]})
        self.assertEqual(results["Address range"].status, "warn")
        self.assertNotIn("vnet-other", results["Address range"].detail)
        self.assertIn("<vnet-1> (10.50.8.0/24)", results["Address range"].detail)

    def test_names_flag_shows_names(self):
        results = {r.title: r for r in preflight.run(values(), az=fake_az({("network", "vnet", "list"): [
            {"name": "vnet-other", "id": "/x/vnet-other", "prefixes": ["10.50.8.0/24"]}]}), show_names=True, **TOOLS)}
        self.assertIn("vnet-other", results["Address range"].detail)

    def test_the_kits_own_earlier_resources_are_not_flagged(self):
        results = by_title({
            ("group", "list"): ["rg-nme-sbx-ab12-network"],
            ("network", "vnet", "list"): [{"name": "vnet-nme-sbx-ab12-avd", "id": "/x/v", "rg": "rg-nme-sbx-ab12-network",
                                           "prefixes": ["10.50.0.0/20"]}],
            ("network", "private-dns"): [{"name": "privatelink.blob.core.windows.net", "rg": "rg-nme-sbx-ab12-network"}]})
        self.assertEqual(results["Address range"].status, "pass")
        self.assertEqual(results["Private DNS"].status, "pass")

    def test_existing_central_zones_warn(self):
        results = by_title({("network", "private-dns"): [{"name": "privatelink.blob.core.windows.net", "rg": "rg-hub-dns"}]})
        self.assertEqual(results["Private DNS"].status, "warn")
        self.assertNotIn("rg-hub-dns", results["Private DNS"].detail)

    def test_policy_names_hide_ids(self):
        results = by_title({("policy", "assignment"): ["ASC Default (subscription: 11111111-2222-3333-4444-555555555555)"]})
        self.assertNotIn("11111111", results["Azure Policy"].detail)

    def test_enforced_policies_are_listed_with_a_command_not_a_portal_path(self):
        results = by_title({("policy", "assignment"): ["Allowed locations", "Require a tag"]})
        self.assertEqual(results["Azure Policy"].status, "manual")
        self.assertIn("Allowed locations", results["Azure Policy"].detail)
        self.assertIn("az policy assignment list", results["Azure Policy"].fix)
        self.assertNotIn("in the portal", results["Azure Policy"].fix)

    def test_unreadable_app_policy_gives_a_command(self):
        results = by_title({("rest", "directoryRole"): None, ("rest", "authorizationPolicy"): None})
        self.assertEqual(results["App registration"].status, "warn")
        self.assertTrue(results["App registration"].fix.startswith("az rest"))

    def test_region_scan_reports_each_region(self):
        az = fake_az({("account", "list-locations"): [
            {"name": "eastus2", "group": "US"}, {"name": "centralus", "group": "US"}, {"name": "eastus2euap", "group": "US"},
            {"name": "westeurope", "group": "Europe"}]})
        regions = preflight.nearby_regions("eastus2", az=az)
        found = preflight.scan_regions(values(), ZERO, regions, az=az)
        self.assertEqual(regions, ["centralus", "eastus2"])
        self.assertEqual(set(found), {"centralus", "eastus2"})
        self.assertIn("Azure SQL region", {r.check for r in found["centralus"]})
        self.assertEqual({r.id for r in found["eastus2"]}, {"avd.vm_size", "avd.vcpu", "sub.app_service", "sub.sql"})

    def test_hub_overlap_and_missing_rights_fail(self):
        hub = "/subscriptions/x/resourceGroups/hub/providers/Microsoft.Network/virtualNetworks/hub"
        results = by_title({("network", "vnet", "show"): {"prefixes": ["10.50.0.0/16"]},
                            ("role", "assignment"): ["Reader"]}, hub_vnet_id=hub)
        self.assertEqual(results["Hub network"].status, "fail")
        self.assertEqual(results["Hub peering rights"].status, "fail")

    def test_unreadable_hub_fails(self):
        results = by_title({("network", "vnet", "show"): None}, hub_vnet_id="/subscriptions/x/hub")
        self.assertEqual(results["Hub network"].status, "fail")

    def test_sql_region_closed_fails(self):
        results = by_title({("rest", "Microsoft.Sql"): {"status": "Disabled", "reason": "RegionDoesNotAllowProvisioning"}})
        self.assertEqual(results["Azure SQL region"].status, "fail")

    def test_marketplace_install_still_needs_app_service_and_sql(self):
        results = by_title(nerdio_install="marketplace")
        self.assertEqual(results["App Service quota"].status, "pass")
        self.assertEqual(results["Azure SQL region"].status, "pass")
        self.assertNotIn("Resource names", results)

    def test_ephemeral_cloud_shell_fails(self):
        _, results, _ = run_all(env={"AZUREPS_HOST_ENVIRONMENT": "cloud-shell/1.0", "HOME": "/home/x"},
                                isdir=lambda p: False)
        shell = [r for r in results if r.id == "op.cloudshell_storage"]
        self.assertEqual(shell[0].status, "fail")

    def test_not_signed_in_stops_early(self):
        results = preflight.run(values(), az=lambda args: None, **TOOLS)
        signin = [r for r in results if r.id == "op.signin"]
        self.assertEqual(signin[0].status, "fail")
        self.assertFalse([r for r in results if r.id.startswith(("id.", "net.", "sub.providers"))])

    def test_legacy_json_is_the_old_bare_list(self):
        out = json.loads(preflight.as_json(preflight.run(values(), az=fake_az(), **TOOLS)))
        self.assertIsInstance(out, list)
        self.assertEqual(set(out[0]), {"status", "check", "detail", "fix", "kb"})
        self.assertTrue({r["status"] for r in out} <= {"pass", "warn", "fail", "manual"})


def ids(overrides=None, vals=None, **kw):
    """Every result by check ID: {id: [results]}."""
    out = {}
    for r in run_all(overrides, vals=vals, **kw)[1]:
        out.setdefault(r.id, []).append(r)
    return out


def statuses(found, cid):
    return [r.status for r in found[cid]]


class PreInstallAdditionTests(unittest.TestCase):
    def test_hub_with_ipv6_prefixes_doesnt_crash(self):
        found = ids({("network", "vnet", "show"): {"prefixes": ["10.0.0.0/16", "fd00::/48"]}},
                    vals=values(hub_vnet_id="/subscriptions/x/hub"))
        self.assertNotIn("stopped unexpectedly", " ".join(r.detail for r in found["net.hub"]))

    """Phase 1c: the gaps found against Nerdio's preparation steps, and the new pre-install checks."""

    def test_everything_new_passes_on_a_ready_subscription(self):
        found = ids(vals=values(nerdio_install="terraform"))
        for cid in ("sub.type", "sub.locks", "sub.names", "id.pim_eligible", "id.tenant_match", "id.leftover_app",
                    "net.outbound"):
            self.assertTrue(set(statuses(found, cid)) <= {"pass", "manual"}, (cid, found[cid]))

    def test_recovery_services_is_now_required(self):
        rows = [{"ns": ns, "state": "Registered"} for ns in preflight.PROVIDERS if ns != "Microsoft.RecoveryServices"]
        found = ids({("provider", "list"): rows})
        self.assertEqual(statuses(found, "sub.providers"), ["fail"])
        self.assertIn("Microsoft.RecoveryServices", found["sub.providers"][0].detail)

    def test_feature_providers_and_host_pool_subscriptions(self):
        found = ids(vals=values(host_pool_subscriptions=["11111111-0000-0000-0000-000000000000"]), features=["ai"])
        self.assertEqual(len(found["sub.providers"]), 2)
        self.assertEqual(statuses(found, "sub.providers"), ["fail", "fail"])  # CognitiveServices isn't in the fixture
        self.assertIn("--subscription", found["sub.providers"][1].fix)

    def test_conditioned_owner_warns(self):
        found = ids({("role", "assignment"): [{"role": "Owner", "condition": "((!(ActionMatches{...})))"}]})
        self.assertEqual(statuses(found, "id.sub_owner"), ["warn"])
        found = ids({("role", "assignment"): [{"role": "Contributor", "condition": None},
                                              {"role": "Role Based Access Control Administrator", "condition": "x"}]})
        self.assertEqual(statuses(found, "id.sub_owner"), ["warn"])

    def test_eligible_but_inactive_owner_warns(self):
        found = ids({("role", "assignment"): ["Contributor"], ("rest", "roleEligibilityScheduleInstances"): {"value": [
            {"properties": {"expandedProperties": {"roleDefinition": {"displayName": "Owner"}}}}]}})
        self.assertEqual(statuses(found, "id.pim_eligible"), ["warn"])
        self.assertIn("./nerdio fix roles", found["id.pim_eligible"][0].fix)

    def test_unreadable_entra_eligibility_is_no_access_not_fail(self):
        found = ids({("rest", "directoryRole"): {"value": []}, ("rest", "roleEligibilityScheduleInstances"): None})
        self.assertIn("no-access", statuses(found, "id.pim_eligible"))
        self.assertNotIn("fail", statuses(found, "id.pim_eligible"))

    def test_guest_account_warns(self):
        found = ids({("rest", "/me?$select=userType"): {"userType": "Guest"}})
        self.assertEqual(statuses(found, "id.tenant_match"), ["warn"])

    def test_leftover_nerdio_app_warns(self):
        found = ids({("rest", "/applications"): {"value": [{"displayName": "nerdio-nmw-app",
                                                             "createdDateTime": "2025-01-02T00:00:00Z"}]}})
        self.assertEqual(statuses(found, "id.leftover_app"), ["warn"])
        self.assertIn("2025-01-02", found["id.leftover_app"][0].detail)

    def test_insights_needs_more_app_service_plans(self):
        web = {"value": [{"name": {"value": "B3 VMs", "localizedValue": "B3"}, "limit": 2, "currentValue": 0},
                         {"name": {"value": "P0v3 VMs", "localizedValue": "P0v3"}, "limit": 1, "currentValue": 0}]}
        found = ids({("rest", "Microsoft.Web"): web}, features=["insights"])
        quota = [r for r in found["sub.app_service"] if r.title == "App Service quota"]
        b3 = next(r for r in quota if r.detail.startswith("B3"))
        self.assertEqual(b3.status, "fail")
        self.assertIn("3 needed", b3.detail)
        self.assertIn("--limit 3", b3.fix)
        self.assertEqual(next(r for r in quota if r.detail.startswith("P0v3")).status, "pass")

    def test_free_trial_fails_for_marketplace_and_warns_for_the_kit(self):
        trial = {("rest", "api-version=2022-12-01"): {"subscriptionPolicies": {"quotaId": "FreeTrial_2014-09-01"}}}
        self.assertEqual(statuses(ids(trial, vals=values(nerdio_install="marketplace")), "sub.type"), ["fail"])
        self.assertEqual(statuses(ids(trial), "sub.type"), ["warn"])

    def test_marketplace_target_group_must_be_empty(self):
        vals = values(nerdio_install="marketplace", resource_group="rg-nerdio")
        found = ids({("group", "exists"): True, ("resource", "list"): ["Microsoft.Web/sites"]}, vals=vals)
        self.assertEqual(statuses(found, "sub.empty_rg"), ["fail"])
        self.assertNotIn("rg-nerdio", found["sub.empty_rg"][0].detail)
        self.assertEqual(statuses(ids(vals=vals), "sub.empty_rg"), ["pass"])

    def test_read_only_lock_fails(self):
        lock = {"level": "ReadOnly", "id": f"/subscriptions/{ZERO}/providers/Microsoft.Authorization/locks/freeze"}
        self.assertEqual(statuses(ids({("lock", "list"): [lock]}), "sub.locks"), ["fail"])
        other = dict(lock, id=f"/subscriptions/{ZERO}/resourceGroups/other/providers/Microsoft.Authorization/locks/x")
        self.assertEqual(statuses(ids({("lock", "list"): [other]}), "sub.locks"), ["warn"])

    def test_kit_names_follow_the_nerdio_core_module(self):
        from readiness.checks.subscription import kit_names
        ctx = Ctx(values())
        ctx.acct = {"id": ZERO}
        names = kit_names(ctx)
        self.assertTrue(names["key_vault"].startswith("nmw-app-kv-"))
        self.assertEqual(len(names["key_vault"]), 24)  # Key Vault's limit; 13-character suffix
        self.assertEqual(names["rg"], f"rg-{ctx.values['prefix']}-nerdio")

    def test_taken_names_fail_and_our_own_existing_ones_pass(self):
        found = ids({("rest", "checkNameAvailability"): {"nameAvailable": False}})
        self.assertEqual(statuses(found, "sub.names"), ["fail"])
        self.assertIn("SQL server", found["sub.names"][0].detail)
        from readiness.checks.subscription import kit_names
        ctx = Ctx(values())
        ctx.acct = {"id": ZERO}
        own = list(kit_names(ctx).values())
        found = ids({("rest", "checkNameAvailability"): {"nameAvailable": False}, ("resource", "list"): own})
        self.assertEqual(statuses(found, "sub.names"), ["pass"])

    def test_soft_deleted_vault_warns(self):
        from readiness.checks.subscription import kit_names
        ctx = Ctx(values())
        ctx.acct = {"id": ZERO}
        found = ids({("keyvault", "list-deleted"): [kit_names(ctx)["key_vault"]]})
        self.assertIn("warn", statuses(found, "sub.names"))

    def standalone_vals(self, **extra):
        return dict({"location": "eastus2", "vnet_id": "/subscriptions/x/resourceGroups/rg-net/providers/"
                     "Microsoft.Network/virtualNetworks/vnet-hub", "hosts_subnet": "snet-hosts",
                     "pe_subnet": "snet-pe", "app_subnet": "snet-app"}, **extra)

    def test_existing_subnets_need_the_app_service_delegation(self):
        found = ids({("network", "vnet", "subnet"): {"addressPrefix": "10.60.1.0/24", "delegations": []}},
                    vals=self.standalone_vals(), mode="standalone")
        app = found["net.subnets"][-1]
        self.assertEqual(app.status, "fail")
        self.assertIn("--delegations Microsoft.Web/serverFarms", app.fix)
        found = ids(vals=self.standalone_vals(), mode="standalone")
        self.assertEqual(statuses(found, "net.subnets"), ["pass", "pass", "pass"])

    def test_small_subnet_fails(self):
        found = ids({("network", "vnet", "subnet"): {"addressPrefix": "10.60.1.0/29"}}, vals=self.standalone_vals(),
                    mode="standalone")
        self.assertEqual(statuses(found, "net.subnets"), ["fail", "fail", "fail"])

    def test_outbound(self):
        no_way_out = {("network", "vnet", "subnet"): {"addressPrefix": "10.60.1.0/24", "defaultOutboundAccess": False}}
        self.assertEqual(statuses(ids(no_way_out, vals=self.standalone_vals(), mode="standalone"), "net.outbound"), ["fail"])
        legacy = {("network", "vnet", "subnet"): {"addressPrefix": "10.60.1.0/24"}}
        self.assertEqual(statuses(ids(legacy, vals=self.standalone_vals(), mode="standalone"), "net.outbound"), ["warn"])
        routed = {("network", "vnet", "subnet"): {"addressPrefix": "10.60.1.0/24", "routeTable": {"id": "/x/rt"}},
                  ("network", "route-table"): [{"prefix": "0.0.0.0/0", "hop": "VirtualAppliance"}]}
        self.assertEqual(statuses(ids(routed, vals=self.standalone_vals(), mode="standalone"), "net.outbound"), ["pass"])
        self.assertEqual(statuses(ids(vals=values(create_nat_gateway=False, hub_vnet_id="")), "net.outbound"), ["warn"])

    def test_automation_zone_is_looked_for(self):
        found = ids({("network", "private-dns"): [{"name": "privatelink.azure-automation.net", "rg": "rg-hub-dns"}]})
        self.assertEqual(statuses(found, "net.private_dns"), ["warn"])

    def test_ai_checks_run_only_with_the_feature_and_a_model(self):
        self.assertNotIn("ai.models", ids())
        found = ids(vals=values(ai_model="gpt-4o"), features=["ai"])
        self.assertEqual(statuses(found, "ai.models"), ["pass"])
        self.assertEqual(statuses(found, "ai.quota"), ["pass"])
        self.assertEqual(statuses(found, "ai.provider"), ["pass"])
        none = ids({("cognitiveservices", "usage", "list"): [{"name": {"value": "OpenAI.GlobalStandard.gpt-4o"},
                                                              "limit": 0, "currentValue": 0}],
                    ("cognitiveservices", "model", "list"): ["Standard"]}, vals=values(ai_model="gpt-4o"), features=["ai"])
        self.assertEqual(statuses(none, "ai.models"), ["fail"])
        self.assertEqual(statuses(none, "ai.quota"), ["fail"])
        self.assertEqual(statuses(ids(features=["ai"]), "ai.models"), ["skipped"])


class RegistryContractTests(unittest.TestCase):
    def test_every_check_has_needs_kb_source_and_never_writes(self):
        self.assertEqual(contract_problems(list(REGISTRY.values())), [])

    def test_kb_links_point_at_pages_that_exist(self):
        for c in REGISTRY.values():
            self.assertTrue((REPO / c.kb.split("#")[0]).exists(), f"{c.id}: {c.kb}")

    def test_full_runs_only_read(self):
        for overrides in (None, {("role", "assignment"): ["Reader"]}):
            ctx, _, _ = run_all(overrides, vals=values(hub_vnet_id="/subscriptions/x/hub"), features=list(runner.FEATURES))
            self.assertTrue(ctx.calls)
            for call in ctx.calls:
                self.assertTrue(is_read_only(call), call)

    def test_guard_tells_reads_from_writes(self):
        for args in (["account", "show"], ["vm", "list-skus", "-l", "x"], ["rest", "--method", "get", "--url", "u"],
                     ["rest", "--url", "u"], ["keyvault", "list-deleted"], ["cloud", "show"]):
            self.assertTrue(is_read_only(args), args)
        self.assertTrue(is_read_only(["rest", "--method", "post", "--url",
                                      "https://x/providers/Microsoft.Sql/checkNameAvailability?api-version=1", "--body", "{}"]))
        for args in (["provider", "register", "-n", "x"], ["rest", "--method", "post", "--url", "u"],
                     ["rest", "--url", "u", "--body", "{}"], ["group", "create", "-n", "x"], ["cloud", "set"], []):
            self.assertFalse(is_read_only(args), args)

    def test_a_check_that_writes_is_refused(self):
        ctx = Ctx({}, az=lambda args: {})
        with self.assertRaises(WriteRefused):
            ctx.az(["provider", "register", "-n", "Microsoft.Web"])

    def test_catalogue_kb_page_is_in_sync(self):
        self.assertTrue(catalogue.page_in_sync(), "run ./nerdio preflight --list --write")

    def test_ids_are_unique_and_registration_refuses_duplicates(self):
        with self.assertRaises(ValueError):
            check("op.signin", "again", needs="x", kb="x", source="https://x")(lambda ctx, c: None)


class SelectionTests(unittest.TestCase):
    def test_features_add_feature_checks_and_core_runs_without_them(self):
        core = {c.id for c in runner.select("pre-install")}
        self.assertIn("sub.providers", core)
        self.assertIn("avd.vcpu", core)
        self.assertNotIn("sub.providers", {c.id for c in runner.select("post-install")})

    def test_only_and_skip(self):
        self.assertEqual([c.id for c in runner.select("pre-install", only=["sub.region"])], ["sub.region"])
        self.assertNotIn("sub.region", {c.id for c in runner.select("pre-install", skip=["sub.region"])})

    def test_unknown_names_are_usage_errors(self):
        with self.assertRaises(runner.UsageError):
            runner.parse_features("app-attach,teleport")
        with self.assertRaises(runner.UsageError):
            runner.parse_ids("sub.nope")
        self.assertEqual(len(runner.parse_features("all")), len(runner.FEATURES))

    def test_missing_input_skips_instead_of_failing(self):
        vals = values()
        vals.pop("address_space")
        _, results, _ = run_all(vals=vals)
        overlap = [r for r in results if r.id == "net.overlap"]
        self.assertEqual(overlap[0].status, "skipped")
        self.assertIn("address_space", overlap[0].detail)

    def test_a_crashing_check_warns_and_the_run_goes_on(self):
        c = Check(id="op.boom", title="Boom", run=lambda ctx, c: 1 / 0, needs="none", kb="x", source="https://x",
                  account=False)
        got = runner.run_check(Ctx({}), c)
        self.assertEqual(got[0].status, "warn")


class VerdictTests(unittest.TestCase):
    def r(self, status, domain="subscription"):
        return Result(id="sub.x", status=status, title="x", detail="", domain=domain)

    def test_rules(self):
        self.assertEqual(report.verdict([self.r("pass")], "pre-install"), report.GO)
        self.assertEqual(report.verdict([self.r("pass"), self.r("manual")], "pre-install"), report.GO_WARN)
        self.assertEqual(report.verdict([self.r("pass"), self.r("warn")], "pre-install"), report.GO_WARN)
        self.assertEqual(report.verdict([self.r("fail"), self.r("no-access")], "pre-install"), report.NO_GO)
        self.assertEqual(report.verdict([self.r("skipped")], "pre-install"), report.INCOMPLETE)
        self.assertEqual(report.verdict([], "post-install"), report.INCOMPLETE)
        blind = [self.r("pass", "operator"), self.r("no-access", "identity"), self.r("pass")]
        self.assertEqual(report.verdict(blind, "pre-install"), report.INCOMPLETE)
        partly = [self.r("pass", "identity"), self.r("no-access", "identity")]
        self.assertEqual(report.verdict(partly, "pre-install"), report.GO_WARN)

    def test_exit_codes_and_strict(self):
        warn = [self.r("warn")]
        self.assertEqual(report.exit_code(report.GO_WARN, warn), 0)
        self.assertEqual(report.exit_code(report.GO_WARN, warn, strict=True), 1)
        self.assertEqual(report.exit_code(report.GO_WARN, [self.r("manual")], strict=True), 0)
        self.assertEqual(report.exit_code(report.NO_GO, []), 1)
        self.assertEqual(report.exit_code(report.INCOMPLETE, []), 3)


def schema_errors(value, schema, path="$"):
    """Enough JSON Schema (type, const, enum, pattern, required, properties, items) for readiness.schema.json."""
    errs = []
    types = {"object": dict, "array": list, "string": str, "integer": int}
    if "const" in schema and value != schema["const"]:
        errs.append(f"{path}: {value!r} != {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} not in {schema['enum']}")
    if "type" in schema and not isinstance(value, types[schema["type"]]):
        return errs + [f"{path}: not {schema['type']}"]
    if "pattern" in schema and not re.search(schema["pattern"], value):
        errs.append(f"{path}: {value!r} doesn't match {schema['pattern']}")
    if isinstance(value, dict):
        errs += [f"{path}: missing {k}" for k in schema.get("required", []) if k not in value]
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            errs += [f"{path}: unexpected {k}" for k in value if k not in props]
        for k, sub in props.items():
            if k in value:
                errs += schema_errors(value[k], sub, f"{path}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errs += schema_errors(item, schema["items"], f"{path}[{i}]")
    return errs


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.ctx, self.results, self.started = run_all({("rest", "Microsoft.Web"): {"value": [
            {"name": {"value": "B3 VMs", "localizedValue": "B3 VMs"}, "limit": 0, "currentValue": 0}]},
            ("network", "vnet", "list"): [{"name": "vnet-acme", "id": "/subscriptions/x/resourceGroups/rg-acme/providers/"
                                           "Microsoft.Network/virtualNetworks/vnet-acme", "prefixes": ["10.50.0.0/24"]}]})

    def test_json_matches_the_published_schema(self):
        doc = json.loads(main.render(self.ctx, self.results, self.started, "json", parameters_version="1"))
        schema = json.loads((REPO / "schema" / "readiness.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema_errors(doc, schema), [])
        self.assertEqual(doc["schema"], SCHEMA_ID)
        self.assertEqual(doc["verdict"], "NO-GO")
        self.assertIn("Owner", doc["identity"]["rights_seen"])
        self.assertEqual(doc["cloud"], "AzureCloud")

    def test_output_is_masked_by_default(self):
        for fmt in ("json", "md", "console"):
            text = main.render(self.ctx, self.results, self.started, fmt)
            for leaked in ("vnet-acme", "rg-acme", "sandbox", ZERO):
                self.assertNotIn(leaked, text, fmt)

    def test_markdown_is_short_and_lists_only_what_needs_attention(self):
        text = main.render(self.ctx, self.results, self.started, "md")
        self.assertTrue(text.startswith("## Nerdio readiness: NO-GO"))
        self.assertIn("`sub.app_service`", text)
        self.assertNotIn("Resource providers", text)  # passed, so only counted
        self.assertLess(len(text.splitlines()), 30)

    def test_console_groups_by_domain_failures_first(self):
        text = main.render(self.ctx, self.results, self.started, "console")
        lines = text.splitlines()
        self.assertLess(lines.index("[subscription]"), lines.index("[network]"))
        sub = lines[lines.index("[subscription]") + 1:]
        self.assertTrue(sub[0].startswith("✗"), sub[0])
        self.assertTrue(lines[-1].startswith("NO-GO: "), lines[-1])

    def test_unredacted_files_are_private(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "readiness.json")
            report.write_private(path, "{}")
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)


class CloudTests(unittest.TestCase):
    def test_government_endpoints_and_zones_come_from_az(self):
        gov = cloud.from_az(GOV_CLOUD)
        self.assertEqual(gov.arm, "https://management.usgovcloudapi.net")
        self.assertEqual(gov.graph_v1, "https://graph.microsoft.us/v1.0")
        self.assertIn("privatelink.vaultcore.usgovcloudapi.net", gov.private_dns_zones())
        self.assertIn("privatelink.azurewebsites.us", gov.private_dns_zones())
        self.assertEqual(cloud.COMMERCIAL.private_dns_zones(), [
            "privatelink.blob.core.windows.net", "privatelink.file.core.windows.net", "privatelink.database.windows.net",
            "privatelink.vaultcore.azure.net", "privatelink.azurewebsites.net", "privatelink.azure-automation.net"])

    def test_checks_call_the_active_clouds_endpoints(self):
        ctx, results, _ = run_all({("cloud", "show"): GOV_CLOUD})
        urls = [c[c.index("--url") + 1] for c in ctx.calls if c[0] == "rest"]
        self.assertTrue(urls)
        self.assertTrue(all(".us" in u.split("/")[2] for u in urls), urls)
        self.assertEqual([r.status for r in results if r.id == "op.cloud"], ["warn"])

    def test_an_unknown_cloud_stops_the_run(self):
        _, results, _ = run_all({("cloud", "show"): dict(COMMERCIAL_CLOUD, name="AzureStackLab")})
        self.assertEqual([r.status for r in results if r.id == "op.cloud"], ["fail"])
        self.assertTrue(all(r.status == "skipped" for r in results if r.id != "op.cloud"))

    def test_fix_uses_the_active_cloud(self):
        with mock.patch.object(cloud, "_current", cloud.from_az(GOV_CLOUD)):
            self.assertEqual(fix._arm(), "https://management.usgovcloudapi.net")
            self.assertEqual(fix._graph(), "https://graph.microsoft.us/v1.0")


class SchemaTagTests(unittest.TestCase):
    def test_readiness_tags_name_known_stages(self):
        schema = engine.load_schema()
        tagged = [p for p in schema["parameters"] if "readiness" in p]
        self.assertTrue(tagged)
        for p in tagged:
            self.assertTrue(set(p["readiness"]) <= set(STAGES), p["id"])
        bad = json.loads(json.dumps(schema))
        bad["parameters"][0]["readiness"] = ["someday"]
        self.assertTrue(any("readiness" in e for e in engine.check_schema(bad)))

    def test_every_input_a_pre_install_check_reads_is_tagged(self):
        from readiness import standalone
        tagged = set(engine.readiness_ids(engine.load_schema(), "pre-install")) | standalone.EXTRA_INPUTS
        for c in runner.select("pre-install", features=runner.FEATURES):
            self.assertTrue(set(c.inputs) <= tagged, (c.id, set(c.inputs) - tagged))


class CliTests(unittest.TestCase):
    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = nerdio.main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def test_list_needs_no_sign_in(self):
        code, out = self.cli("preflight", "--list")
        self.assertEqual(code, 0)
        self.assertIn("sub.providers", out)

    def test_bad_usage_exits_2(self):
        self.assertEqual(self.cli("preflight", "--features", "teleport")[0], 2)
        self.assertEqual(self.cli("preflight", "--no-redact")[0], 2)

    def test_json_run_prints_the_v1_object(self):
        with mock.patch.object(nerdio, "check_profile", return_value=True), \
             mock.patch.object(engine, "load_answers", return_value={"_random4": "ab12"}), \
             mock.patch.object(engine, "az_json", side_effect=fake_az()), \
             mock.patch("readiness.context.shutil.which", side_effect=TOOLS["which"]), \
             mock.patch("readiness.context.tool_version", side_effect=TOOLS["run_tool"]):
            code, out = self.cli("preflight", "--json", "--strict")
        doc = json.loads(out)
        self.assertEqual(doc["schema"], SCHEMA_ID)
        self.assertEqual(code, report.exit_code(doc["verdict"], [Result(**r) for r in doc["results"]], strict=True))


if __name__ == "__main__":
    unittest.main()
