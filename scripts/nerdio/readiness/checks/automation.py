"""sa.* and auto.*: scripted actions and Nerdio's own automation (--features scripted-actions, automation)."""

from __future__ import annotations

import datetime as dt

from ..model import PRE, WIZARD, check
from .avd import vm_sku
from .hardening import public_access_off
from .nerdio import first, need, parse_time, resources

KB = "docs/knowledge/nerdio/readiness.md#scripted-actions-and-automation"
RUNBOOKS = "https://nmehelp.getnerdio.com/hc/en-us/articles/26124302308109"
AA_API = "2023-11-01"
SA = ["scripted-actions"]
WORKER_STALE_HOURS = 1


@check("sa.runbooks_enabled", "Azure runbook scripted actions", needs="Reader on Nerdio's resource group", kb=KB,
       stages=[WIZARD], features=SA, source=RUNBOOKS, reads=["ARM automationAccounts/runbooks"])
def runbooks_enabled(ctx, c):
    acct, skipped = need(ctx, c, "automation")
    if skipped:
        return skipped
    data = ctx.get(ctx.arm(f"{acct['id']}/runbooks?api-version={AA_API}"))
    if data is None:
        return c.no_access("can't read the Automation account's runbooks")
    names = [r.get("name", "") for r in data.get("value", [])]
    if len(names) <= 1:
        return c.warn("the Automation account has only Nerdio's updater; Azure runbook scripted actions look off",
                      "Turn them on in Nerdio: Settings > Integrations > Azure runbooks (no API)")
    return c.manual(f"{len(names)} runbooks; confirm in Nerdio that the subscriptions you script against are connected")


@check("sa.modules", "Automation modules", needs="Reader on Nerdio's resource group", kb=KB, stages=[WIZARD],
       features=SA, source=RUNBOOKS, reads=["ARM automationAccounts/modules"])
def modules(ctx, c):
    acct, skipped = need(ctx, c, "automation")
    if skipped:
        return skipped
    data = ctx.get(ctx.arm(f"{acct['id']}/modules?api-version={AA_API}"))
    if data is None:
        return c.no_access("can't read the Automation account's modules")
    failed = [m.get("name") for m in data.get("value", [])
              if (m.get("properties") or {}).get("provisioningState") == "Failed"]
    if failed:
        return c.fail("modules failed to import: " + ", ".join(failed),
                      "Update them in Nerdio: Settings > Azure runbooks > Manage Module Versions")
    accounts = next((m for m in data.get("value", []) if m.get("name") == "Az.Accounts"), None)
    version = ((accounts or {}).get("properties") or {}).get("version")
    return c.ok(f"{len(data.get('value', []))} modules imported" + (f"; Az.Accounts {version}" if version else ""))


def hybrid_groups(ctx, acct):
    return ctx.cached(("hybrid", acct["id"]), lambda: ctx.get(
        ctx.arm(f"{acct['id']}/hybridRunbookWorkerGroups?api-version={AA_API}")))


@check("sa.mode_vs_network", "Scripted actions and storage", needs="Reader on Nerdio's resource group", kb=KB,
       stages=[WIZARD], features=SA, source=RUNBOOKS,
       reads=["az resource show", "ARM automationAccounts/hybridRunbookWorkerGroups"])
def mode_vs_network(ctx, c):
    """Storage mode can't read private storage without a hybrid worker; inline mode can't run
    scripts over 500 KB. Which mode is set has no API, so the mode itself is `manual`."""
    res = resources(ctx)
    acct = first(ctx, "automation")
    if res is None or not acct:
        return c.skip("needs Nerdio's resource group with its Automation account")
    states = [public_access_off(ctx, st) for st in res.get("storage", [])]
    groups = hybrid_groups(ctx, acct)
    if None in states or groups is None:
        return c.no_access("can't read Nerdio's storage or hybrid worker groups")
    if any(states) and not groups.get("value"):
        return c.warn("Nerdio's storage is private and there's no hybrid worker: storage-mode scripted actions will fail",
                      "Use inline mode (scripts up to 500 KB) or add a hybrid worker group in the VNet")
    return c.manual("confirm the scripted-action mode: storage mode needs the storage reachable, inline mode keeps "
                    "each script under 500 KB")


@check("sa.hybrid_worker", "Hybrid workers", needs="Reader on Nerdio's resource group, Key Vault Reader", kb=KB,
       stages=[WIZARD], features=SA, source="https://learn.microsoft.com/azure/automation/automation-hybrid-runbook-worker",
       reads=["ARM hybridRunbookWorkerGroups/hybridRunbookWorkers", "az keyvault certificate list"])
