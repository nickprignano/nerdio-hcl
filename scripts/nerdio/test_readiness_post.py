"""Tests for the post-install and post-wizard checks (nme.*, avd.*, hard.*, rbac.*, self.*, kit.*).

Run: python3 -m unittest discover -s scripts/nerdio
Every az, Graph and HTTPS call is answered from the fixtures below; nothing reaches the network.
"""

from __future__ import annotations

import datetime
import json
import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from readiness import main  # noqa: E402
from readiness.context import NOT_AZ, is_read_only  # noqa: E402
from readiness.checks.insights import IDENTITY_ROLES  # noqa: E402
from readiness.checks.subscription import FEATURE_PROVIDERS, PROVIDERS  # noqa: E402
from readiness.model import FEATURES, REGISTRY  # noqa: E402
from test_readiness import TOOLS, ZERO, fake_az, values  # noqa: E402

RG = "rg-nerdio"
SUB = f"/subscriptions/{ZERO}/resourceGroups/{RG}/providers"
WEB = f"{SUB}/Microsoft.Web/sites/nmw-app-abc"
RESOURCES = [
    {"name": "nmw-app-abc", "type": "Microsoft.Web/sites", "id": WEB},
    {"name": "nmw-app-plan-abc", "type": "Microsoft.Web/serverFarms", "id": f"{SUB}/Microsoft.Web/serverFarms/p"},
    {"name": "nmw-app-kv-abc", "type": "Microsoft.KeyVault/vaults", "id": f"{SUB}/Microsoft.KeyVault/vaults/kv"},
    {"name": "nmw-app-sql-abc", "type": "Microsoft.Sql/servers", "id": f"{SUB}/Microsoft.Sql/servers/s"},
    {"name": "nmw-app-db", "type": "Microsoft.Sql/servers/databases", "id": f"{SUB}/Microsoft.Sql/servers/s/databases/d"},
    {"name": "nmw-app-scripted-actions-abc", "type": "Microsoft.Automation/automationAccounts",
     "id": f"{SUB}/Microsoft.Automation/automationAccounts/a"},
    {"name": "nmw-app-insights-abc", "type": "Microsoft.Insights/components", "id": f"{SUB}/Microsoft.Insights/components/i"},
    {"name": "nmwdpabc", "type": "Microsoft.Storage/storageAccounts", "id": f"{SUB}/Microsoft.Storage/storageAccounts/st"},
    {"name": "nmw-app-law-abc", "type": "Microsoft.OperationalInsights/workspaces",
     "id": f"{SUB}/Microsoft.OperationalInsights/workspaces/law"},
]
ROLE_IDS = {"WvdAdmin": "r-admin", "DesktopAdmin": "r-desktop", "HelpDesk": "r-help", "Reviewer": "r-review",
            "EndUser": "r-user", "RestClient": "r-rest"}
APP = {"id": "app-obj", "appId": "app-id", "displayName": "nerdio-nmw-app", "keyCredentials": [],
       "requiredResourceAccess": [{"resourceAccess": [{"id": "graph-role", "type": "Role"},
                                                      {"id": "graph-scope", "type": "Scope"}]}]}
SP = {"id": "sp-obj", "appRoleAssignmentRequired": True, "accountEnabled": True,
      "appRoles": [{"id": i, "value": v} for v, i in ROLE_IDS.items()]}
ALL = [f for f in FEATURES if f != "ai"]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
HOST_POOL = f"/subscriptions/{ZERO}/resourceGroups/rg-avd/providers/Microsoft.DesktopVirtualization/hostPools/hp1"


