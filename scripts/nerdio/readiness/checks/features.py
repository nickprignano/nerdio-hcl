"""Feature domain checks: app-mgmt (app.*), app-attach (attach.*), insights (ins.*),
scripted-actions (sa.*), and automation (auto.*)."""

from __future__ import annotations

from ..model import WIZARD, check
from .avd import DV, arm_list, pools_or_skip
from .nerdio import need, resources

KB = "docs/knowledge/nerdio/readiness.md#features"
NERDIO_RESOURCES = "https://nmehelp.getnerdio.com/hc/en-us/articles/26124345260941-Nerdio-Manager-Default-Deployment-Resources-and-Costs"


@check("app.repository", "UAM package storage", needs="Reader on Nerdio's resource group", kb=KB,
       stages=[WIZARD], features=["app-mgmt"], source=NERDIO_RESOURCES, reads=["az resource list"])
def repository(ctx, c):
    """Unified Application Management stores custom packages in a storage account in Nerdio's group."""
    res = resources(ctx)
    if res is None:
        return c.skip("needs Nerdio's resource group: --resource-group or --nerdio-url")
    stores = res.get("storage") or []
    if not stores:
        return c.fail("no storage account in Nerdio's resource group for Unified Application Management packages",
                      "Create or link a storage account in Nerdio under Settings > Environment")
    return c.ok(f"{len(stores)} storage account(s) in Nerdio's resource group for UAM packages")


@check("attach.packages", "App Attach packages", needs="Reader on the subscription", kb=KB,
       stages=[WIZARD], features=["app-attach"],
       source="https://learn.microsoft.com/azure/virtual-desktop/app-attach-overview",
       reads=["ARM hostPools", "ARM hostPools/msixPackages"])
def packages(ctx, c):
    """MSIX / App Attach packages registered on host pools have an image path configured."""
    pools, skipped = pools_or_skip(ctx, c)
    if skipped:
        return skipped
    total, missing_path = 0, []
    for pool in pools:
        pkgs = arm_list(ctx, f"{pool['id']}/msixPackages?api-version={DV}")
        if pkgs is None:
            return c.no_access("can't list App Attach packages")
        for pkg in pkgs:
            total += 1
            props = pkg.get("properties") or {}
            if not props.get("imagePath"):
                missing_path.append(ctx.name("package", pkg.get("name", "")))
    if not total:
        return c.skip("no App Attach packages registered on any host pool yet")
    if missing_path:
        return c.warn("App Attach package(s) without an image path: " + ", ".join(missing_path),
                      "Update the package path in Nerdio under Applications > App Attach")
    return c.ok(f"{total} App Attach package(s) registered with image paths")


@check("ins.workspace", "Log Analytics workspace", needs="Reader on Nerdio's resource group", kb=KB,
       stages=[WIZARD], features=["insights"],
       source="https://learn.microsoft.com/azure/virtual-desktop/insights",
       reads=["ARM operationalInsights/workspaces"])
def workspace(ctx, c):
    """Nerdio's Log Analytics workspace exists and retains data for at least 30 days for Insights."""
    law, skipped = need(ctx, c, "law")
    if skipped:
        return skipped
    data = ctx.get(ctx.arm(f"{law['id']}?api-version=2022-10-01"))
    if data is None:
        return c.no_access("can't read Nerdio's Log Analytics workspace")
    props = data.get("properties") or {}
    retention = int(props.get("retentionInDays") or 0)
    sku = (props.get("sku") or {}).get("name") or "unknown"
    if retention < 30:
        return c.warn(f"Log Analytics retention is {retention} days (at least 30 days recommended for Insights)",
                      "az monitor log-analytics workspace update --ids <workspace> --retention-time 30")
    return c.ok(f"Log Analytics workspace ({sku}, {retention} days retention)")


@check("sa.automation_identity", "Scripted Actions identity", needs="Reader on Nerdio's resource group", kb=KB,
       stages=[WIZARD], features=["scripted-actions"],
       source="https://nmehelp.getnerdio.com/hc/en-us/articles/26124302308109",
       reads=["az resource show", "ARM automationAccounts/runbooks"])
def automation_identity(ctx, c):
    """Nerdio's Automation account has a system-assigned managed identity and runbooks for Scripted Actions."""
    acct, skipped = need(ctx, c, "automation")
    if skipped:
        return skipped
    info = ctx.az(["resource", "show", "--ids", acct["id"], "--query", "{identity:identity.type}"])
    runbooks = ctx.get(ctx.arm(f"{acct['id']}/runbooks?api-version=2023-11-01"))
    if info is None or runbooks is None:
        return c.no_access("can't read Nerdio's Automation account")
    if "SystemAssigned" not in (info.get("identity") or ""):
        return c.warn("Nerdio's Automation account has no system-assigned managed identity for Azure runbooks",
                      "Enable the system-assigned managed identity on Nerdio's Automation account")
    count = len(runbooks.get("value") or [])
    if not count:
        return c.warn("no runbooks found in Nerdio's Automation account",
                      "Link or recreate the Scripted Actions Automation account in Nerdio")
    return c.ok(f"Automation account has a system-assigned identity and {count} runbook(s)")


@check("auto.scaling", "Host pool session limits", needs="Reader on the subscription", kb=KB,
       stages=[WIZARD], features=["automation"],
       source="https://learn.microsoft.com/azure/virtual-desktop/autoscale-scenarios",
       reads=["ARM hostPools"])
def scaling(ctx, c):
    """Pooled host pools define a maxSessionLimit so session-based auto-scale can trigger."""
    pools, skipped = pools_or_skip(ctx, c)
    if skipped:
        return skipped
    unbounded = []
    for pool in pools:
        props = pool.get("properties") or {}
        if props.get("hostPoolType") == "Pooled" and int(props.get("maxSessionLimit") or 0) >= 999999:
            unbounded.append(ctx.name("hostpool", pool.get("name", "")))
    if unbounded:
        return c.warn("pooled host pool(s) with no session limit (maxSessionLimit is 999999): " + ", ".join(unbounded),
                      "Set Max sessions per host in Nerdio: host pool > Properties > Session limits")
    return c.ok(f"{len(pools)} host pool(s) checked for auto-scale session limits")
