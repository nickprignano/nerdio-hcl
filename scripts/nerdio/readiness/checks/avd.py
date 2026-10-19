"""avd.*: session host size and vCPU quota before the install; the AVD estate after the wizard."""

from __future__ import annotations

import math

from ..model import PRE, WIZARD, check

KB = "docs/knowledge/nerdio/readiness.md#avd"


def full_scale_hosts(values) -> int:
    return values.get("host_pool_capacity") or math.ceil(values["user_count"] / values["max_sessions_per_host"])


def vm_sku(ctx):
    """The size's SKU row in the region: a dict, False when it isn't offered, None when az can't say."""
    location, size = ctx.values["location"], ctx.values["vm_size"]

    def read():
        skus = ctx.az(["vm", "list-skus", "-l", location, "--size", size, "--resource-type", "virtualMachines"])
        if skus is None:
            return None
        return next((s for s in skus if s.get("name", "").lower() == size.lower()), False)
    return ctx.cached(("sku", location, size), read)


@check("avd.vm_size", "VM size", needs="Reader on the subscription", kb=KB, inputs=["location", "vm_size"], region=True,
       source="https://learn.microsoft.com/azure/azure-resource-manager/troubleshooting/error-sku-not-available",
       reads=["az vm list-skus"])
def vm_size(ctx, c):
    location, size = ctx.values["location"], ctx.values["vm_size"]
    sku = vm_sku(ctx)
    if sku is None:
        return c.warn(f"couldn't look up {size} in {location}")
    if sku is False:
        return c.fail(f"{size} isn't offered in {location}", f"az vm list-skus -l {location} --size Standard_D -o table")
    if [r for r in sku.get("restrictions", []) if r.get("reasonCode") == "NotAvailableForSubscription"]:
        return c.fail(f"{size} is restricted for this subscription in {location}",
                      "Pick another size, or open a support request to lift the restriction")
    return c.ok(f"{size} is offered in {location}")


@check("avd.vcpu", "vCPU quota", needs="Reader on the subscription", kb=KB, region=True,
       inputs=["location", "vm_size", "user_count", "max_sessions_per_host"], features=["automation"], core=True,
       source="https://learn.microsoft.com/azure/quotas/per-vm-quota-requests", reads=["az vm list-skus", "az vm list-usage"])
def vcpu(ctx, c):
    """Family and regional vCPU quota for the host pool at full scale."""
    location, size = ctx.values["location"], ctx.values["vm_size"]
    sku = vm_sku(ctx)
    if not sku:
        return c.skip(f"needs {size} to be offered in {location} (see VM size)")
    caps = {x["name"]: x["value"] for x in sku.get("capabilities", [])}
    vcpus = int(caps.get("vCPUs", "0") or 0)
    family = sku.get("family")
    hosts = full_scale_hosts(ctx.values)
    need = vcpus * hosts
    usage = ctx.az(["vm", "list-usage", "-l", location])
    if usage is None or not family:
        return c.warn(f"couldn't read quota; you need {need} vCPUs of {family or size}")
    out = []
    for key, label in ((family, f"{family} vCPUs"), ("cores", "Total regional vCPUs")):
        row = next((u for u in usage if u.get("name", {}).get("value") == key), None)
        if not row:
            out.append(c.warn(f"no quota row for {label}"))
            continue
        free = int(row["limit"]) - int(row["currentValue"])
        if free >= need:
            out.append(c.ok(f"{label}: {free} free, {need} needed for {hosts} hosts at full scale"))
        else:
            out.append(c.fail(f"{label}: {free} free, {need} needed for {hosts} hosts at full scale",
                              f"./nerdio fix vcpu --family {key} --limit {int(row['currentValue']) + need}, "
                              "or lower host_pool_capacity"))
    return out


# --- The image, before the install ---------------------------------------------------------------


