"""app.* and attach.*: application management and App Attach (--features app-mgmt, app-attach)."""

from __future__ import annotations

from ..model import PRE, WIZARD, check
from .avd import AVD_APP_ID, arm_list, avd_sp, dv_list, premium_files_offered
from .nerdio import graph_list, granted_graph_roles, nerdio_app

KB = "docs/knowledge/nerdio/readiness.md#applications"
WINGET = "https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps"
ATTACH = "https://nmehelp.getnerdio.com/hc/en-us/articles/26124362318989-Configure-Azure-Files-Permissions-for-App-Attach"
INTUNE_PLANS = ("INTUNE_A", "INTUNE_EDU", "INTUNE_SMBIZ")
INTUNE_APP_PERMISSION = "DeviceManagementApps.ReadWrite.All"


@check("app.intune_repo", "Intune app repository", needs="Directory Readers", kb=KB, stages=[WIZARD],
       features=["app-mgmt"], source="https://learn.microsoft.com/graph/permissions-reference",
       reads=["Graph /subscribedSkus", "Graph /servicePrincipals/{id}/appRoleAssignments"])
def intune_repo(ctx, c):
    skus = graph_list(ctx, "/subscribedSkus?$select=skuPartNumber,prepaidUnits,servicePlans")
    if skus is None:
        return c.no_access("can't read the tenant's licenses")
    intune = [s for s in skus if (s.get("prepaidUnits") or {}).get("enabled") and
              any(p.get("servicePlanName") in INTUNE_PLANS for p in s.get("servicePlans") or [])]
    out = []
    if not intune:
        out.append(c.fail("no Intune licenses in the tenant", "Intune comes with Microsoft 365 E3/E5 or Business Premium"))
    found = nerdio_app(ctx) or {}
    if not found.get("sp"):
        return out + [c.skip("needs Nerdio's service principal (see Nerdio's Entra app)")]
    granted = granted_graph_roles(ctx, found["sp"]["id"])
    if granted is None:
        return out + [c.no_access("can't read Nerdio's Graph permissions")]
    if INTUNE_APP_PERMISSION not in granted:
        out.append(c.fail(f"Nerdio's app doesn't hold {INTUNE_APP_PERMISSION} with consent",
                          "Turn on the Intune integration in Nerdio, then grant admin consent for the permission it adds"))
    return out or [c.ok(f"Intune licensed and Nerdio holds {INTUNE_APP_PERMISSION}")]


@check("app.private_winget", "Private WinGet", needs="Reader on the subscription", kb=KB, stages=[PRE],
       features=["app-mgmt"], inputs=["location"], source=WINGET,
       reads=["az provider show", "ARM Microsoft.DocumentDB/locations"])
def private_winget(ctx, c):
    """Private WinGet adds Cosmos DB, a Function App and, when private, seven more private endpoints."""
    location = ctx.values["location"].lower()
    out = []
    for ns in ("Microsoft.DocumentDB", "Microsoft.Web"):
        state = ctx.az(["provider", "show", "-n", ns, "--query", "registrationState"])
        if state is None:
            out.append(c.warn(f"couldn't read {ns}'s registration"))
        elif state != "Registered":
            out.append(c.fail(f"{ns} isn't registered", f"az provider register -n {ns}"))
    regions = ctx.get(ctx.arm(f"/subscriptions/{ctx.subscription_id}/providers/Microsoft.DocumentDB/locations"
                              "?api-version=2023-11-15"))
    if regions is None:
        out.append(c.warn("couldn't list Cosmos DB regions"))
    else:
        here = [r for r in regions.get("value", []) if r.get("name", "").replace(" ", "").lower() == location]
        if not here or (here[0].get("properties") or {}).get("isSubscriptionRegionAccessAllowedForRegular") is False:
            out.append(c.fail(f"Cosmos DB isn't open to this subscription in {location}",
                              "Pick another region, or request region access from Microsoft support"))
    out.append(c.manual("when private, the private endpoint subnet needs room for seven more endpoints",
                        title="Private WinGet endpoints"))
    return out


@check("app.winget_reach", "WinGet reach", needs="Reader on the subscription", kb=KB, stages=[WIZARD],
       features=["app-mgmt"], source=WINGET, reads=["az network nsg list"])
