"""ins.*: Nerdio's Intune Insights, Real-Time Insights and Cost Attribution (--features insights).

App Service plans and their quota, Cost Attribution's P0v3 included, are in sub.app_service.
"""

from __future__ import annotations

from ..model import PRE, WIZARD, check
from .nerdio import granted_graph_roles, resources

KB = "docs/knowledge/nerdio/readiness.md#insights"
INTUNE = "https://nmehelp.getnerdio.com/hc/en-us/articles/35702701977485"
REAL_TIME = "https://nmehelp.getnerdio.com/hc/en-us/articles/41694103483533-Insights-Real-Time"
FEATURE = ["insights"]
SQL_API = "2021-11-01"
# Intune Insights' SQL tier by device count (Nerdio's Intune Insights article).
SQL_TIERS = ((20000, "S1"), (50000, "S2"), (120000, "S4"))
IDENTITY_ROLES = ("Storage Blob Data Contributor", "Storage Table Data Contributor", "Monitoring Reader",
                  "Log Analytics Reader")
ENABLER_AZURE = {"Owner", "Role Based Access Control Administrator", "User Access Administrator"}
ENABLER_ENTRA = {"Global Administrator", "Privileged Role Administrator"}


@check("ins.capacity", "Insights SQL tier", needs="Reader on the subscription", kb=KB, stages=[PRE], features=FEATURE,
       inputs=["location", "intune_devices"], source=INTUNE, reads=["ARM Microsoft.Sql/locations/capabilities"])
def capacity(ctx, c):
    devices, location = int(ctx.values["intune_devices"]), ctx.values["location"]
    tier = next((t for limit, t in SQL_TIERS if devices <= limit), None)
    if tier is None:
        return c.manual(f"{devices} devices is above Nerdio's published sizing (120,000); ask Nerdio for the tier")
    caps = ctx.cached(("sql_caps", location), lambda: ctx.get(ctx.arm(
        f"/subscriptions/{ctx.subscription_id}/providers/Microsoft.Sql/locations/{location}/capabilities"
        f"?api-version={SQL_API}")))
    if caps is None:
        return c.warn(f"couldn't read Azure SQL capabilities in {location}")
    objectives = {o.get("name") for v in caps.get("supportedServerVersions", [])
                  for e in v.get("supportedEditions", []) for o in e.get("supportedServiceLevelObjectives", [])}
    if objectives and tier not in objectives:
        return c.fail(f"{devices} devices needs SQL {tier}, which isn't offered in {location}", "Pick another region")
    return c.ok(f"{devices} devices needs SQL {tier} (offered in {location}); App Service plans are in App Service quota")


@check("ins.enabler_rights", "Rights to turn on Insights", needs="Reader on the subscription", kb=KB, stages=[PRE],
       features=FEATURE, source=INTUNE, reads=["az role assignment list", "Graph /me/transitiveMemberOf"])
def enabler_rights(ctx, c):
    """Whoever turns Insights on grants its identities their Azure roles and, once, a Graph permission."""
    if not ctx.is_user:
        return c.manual("signed in as a service principal; whoever turns Insights on needs Owner, RBAC Administrator or "
                        "User Access Administrator, and Global or Privileged Role Administrator once")
    rows = ctx.assignments_at(f"/subscriptions/{ctx.subscription_id}")
    entra = ctx.directory_roles()
    if rows is None or entra is None:
        return c.no_access("can't read your roles")
    out = []
    if not any(r.get("role") in ENABLER_AZURE and not r.get("condition") for r in rows):
        out.append(c.fail("you hold none of Owner, RBAC Administrator or User Access Administrator (unconditioned), so "
                          "Insights can't grant its identities their roles", "./nerdio fix roles, or ask an Owner"))
    if not entra & ENABLER_ENTRA:
        out.append(c.warn("Global or Privileged Role Administrator is needed once, to grant the Intune Insights identity "
                          "Directory.Read.All", "./nerdio fix roles (PIM)"))
    return out or [c.ok("you can grant the Insights identities their Azure roles and Graph permission")]


@check("ins.rti_new_kv_sql", "Real-Time Insights stores", needs="none", kb=KB, stages=[PRE], features=FEATURE,
       account=False, source=REAL_TIME)
def rti_new_kv_sql(ctx, c):
    reuse = ctx.values.get("rti_reuse_existing")
    if reuse in (True, "true", "yes"):
        return c.fail("Real-Time Insights breaks when it reuses Nerdio's Key Vault or SQL (per Nerdio)",
                      "Choose new ones when you turn it on")
    if reuse in (False, "false", "no"):
        return c.ok("Real-Time Insights gets its own Key Vault and SQL")
    return c.manual("when you turn on Real-Time Insights, choose a new Key Vault and SQL; reusing Nerdio's breaks it")


