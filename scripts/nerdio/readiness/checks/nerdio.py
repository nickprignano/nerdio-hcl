"""nme.*: the installed Nerdio Manager instance (post-install and post-wizard)."""

from __future__ import annotations

import datetime as dt
import re
from typing import Dict, List, Optional

from ..model import INSTALLED, WIZARD, check

KB = "docs/knowledge/nerdio/readiness.md#nerdio-manager"
ARCH = "https://nmehelp.getnerdio.com/hc/en-us/articles/26124379482381-How-to-Check-the-Health-of-Nerdio-Manager"
NERDIO_PREP = "https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps"
BOTH = [INSTALLED, WIZARD]
EXPIRY_DAYS = 30
WEB_QUERY = "{state:state, https:httpsOnly, identity:identity.type, host:defaultHostName}"
TYPES = {
    "microsoft.web/sites": "web", "microsoft.web/serverfarms": "plan", "microsoft.keyvault/vaults": "key_vault",
    "microsoft.sql/servers": "sql", "microsoft.sql/servers/databases": "sql_db",
    "microsoft.automation/automationaccounts": "automation", "microsoft.insights/components": "insights",
    "microsoft.operationalinsights/workspaces": "law", "microsoft.storage/storageaccounts": "storage",
}


def nerdio_group(ctx) -> Optional[str]:
    """The resource group Nerdio Manager is in: --resource-group, the web app behind --nerdio-url,
    or (kit mode) the group modules/nerdio-core names."""
    if ctx.values.get("resource_group"):
        return ctx.values["resource_group"]
    url = (ctx.values.get("nerdio_url") or "").strip()
    if url:
        host = url.split("//")[-1].split("/")[0].lower()
        rows = ctx.az(["webapp", "list", "--query", f"[?defaultHostName=='{host}'].resourceGroup"]) or []
        return rows[0] if rows else None
    if ctx.mode == "kit":
        from .subscription import kit_names
        return kit_names(ctx)["rg"]
    return None


def resources(ctx) -> Optional[Dict[str, List[Dict]]]:
    """Nerdio's resources by kind, found by type in its group (names follow Nerdio's own scheme)."""
    def read():
        rg = nerdio_group(ctx)
        if not rg:
            return None
        rows = ctx.az(["resource", "list", "-g", rg, "--query", "[].{name:name, type:type, id:id}"])
        if rows is None:
            return None
        out: Dict[str, List[Dict]] = {"rg": [{"name": rg}]}
        for r in rows:
            kind = TYPES.get((r.get("type") or "").lower())
            if kind:
                out.setdefault(kind, []).append(r)
        # The core app is nmw-app-<suffix>; Insights apps carry their own names.
        webs = out.get("web", [])
        out["web"] = sorted(webs, key=lambda w: ("insights" in w["name"].lower() or "rti" in w["name"].lower(), w["name"]))
        return out
    return ctx.cached("nerdio_resources", read)


def first(ctx, kind: str) -> Optional[Dict]:
    found = (resources(ctx) or {}).get(kind) or []
    return found[0] if found else None


def need(ctx, c, kind: str):
    """(resource, None) or (None, a skipped/failed result)."""
    res = resources(ctx)
    if res is None:
        return None, c.skip("needs Nerdio's resource group: --resource-group or --nerdio-url")
    item = first(ctx, kind)
    if not item:
        return None, c.skip(f"no {kind.replace('_', ' ')} found in Nerdio's resource group")
    return item, None


def parse_time(when) -> Optional[dt.datetime]:
    """An ARM or Graph timestamp, in UTC. ARM writes seven fractional digits, which Python 3.9's
    fromisoformat refuses, so the fraction is dropped."""
    try:
        text = re.sub(r"\.\d+", "", when.strip()).replace("Z", "+00:00")
        end = dt.datetime.fromisoformat(text)
    except (ValueError, AttributeError):
        return None
    return end if end.tzinfo else end.replace(tzinfo=dt.timezone.utc)


def days_left(when) -> Optional[int]:
    end = parse_time(when)
    return None if end is None else (end - dt.datetime.now(dt.timezone.utc)).days