@check("avd.image", "Session host image", needs="Reader on the subscription", kb=KB, inputs=["location", "image"],
       source="https://learn.microsoft.com/azure/virtual-machines/generation-2",
       reads=["az vm image list-skus", "az vm list-skus"])
def image(ctx, c):
    """The Marketplace image (publisher/offer/sku) is offered in the region, and the VM size runs
    Generation 2 VMs, which Windows 11 needs."""
    parts = (ctx.values["image"] or "").split("/")
    if len(parts) < 3:
        return c.skip("the image isn't a Marketplace publisher/offer/sku")
    publisher, offer, sku = parts[:3]
    location = ctx.values["location"]
    skus = ctx.az(["vm", "image", "list-skus", "-l", location, "-p", publisher, "-f", offer, "--query", "[].name"])
    if skus is None:
        return c.warn(f"couldn't list {offer} images in {location}")
    if sku not in skus:
        return c.fail(f"{offer}/{sku} isn't offered in {location}",
                      f"az vm image list-skus -l {location} -p {publisher} -f {offer} -o table")
    size = vm_sku(ctx) if ctx.values.get("vm_size") else None
    gens = {x["name"]: x["value"] for x in (size or {}).get("capabilities", [])}.get("HyperVGenerations", "")
    if size and gens and "V2" not in gens and "win11" in sku.lower():
        return c.fail(f"{ctx.values['vm_size']} runs Generation 1 VMs only; Windows 11 needs Generation 2",
                      "Pick a v3 or later size")
    return c.ok(f"{offer}/{sku} is offered in {location}")


# --- After Nerdio's wizard: the AVD estate it manages -------------------------------------------

DV = "2024-04-03"  # Microsoft.DesktopVirtualization; az has no built-in desktopvirtualization commands
AVD_SECURITY = "https://learn.microsoft.com/azure/virtual-desktop/security-recommendations"
# Microsoft's first-party Azure Virtual Desktop app, the same in every tenant. Its display name
# varies (older tenants still say Windows Virtual Desktop), so it's matched by app ID.
AVD_APP_ID = "9cdead84-a844-4324-93f2-b2e6bb768d07"
UNHEALTHY = {"Unavailable", "NeedsAssistance", "UpgradeFailed", "NoHeartbeat", "NotJoinedToDomain",
             "DomainTrustRelationshipLost", "SxSStackListenerNotReady", "FSLogixNotHealthy"}


def arm_list(ctx, path: str):
    data = ctx.get(ctx.arm(path))
    return None if data is None else data.get("value", [])


def dv_list(ctx, kind: str):
    return ctx.cached(("dv", kind), lambda: arm_list(
        ctx, f"/subscriptions/{ctx.subscription_id}/providers/Microsoft.DesktopVirtualization/{kind}?api-version={DV}"))


def pools_or_skip(ctx, c):
    pools = dv_list(ctx, "hostPools")
    if pools is None:
        return None, c.no_access("can't list host pools")
    if not pools:
        return None, c.skip("no host pools yet")
    return pools, None


def avd_sp(ctx):
    return ctx.cached("avd_sp", lambda: ctx.az(["ad", "sp", "list", "--filter", f"appId eq '{AVD_APP_ID}'",
                                                "--query", "[0].id"]))


@check("avd.entra_join_login", "Entra sign-in to hosts", needs="Reader on the subscription", kb=KB,
       stages=[WIZARD], inputs=["identity_model"],
       source="https://learn.microsoft.com/azure/virtual-desktop/azure-ad-joined-session-hosts",
       reads=["az role assignment list", "ARM hostPools"])