def hybrid_worker(ctx, c):
    acct = first(ctx, "automation")
    if resources(ctx) is None or not acct:
        return c.skip("needs Nerdio's resource group with its Automation account")
    groups = hybrid_groups(ctx, acct)
    if groups is None:
        return c.no_access("can't read the hybrid worker groups")
    if not groups.get("value"):
        return c.skip("no hybrid worker groups")
    out, now = [], dt.datetime.now(dt.timezone.utc)
    for g in groups["value"]:
        workers = ctx.get(ctx.arm(f"{g['id']}/hybridRunbookWorkers?api-version={AA_API}"))
        if workers is None:
            return c.no_access("can't read the hybrid workers")
        online = 0
        for w in workers.get("value", []):
            when = parse_time((w.get("properties") or {}).get("lastSeenDateTime"))
            if when and (now - when).total_seconds() < WORKER_STALE_HOURS * 3600:
                online += 1
        if not online:
            out.append(c.fail(f"no worker in {ctx.name('workers', g.get('name', ''))} has checked in for an hour",
                              "Check the worker VMs are running and their Hybrid Worker extension is healthy"))
    kv = first(ctx, "key_vault")
    if kv and ctx.az(["keyvault", "certificate", "list", "--vault-name", kv["name"], "--query", "[].name"]) is None:
        out.append(c.no_access("you can't list certificates in Nerdio's vault, which installing the worker certificate needs",
                               "Key Vault Reader (list) and Key Vault Certificate User (get) on Nerdio's vault"))
    out.append(c.manual("confirm Nerdio's scripted-action certificate is installed on each worker", title="Worker certificate"))
    return out


@check("sa.windows", "Windows scripted actions", needs="none", kb=KB, stages=[PRE], features=SA, account=False,
       source="https://learn.microsoft.com/azure/virtual-machines/extensions/custom-script-windows")
def windows(ctx, c):
    return c.manual("Windows scripted actions use the Custom Script Extension: confirm no Azure Policy denies it "
                    "(see Policy evaluation) and the scripted-actions storage is reachable from the host subnets")


@check("auto.backup", "Backup", needs="Reader on the subscription", kb=KB, stages=[PRE, WIZARD], features=["automation"],
       inputs=["location"], source="https://learn.microsoft.com/azure/backup/backup-azure-vms-introduction",
       reads=["az provider show", "az backup vault list"])
def backup(ctx, c):
    state = ctx.az(["provider", "show", "-n", "Microsoft.RecoveryServices", "--query", "registrationState"])
    if state is None:
        return c.warn("couldn't read Microsoft.RecoveryServices' registration")
    if state != "Registered":
        return c.fail("Microsoft.RecoveryServices isn't registered", "az provider register -n Microsoft.RecoveryServices")
    if ctx.stage == PRE:
        return c.ok("Microsoft.RecoveryServices is registered")
    vaults = ctx.az(["backup", "vault", "list", "--query", "[].location"])
    if vaults is None:
        return c.no_access("can't list Recovery Services vaults")
    location = ctx.values["location"].lower()
    if location not in [v.lower() for v in vaults]:
        return c.warn(f"no Recovery Services vault in {location}; Nerdio's backup features need one there",
                      "Create one when you turn on backup in Nerdio")
    return c.ok(f"a Recovery Services vault is in {location}")


@check("auto.image_mgmt", "Image management", needs="Reader on the subscription", kb=KB, stages=[PRE],
       features=["automation"], inputs=["location", "vm_size"], source="https://learn.microsoft.com/azure/virtual-machines/shared-image-galleries",
       reads=["az sig list", "az vm list-usage"])
def image_mgmt(ctx, c):
    """Nerdio builds images on a temporary VM, and the kit's Packer build needs a Compute Gallery."""
    out = []
    if ctx.values.get("image_gallery_enabled") is not False:
        galleries = ctx.az(["sig", "list", "--query", "[].name"])
        name = ctx.values.get("gallery_name")
        if galleries is None:
            out.append(c.warn("couldn't list Compute Galleries"))
        elif (name and name in galleries) or (not name and galleries):
            out.append(c.ok("a Compute Gallery is there"))
        else:
            out.append(c.ok("no Compute Gallery yet; the kit or Nerdio creates one"))
    sku = vm_sku(ctx)
    usage = ctx.az(["vm", "list-usage", "-l", ctx.values["location"]])
    if sku and usage is not None:
        vcpus = int({x["name"]: x["value"] for x in sku.get("capabilities", [])}.get("vCPUs", "0") or 0)
        row = next((u for u in usage if u.get("name", {}).get("value") == sku.get("family")), None)
        if row and int(row["limit"]) - int(row["currentValue"]) < vcpus:
            out.append(c.fail(f"no {sku.get('family')} quota left for an image-build VM ({vcpus} vCPUs)",
                              f"./nerdio fix vcpu --family {sku.get('family')} --limit {int(row['limit']) + vcpus}"))
    return out or [c.ok("image builds have a gallery and quota")]
