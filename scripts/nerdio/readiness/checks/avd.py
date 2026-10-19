"""avd.*: session host size and vCPU quota."""

from __future__ import annotations

import math

from ..model import check

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