def entra_join_login(ctx, c):
    """People sign in to Entra-joined hosts only with Virtual Machine User Login (or Administrator
    Login), and only through a host pool whose RDP properties allow Entra sign-in."""
    if ctx.values["identity_model"] != "entra_joined":
        return c.skip("only for Entra-joined session hosts")
    out = []
    rows = ctx.az(["role", "assignment", "list", "--all", "--query",
                   "[?roleDefinitionName=='Virtual Machine User Login' || "
                   "roleDefinitionName=='Virtual Machine Administrator Login'].scope"])
    if rows is None:
        out.append(c.no_access("can't list role assignments"))
    elif not rows:
        out.append(c.fail("nobody holds Virtual Machine User Login, so users can't sign in to Entra-joined hosts",
                          "az role assignment create --assignee <AVD users group> --role \"Virtual Machine User Login\" "
                          "--scope <session host resource group>"))
    for pool in dv_list(ctx, "hostPools") or []:
        rdp = ((pool.get("properties") or {}).get("customRdpProperty") or "").lower()
        if "targetisaadjoined:i:1" not in rdp and "enablerdsaadauth:i:1" not in rdp:
            out.append(c.fail(f"{ctx.name('hostpool', pool.get('name', ''))} doesn't allow Entra sign-in in its RDP "
                              "properties, so Entra-joined hosts refuse connections",
                              "Add enablerdsaadauth:i:1 (single sign-on) or targetisaadjoined:i:1 in Nerdio: "
                              "host pool > Properties > RDP settings"))
    return out or [c.ok(f"Virtual Machine User Login is assigned at {len(rows)} scopes and host pools allow Entra sign-in")]


@check("avd.assignments", "User assignments", needs="Reader on the subscription", kb=KB, stages=[WIZARD],
       source="https://learn.microsoft.com/azure/virtual-desktop/app-groups",
       reads=["ARM applicationGroups", "ARM workspaces", "az role assignment list"])
def assignments(ctx, c):
    groups = dv_list(ctx, "applicationGroups")
    if groups is None:
        return c.no_access("can't list application groups")
    if not groups:
        return c.skip("no application groups yet")
    out, empty = [], []
    for g in groups:
        rows = ctx.az(["role", "assignment", "list", "--scope", g["id"], "--role", "Desktop Virtualization User",
                       "--query", "[].principalId"])
        if rows is None:
            return c.no_access("can't list application group assignments")
        if not rows:
            empty.append(ctx.name("appgroup", g.get("name", "")))
    if empty:
        out.append(c.warn("nobody is assigned to " + ", ".join(empty),
                          "Assign users or a group in Nerdio: host pool > Assignments"))
    listed = {ref.lower() for w in dv_list(ctx, "workspaces") or []
              for ref in (w.get("properties") or {}).get("applicationGroupReferences") or []}
    orphans = [ctx.name("appgroup", g.get("name", "")) for g in groups if g["id"].lower() not in listed]
    if orphans:
        out.append(c.warn("no workspace shows " + ", ".join(orphans) + ", so users won't see it",
                          "Add it to a workspace in Nerdio"))
    return out or [c.ok(f"all {len(groups)} application groups have users and a workspace")]


@check("avd.start_vm_on_connect", "Start VM on connect", needs="Reader on the subscription", kb=KB,
       stages=[WIZARD], features=["self-service", "automation"],
       source="https://learn.microsoft.com/azure/virtual-desktop/start-virtual-machine-connect",
       reads=["ARM hostPools", "ARM scalingPlans", "az role assignment list", "az ad sp list"])
