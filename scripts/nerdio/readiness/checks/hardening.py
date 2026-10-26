"""hard.*: Nerdio Manager's own resources locked down (--features hardening, after the wizard)."""

from __future__ import annotations

from ..model import WIZARD, check
from .nerdio import first, need, nerdio_app, nerdio_group, resources

KB = "docs/knowledge/nerdio/readiness.md#hardening"
PLATFORM_KB = "docs/knowledge/nerdio/platform.md"
NERDIO_PREP = "https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps"
FEATURE = ["hardening"]
STAGES = [WIZARD]
PRIVATE_KINDS = ("sql", "key_vault", "web", "automation", "storage")


def public_off(value) -> bool:
    """publicNetworkAccess is "Disabled" on most types and a boolean on Automation accounts."""
    return value is False or value == "Disabled"


def is_private(ctx, item) -> "bool | None":
    """Public network access off and at least one private endpoint; None when unreadable. Web apps
    list their endpoints at their own URL, not in the site's properties."""
    props = ctx.az(["resource", "show", "--ids", item["id"], "--query",
                    "{public:properties.publicNetworkAccess, pe:length(properties.privateEndpointConnections || `[]`)}"])
    if props is None:
        return None
    pe = props.get("pe")
    if item.get("type", "").lower() == "microsoft.web/sites":
        data = ctx.get(ctx.arm(f"{item['id']}/privateEndpointConnections?api-version=2023-01-01"))
        if data is None:
            return None
        pe = len(data.get("value", []))
    return bool(pe) and public_off(props.get("public"))


def public_access_off(ctx, item) -> "bool | None":
    props = ctx.az(["resource", "show", "--ids", item["id"], "--query", "{public:properties.publicNetworkAccess}"])
    return None if props is None else public_off(props.get("public"))


def resources_or_skip(ctx, c):
    res = resources(ctx)
    if res is None:
        return None, c.skip("needs Nerdio's resource group: --resource-group or --nerdio-url")
    return res, None


@check("hard.private_endpoints", "Private endpoints", needs="Reader on Nerdio's resource group", kb=KB,
       stages=STAGES, features=FEATURE, source="https://learn.microsoft.com/azure/private-link/private-endpoint-overview",
       reads=["az resource show"])
def private_endpoints(ctx, c):
    """SQL, Key Vault, the web app, Automation and storage have private endpoints and refuse public traffic."""
    res, skipped = resources_or_skip(ctx, c)
    if skipped:
        return skipped
    open_ = []
    for kind in PRIVATE_KINDS:
        for item in res.get(kind, [])[:1] if kind == "web" else res.get(kind, []):
            private = is_private(ctx, item)
            if private is None:
                return c.no_access(f"can't read Nerdio's {kind.replace('_', ' ')}")
            if not private:
                open_.append(f"{kind.replace('_', ' ')} {ctx.name(kind, item['name'])}")
    if open_:
        return c.warn("public or without a private endpoint: " + ", ".join(open_),
                      "Set enable_hardening = true in the kit, or follow Nerdio's private networking guide")
    return c.ok("SQL, Key Vault, web app, Automation and storage are private")


@check("hard.vnet_integration", "App Service VNet integration", needs="Reader on Nerdio's resource group", kb=KB,
       stages=STAGES, features=FEATURE, source="https://learn.microsoft.com/azure/app-service/overview-vnet-integration",
       reads=["az webapp show"])
def vnet_integration(ctx, c):
    web, skipped = need(ctx, c, "web")
    if skipped:
        return skipped
    data = ctx.az(["webapp", "show", "--ids", web["id"], "--query",
                   "{subnet:virtualNetworkSubnetId, routeAll:siteConfig.vnetRouteAllEnabled, "
                   "allTraffic:outboundVnetRouting.allTraffic}"])
    if data is None:
        return c.no_access("can't read the web app")
    if not data.get("subnet"):
        return c.warn("Nerdio Manager's web app isn't VNet-integrated, so it can't reach private SQL and Key Vault",
                      "Integrate it into the delegated subnet (enable_hardening = true in the kit)")
    if not (data.get("routeAll") or data.get("allTraffic")):
        return c.warn("VNet-integrated, but only private traffic goes through the VNet (route-all is off)",
                      "az webapp config set --ids <web app> --vnet-route-all-enabled true")
    return c.ok("VNet-integrated with all outbound traffic routed through the VNet")