def role_rows(args):
    """`az role assignment list` answers by what's asked: the shape each caller queries."""
    if "--assignee" in args and args[args.index("--assignee") + 1] == "sp-obj":
        return [{"role": "Reader", "scope": f"/subscriptions/{ZERO}"},
                {"role": "Backup Reader", "scope": f"/subscriptions/{ZERO}"},
                {"role": "Contributor", "scope": f"/subscriptions/{ZERO}/resourceGroups/{RG}"}]
    if "--assignee" in args and args[args.index("--assignee") + 1] == "avd-sp":
        return [{"role": "Desktop Virtualization Power On Off Contributor", "scope": f"/subscriptions/{ZERO}"}]
    if "--role" in args and args[args.index("--role") + 1] == "Reader and Data Access":
        return [{"id": "avd-sp", "name": "Azure Virtual Desktop"}, {"id": "arm-sp", "name": "Azure Virtual Desktop ARM Provider"}]
    if "--assignee" in args and args[args.index("--assignee") + 1] == "pid-intune":
        return [{"role": r, "scope": f"/subscriptions/{ZERO}/resourceGroups/{RG}"} for r in IDENTITY_ROLES]
    if "--role" in args:
        return ["user-group"]
    if "--scope" in args and "storageAccounts" in args[args.index("--scope") + 1]:
        return ["Storage File Data SMB Share Contributor", "Storage File Data SMB Share Elevated Contributor"]
    query = args[args.index("--query") + 1] if "--query" in args else ""
    if "Virtual Machine User Login" in query:
        return [f"/subscriptions/{ZERO}/resourceGroups/rg-avd"]
    return ["Owner"]