def winget_reach(ctx, c):
    """Session hosts reach the WinGet community source and the private WinGet Function App over 443."""
    rows = ctx.az(["network", "nsg", "list", "--query",
                   "[].{name:name, rules:securityRules[?direction=='Outbound' && access=='Deny']."
                   "{port:destinationPortRange, ports:destinationPortRanges, to:destinationAddressPrefix}}"])
    if rows is None:
        return c.no_access("can't list network security groups")
    blocking = []
    for nsg in rows:
        for r in nsg.get("rules") or []:
            ports = [r.get("port")] + list(r.get("ports") or [])
            if (r.get("to") in ("Internet", "*", "0.0.0.0/0")) and any(p in ("*", "443") for p in ports if p):
                blocking.append(ctx.name("nsg", nsg.get("name", "")))
    if blocking:
        return c.warn("outbound 443 to the internet is denied by " + ", ".join(sorted(set(blocking))),
                      "Allow 443 to the WinGet source and the private WinGet Function App")
    return c.manual("no security group denies outbound 443; confirm a firewall on the route allows the WinGet "
                    "source and the private WinGet Function App")


@check("app.shell_apps", "Shell Apps storage", needs="Reader on Nerdio's resource group", kb=KB, stages=[WIZARD],
       features=["app-mgmt"], account=False, source=WINGET)
def shell_apps(ctx, c):
    return c.manual("confirm the Shell Apps storage account Nerdio created is reachable from the host subnets "
                    "(its name isn't documented, so it isn't found automatically)")


@check("app.sccm", "ConfigMgr repository", needs="none", kb=KB, stages=[PRE], features=["app-mgmt"], account=False,
       source=WINGET)
def sccm(ctx, c):
    return c.manual("a ConfigMgr repository lives on-premises; confirm the site server is reachable from the hosts")


# --- App Attach ------------------------------------------------------------------------------


def attach_account(ctx):
    name = ctx.values.get("app_attach_storage")

    def read():
        rows = ctx.az(["storage", "account", "list", "--query", f"[?name=='{name}']."
                       "{id:id, auth:azureFilesIdentityBasedAuthentication.directoryServiceOptions, "
                       "share:azureFilesIdentityBasedAuthentication.defaultSharePermission}"])
        return None if rows is None else (rows[0] if rows else False)
    return ctx.cached(("attach", name), read)


@check("attach.storage_sub", "App Attach storage", needs="Reader on the subscription", kb=KB, stages=[PRE, WIZARD],
       features=["app-attach"], inputs=["app_attach_storage"], source=ATTACH, reads=["az storage account list"])
def storage_sub(ctx, c):
    acct = attach_account(ctx)
    if acct is None:
        return c.no_access("can't list storage accounts")
    if acct is False:
        return c.fail(f"{ctx.name('storage', ctx.values['app_attach_storage'])} isn't in this subscription; App Attach "
                      "needs its storage in the session hosts' subscription", "Create it in this subscription")
    return c.ok("the App Attach storage account is in the session hosts' subscription")


# Microsoft's first-party Azure Virtual Desktop ARM Provider app, the same in every tenant.
ARM_PROVIDER_APP_ID = "50e95039-b200-4007-bc97-8d5790743a63"


def arm_provider_sp(ctx):
    return ctx.cached("arm_provider_sp", lambda: ctx.az(["ad", "sp", "list", "--filter", f"appId eq '{ARM_PROVIDER_APP_ID}'",
                                                          "--query", "[0].id"]))


@check("attach.entra_hosts", "App Attach for Entra-joined hosts", needs="Reader on the subscription", kb=KB,
       stages=[WIZARD], features=["app-attach"], inputs=["app_attach_storage", "identity_model"], source=ATTACH,
       reads=["az role assignment list", "az ad sp list"])