def start_vm_on_connect(ctx, c):
    found, skipped = pools_or_skip(ctx, c)
    if skipped:
        return skipped
    using = [p for p in found if (p.get("properties") or {}).get("startVMOnConnect")]
    plans = dv_list(ctx, "scalingPlans") or []
    if not using and not plans:
        return c.skip("no host pool uses Start VM on connect or a Microsoft scaling plan")
    sp = avd_sp(ctx)
    if not sp:
        return c.no_access("can't find the Azure Virtual Desktop service principal")
    rows = ctx.az(["role", "assignment", "list", "--assignee", sp, "--all", "--query",
                   "[].{role:roleDefinitionName, scope:scope}"])
    if rows is None:
        return c.no_access("can't list the Azure Virtual Desktop service principal's roles")
    sub = f"/subscriptions/{ctx.subscription_id}".lower()
    roles = {r.get("role") for r in rows}
    at_sub = {r.get("role") for r in rows if (r.get("scope") or "").lower() == sub}
    out = []
    if using and not {"Desktop Virtualization Power On Contributor", "Desktop Virtualization Power On Off Contributor"} & roles:
        out.append(c.fail(f"{len(using)} host pools use Start VM on connect, but Azure Virtual Desktop can't start VMs",
                          "az role assignment create --assignee <Azure Virtual Desktop SP> --role "
                          "\"Desktop Virtualization Power On Contributor\" --scope /subscriptions/<id>"))
    if plans and "Desktop Virtualization Power On Off Contributor" not in at_sub:
        out.append(c.fail("Microsoft scaling plans need Desktop Virtualization Power On Off Contributor at subscription "
                          "scope (lower scopes break autoscale)",
                          "az role assignment create --assignee <Azure Virtual Desktop SP> --role "
                          "\"Desktop Virtualization Power On Off Contributor\" --scope /subscriptions/<id>"))
    return out or [c.ok("Azure Virtual Desktop holds the power roles it needs")]


@check("avd.host_health", "Session hosts", needs="Reader on the subscription", kb=KB, stages=[WIZARD],
       source="https://learn.microsoft.com/azure/virtual-desktop/troubleshoot-statuses-checks",
       reads=["ARM hostPools/sessionHosts"])
def host_health(ctx, c):
    found, skipped = pools_or_skip(ctx, c)
    if skipped:
        return skipped
    bad, total = [], 0
    for pool in found:
        hosts = arm_list(ctx, f"{pool['id']}/sessionHosts?api-version={DV}")
        if hosts is None:
            return c.no_access("can't list session hosts")
        for h in hosts:
            total += 1
            props = h.get("properties") or {}
            # Upgrading is normal and still takes sessions; shut-down hosts are auto-scale at work.
            status = "UpgradeFailed" if props.get("updateState") == "Failed" else props.get("status")
            if status in UNHEALTHY:
                failing = [x.get("healthCheckName") for x in props.get("sessionHostHealthCheckResults") or []
                           if x.get("healthCheckResult") == "HealthCheckFailed"]
                bad.append(f"{ctx.name('host', h.get('name', '').split('/')[-1])} ({status}"
                           + (": " + ", ".join(failing) if failing else "") + ")")
    if bad:
        return c.warn(f"{len(bad)} of {total} session hosts are unhealthy: " + "; ".join(bad[:5]),
                      "Open the host in Nerdio and read its health checks; reimage it if the agent is broken")
    if not total:
        return c.warn("the host pools have no session hosts yet")
    return c.ok(f"{total} session hosts, none unhealthy")


@check("avd.diagnostics", "AVD diagnostics", needs="Reader on the subscription", kb=KB, stages=[WIZARD],
       source="https://learn.microsoft.com/azure/virtual-desktop/insights", reads=["ARM diagnosticSettings"])
def diagnostics(ctx, c):
    """Host pools and workspaces send diagnostics to Log Analytics; AVD Insights needs them."""
    pools, spaces = dv_list(ctx, "hostPools"), dv_list(ctx, "workspaces")
    if pools is None or spaces is None:
        return c.no_access("can't list host pools and workspaces")
    items = pools + spaces
    if not items:
        return c.skip("no host pools or workspaces yet")
    silent = []
    for item in items:
        diag = arm_list(ctx, f"{item['id']}/providers/Microsoft.Insights/diagnosticSettings?api-version=2021-05-01-preview")
        if diag is None:
            return c.no_access("can't read diagnostic settings")
        if not diag:
            silent.append(ctx.name("avd", item.get("name", "")))
    if silent:
        return c.warn("no diagnostics from " + ", ".join(silent),
                      "Turn on monitoring in Nerdio: host pool > Properties > Monitoring")
    return c.ok(f"{len(items)} host pools and workspaces send diagnostics")