def post_az(overrides=None):
    """az answers for a healthy Nerdio Manager after its wizard; overrides change one answer."""
    data = {
        ("rest", "appRoleAssignedTo"): {"value": [
            {"appRoleId": "r-admin", "principalType": "User"}, {"appRoleId": "r-admin", "principalType": "Group"},
            {"appRoleId": "r-rest", "principalType": "ServicePrincipal"}] + [
            {"appRoleId": ROLE_IDS[r], "principalType": "Group", "principalId": f"g-{r}"}
            for r in ("DesktopAdmin", "HelpDesk", "Reviewer", "EndUser")]},
        ("rest", "/members?"): {"value": [{"id": "m"}]},
        ("rest", "conditionalAccess"): {"value": [{"state": "enabled", "conditions": {"applications": {
            "includeApplications": ["All"]}}, "grantControls": {"builtInControls": ["mfa"]}}]},
        ("rest", "basicPublishingCredentialsPolicies"): {"properties": {"allow": False}},
        ("rest", "/firewallRules"): {"value": []},
        ("rest", "/hybridRunbookWorkers?"): {"value": [{"properties": {"lastSeenDateTime": NOW}}]},
        ("rest", "hybridRunbookWorkerGroups"): {"value": [{"name": "hw", "id": f"{SUB}/Microsoft.Automation/a/hw"}]},
        ("rest", "/modules?"): {"value": [{"name": "Az.Accounts", "properties": {"version": "2.12.1",
                                                                              "provisioningState": "Succeeded"}}]},
        ("rest", "/subscribedSkus"): {"value": [{"skuPartNumber": "SPE_E3", "prepaidUnits": {"enabled": 100},
                                                 "servicePlans": [{"servicePlanName": "INTUNE_A"}]}]},
        ("rest", "appId eq '00000003-0000-0000-c000-000000000000'"): {"value": [{"id": "graph-sp", "appRoles": [
            {"id": "graph-role", "value": "DeviceManagementApps.ReadWrite.All"}, {"id": "dir", "value": "Directory.Read.All"}]}]},
        ("rest", "Microsoft.DocumentDB/locations"): {"value": [{"name": "East US 2", "properties": {
            "isSubscriptionRegionAccessAllowedForRegular": True}}]},
        ("rest", "dataCollectionRules"): {"value": [{"name": "microsoft-avdi-eastus2"}]},
        ("rest", "/scalingPlans?"): {"value": []},
        ("rest", "/workspaces?"): {"value": [{"id": f"{HOST_POOL}-ws", "name": "ws", "properties": {
            "applicationGroupReferences": [f"{HOST_POOL}-dag"]}}]},
        ("rest", "/appRoleAssignments"): {"value": [{"appRoleId": "graph-role"}, {"appRoleId": "dir"}]},
        ("rest", "oauth2PermissionGrants"): {"value": [{"consentType": "AllPrincipals"}]},
        ("rest", "/servicePrincipals?"): {"value": [SP]},
        ("rest", "/applications?$filter=startswith(displayName,'nerdio-nmw-app')&$select=id,appId"): {"value": [APP]},
        ("rest", "/runbooks"): {"value": [{"name": "nmwUpdateRunAs"}, {"name": "nmwScriptedAction"}]},
        ("rest", "automationAccounts/a/certificates"): {"value": []},
        ("rest", "/sessionHosts"): {"value": [{"name": "hp1/host-0", "properties": {"status": "Available"}},
                                              {"name": "hp1/host-1", "properties": {"status": "Shutdown"}}]},
        ("rest", "diagnosticSettings"): {"value": [{"name": "nerdio"}]},
        ("rest", "/privateEndpointConnections?"): {"value": [{"name": "pe"}]},
        ("rest", "/hostPools?"): {"value": [{"id": HOST_POOL, "name": "hp1", "properties": {
            "hostPoolType": "Pooled", "maxSessionLimit": 16,
            "customRdpProperty": "targetisaadjoined:i:1;enablerdsaadauth:i:1", "startVMOnConnect": True}}]},
        ("rest", "/msixPackages"): {"value": [{"name": "hp1/pkg1", "properties": {"imagePath": "\\\\st\\msix\\app.vhdx"}}]},
        ("rest", "OperationalInsights/workspaces/law"): {"properties": {"retentionInDays": 30, "sku": {"name": "PerGB2018"}}},
        ("rest", "/applicationGroups?"): {"value": [{"id": f"{HOST_POOL}-dag", "name": "hp1-dag"}]},
        ("resource", "list"): RESOURCES,
        ("webapp", "show"): {"state": "Running", "https": True, "identity": "SystemAssigned",
                             "host": "nmw-app-abc.azurewebsites.net", "subnet": "/x/subnet", "routeAll": True},
        ("webapp", "config", "access-restriction"): {"ipSecurityRestrictions": [
            {"action": "Allow", "ipAddress": "198.51.100.0/24"}, {"action": "Deny", "ipAddress": "Any"}]},
        ("sql", "server", "show"): {"entraOnly": True, "public": "Disabled"},
        ("sql", "db", "show"): {"collation": "SQL_Latin1_General_CP1_CI_AS", "slo": "S1"},
        ("keyvault", "certificate", "list"): [{"name": "nmw-app-cert", "expires": "2099-01-01T00:00:00+00:00"}],
        ("keyvault", "show"): {"purge": False},
        ("resource", "show"): {"public": "Disabled", "pe": 1, "identity": "SystemAssigned"},
        ("webapp", "config", "show"): {"tls": "1.2", "ftps": "Disabled", "rules": 2, "useMain": True},
        ("storage", "account", "list"): [{"id": f"{SUB}/Microsoft.Storage/storageAccounts/stprofiles", "auth": "AADKERB",
                                          "public": "Disabled", "endpoints": 1}],
        ("lock", "list"): ["CanNotDelete"],
        ("monitor", "action-group", "list"): [],
        ("backup", "vault", "list"): ["eastus2"],
        ("provider", "list"): [{"ns": ns, "state": "Registered"} for ns in
                               [*PROVIDERS, "Microsoft.DocumentDB", "Microsoft.ManagedIdentity",
                                           *[p for ps in FEATURE_PROVIDERS.values() for p in ps]]],
        ("network", "nsg", "list"): [],
        ("sig", "list"): [],
        ("webapp", "identity", "show"): "pid-intune",
        ("role", "assignment", "list"): role_rows,
        ("ad", "sp", "list"): lambda args: "arm-sp" if "50e95039" in " ".join(args) else "avd-sp",
    }
    # Overrides first, so a specific URL fragment wins over a general default.
    overrides = overrides or {}
    data = {**overrides, **{k: v for k, v in data.items() if k not in overrides}}
    base = fake_az()

    def fake(args):
        if args[0] == "rest":
            url = args[args.index("--url") + 1]
            hit = next(((v,) for key, v in data.items() if key[0] == "rest" and key[1] in url), None)
            return hit[0] if hit else base(args)
        for n in (3, 2):
            if tuple(args[:n]) in data:
                v = data[tuple(args[:n])]
                return v(args) if callable(v) else v
        return base(args)
    return fake