@check("ins.rti_endpoints", "Real-Time Insights endpoints", needs="none", kb=KB, stages=[WIZARD], features=FEATURE,
       account=False, source=REAL_TIME)
def rti_endpoints(ctx, c):
    return c.manual("confirm outbound 443 from every AVD, Windows 365 and Intune endpoint network to the Real-Time "
                    "Insights app; PowerShell execution policy RemoteSigned or AllSigned with the publisher trusted; "
                    "and AppLocker or WDAC allowing the signed worker")


def insights_apps(ctx):
    """The Insights web apps in Nerdio's group: every web app but Nerdio Manager's own."""
    res = resources(ctx)
    if res is None:
        return None
    return [w for w in res.get("web", []) if any(k in w["name"].lower() for k in ("insight", "rti", "intune"))]


def principal(ctx, web):
    return ctx.az(["webapp", "identity", "show", "--ids", web["id"], "--query", "principalId"])


@check("ins.identity_roles", "Insights identities", needs="Reader on the subscription", kb=KB, stages=[WIZARD],
       features=FEATURE, source=INTUNE, reads=["az webapp identity show", "az role assignment list"])
def identity_roles(ctx, c):
    apps = insights_apps(ctx)
    if apps is None:
        return c.skip("needs Nerdio's resource group: --resource-group or --nerdio-url")
    if not apps:
        return c.skip("no Insights apps in Nerdio's group yet")
    out = []
    sub = f"/subscriptions/{ctx.subscription_id}".lower()
    for web in apps:
        name = ctx.name("web", web["name"])
        pid = principal(ctx, web)
        if not pid:
            out.append(c.warn(f"{name} has no managed identity"))
            continue
        rows = ctx.az(["role", "assignment", "list", "--assignee", pid, "--all", "--query",
                       "[].{role:roleDefinitionName, scope:scope}"])
        if rows is None:
            return out + [c.no_access("can't list role assignments")]
        roles = {r.get("role") for r in rows}
        missing = [r for r in IDENTITY_ROLES if r not in roles]
        broad = [r.get("role") for r in rows if (r.get("scope") or "").lower() == sub
                 or r.get("role") in ("Owner", "Contributor")]
        if missing:
            out.append(c.fail(f"{name} lacks " + ", ".join(missing), "Turn Insights off and on again in Nerdio to re-grant"))
        if broad:
            out.append(c.warn(f"{name} holds {', '.join(sorted(set(broad)))} beyond its own resources"))
    return out or [c.ok(f"{len(apps)} Insights identities hold exactly the roles they need")]


@check("ins.intune_graph", "Intune Insights Graph access", needs="Directory Readers", kb=KB, stages=[WIZARD],
       features=FEATURE, source=INTUNE, reads=["az webapp identity show", "Graph appRoleAssignments"])
def intune_graph(ctx, c):
    apps = [w for w in insights_apps(ctx) or [] if "intune" in w["name"].lower()]
    if not apps:
        return c.skip("no Intune Insights app in Nerdio's group yet")
    pid = principal(ctx, apps[0])
    if not pid:
        return c.fail("the Intune Insights app has no managed identity")
    granted = granted_graph_roles(ctx, pid)
    if granted is None:
        return c.no_access("can't read the Intune Insights identity's Graph permissions")
    if "Directory.Read.All" not in granted:
        return c.fail("the Intune Insights identity lacks Directory.Read.All",
                      "A Global or Privileged Role Administrator grants it from Nerdio's Insights settings")
    return c.ok("the Intune Insights identity holds Directory.Read.All")


@check("ins.avd_insights", "AVD Insights", needs="Reader on the subscription", kb=KB, stages=[WIZARD],
       features=FEATURE, source="https://learn.microsoft.com/azure/virtual-desktop/insights",
       reads=["ARM dataCollectionRules"])
def avd_insights(ctx, c):
    """Microsoft's AVD Insights uses a data collection rule named microsoft-avdi-<region>. (An ARM
    GET, because az's data-collection commands come from an extension Cloud Shell may not have.)"""
    data = ctx.get(ctx.arm(f"/subscriptions/{ctx.subscription_id}/providers/Microsoft.Insights/dataCollectionRules"
                           "?api-version=2022-06-01"))
    if data is None:
        return c.no_access("can't list data collection rules")
    rows = [r.get("name") for r in data.get("value", [])]
    if not any((n or "").lower().startswith("microsoft-avdi-") for n in rows):
        return c.warn("no AVD Insights data collection rule (microsoft-avdi-*)",
                      "Set up AVD Insights: a Log Analytics workspace, its data collection rule and the Azure Monitor Agent on hosts")
    return c.manual("the AVD Insights data collection rule exists; confirm the Azure Monitor Agent is on the hosts")
