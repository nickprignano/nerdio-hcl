"""sub.*: the subscription: providers, region, App Service and SQL capacity, policy."""

from __future__ import annotations

import re

from ..model import check

KB = "docs/knowledge/nerdio/platform.md#marketplace-deployment"
NERDIO_PREP = "https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps"
NERDIO_SCRIPT = "https://github.com/Get-Nerdio/NME-SE/tree/main/preflight"
UUID_IN_TEXT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

# App Service REST API version for Get Usages in Location, and the SQL capabilities API.
WEB_API = "2024-11-01"
SQL_API = "2021-11-01"

# Namespaces the kit's resources live in, including what Nerdio's own deployment creates.
PROVIDERS = [
    "Microsoft.DesktopVirtualization",
    "Microsoft.Compute",
    "Microsoft.Network",
    "Microsoft.Storage",
    "Microsoft.Web",
    "Microsoft.Sql",
    "Microsoft.KeyVault",
    "Microsoft.Automation",
    "Microsoft.Insights",
    "Microsoft.OperationalInsights",
]


def terraform_install(ctx) -> bool:
    return ctx.values.get("nerdio_install", "terraform") == "terraform"


@check("sub.providers", "Resource providers", needs="Reader on the subscription", kb=KB, source=NERDIO_PREP,
       reads=["az provider list"])
def providers(ctx, c):
    rows = ctx.az(["provider", "list", "--query", "[].{ns:namespace, state:registrationState}"])
    if rows is None:
        return c.warn("couldn't list resource providers", "az provider list -o table")
    state = {r["ns"].lower(): r["state"] for r in rows}
    missing = [ns for ns in PROVIDERS if state.get(ns.lower()) != "Registered"]
    if not missing:
        return c.ok(f"all {len(PROVIDERS)} registered")
    return c.fail("not registered: " + ", ".join(missing), " && ".join(f"az provider register -n {ns}" for ns in missing))


@check("sub.region", "Region", needs="Reader on the subscription", kb=KB, inputs=["location"],
       source="https://learn.microsoft.com/cli/azure/account#az-account-list-locations", reads=["az account list-locations"])
def region(ctx, c):
    location = ctx.values["location"]
    names = ctx.az(["account", "list-locations", "--query", "[].name"])
    if names is None:
        return c.warn(f"couldn't list regions to check {location}")
    if location in names:
        return c.ok(f"{location} is available to this subscription")
    return c.fail(f"{location} isn't a region this subscription can use", "az account list-locations -o table")


@check("sub.policy_list", "Azure Policy", needs="Reader on the subscription", kb=KB,
       source="https://learn.microsoft.com/azure/governance/policy/overview", reads=["az policy assignment list"])
def policy_list(ctx, c):
    """Deny policies (allowed locations, allowed SKUs, no public access, required tags) fail an apply late."""
    rows = ctx.az(["policy", "assignment", "list", "--scope", f"/subscriptions/{ctx.subscription_id}",
                   "--disable-scope-strict-match", "--query", "[?enforcementMode=='Default'].displayName"])
    if rows is None:
        return c.warn("couldn't list the policy assignments that apply to this subscription")
    # Some built-in assignment names carry the subscription ID; keep it out of output people paste.
    rows = sorted({UUID_IN_TEXT.sub("<id>", r) for r in rows if r})
    if not rows:
        return c.ok("no enforced policy assignments on this subscription")
    shown = ", ".join(rows[:8]) + (f" and {len(rows) - 8} more" if len(rows) > 8 else "")
    return c.manual(f"{len(rows)} enforced assignments apply: {shown}",
                    "Check none of them deny the kit's regions, SKUs, public endpoints or missing tags; read their rules "
                    "with az policy assignment list --disable-scope-strict-match --query "
                    "\"[?enforcementMode=='Default'].{name:displayName, policy:policyDefinitionId}\" -o table "
                    f"and az policy definition show. Nerdio's readiness script ({NERDIO_SCRIPT}) tests whether they "
                    "deny the install; a deny otherwise shows up only at apply time")