def health(status=200, body='{"status":"Healthy"}'):
    calls = []

    def get(url):
        calls.append(url)
        return status, body
    get.calls = calls
    return get


def run(stage="post-wizard", overrides=None, features=(), http=None, mode="kit", nerdio_data=False, nerdio_client=None,
        **vals):
    vals = values(resource_group=RG, fslogix_storage_account_name="stprofiles", **vals)
    ctx, results, _ = main.evaluate(vals, az=post_az(overrides), stage=stage, features=list(features), mode=mode,
                                    http=http or health(), nerdio_data=nerdio_data, nerdio_client=nerdio_client,
                                    **dict(TOOLS, isdir=lambda p: False))
    return ctx, results


def by_id(results):
    out = {}
    for r in results:
        out.setdefault(r.id, []).append(r.status)
    return out


class HealthyInstallTests(unittest.TestCase):
    def test_healthy_install_passes_every_stage(self):
        for stage in ("post-install", "post-wizard"):
            _, results = run(stage, features=ALL)
            bad = [(r.id, r.status, r.detail) for r in results if r.status in ("fail", "warn", "no-access")]
            self.assertFalse(bad, stage)

    def test_post_runs_only_read(self):
        ctx, _ = run("post-install", features=ALL)
        ctx2, _ = run("post-wizard", features=ALL)
        for call in ctx.calls + ctx2.calls:
            self.assertTrue(call[0] in NOT_AZ or is_read_only(call), call)
        gets = [c for c in ctx.calls if c[0] == "GET"]
        self.assertEqual(gets, [["GET", "https://nmw-app-abc.azurewebsites.net/public/health/status"]])

    def test_stages_pick_their_checks(self):
        _, installed = run("post-install")
        _, wizard = run("post-wizard")
        self.assertIn("nme.health", by_id(installed))
        self.assertNotIn("avd.assignments", by_id(installed))
        self.assertIn("avd.assignments", by_id(wizard))
        self.assertIn("nme.health", by_id(wizard))  # post-wizard re-runs the post-install checks
        self.assertNotIn("id.sub_owner", by_id(wizard))
        self.assertNotIn("hard.defender", by_id(installed))  # a feature check needs --features