def premium_files_offered(ctx):
    """True when premium file shares (FileStorage, Premium_LRS) are offered in the region; None when unreadable."""
    location = ctx.values["location"].lower()

    def read():
        rows = ctx.az(["storage", "sku", "list", "--query", "[?name=='Premium_LRS' && kind=='FileStorage'].locations"])
        return None if rows is None else any(location in [x.lower() for x in locs] for locs in rows)
    return ctx.cached(("premium_files", location), read)


AUTH = {"entra_joined": "AADKERB", "ad_ds": "AD", "entra_ds": "AADDS"}
SHARE_ROLES = ("Storage File Data SMB Share Contributor", "Storage File Data SMB Share Elevated Contributor")


@check("avd.fslogix_storage", "FSLogix storage", needs="Reader on the subscription", kb=KB, stages=[PRE, WIZARD],
       inputs=["location"],
       source="https://learn.microsoft.com/azure/virtual-desktop/fslogix-profile-container-configure-azure-files-active-directory",
       reads=["az storage sku list", "az storage account list", "az role assignment list"])
def fslogix_storage(ctx, c):
    """Before the install: premium file shares are offered in the region. After the wizard: the
    profile share signs in the way hosts join, users and admins hold the share roles, and it isn't
    open to the internet."""
    if ctx.values.get("fslogix_enabled") is False:
        return c.skip("FSLogix is turned off in the answers")
    if ctx.stage == PRE:
        offered = premium_files_offered(ctx)
        if offered is None:
            return c.warn("couldn't list storage SKUs")
        if not offered:
            return c.fail(f"premium file shares (FileStorage) aren't offered in {ctx.values['location']}", "Pick another region")
        return c.ok(f"premium file shares are offered in {ctx.values['location']}")
    name = ctx.values.get("fslogix_storage_account_name")
    if not name:
        return c.skip("needs input: fslogix_storage_account_name (--fslogix-storage)")
    found = ctx.az(["storage", "account", "list", "--query", f"[?name=='{name}']."
                    "{id:id, auth:azureFilesIdentityBasedAuthentication.directoryServiceOptions, public:publicNetworkAccess, "
                    "endpoints:length(privateEndpointConnections || `[]`)}"])
    if found is None:
        return c.no_access("can't list storage accounts")
    if not found:
        return c.fail(f"no storage account {ctx.name('storage', name)} in this subscription",
                      "Create the FSLogix share in Nerdio: Settings > FSLogix")
    acct = found[0]
    want = AUTH.get(ctx.values.get("identity_model"))
    out = []
    if want and acct.get("auth") != want:
        flag = {"AADKERB": "aadkerb", "AD": "adds", "AADDS": "aadds"}[want]
        out.append(c.fail(f"the share signs in with {acct.get('auth') or 'nothing'}; "
                          f"{ctx.values.get('identity_model')} hosts need {want}",
                          f"az storage account update -n <account> --enable-files-{flag} true"))
    roles = ctx.az(["role", "assignment", "list", "--scope", acct["id"], "--include-inherited", "--query",
                    "[].roleDefinitionName"]) if acct.get("id") else None
    if roles is not None:
        missing = [r for r in SHARE_ROLES if r not in roles]
        if missing:
            out.append(c.fail("nobody holds " + " or ".join(missing) + " on the profile share",
                              "Assign the users' group SMB Share Contributor and the admins Elevated Contributor"))
    if acct.get("public") != "Disabled" and not acct.get("endpoints"):
        out.append(c.warn("the profile share is reachable from the internet and has no private endpoint",
                          "Add a private endpoint and turn off public network access"))
    return out or [c.ok(f"signs in with {acct.get('auth')}, share roles assigned, private")]