@check("nme.discover", "Nerdio resources", needs="Reader on Nerdio's resource group", kb=KB, stages=BOTH,
       source=NERDIO_PREP, reads=["az resource list", "az webapp list"])
def discover(ctx, c):
    res = resources(ctx)
    if res is None:
        if not nerdio_group(ctx):
            return c.skip("needs Nerdio's resource group: --resource-group or --nerdio-url")
        return c.no_access(f"can't list Nerdio's resource group {ctx.name('rg', nerdio_group(ctx))}")
    if not res.get("web"):
        return c.fail(f"no web app in {ctx.name('rg', res['rg'][0]['name'])}: is this Nerdio's resource group?",
                      "Pass the group Nerdio Manager was deployed into with --resource-group")
    wanted = ("web", "plan", "key_vault", "sql", "sql_db", "automation", "insights", "law", "storage")
    missing = [k for k in wanted if not res.get(k)]
    if missing:
        return c.warn("found Nerdio's web app but not its " + ", ".join(k.replace("_", " ") for k in missing))
    return c.ok("found the web app, plan, Key Vault, SQL, Automation, Application Insights, Log Analytics and storage")


@check("nme.app", "Web app", needs="Reader on Nerdio's resource group", kb=KB, stages=[INSTALLED],
       source="https://learn.microsoft.com/azure/app-service/overview-security", reads=["az webapp show", "az webapp config show"])
def app(ctx, c):
    web, skipped = need(ctx, c, "web")
    if skipped:
        return skipped
    data = ctx.az(["webapp", "show", "--ids", web["id"], "--query", WEB_QUERY])
    conf = ctx.az(["webapp", "config", "show", "--ids", web["id"], "--query", "{tls:minTlsVersion, ftps:ftpsState}"])
    if data is None or conf is None:
        return c.no_access("can't read the web app's settings")
    problems = []
    if data.get("state") != "Running":
        return c.fail(f"the web app is {data.get('state')}", f"az webapp start --ids {web['id']}")
    if not data.get("https"):
        problems.append("HTTPS-only is off")
    if (conf.get("tls") or "1.0") < "1.2":
        problems.append(f"minimum TLS is {conf.get('tls')}")
    if conf.get("ftps") not in ("Disabled", "FtpsOnly"):
        problems.append("plain FTP is allowed")
    if "SystemAssigned" not in (data.get("identity") or ""):
        problems.append("the managed identity is off")
    if problems:
        return c.warn("running, but " + "; ".join(problems))
    return c.ok("running, HTTPS-only, TLS " + str(conf.get("tls")) + ", FTP off, managed identity on")


@check("nme.health", "Health page", needs="none (unauthenticated)", kb=KB, stages=[INSTALLED], source=ARCH,
       reads=["GET <nerdio_url>/public/health/status"])
def health(ctx, c):
    """Nerdio allows one call per five minutes, and the chat, the verify job and a person can all
    call it, so a rate-limited answer is `skipped`, not unhealthy."""
    host = (ctx.values.get("nerdio_url") or "").split("//")[-1].split("/")[0]
    if not host:
        web = first(ctx, "web")
        if web:
            host = (ctx.az(["webapp", "show", "--ids", web["id"], "--query", WEB_QUERY]) or {}).get("host") or ""
    if not host:
        return c.skip("needs --nerdio-url or Nerdio's resource group")
    status, body = ctx.http_get(f"https://{host}/public/health/status")
    if status == 429:
        return c.skip("rate-limited (one call per five minutes); try again later")
    if status is None:
        return c.fail(f"no answer from Nerdio Manager ({body})", "Check the web app is running and reachable from here")
    if status != 200:
        return c.fail(f"the health page answered HTTP {status}",
                      "Restart the web app, then look at Application Insights' failures")
    # Its body's format is unverified, so only the HTTP status counts for now.
    return c.ok("the health page answers HTTP 200 (open it once to read the per-dependency detail)")