@check("sub.app_service", "App Service quota", needs="Reader on the subscription", kb=KB, source=NERDIO_PREP,
       inputs=["location"], region=True, reads=["az appservice list-locations", "ARM Microsoft.Web/locations/usages"])
def app_service(ctx, c):
    """Nerdio Manager runs on a Windows App Service plan (B3 by default). Sandbox and trial
    subscriptions often have a limit of 0 for some tiers, and the apply then fails late with
    "Operation cannot be completed without additional quota"."""
    if not terraform_install(ctx):
        return c.skip("the Marketplace install sizes its own plan")
    location = ctx.values["location"]
    sku = ctx.values.get("app_service_plan_sku") or "B3"
    out = []
    regions = ctx.az(["appservice", "list-locations", "--sku", sku, "--query", "[].name"])
    wanted = location.replace(" ", "").lower()
    if regions is None:
        out.append(c.warn(f"couldn't check whether {sku} is offered in {location}", title="App Service SKU"))
    elif wanted in {r.replace(" ", "").lower() for r in regions}:
        out.append(c.ok(f"{sku} is offered in {location}", title="App Service SKU"))
    else:
        out.append(c.fail(f"{sku} isn't offered in {location}",
                          f"az appservice list-locations --sku {sku} -o table, then pick another region or SKU",
                          title="App Service SKU"))
    rows = ctx.get(ctx.arm(f"/subscriptions/{ctx.subscription_id}/providers/Microsoft.Web"
                           f"/locations/{location}/usages?api-version={WEB_API}"))
    request = f"./nerdio fix quota --sku {sku} --location {location}"
    if rows is None:
        out.append(c.warn(f"couldn't read App Service quota in {location}",
                          "If the apply fails with 'without additional quota': " + request))
        return out
    sku_l = sku.lower()
    row = next((u for u in rows.get("value", [])
                if sku_l in (u.get("name", {}).get("value", "") + " " + u.get("name", {}).get("localizedValue", "")).lower()), None)
    if not row:
        out.append(c.warn(f"no quota row for {sku} in {location}; it may be fine",
                          "If the apply fails with 'without additional quota': " + request))
        return out
    free = int(row.get("limit", 0)) - int(row.get("currentValue", 0))
    if free >= 1:
        out.append(c.ok(f"{sku}: {free} free in {location}, 1 needed"))
    else:
        out.append(c.fail(f"{sku}: limit {row.get('limit')}, {row.get('currentValue')} used in {location}; 1 needed", request))
    return out


@check("sub.sql", "Azure SQL region", needs="Reader on the subscription", kb=KB, inputs=["location"], region=True,
       source="https://learn.microsoft.com/rest/api/sql/capabilities/list-by-location",
       reads=["ARM Microsoft.Sql/locations/capabilities"])
def sql_region(ctx, c):
    """Some regions stop new SQL servers for some subscriptions; the apply fails with RegionDoesNotAllowProvisioning."""
    if not terraform_install(ctx):
        return c.skip("the Marketplace install checks its own SQL region")
    location = ctx.values["location"]
    caps = ctx.get(ctx.arm(f"/subscriptions/{ctx.subscription_id}/providers/Microsoft.Sql"
                           f"/locations/{location}/capabilities?api-version={SQL_API}"))
    if caps is None:
        return c.warn(f"couldn't read Azure SQL capabilities in {location}")
    if caps.get("reason") or caps.get("status") == "Disabled":
        return c.fail(f"Azure SQL isn't open to new servers in {location} for this subscription"
                      + (f": {caps['reason']}" if caps.get("reason") else ""),
                      "Pick another region, or open a support request (Service and subscription limits > SQL Database) "
                      "for region access")
    objectives = {o.get("name") for v in caps.get("supportedServerVersions", [])
                  for e in v.get("supportedEditions", []) for o in e.get("supportedServiceLevelObjectives", [])}
    if objectives and "S1" not in objectives:
        return c.fail(f"the S1 database tier isn't offered in {location}", "Pick another region")
    return c.ok(f"new SQL servers and the S1 tier are available in {location}")
