"""sub.*: the subscription: providers, region, App Service and SQL capacity, policy."""

from __future__ import annotations

import hashlib
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
    "Microsoft.RecoveryServices",
]
# Extra namespaces a feature or identity model needs.
FEATURE_PROVIDERS = {"ai": ["Microsoft.CognitiveServices"], "app-mgmt": ["Microsoft.DocumentDB"],
                     "insights": ["Microsoft.ManagedIdentity"]}
IDENTITY_PROVIDERS = {"entra_ds": ["Microsoft.AAD"]}


def terraform_install(ctx) -> bool:
    return ctx.values.get("nerdio_install", "terraform") == "terraform"


def wanted_providers(ctx):
    names = list(PROVIDERS)
    for f in ctx.features:
        names += FEATURE_PROVIDERS.get(f, [])
    names += IDENTITY_PROVIDERS.get(ctx.values.get("identity_model"), [])
    return list(dict.fromkeys(names))


@check("sub.providers", "Resource providers", needs="Reader on the subscription and each host pool subscription", kb=KB,
       source=NERDIO_PREP, reads=["az provider list"], stages=["pre-install", "post-wizard"])
def providers(ctx, c):
    """Registered in the target subscription and every subscription host pools will live in."""
    wanted = wanted_providers(ctx)
    subs = [""] + [s for s in ctx.values.get("host_pool_subscriptions") or [] if s and s != ctx.subscription_id]
    out = []
    for sub in subs:
        args = ["provider", "list", "--query", "[].{ns:namespace, state:registrationState}"]
        label = "" if not sub else f" in host pool subscription {ctx.name('subscription', sub)}"
        if sub:
            args += ["--subscription", sub]
        rows = ctx.az(args)
        if rows is None:
            out.append(c.warn(f"couldn't list resource providers{label}", "az provider list -o table"))
            continue
        state = {r["ns"].lower(): r["state"] for r in rows}
        missing = [ns for ns in wanted if state.get(ns.lower()) != "Registered"]
        if not missing:
            out.append(c.ok(f"all {len(wanted)} registered{label}"))
        else:
            extra = f" --subscription {sub}" if sub else ""
            out.append(c.fail(f"not registered{label}: " + ", ".join(missing),
                              " && ".join(f"az provider register -n {ns}{extra}" for ns in missing)))
    return out


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


def plans_needed(ctx):
    """(sku, count, why) rows: Nerdio's app, plus Intune Insights, Real-Time Insights and Cost
    Attribution when the insights feature is on (Nerdio's preparation article)."""
    core = ctx.values.get("app_service_plan_sku") or "B3"
    rows = [(core, 1, "Nerdio Manager")]
    if "insights" in ctx.features:
        devices = int(ctx.values.get("intune_devices") or 0)
        intune = "P2v3" if devices > 20000 else "B3"
        if intune == core:
            rows[0] = (core, 2, "Nerdio Manager and Intune Insights")
        else:
            rows.append((intune, 1, "Intune Insights"))
        rows.append(("B3", 1, "Real-Time Insights"))
        rows.append(("P0v3", 1, "Cost Attribution"))
    merged = {}
    for sku, n, why in rows:
        have = merged.get(sku, (0, []))
        merged[sku] = (have[0] + n, have[1] + [why])
    return [(sku, n, " and ".join(whys)) for sku, (n, whys) in merged.items()]


def usage_row(rows, sku):
    sku_l = sku.lower()
    return next((u for u in rows.get("value", [])
                 if sku_l in (u.get("name", {}).get("value", "") + " " + u.get("name", {}).get("localizedValue", "")).lower()),
                None)


@check("sub.app_service", "App Service quota", needs="Reader on the subscription", kb=KB, source=NERDIO_PREP,
       inputs=["location"], region=True, features=["insights"], core=True,
       reads=["az appservice list-locations", "ARM Microsoft.Web/locations/usages"])
def app_service(ctx, c):
    """Nerdio Manager runs on a Windows App Service plan (B3 by default), and each Insights app adds
    one. Sandbox and trial subscriptions often have a limit of 0 for some tiers, and the deploy then
    fails late with "Operation cannot be completed without additional quota"."""
    location = ctx.values["location"]
    needed = plans_needed(ctx)
    out = []
    for sku, _, _ in needed:
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
    for sku, count, why in needed:
        request = f"./nerdio fix quota --sku {sku} --location {location} --limit {count}"
        if rows is None:
            out.append(c.warn(f"couldn't read App Service quota in {location}",
                              "If the deploy fails with 'without additional quota': " + request))
            break
        row = usage_row(rows, sku)
        if not row:
            out.append(c.warn(f"no quota row for {sku} in {location}; it may be fine",
                              "If the deploy fails with 'without additional quota': " + request))
            continue
        free = int(row.get("limit", 0)) - int(row.get("currentValue", 0))
        if free >= count:
            out.append(c.ok(f"{sku}: {free} free in {location}, {count} needed ({why})"))
        else:
            used = int(row.get("currentValue", 0))
            out.append(c.fail(f"{sku}: limit {row.get('limit')}, {used} used in {location}; {count} needed ({why})",
                              f"./nerdio fix quota --sku {sku} --location {location} --limit {used + count}"))
    return out