@check("hard.sql_firewall", "SQL firewall", needs="Reader on Nerdio's resource group", kb=KB, stages=STAGES,
       features=FEATURE, source="https://learn.microsoft.com/azure/azure-sql/database/firewall-configure",
       reads=["ARM sql servers/firewallRules"])
def sql_firewall(ctx, c):
    server, skipped = need(ctx, c, "sql")
    if skipped:
        return skipped
    data = ctx.get(ctx.arm(f"{server['id']}/firewallRules?api-version=2021-11-01"))
    if data is None:
        return c.no_access("can't read the SQL server's firewall rules")
    names = [r.get("name") for r in data.get("value", [])]
    if "AllowAllWindowsAzureIps" in names:
        return c.warn("\"Allow Azure services\" is on: any Azure tenant's resources can try to reach Nerdio's SQL",
                      "Remove the AllowAllWindowsAzureIps rule once the web app reaches SQL privately")
    if names:
        return c.warn(f"{len(names)} firewall rules open SQL to specific addresses")
    return c.ok("no firewall rules; SQL takes private traffic only")


@check("hard.scm", "Publishing credentials", needs="Reader on Nerdio's resource group", kb=KB, stages=STAGES,
       features=FEATURE, source="https://learn.microsoft.com/azure/app-service/configure-basic-auth-disable",
       reads=["ARM sites/basicPublishingCredentialsPolicies", "az webapp config show"])
def scm(ctx, c):
    """Basic auth off for SCM and FTP on the core app only: Nerdio's docs say the Intune and
    Real-Time Insights apps need it on theirs."""
    web, skipped = need(ctx, c, "web")
    if skipped:
        return skipped
    on = []
    for kind in ("scm", "ftp"):
        data = ctx.get(ctx.arm(f"{web['id']}/basicPublishingCredentialsPolicies/{kind}?api-version=2023-01-01"))
        if data is None:
            return c.no_access("can't read the web app's publishing credentials policy")
        if (data.get("properties") or {}).get("allow"):
            on.append(kind.upper())
    conf = ctx.az(["webapp", "config", "show", "--ids", web["id"], "--query",
                   "{rules:length(scmIpSecurityRestrictions || `[]`), useMain:scmIpSecurityRestrictionsUseMain}"]) or {}
    out = []
    if on:
        out.append(c.warn("basic publishing credentials are on for " + " and ".join(on),
                          "az resource update --ids <web app>/basicPublishingCredentialsPolicies/scm --set properties.allow=false "
                          "(and the same for ftp)"))
    if not conf.get("useMain") and (conf.get("rules") or 0) <= 1:
        out.append(c.warn("the SCM (Kudu) site has no access restrictions of its own"))
    return out or [c.ok("basic auth off for SCM and FTP, and SCM access is restricted")]


@check("hard.runbooks_vs_private_storage", "Runbooks and private storage", needs="Reader on Nerdio's resource group",
       kb=PLATFORM_KB, stages=STAGES, features=FEATURE,
       source="https://nmehelp.getnerdio.com/hc/en-us/articles/26124302308109",
       reads=["az resource show", "ARM automationAccounts/hybridRunbookWorkerGroups"])
def runbooks_vs_private_storage(ctx, c):
    """Making the scripted-actions storage private breaks Azure runbook scripted actions in storage
    mode unless a hybrid worker runs them."""
    res, skipped = resources_or_skip(ctx, c)
    if skipped:
        return skipped
    acct = first(ctx, "automation")
    if not acct or not res.get("storage"):
        return c.skip("no Automation account or storage account in Nerdio's group")
    states = [public_access_off(ctx, st) for st in res["storage"]]
    if None in states:
        return c.no_access("can't read Nerdio's storage accounts")
    if not any(states):
        return c.ok("Nerdio's storage is public, so runbooks in storage mode can read their scripts")
    groups = ctx.get(ctx.arm(f"{acct['id']}/hybridRunbookWorkerGroups?api-version=2023-11-01"))
    if groups is None:
        return c.no_access("can't read the Automation account's hybrid worker groups")
    if not groups.get("value"):
        return c.warn("Nerdio's storage is private and there's no hybrid worker group, so Azure runbook scripted "
                      "actions in storage mode will fail",
                      "Switch scripted actions to inline mode, or add a hybrid worker group inside the VNet")
    return c.ok("storage is private and a hybrid worker group runs the runbooks")