@check("nme.version", "Nerdio version", needs="none", kb=KB, stages=BOTH, account=False, source=ARCH)
def version(ctx, c):
    return c.manual("Nerdio publishes no read of its version yet (an upstream ask); check Settings > About against "
                    "each feature's minimum (8.0 for the current Copilot)")


GRAPH_PAGES = 20  # at most 20 pages (2,000 rows at Graph's default page size)


def graph_list(ctx, path: str) -> Optional[List[Dict]]:
    """Every row of a Graph list, following @odata.nextLink; None when unreadable."""
    data = ctx.get(ctx.graph(path))
    if data is None:
        return None
    rows = list(data.get("value", []))
    for _ in range(GRAPH_PAGES - 1):
        link = data.get("@odata.nextLink")
        if not link or not link.startswith(ctx.cloud.graph):
            break
        data = ctx.get(link)
        if data is None:
            return None
        rows += data.get("value", [])
    return rows


def nerdio_app(ctx) -> Optional[Dict]:
    """Nerdio's app registration and its service principal: {"app": {...}, "sp": {...}} or {}."""
    def read():
        apps = graph_list(ctx, "/applications?$filter=startswith(displayName,'nerdio-nmw-app')"
                               "&$select=id,appId,displayName,keyCredentials,passwordCredentials,requiredResourceAccess")
        if apps is None:
            return None
        main = [a for a in apps if not a.get("displayName", "").endswith("-rest-client")]
        if not main:
            return {}
        app_ = main[0]
        sps = graph_list(ctx, f"/servicePrincipals?$filter=appId eq '{app_['appId']}'&$select=id,appRoles,appRoleAssignmentRequired,accountEnabled")
        return {"app": app_, "sp": (sps or [None])[0], "count": len(main)}
    return ctx.cached("nerdio_app", read)


@check("nme.entra_app", "Nerdio's Entra app", needs="Directory Readers", kb="docs/knowledge/nerdio/entra-app.md",
       stages=[INSTALLED], source=NERDIO_PREP,
       reads=["Graph /applications", "Graph /servicePrincipals", "appRoleAssignments", "oauth2PermissionGrants"])
def entra_app(ctx, c):
    found = nerdio_app(ctx)
    if found is None:
        return c.no_access("can't read app registrations")
    if not found:
        return c.fail("no nerdio-nmw-app registration", "Nerdio's install creates it; rerun the install step")
    out = []
    if found["count"] > 1:
        out.append(c.warn(f"{found['count']} nerdio-nmw-app registrations; make sure the right one is in use"))
    sp = found.get("sp")
    if not sp:
        return out + [c.fail("the app has no service principal in this tenant", "az ad sp create --id <appId>")]
    granted = graph_list(ctx, f"/servicePrincipals/{sp['id']}/appRoleAssignments")
    grants = graph_list(ctx, f"/oauth2PermissionGrants?$filter=clientId eq '{sp['id']}'")
    if granted is None or grants is None:
        return out + [c.no_access("can't read the app's consented permissions")]
    granted_roles = {g.get("appRoleId") for g in granted}
    wanted_roles = {r["id"] for rra in found["app"].get("requiredResourceAccess", [])
                    for r in rra.get("resourceAccess", []) if r.get("type") == "Role"}
    wants_scopes = any(r.get("type") == "Scope" for rra in found["app"].get("requiredResourceAccess", [])
                       for r in rra.get("resourceAccess", []))
    missing = wanted_roles - granted_roles
    if missing:
        out.append(c.fail(f"admin consent is missing for {len(missing)} of {len(wanted_roles)} application permissions",
                          "Grant admin consent for nerdio-nmw-app (an Entra admin: az ad app permission admin-consent --id <appId>)"))
    elif wants_scopes and not any(g.get("consentType") == "AllPrincipals" for g in grants):
        out.append(c.fail("the delegated permissions have no tenant-wide consent (the wizard's second consent)",
                          "Run the consent step in Nerdio's wizard as an Entra admin"))
    else:
        out.append(c.ok("app, service principal and admin consent are in place"))
    for cred in found["app"].get("keyCredentials") or []:
        left = days_left(cred.get("endDateTime"))
        if left is not None and left < EXPIRY_DAYS:
            out.append(c.warn(f"a sign-in certificate on Nerdio's app expires in {left} days", title="App certificate"))
    return out