@check("sub.sql", "Azure SQL region", needs="Reader on the subscription", kb=KB, inputs=["location"], region=True,
       source="https://learn.microsoft.com/rest/api/sql/capabilities/list-by-location",
       reads=["ARM Microsoft.Sql/locations/capabilities"])
def sql_region(ctx, c):
    """Some regions stop new SQL servers for some subscriptions; the apply fails with RegionDoesNotAllowProvisioning."""
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


# quotaId prefixes of offers that can't buy third-party Marketplace offers (unverified list,
# from Microsoft's Marketplace purchasing docs: free and credit-based offers).
NO_MARKETPLACE = ("FreeTrial", "Sponsored", "AzurePass", "DreamSpark", "AzureForStudents", "MSDN", "MPN")


@check("sub.type", "Subscription offer", needs="Reader on the subscription", kb=KB,
       source="https://learn.microsoft.com/marketplace/purchase-saas-offer-in-azure-portal",
       reads=["ARM GET /subscriptions/{id}"])
def subscription_type(ctx, c):
    data = ctx.get(ctx.arm(f"/subscriptions/{ctx.subscription_id}?api-version=2022-12-01"))
    if data is None:
        return c.warn("couldn't read the subscription's offer")
    policies = data.get("subscriptionPolicies") or {}
    quota = policies.get("quotaId") or ""
    limit = policies.get("spendingLimit") or ""
    offer = quota.split("_")[0] or "unknown"
    if quota.startswith(NO_MARKETPLACE) or limit == "On":
        why = f"offer {offer}" + (", spending limit on" if limit == "On" else "")
        detail = (f"{why}: these subscriptions usually can't deploy third-party Marketplace offers or exceed their "
                  "credit (unverified list)")
        fix = "Use a pay-as-you-go, EA, MCA or CSP subscription, or remove the spending limit"
        if terraform_install(ctx):
            return c.warn(detail + "; the kit's Terraform install doesn't use the Marketplace, but credit limits still apply", fix)
        return c.fail(detail, fix)
    return c.ok(f"offer {offer}")


@check("sub.empty_rg", "Target resource group", needs="Reader on the resource group", kb=KB, source=NERDIO_PREP,
       inputs=["resource_group"], reads=["az group exists", "az resource list"])
def empty_rg(ctx, c):
    """Nerdio's Marketplace deployment goes into an empty resource group."""
    if terraform_install(ctx):
        return c.skip("the kit's Terraform install names its own resource groups")
    rg = ctx.values["resource_group"]
    shown = ctx.name("rg", rg)
    exists = ctx.az(["group", "exists", "--name", rg])
    if exists is None:
        return c.warn(f"couldn't tell whether {shown} exists")
    if exists is False:
        return c.ok(f"{shown} doesn't exist yet; the deployment can create it")
    rows = ctx.az(["resource", "list", "-g", rg, "--query", "[].type"])
    if rows is None:
        return c.no_access(f"can't list what's in {shown}")
    if rows:
        return c.fail(f"{shown} already holds {len(rows)} resources; Nerdio deploys into an empty resource group",
                      "Pick a new resource group name")
    return c.ok(f"{shown} exists and is empty")


@check("sub.locks", "Resource locks", needs="Reader on the subscription", kb=KB,
       source="https://learn.microsoft.com/azure/azure-resource-manager/management/lock-resources",
       reads=["az lock list"])