class NerdioManagerTests(unittest.TestCase):
    def test_no_group_skips_with_how_to_find_it(self):
        vals = values(fslogix_storage_account_name="x")
        _, results, _ = main.evaluate(vals, az=post_az(), stage="post-install", mode="standalone", http=health(), **TOOLS)
        found = {r.id: r for r in results}
        self.assertEqual(found["nme.discover"].status, "skipped")
        self.assertIn("--resource-group", found["nme.discover"].detail)

    def test_group_from_the_url(self):
        vals = values(nerdio_url="https://nmw-app-abc.azurewebsites.net/")
        _, results, _ = main.evaluate(vals, az=post_az({("webapp", "list"): [RG]}), stage="post-install",
                                      mode="standalone", http=health(), **TOOLS)
        self.assertEqual(by_id(results)["nme.discover"], ["pass"])

    def test_stopped_app_and_weak_tls(self):
        _, r = run("post-install", {("webapp", "show"): {"state": "Stopped"}})
        self.assertEqual(by_id(r)["nme.app"], ["fail"])
        _, r = run("post-install", {("webapp", "config", "show"): {"tls": "1.0", "ftps": "AllAllowed"}})
        self.assertEqual(by_id(r)["nme.app"], ["warn"])

    def test_health_rate_limit_is_skipped_not_unhealthy(self):
        _, r = run("post-install", http=health(429))
        self.assertEqual(by_id(r)["nme.health"], ["skipped"])
        _, r = run("post-install", http=health(503))
        self.assertEqual(by_id(r)["nme.health"], ["fail"])
        _, r = run("post-install", http=health(None, "timed out"))
        self.assertEqual(by_id(r)["nme.health"], ["fail"])

    def test_missing_consent(self):
        _, r = run("post-install", {("rest", "/appRoleAssignments"): {"value": []}})
        found = [x for x in r if x.id == "nme.entra_app"]
        self.assertEqual([x.status for x in found], ["fail"])
        self.assertIn("admin consent", found[0].detail)
        _, r = run("post-install", {("rest", "oauth2PermissionGrants"): {"value": []}})
        self.assertEqual(by_id(r)["nme.entra_app"], ["fail"])

    def test_sp_roles_missing_and_too_broad(self):
        def only_reader(args):
            return [{"role": "Reader", "scope": f"/subscriptions/{ZERO}"}] if "sp-obj" in args else role_rows(args)

        def owner(args):
            return [{"role": "Owner", "scope": f"/subscriptions/{ZERO}"}, {"role": "Reader", "scope": f"/subscriptions/{ZERO}"},
                    {"role": "Backup Reader", "scope": f"/subscriptions/{ZERO}"}] if "sp-obj" in args else role_rows(args)
        _, r = run("post-install", {("role", "assignment", "list"): only_reader})
        self.assertEqual(by_id(r)["nme.sp_roles"], ["fail"])
        _, r = run("post-install", {("role", "assignment", "list"): owner})
        self.assertEqual(by_id(r)["nme.sp_roles"], ["warn"])

    def test_sql_collation_and_tier(self):
        _, r = run("post-install", {("sql", "db", "show"): {"collation": "SQL_Latin1_General_CP1_CS_AS", "slo": "Basic"}})
        self.assertEqual(sorted(by_id(r)["nme.sql"]), ["fail", "warn"])

    def test_expiring_certificate(self):
        _, r = run("post-install", {("keyvault", "certificate", "list"): [{"name": "c", "expires": "2000-01-01T00:00:00Z"}]})
        self.assertEqual(by_id(r)["nme.keyvault"], ["warn"])

    def test_missing_updater_runbook(self):
        _, r = run("post-install", {("rest", "/runbooks"): {"value": [{"name": "other"}]}})
        self.assertEqual(by_id(r)["nme.automation"], ["fail"])

    def test_smart_detection_group_warns(self):
        _, r = run("post-install", {("monitor", "action-group", "list"): ["Application Insights Smart Detection"]})
        self.assertEqual(by_id(r)["nme.smart_detection"], ["warn"])

    def test_rest_api_needs_a_rest_client(self):
        _, r = run("post-wizard", {("rest", "appRoleAssignedTo"): {"value": [{"appRoleId": "r-admin"}]}})
        self.assertEqual(by_id(r)["nme.rest_api"], ["fail"])

    def test_version_is_manual(self):
        _, r = run("post-install")
        self.assertEqual(by_id(r)["nme.version"], ["manual"])