def principal_ids(ctx) -> List[str]:
    found = nerdio_app(ctx) or {}
    ids = [found["sp"]["id"]] if found.get("sp") else []
    return ids


@check("nme.sp_roles", "Nerdio's Azure roles", needs="Reader on the subscription", kb=KB, stages=BOTH,
       source=NERDIO_PREP, reads=["az role assignment list"])
def sp_roles(ctx, c):
    """Reader and Backup Reader on the subscription, Contributor on Nerdio's group (and each group it
    manages), and nothing broader."""
    ids = principal_ids(ctx)
    if not ids:
        return c.skip("needs Nerdio's service principal (see Nerdio's Entra app)")
    rows = ctx.az(["role", "assignment", "list", "--assignee", ids[0], "--all", "--query",
                   "[].{role:roleDefinitionName, scope:scope}"])
    if rows is None:
        return c.no_access("can't list Nerdio's role assignments")
    sub = f"/subscriptions/{ctx.subscription_id}".lower()
    at_sub = {r["role"] for r in rows if (r.get("scope") or "").lower() == sub}
    rg = (nerdio_group(ctx) or "").lower()
    at_rg = {r["role"] for r in rows if (r.get("scope") or "").lower().endswith(f"/resourcegroups/{rg}")}
    missing = [r for r in ("Reader", "Backup Reader") if r not in at_sub]
    if rg and not ({"Contributor", "Owner"} & (at_rg | at_sub)):
        missing.append("Contributor on Nerdio's resource group")
    broad = at_sub & {"Owner", "Contributor", "User Access Administrator"}
    if missing:
        return c.fail("Nerdio's service principal lacks " + ", ".join(missing),
                      "az role assignment create --assignee <Nerdio SP> --role <role> --scope <scope>")
    if broad:
        return c.warn("Nerdio's service principal holds " + ", ".join(sorted(broad))
                      + " on the whole subscription; the kit grants Contributor only on the groups Nerdio manages")
    return c.ok("Reader and Backup Reader on the subscription, Contributor on its resource groups")


@check("nme.sql", "Nerdio's SQL", needs="Reader on Nerdio's resource group", kb="docs/knowledge/nerdio/platform.md",
       stages=[INSTALLED], source=NERDIO_PREP, reads=["az sql server show", "az sql db show"])
def sql(ctx, c):
    db, skipped = need(ctx, c, "sql_db")
    if skipped:
        return skipped
    server_id = db["id"].rsplit("/databases/", 1)[0]
    server = ctx.az(["sql", "server", "show", "--ids", server_id, "--query", "{entraOnly:administrators.azureAdOnlyAuthentication}"])
    data = ctx.az(["sql", "db", "show", "--ids", db["id"], "--query", "{collation:collation, slo:currentServiceObjectiveName}"])
    if server is None or data is None:
        return c.no_access("can't read Nerdio's SQL server or database")
    out = []
    if data.get("collation") != "SQL_Latin1_General_CP1_CI_AS" and data.get("collation") != "Latin1_General_CP1_CI_AS":
        out.append(c.fail(f"collation is {data.get('collation')}; Nerdio's template uses SQL_Latin1_General_CP1_CI_AS "
                          "(its docs name Latin1_General_CP1_CI_AS), and a collation can't be changed afterwards",
                          "Reinstall into a new database"))
    slo = data.get("slo") or ""
    if slo in ("Basic", "S0") or slo.startswith("Free"):
        out.append(c.warn(f"the database tier is {slo}; Nerdio's default is S1"))
    if not server.get("entraOnly"):
        out.append(c.warn("SQL authentication is still allowed; Nerdio's install works with Entra-only"))
    return out or [c.ok(f"Entra-only, collation {data.get('collation')}, tier {slo}")]


@check("nme.keyvault", "Nerdio's certificates", needs="Key Vault Reader on Nerdio's vault", kb=KB, stages=[INSTALLED],
       source="https://learn.microsoft.com/azure/key-vault/general/rbac-guide", reads=["az keyvault certificate list"])