def locks(ctx, c):
    rows = ctx.az(["lock", "list", "--query", "[].{level:level, id:id}"])
    if rows is None:
        return c.warn("couldn't list resource locks", "az lock list -o table")
    sub_scope = f"/subscriptions/{ctx.subscription_id}/providers/microsoft.authorization/locks/".lower()
    rg = (ctx.values.get("resource_group") or "").lower()
    target = [r for r in rows if (r.get("id") or "").lower().startswith(sub_scope)
              or (rg and f"/resourcegroups/{rg}/providers/microsoft.authorization/locks/" in (r.get("id") or "").lower())]
    if any(r.get("level") == "ReadOnly" for r in target):
        return c.fail("a ReadOnly lock on the subscription or the target resource group blocks the install and "
                      "Nerdio's updates", "Remove it (az lock delete --ids <lock id>) or deploy elsewhere")
    if target:
        return c.warn("a CanNotDelete lock on the subscription or target group stops Nerdio removing what it "
                      "creates (temporary image VMs, scaled-in hosts)", "Scope the lock to the resources that need it")
    if any(r.get("level") == "ReadOnly" for r in rows):
        return c.warn("ReadOnly locks exist on other resource groups; don't link those groups to Nerdio")
    return c.ok("no locks that would block the install")


def kit_names(ctx) -> dict:
    """The names modules/nerdio-core gives Nerdio's resources: a 13-character suffix from a SHA-1 of
    the subscription ID and Nerdio's resource group (modules/nerdio-core/main.tf)."""
    import engine  # the kit's own template expansion, so the name matches what Terraform gets

    rg = engine.expand(ctx.values.get("resource_group_pattern") or "rg-{prefix}-{role}", ctx.values, {"role": "nerdio"})
    suffix = hashlib.sha1(f"/subscriptions/{ctx.subscription_id}/resourceGroups/{rg}".encode()).hexdigest()[:13]
    app = "nmw-app"
    return {"rg": rg, "key_vault": f"{app}-kv-{suffix}", "storage": f"nmwdp{suffix}", "sql": f"{app}-sql-{suffix}",
            "web": f"{app}-{suffix}"}


@check("sub.names", "Resource names", needs="Reader on the subscription", kb=KB, modes=["kit"],
       source="https://learn.microsoft.com/azure/azure-resource-manager/management/resource-name-rules",
       reads=["az keyvault list-deleted", "az keyvault check-name", "az storage account check-name",
              "ARM checkNameAvailability (Microsoft.Sql, Microsoft.Web)"])
def names(ctx, c):
    """The Key Vault, storage, SQL server and web app names the kit plans are free. Names are global,
    so a clash in another tenant only shows through name availability."""
    if not terraform_install(ctx):
        return c.skip("the Marketplace install picks its own names")
    n = kit_names(ctx)
    ours = {r.lower() for r in ctx.az(["resource", "list", "-g", n["rg"], "--query", "[].name"]) or []}
    out, taken = [], []
    deleted = ctx.az(["keyvault", "list-deleted", "--query", "[].name"])
    if deleted and n["key_vault"] in deleted:
        out.append(c.warn(f"the planned Key Vault {ctx.name('vault', n['key_vault'])} is soft-deleted in this subscription; "
                          "Terraform recovers it (azurerm's default), which is right only if it's from this kit",
                          f"If it isn't: az keyvault purge --name {ctx.name('vault', n['key_vault'])}", title="Key Vault name"))
    checks = [("Key Vault", n["key_vault"], lambda name: ctx.az(["keyvault", "check-name", "--name", name])),
              ("storage account", n["storage"], lambda name: ctx.az(["storage", "account", "check-name", "--name", name])),
              ("SQL server", n["sql"], lambda name: ctx.post_check(
                  ctx.arm(f"/subscriptions/{ctx.subscription_id}/providers/Microsoft.Sql/checkNameAvailability?api-version={SQL_API}"),
                  {"name": name, "type": "Microsoft.Sql/servers"})),
              ("web app", n["web"], lambda name: ctx.post_check(
                  ctx.arm(f"/subscriptions/{ctx.subscription_id}/providers/Microsoft.Web/checknameavailability?api-version={WEB_API}"),
                  {"name": name, "type": "Site"}))]
    if ctx.values.get("fslogix_enabled") and ctx.values.get("fslogix_storage_account_name"):
        sa = ctx.values["fslogix_storage_account_name"]
        checks.append(("FSLogix storage account", sa, lambda name: ctx.az(["storage", "account", "check-name", "--name", name])))
    unknown = []
    for label, name, probe in checks:
        if name.lower() in ours:
            continue  # already this kit's
        got = probe(name)
        if got is None:
            unknown.append(label)
            continue
        free = got.get("nameAvailable", got.get("available"))
        if free is False:
            taken.append(f"{label} {ctx.name('name', name)}")
    if taken:
        out.append(c.fail("taken elsewhere (names are global): " + ", ".join(taken),
                          "Change prefix (or nerdio_core.name_suffix in the platform tfvars) so the names change"))
    elif unknown:
        out.append(c.warn("couldn't check the names of: " + ", ".join(unknown)))
    else:
        out.append(c.ok("the Key Vault, storage, SQL server and web app names are free"))
    return out