class ReviewFixTests(unittest.TestCase):
    def test_arm_timestamps_with_seven_fraction_digits(self):
        from readiness.checks.nerdio import days_left, parse_time
        self.assertIsNotNone(parse_time("2021-07-20T08:46:56.2933342+00:00"))
        self.assertLess(days_left("2000-01-01T00:00:00.1234567Z"), 0)
        self.assertIsNone(parse_time(None))

    def test_graph_lists_follow_next_link(self):
        page2 = "https://graph.microsoft.com/v1.0/page2?$skiptoken=2"
        first = {"value": [{"appRoleId": "r-user", "principalType": "Group"}], "@odata.nextLink": page2}
        rest = {"value": [{"appRoleId": "r-admin", "principalType": "User"}, {"appRoleId": "r-admin", "principalType": "Group"}]}
        _, r = run(overrides={("rest", "$skiptoken=2"): rest, ("rest", "appRoleAssignedTo"): first}, features=["rbac"])
        self.assertEqual(by_id(r)["rbac.admins"], ["pass"])

    def test_automation_public_access_is_a_boolean(self):
        from readiness.checks.hardening import public_off
        self.assertTrue(public_off(False))
        self.assertTrue(public_off("Disabled"))
        self.assertFalse(public_off(True))
        self.assertFalse(public_off(None))

    def test_unreadable_reads_are_never_a_pass(self):
        _, r = run(overrides={("rest", "diagnosticSettings"): None}, features=["hardening"])
        found = by_id(r)
        self.assertEqual(found["hard.diagnostics"], ["no-access"])
        self.assertEqual(found["avd.diagnostics"], ["no-access"])

        def unreadable(args):
            return None if "--role" in args else role_rows(args)
        _, r = run(overrides={("role", "assignment", "list"): unreadable})
        self.assertEqual(by_id(r)["avd.assignments"], ["no-access"])
        _, r = run(overrides={("rest", "/members?"): None}, features=["rbac"])
        self.assertEqual(by_id(r)["rbac.groups"], ["no-access"] * 4)

    def test_new_unhealthy_statuses(self):
        hosts = {"value": [{"name": "hp1/h", "properties": {"status": "NoHeartbeat"}}]}
        _, r = run(overrides={("rest", "/sessionHosts"): hosts})
        self.assertEqual(by_id(r)["avd.host_health"], ["warn"])

    def test_health_failure_hides_the_hostname(self):
        import ssl
        import urllib.error
        from readiness import context
        with unittest.mock.patch("urllib.request.urlopen",
                                 side_effect=urllib.error.URLError(ssl.SSLError("hostname 'nme.contoso.com' mismatch"))):
            status, body = context.http_get("https://nme.contoso.com/public/health/status")
        self.assertIsNone(status)
        self.assertNotIn("contoso", body)


class AvdTests(unittest.TestCase):
    def test_entra_joined_pool_needs_entra_sign_in(self):
        pool = {"value": [{"id": HOST_POOL, "name": "hp1", "properties": {"customRdpProperty": ""}}]}
        _, r = run(overrides={("rest", "/hostPools?"): pool}, identity_model="entra_joined")
        self.assertEqual(by_id(r)["avd.entra_join_login"], ["fail"])

    def test_no_pools_skip(self):
        _, r = run(overrides={("rest", "/hostPools?"): {"value": []}}, features=ALL)
        found = by_id(r)
        self.assertEqual(found["avd.host_health"], ["skipped"])
        self.assertEqual(found["avd.start_vm_on_connect"], ["skipped"])

    def test_unhealthy_hosts_name_the_failing_check(self):
        hosts = {"value": [{"name": "hp1/h", "properties": {"status": "NeedsAssistance", "sessionHostHealthCheckResults": [
            {"healthCheckName": "DomainJoinedCheck", "healthCheckResult": "HealthCheckFailed"}]}},
            {"name": "hp1/u", "properties": {"status": "Upgrading"}}]}
        _, r = run(overrides={("rest", "/sessionHosts"): hosts})
        found = [x for x in r if x.id == "avd.host_health"]
        self.assertEqual([x.status for x in found], ["warn"])
        self.assertIn("1 of 2", found[0].detail)
        self.assertIn("DomainJoinedCheck", found[0].detail)

    def test_empty_app_group_and_no_workspace(self):
        def nobody(args):
            return [] if "--role" in args else role_rows(args)
        _, r = run(overrides={("role", "assignment", "list"): nobody, ("rest", "/workspaces?"): {"value": []}})
        self.assertEqual(by_id(r)["avd.assignments"], ["warn", "warn"])

    def test_entra_login_role(self):
        def none(args):
            q = args[args.index("--query") + 1] if "--query" in args else ""
            return [] if "Virtual Machine User Login" in q else role_rows(args)
        _, r = run(overrides={("role", "assignment", "list"): none}, identity_model="entra_joined")
        self.assertEqual(by_id(r)["avd.entra_join_login"], ["fail"])

    def test_power_roles(self):
        def none(args):
            return [] if "avd-sp" in args else role_rows(args)
        _, r = run(overrides={("role", "assignment", "list"): none}, features=["automation"])
        self.assertEqual(by_id(r)["avd.start_vm_on_connect"], ["fail"])

        def low_scope(args):
            if "avd-sp" in args:
                return [{"role": "Desktop Virtualization Power On Off Contributor", "scope": f"/subscriptions/{ZERO}/resourceGroups/x"}]
            return role_rows(args)
        plans = {("rest", "/scalingPlans?"): {"value": [{"id": "plan"}]}, ("role", "assignment", "list"): low_scope}
        _, r = run(overrides=plans, features=["automation"])
        found = [x for x in r if x.id == "avd.start_vm_on_connect"]
        self.assertEqual([x.status for x in found], ["fail"])
        self.assertIn("subscription", found[0].detail)

    def test_diagnostics(self):
        _, r = run(overrides={("rest", "diagnosticSettings"): {"value": []}})
        self.assertEqual(by_id(r)["avd.diagnostics"], ["warn"])

    def test_fslogix_auth_roles_and_exposure(self):
        bad = [{"id": "/x/storageAccounts/p", "auth": "None", "public": "Enabled", "endpoints": 0}]

        def no_share_roles(args):
            return [] if "--scope" in args and "storageAccounts" in args[args.index("--scope") + 1] else role_rows(args)
        _, r = run(overrides={("storage", "account", "list"): bad, ("role", "assignment", "list"): no_share_roles},
                   identity_model="entra_joined")
        self.assertEqual(sorted(by_id(r)["avd.fslogix_storage"]), ["fail", "fail", "warn"])
        _, r = run(overrides={("storage", "account", "list"): []})
        self.assertEqual(by_id(r)["avd.fslogix_storage"], ["fail"])

    def test_fslogix_region_before_the_install(self):
        _, r = run("pre-install", {("storage", "sku", "list"): [["westeurope"]]})
        self.assertEqual(by_id(r)["avd.fslogix_storage"], ["fail"])
        _, r = run("pre-install", fslogix_enabled=False)
        self.assertEqual(by_id(r)["avd.fslogix_storage"], ["skipped"])

    def test_image(self):
        _, r = run("pre-install")
        self.assertEqual(by_id(r)["avd.image"], ["pass"])
        _, r = run("pre-install", {("vm", "image", "list-skus"): ["win10-22h2-avd"]})
        self.assertEqual(by_id(r)["avd.image"], ["fail"])