def keyvault(ctx, c):
    kv, skipped = need(ctx, c, "key_vault")
    if skipped:
        return skipped
    rows = ctx.az(["keyvault", "certificate", "list", "--vault-name", kv["name"], "--query",
                   "[].{name:name, expires:attributes.expires}"])
    if rows is None:
        return c.no_access("can't list certificates in Nerdio's vault (metadata only, never values)")
    soon = [(r["name"], days_left(r.get("expires"))) for r in rows]
    soon = [(n, d) for n, d in soon if d is not None and d < EXPIRY_DAYS]
    if soon:
        return c.warn("expiring within 30 days: " + ", ".join(f"{ctx.name('cert', n)} ({d} days)" for n, d in soon),
                      "Renew them in Nerdio (Settings) or Key Vault before they lapse")
    return c.ok(f"{len(rows)} certificates, none expiring within 30 days")


@check("nme.automation", "Nerdio's Automation", needs="Reader on Nerdio's resource group", kb=KB, stages=[INSTALLED],
       source="https://nmehelp.getnerdio.com/hc/en-us/articles/26124345260941-Nerdio-Manager-Default-Deployment-Resources-and-Costs",
       reads=["ARM automationAccounts/runbooks", "ARM automationAccounts/certificates"])
def automation(ctx, c):
    acct, skipped = need(ctx, c, "automation")
    if skipped:
        return skipped
    runbooks = ctx.get(ctx.arm(f"{acct['id']}/runbooks?api-version=2023-11-01"))
    if runbooks is None:
        return c.no_access("can't read the Automation account's runbooks")
    names = [r.get("name", "") for r in runbooks.get("value", [])]
    out = []
    if not any("update" in n.lower() for n in names):
        out.append(c.fail("no updater runbook (nmwUpdate...) in the Automation account; Nerdio's in-app updates will fail",
                          "Reinstall the runbook from Nerdio's install step"))
    certs = ctx.get(ctx.arm(f"{acct['id']}/certificates?api-version=2023-11-01")) or {}
    for cert in certs.get("value", []):
        left = days_left((cert.get("properties") or {}).get("expiryTime"))
        if left is not None and left < EXPIRY_DAYS:
            out.append(c.warn(f"the Automation certificate {ctx.name('cert', cert.get('name', ''))} expires in {left} days"))
    return out or [c.ok(f"{len(names)} runbooks, the updater among them")]


@check("nme.smart_detection", "Smart Detection action group", needs="Reader on Nerdio's resource group", kb=KB,
       stages=[INSTALLED], source="https://learn.microsoft.com/azure/azure-monitor/alerts/proactive-arm-config",
       reads=["az monitor action-group list"])
def smart_detection(ctx, c):
    rg = nerdio_group(ctx)
    if not rg or resources(ctx) is None:
        return c.skip("needs Nerdio's resource group")
    rows = ctx.az(["monitor", "action-group", "list", "-g", rg, "--query", "[].name"])
    if rows is None:
        return c.skip("couldn't list action groups")
    if "Application Insights Smart Detection" in rows:
        return c.warn("Azure created the \"Application Insights Smart Detection\" action group itself; it isn't in "
                      "Terraform's state and blocks a destroy of the group (known error smart-detection-action-group-blocks-destroy)",
                      "Before a teardown: az monitor action-group delete -g <group> -n \"Application Insights Smart Detection\"",
                      kb="docs/knowledge/troubleshooting/README.md")
    return c.ok("no unmanaged action group")


@check("nme.rest_api", "Nerdio REST API", needs="Directory Readers", kb="docs/knowledge/nerdio/entra-app.md",
       stages=[WIZARD], source="https://nmehelp.getnerdio.com/hc/en-us/articles/27422824784269",
       reads=["Graph /servicePrincipals/{id}/appRoleAssignedTo"])