@check("hard.mfa", "MFA for Nerdio Manager", needs="Policy.Read.All (Security Reader or Global Reader)", kb=KB,
       stages=STAGES, features=FEATURE,
       source="https://learn.microsoft.com/entra/identity/conditional-access/policy-all-users-mfa-strength",
       reads=["Graph /identity/conditionalAccess/policies"])
def mfa(ctx, c):
    data = ctx.get(ctx.graph("/identity/conditionalAccess/policies"))
    if data is None:
        return c.manual("can't read Conditional Access; confirm a policy requires MFA for Nerdio Manager's app",
                        "Needs Policy.Read.All (Security Reader or Global Reader)")
    app_id = ((nerdio_app(ctx) or {}).get("app") or {}).get("appId")
    for p in data.get("value", []):
        if p.get("state") != "enabled":
            continue
        apps = ((p.get("conditions") or {}).get("applications") or {}).get("includeApplications") or []
        grant = p.get("grantControls") or {}
        mfa_on = "mfa" in (grant.get("builtInControls") or []) or grant.get("authenticationStrength")
        if mfa_on and ("All" in apps or (app_id and app_id in apps)):
            return c.ok("an enabled Conditional Access policy requires MFA for Nerdio Manager")
    return c.warn("no enabled Conditional Access policy requires MFA for Nerdio Manager's app",
                  "Add Nerdio Manager's enterprise app to a policy that requires MFA")


@check("hard.diagnostics", "Nerdio diagnostics", needs="Reader on Nerdio's resource group", kb=KB, stages=STAGES,
       features=FEATURE, source="https://learn.microsoft.com/azure/azure-monitor/essentials/diagnostic-settings",
       reads=["ARM diagnosticSettings"])
def diagnostics(ctx, c):
    res, skipped = resources_or_skip(ctx, c)
    if skipped:
        return skipped
    silent = []
    for kind in ("key_vault", "sql_db", "web"):
        item = first(ctx, kind)
        if not item:
            continue
        data = ctx.get(ctx.arm(f"{item['id']}/providers/Microsoft.Insights/diagnosticSettings?api-version=2021-05-01-preview"))
        if data is None:
            return c.no_access("can't read diagnostic settings")
        if not data.get("value"):
            silent.append(kind.replace("_", " "))
    if silent:
        return c.warn("no diagnostic settings on Nerdio's " + ", ".join(silent),
                      "Send their logs to Nerdio's Log Analytics workspace")
    return c.ok("Key Vault, SQL and the web app send diagnostics")


@check("hard.locks", "Delete lock", needs="Reader on Nerdio's resource group", kb=KB, stages=STAGES, features=FEATURE,
       source="https://learn.microsoft.com/azure/azure-resource-manager/management/lock-resources", reads=["az lock list"])
def locks(ctx, c):
    rg = nerdio_group(ctx)
    if not rg:
        return c.skip("needs Nerdio's resource group")
    rows = ctx.az(["lock", "list", "-g", rg, "--query", "[].level"])
    if rows is None:
        return c.no_access("can't list locks")
    if "CanNotDelete" not in rows:
        return c.warn("no CanNotDelete lock on Nerdio's resource group (recommended, not required)",
                      "Add one after the install; remove it before a teardown")
    return c.ok("a CanNotDelete lock protects Nerdio's resource group")


@check("hard.kv_purge", "Key Vault purge protection", needs="Reader on Nerdio's resource group", kb=KB,
       stages=STAGES, features=FEATURE, source="https://learn.microsoft.com/azure/key-vault/general/soft-delete-overview",
       reads=["az keyvault show"])
def kv_purge(ctx, c):
    """Informational: Nerdio's template leaves purge protection off, and whether turning it on
    affects Nerdio's updater is unverified."""
    kv, skipped = need(ctx, c, "key_vault")
    if skipped:
        return skipped
    data = ctx.az(["keyvault", "show", "--ids", kv["id"], "--query", "{purge:properties.enablePurgeProtection}"])
    if data is None:
        return c.no_access("can't read Nerdio's Key Vault")
    state = "on" if data.get("purge") else "off (Nerdio's template default)"
    return c.ok(f"purge protection is {state}; whether turning it on affects Nerdio's updater is unverified")