class FeatureTests(unittest.TestCase):
    def test_hardening_finds_open_services(self):
        _, r = run(overrides={("resource", "show"): {"public": "Enabled", "pe": 0},
                              ("webapp", "show"): {"state": "Running", "subnet": None},
                              ("rest", "/firewallRules"): {"value": [{"name": "AllowAllWindowsAzureIps"}]},
                              ("rest", "basicPublishingCredentialsPolicies"): {"properties": {"allow": True}},
                              ("rest", "conditionalAccess"): {"value": []},
                              ("rest", "diagnosticSettings"): {"value": []},
                              ("lock", "list"): []}, features=["hardening"])
        found = by_id(r)
        for cid in ("hard.private_endpoints", "hard.vnet_integration", "hard.sql_firewall", "hard.mfa",
                    "hard.diagnostics", "hard.locks"):
            self.assertEqual(found[cid], ["warn"], cid)
        self.assertEqual(found["hard.scm"], ["warn"])
        self.assertEqual(found["hard.kv_purge"], ["pass"])

    def test_private_storage_without_a_hybrid_worker(self):
        _, r = run(overrides={("rest", "hybridRunbookWorkerGroups"): {"value": []}}, features=["hardening"])
        self.assertEqual(by_id(r)["hard.runbooks_vs_private_storage"], ["warn"])

    def test_conditional_access_unreadable_is_manual(self):
        _, r = run(overrides={("rest", "conditionalAccess"): None}, features=["hardening"])
        self.assertEqual(by_id(r)["hard.mfa"], ["manual"])

    def test_admins_need_a_direct_person_and_a_second(self):
        only_group = {"value": [{"appRoleId": "r-admin", "principalType": "Group"}]}
        _, r = run(overrides={("rest", "appRoleAssignedTo"): only_group}, features=["rbac", "self-service"])
        found = by_id(r)
        self.assertEqual(found["rbac.admins"], ["fail"])
        self.assertEqual(found["self.end_user_role"], ["fail"])
        self.assertEqual(found["rbac.groups"], ["warn"])
        one = {"value": [{"appRoleId": "r-admin", "principalType": "User"}]}
        _, r = run(overrides={("rest", "appRoleAssignedTo"): one}, features=["rbac"])
        self.assertEqual(by_id(r)["rbac.admins"], ["warn"])

    def test_empty_role_group(self):
        _, r = run(overrides={("rest", "/members?"): {"value": []}}, features=["rbac"])
        self.assertEqual(by_id(r)["rbac.groups"], ["warn"] * 4)

    def test_self_service_consent(self):
        _, r = run(overrides={("rest", "oauth2PermissionGrants"): {"value": []}}, features=["self-service"])
        self.assertEqual(by_id(r)["self.consent"], ["fail"])

    def test_azure_side_before_the_install(self):
        _, r = run("pre-install", features=["rbac"])
        self.assertEqual(by_id(r)["rbac.azure_side"], ["pass"])

    def test_app_mgmt_repository(self):
        no_storage = [x for x in RESOURCES if x["type"] != "Microsoft.Storage/storageAccounts"]
        _, r = run(overrides={("resource", "list"): no_storage}, features=["app-mgmt"])
        self.assertEqual(by_id(r)["app.repository"], ["fail"])

    def test_app_attach_packages(self):
        _, r = run(overrides={("rest", "/msixPackages"): {"value": []}}, features=["app-attach"])
        self.assertEqual(by_id(r)["attach.packages"], ["skipped"])
        bad_pkg = {"value": [{"name": "hp1/pkg1", "properties": {"imagePath": ""}}]}
        _, r = run(overrides={("rest", "/msixPackages"): bad_pkg}, features=["app-attach"])
        self.assertEqual(by_id(r)["attach.packages"], ["warn"])

    def test_insights_workspace_retention(self):
        short = {"properties": {"retentionInDays": 7, "sku": {"name": "PerGB2018"}}}
        _, r = run(overrides={("rest", "OperationalInsights/workspaces/law"): short}, features=["insights"])
        self.assertEqual(by_id(r)["ins.workspace"], ["warn"])

    def test_scripted_actions_identity(self):
        _, r = run(overrides={("resource", "show"): {"identity": "None"}}, features=["scripted-actions"])
        self.assertEqual(by_id(r)["sa.automation_identity"], ["warn"])

    def test_automation_scaling_session_limit(self):
        unbounded = {"value": [{"id": HOST_POOL, "name": "hp1", "properties": {
            "hostPoolType": "Pooled", "maxSessionLimit": 999999,
            "customRdpProperty": "targetisaadjoined:i:1", "startVMOnConnect": True}}]}
        _, r = run(overrides={("rest", "/hostPools?"): unbounded}, features=["automation"])
        self.assertEqual(by_id(r)["auto.scaling"], ["warn"])