def rest_api(ctx, c):
    """Enabled when an application holds Nerdio's Rest client app role; the kit's stage 2 needs it."""
    found = nerdio_app(ctx)
    if not found or not found.get("sp"):
        return c.skip("needs Nerdio's service principal (see Nerdio's Entra app)")
    roles = {r.get("id"): r.get("value") for r in found["sp"].get("appRoles") or []}
    assigned = graph_list(ctx, f"/servicePrincipals/{found['sp']['id']}/appRoleAssignedTo")
    if assigned is None:
        return c.no_access("can't read who holds Nerdio's app roles")
    if any(roles.get(a.get("appRoleId")) == "RestClient" for a in assigned):
        if not ctx.nerdio_data:
            return c.ok("a REST client holds Nerdio's Rest client role (--nerdio-data also tries a read)")
        from ..nerdio_api import NotConfigured

        try:
            status, _ = ctx.nerdio_get("/api/v1/ad/config")
        except NotConfigured as exc:
            return c.warn(f"a REST client holds the role, but the data tier can't sign in: {exc}")
        if status in (200, 404):
            return c.ok("the REST API answers a read-only call")
        return c.fail(f"the REST client holds the role, but a read-only call got HTTP {status}",
                      "Check the REST client's secret and role in Nerdio: Settings > Integrations > REST API")
    return c.fail("no application holds Nerdio's Rest client role, so the REST API isn't enabled",
                  "Enable it in Nerdio under Settings > Integrations > REST API (no API for this yet)")


GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"  # Microsoft Graph, the same in every tenant


def graph_app_roles(ctx) -> Optional[Dict[str, str]]:
    """Microsoft Graph's application permissions in this tenant: {value: app role id}."""
    def read():
        sps = graph_list(ctx, f"/servicePrincipals?$filter=appId eq '{GRAPH_APP_ID}'&$select=id,appRoles")
        if not sps:
            return None
        return {r.get("value"): r.get("id") for r in sps[0].get("appRoles") or []}
    return ctx.cached("graph_app_roles", read)


def granted_graph_roles(ctx, principal_id: str) -> Optional[set]:
    """Graph application permission names a service principal or managed identity holds."""
    roles = graph_app_roles(ctx)
    rows = graph_list(ctx, f"/servicePrincipals/{principal_id}/appRoleAssignments")
    if roles is None or rows is None:
        return None
    by_id = {v: k for k, v in roles.items()}
    return {by_id.get(r.get("appRoleId")) for r in rows} - {None}


@check("nme.wizard", "Nerdio's wizard", needs="Nerdio's REST client (the data tier, --nerdio-data)",
       kb="docs/knowledge/nerdio/platform.md", stages=[WIZARD],
       source="https://nmehelp.getnerdio.com/hc/en-us/articles/27422824784269", reads=["Nerdio GET /api/v1/ad/config"])
def wizard(ctx, c):
    """The directory profile is set. Linked networks and resource groups have no read in Nerdio's
    API yet, so the rest of the wizard is `manual`."""
    from ..nerdio_api import NotConfigured, SignInFailed

    if not ctx.nerdio_data:
        return c.skip("reads Nerdio's own API; add --nerdio-data")
    try:
        status, body = ctx.nerdio_get("/api/v1/ad/config")
    except SignInFailed as exc:
        return c.warn(f"Nerdio data tier: {exc}")
    except NotConfigured as exc:
        return c.skip(f"Nerdio data tier: {exc}")
    if status in (401, 403):
        return c.no_access(f"Nerdio's API refused the REST client (HTTP {status})",
                           "Check the REST client's role in Nerdio: Settings > Integrations > REST API")
    if status is None:
        return c.warn("Nerdio's API didn't answer")
    out = []
    if status == 404 or not body:
        out.append(c.fail("no directory profile is set in Nerdio", "Finish the wizard's directory step (no API yet)"))
    elif status == 200:
        out.append(c.ok("a directory profile is set"))
    else:
        out.append(c.warn(f"Nerdio's API answered HTTP {status} for the directory profile"))
    out.append(c.manual("confirm the wizard linked the AVD network and the host pool resource group "
                        "(Nerdio's API has no read for them yet)", title="Wizard links"))
    return out