def entra_hosts(ctx, c):
    """Azure Virtual Desktop and its ARM Provider read the packages: Reader and Data Access on the account."""
    if ctx.values["identity_model"] != "entra_joined":
        return c.skip("only for Entra-joined session hosts")
    acct = attach_account(ctx)
    if not acct:
        return c.skip("needs the App Attach storage account (see App Attach storage)")
    rows = ctx.az(["role", "assignment", "list", "--scope", acct["id"], "--role", "Reader and Data Access",
                   "--include-inherited", "--query", "[].{id:principalId}"])
    if rows is None:
        return c.no_access("can't list the storage account's role assignments")
    holders = {r.get("id") for r in rows}
    sps = {"Azure Virtual Desktop": (AVD_APP_ID, avd_sp(ctx)),
           "Azure Virtual Desktop ARM Provider": (ARM_PROVIDER_APP_ID, arm_provider_sp(ctx))}
    if any(sp is None for _, sp in sps.values()):
        return c.no_access("can't look up the Azure Virtual Desktop service principals")
    missing = [(name, app) for name, (app, sp) in sps.items() if sp not in holders]
    if missing:
        return c.fail(" and ".join(n for n, _ in missing) + " lack Reader and Data Access on the App Attach storage",
                      "az role assignment create --assignee <app ID> --role \"Reader and Data Access\" --scope <storage account> "
                      "(app IDs: " + ", ".join(f"{n} {a}" for n, a in missing) + ")")
    return c.ok("both Azure Virtual Desktop service principals can read the packages")


@check("attach.adds_hosts", "App Attach for AD DS hosts", needs="Reader on the subscription", kb=KB, stages=[WIZARD],
       features=["app-attach"], inputs=["app_attach_storage", "identity_model"], source=ATTACH,
       reads=["az storage account list", "az role assignment list"])
def adds_hosts(ctx, c):
    if ctx.values["identity_model"] != "ad_ds":
        return c.skip("only for AD DS-joined session hosts")
    acct = attach_account(ctx)
    if not acct:
        return c.skip("needs the App Attach storage account (see App Attach storage)")
    out = []
    if acct.get("auth") != "AD":
        out.append(c.fail("the App Attach storage account isn't joined to AD DS", "Join it with AzFilesHybrid"))
    rows = ctx.az(["role", "assignment", "list", "--scope", acct["id"], "--role", "Storage File Data SMB Share Reader",
                   "--include-inherited", "--query", "[].principalId"])
    if rows == [] and acct.get("share") in (None, "None"):
        out.append(c.fail("nobody can read the share: no Storage File Data SMB Share Reader and no default share permission",
                          "Give the session hosts' computer group (or all authenticated identities) SMB Share Reader"))
    out.append(c.manual("confirm the NTFS permissions on the share let the hosts' computer accounts read", title="NTFS"))
    return out


# Windows Server 2016, 2019 and 2022 builds. Server 2025 shares build 26100 with Windows 11 24H2,
# so it can't be told apart here.
SERVER_BUILDS = ("10.0.14393", "10.0.17763", "10.0.20348")


@check("attach.host_pools", "App Attach host pools", needs="Reader on the subscription", kb=KB, stages=[WIZARD],
       features=["app-attach"], source="https://learn.microsoft.com/azure/virtual-desktop/app-attach-overview",
       reads=["ARM hostPools/sessionHosts"])
def host_pools(ctx, c):
    pools = dv_list(ctx, "hostPools")
    if pools is None:
        return c.no_access("can't list host pools")
    if not pools:
        return c.skip("no host pools yet")
    server = []
    for pool in pools:
        for h in arm_list(ctx, f"{pool['id']}/sessionHosts?api-version=2024-04-03") or []:
            if ((h.get("properties") or {}).get("osVersion") or "").startswith(SERVER_BUILDS):
                server.append(ctx.name("hostpool", pool.get("name", "")))
                break
    if server:
        return c.warn("these host pools run Windows Server, which App Attach doesn't support: " + ", ".join(server))
    return c.ok("host pools are ARM-based and run client Windows")


@check("attach.premium", "App Attach premium shares", needs="Reader on the subscription", kb=KB, stages=[PRE],
       features=["app-attach"], inputs=["location"], source=ATTACH, reads=["az storage sku list"])
def premium(ctx, c):
    offered = premium_files_offered(ctx)
    if offered is None:
        return c.warn("couldn't list storage SKUs")
    if not offered:
        return c.warn(f"premium file shares (recommended for App Attach) aren't offered in {ctx.values['location']}")
    return c.ok("premium file shares are offered in the region")