class KitTerraformTests(unittest.TestCase):
    def state(self, status):
        return json.dumps({"check_results": [{"config_addr": "module.core.check.nerdio_health", "status": status,
                                              "objects": [{"failure_messages": ["Nerdio Manager isn't answering yet."]}]}]})

    def run_kit(self, raw):
        vals = values(resource_group=RG)
        kw = dict(TOOLS, isdir=lambda p: p.replace("\\", "/").endswith("01-platform/.terraform"), run_tool=lambda cmd: raw)
        _, results, _ = main.evaluate(vals, az=post_az(), stage="post-install", only=["kit.terraform_checks"],
                                      http=health(), **kw)
        return results

    def test_failed_check_fails(self):
        results = self.run_kit(self.state("fail"))
        self.assertEqual([r.status for r in results], ["fail"])
        self.assertIn("isn't answering", results[0].detail)

    def test_passed_and_missing(self):
        self.assertEqual([r.status for r in self.run_kit(self.state("pass"))], ["pass"])
        self.assertEqual([r.status for r in self.run_kit("{}")], ["skipped"])

    def test_standalone_has_no_kit_checks(self):
        self.assertEqual(REGISTRY["kit.terraform_checks"].modes, ("kit",))


if __name__ == "__main__":
    unittest.main()
