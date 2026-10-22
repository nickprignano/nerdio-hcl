"""net.*: the AVD address range, the hub and private DNS."""

from __future__ import annotations

import ipaddress

from ..model import check

KB = "docs/knowledge/nerdio/readiness.md#network"
PEERING = "https://learn.microsoft.com/azure/virtual-network/virtual-network-peering-overview"
HUB_ROLES = {"Owner", "Contributor", "Network Contributor"}


def kit_groups(ctx) -> set:
    """Resource groups an earlier run of the kit made (tagged nerdio-kit-role), so their VNet and DNS zones aren't flagged."""
    def read():
        rows = ctx.az(["group", "list", "--query", "[?tags.\"nerdio-kit-role\"].name"])
        return {r.lower() for r in rows or [] if r}
    return ctx.cached("kit_groups", read)


def avd_range(ctx):
    try:
        return ipaddress.IPv4Network(ctx.values["address_space"])
    except (KeyError, ValueError, TypeError):
        return None


@check("net.overlap", "Address range", needs="Reader on the subscription", kb=KB, source=PEERING, inputs=["address_space"],
       reads=["az network vnet list", "az group list"])
def overlap(ctx, c):
    """The AVD address range against what's already in the subscription."""
    space = avd_range(ctx)
    if space is None:
        return c.warn("no valid address_space to check")
    own_vnet = f"vnet-{ctx.values.get('prefix', '')}-avd".lower()
    kit = kit_groups(ctx)
    hub_id = (ctx.values.get("hub_vnet_id") or "").strip()
    vnets = ctx.az(["network", "vnet", "list", "--query",
                    "[].{name:name, id:id, rg:resourceGroup, prefixes:addressSpace.addressPrefixes}"])
    if vnets is None:
        return c.warn("couldn't list the subscription's virtual networks to check for overlaps", "az network vnet list -o table")
    clashes = []
    for v in vnets:
        if ((v.get("name") or "").lower() == own_vnet or (v.get("rg") or "").lower() in kit
                or (hub_id and (v.get("id") or "").lower() == hub_id.lower())):
            continue
        for pfx in v.get("prefixes") or []:
            try:
                if space.overlaps(ipaddress.IPv4Network(pfx, strict=False)):
                    clashes.append(f"{ctx.name('vnet', v['name'])} ({pfx})")
            except ValueError:
                pass
    if clashes:
        return c.warn(f"{space} overlaps existing networks: " + ", ".join(clashes),
                      "Pick a free range if these networks are, or will be, peered or connected to the AVD network")
    return c.ok(f"{space} doesn't overlap the subscription's other virtual networks")


def ipv4_overlaps(space, prefix: str) -> bool:
    """False for IPv6 or malformed prefixes, which can't overlap an IPv4 range."""
    try:
        return space.overlaps(ipaddress.IPv4Network(prefix, strict=False))
    except ValueError:
        return False


@check("net.hub", "Hub network", needs="Reader on the hub VNet", kb=KB, inputs=["hub_vnet_id"], source=PEERING,
       reads=["az network vnet show", "az role assignment list"])
def hub(ctx, c):
    """The hub when peering: readable, no overlap, and rights to create the hub side of the peering."""
    space = avd_range(ctx)
    hub_id = ctx.values["hub_vnet_id"].strip()
    out = []
    data = ctx.az(["network", "vnet", "show", "--ids", hub_id, "--query", "{prefixes:addressSpace.addressPrefixes}"])
    if data is None:
        out.append(c.fail("can't read the hub VNet (wrong ID, another subscription you can't see, or no access)",
                          "Check hub_vnet_id, and ask for Network Contributor on the hub VNet"))
        return out
    bad = [p for p in data.get("prefixes") or [] if space and ipv4_overlaps(space, p)]
    if bad:
        out.append(c.fail(f"{space} overlaps the hub ({', '.join(bad)}); peering would be refused",
                          "Pick an address range outside the hub's"))
    else:
        out.append(c.ok("the hub VNet is readable and doesn't overlap the AVD range"))
    roles = ctx.roles_at(hub_id)
    if roles is None:
        out.append(c.warn("couldn't read your roles on the hub VNet", title="Hub peering rights"))
    elif HUB_ROLES & set(roles):
        out.append(c.ok("you can create the hub side of the peering", title="Hub peering rights"))
    else:
        out.append(c.fail("peering needs Network Contributor (or Contributor) on the hub VNet",
                          "Ask the hub's owner for Network Contributor on that VNet, or leave hub_vnet_id empty and peer later",
                          title="Hub peering rights"))
    return out


@check("net.private_dns", "Private DNS", needs="Reader on the private DNS zones' subscription", kb=KB,
       source="https://learn.microsoft.com/azure/private-link/private-endpoint-dns",
       reads=["az network private-dns zone list"])
def private_dns(ctx, c):
    zones = ctx.az(["network", "private-dns", "zone", "list", "--query", "[].{name:name, rg:resourceGroup}"])
    if zones is None:
        return c.skip("couldn't list private DNS zones")
    wanted = set(ctx.cloud.private_dns_zones())
    kit = kit_groups(ctx)
    own = f"rg-{ctx.values.get('prefix', '')}-".lower()
    found = sorted({f"{z['name']} ({ctx.name('rg', z.get('rg') or '')})" for z in zones if z.get("name") in wanted
                    and (z.get("rg") or "").lower() not in kit and not (z.get("rg") or "").lower().startswith(own)})
    if found:
        return c.warn("privatelink zones already exist elsewhere: " + ", ".join(found),
                      "If those are your central DNS zones, link the AVD VNet to them instead of using the kit's own zones")
    return c.ok("no privatelink zones outside the kit's own")


SUBNET_ROLES = (("hosts_subnet", "session host"), ("pe_subnet", "private endpoint"), ("app_subnet", "App Service integration"))


def subnet(ctx, name: str):
    vnet = ctx.values["vnet_id"]
    return ctx.cached(("subnet", name), lambda: ctx.az(["network", "vnet", "subnet", "show", "--ids", f"{vnet}/subnets/{name}"]))


@check("net.subnets", "Existing subnets", needs="Reader on the VNet", kb=KB, inputs=["vnet_id"], modes=["standalone"],
       source="https://learn.microsoft.com/azure/app-service/overview-vnet-integration#subnet-requirements",
       reads=["az network vnet subnet show"])
def subnets(ctx, c):
    """Into an existing VNet: the subnets exist, are /28 or bigger, and the App Service integration
    subnet is delegated to Microsoft.Web/serverFarms."""
    out = []
    for key, label in SUBNET_ROLES:
        name = ctx.values.get(key)
        if not name:
            out.append(c.skip(f"no {label} subnet given (--set {key}=<name>)"))
            continue
        shown = ctx.name("subnet", name)
        data = subnet(ctx, name)
        if data is None:
            out.append(c.fail(f"the {label} subnet {shown} doesn't exist in that VNet, or you can't read it",
                              "Check the name, or ask for Reader on the VNet"))
            continue
        prefixes = data.get("addressPrefixes") or [data.get("addressPrefix")]
        sizes = [ipaddress.IPv4Network(p, strict=False).prefixlen for p in prefixes if p]
        if sizes and min(sizes) > 28:
            out.append(c.fail(f"the {label} subnet {shown} is smaller than /28", "Use a /28 or larger subnet"))
            continue
        if key == "app_subnet":
            services = [d.get("serviceName") for d in data.get("delegations") or []]
            if services != ["Microsoft.Web/serverFarms"]:
                vnet = ctx.values["vnet_id"]
                out.append(c.fail(f"the App Service integration subnet {shown} must be delegated to "
                                  "Microsoft.Web/serverFarms" + (f" (it's delegated to {', '.join(services)})" if services else ""),
                                  f"az network vnet subnet update --ids {vnet}/subnets/{name} "
                                  "--delegations Microsoft.Web/serverFarms (printed, not run)"))
                continue
        out.append(c.ok(f"the {label} subnet {shown} exists" + (" and is delegated to App Service" if key == "app_subnet" else "")))
    return out


# VNets created after this date get no default outbound access (Microsoft's retirement notice).
DEFAULT_OUTBOUND_ENDS = "2026-03-31"


@check("net.outbound", "Outbound access", needs="Reader on the VNet", kb=KB, stages=["pre-install", "post-wizard"],
       source="https://learn.microsoft.com/azure/virtual-network/ip-services/default-outbound-access",
       reads=["az network vnet subnet show", "az network route-table show"])
def outbound(ctx, c):
    """Session hosts need an explicit way out: a NAT gateway, a firewall route or a load balancer."""
    if ctx.mode == "kit":
        if ctx.values.get("create_nat_gateway"):
            return c.ok("the kit creates a NAT gateway for the session host subnet")
        if ctx.values.get("hub_vnet_id"):
            return c.manual("no NAT gateway: outbound must go through the hub (a 0.0.0.0/0 route to its firewall)",
                            "Confirm the hub's route table covers the AVD subnets, or set create_nat_gateway=true")
        return c.warn("no NAT gateway and no hub: new VNets get no default outbound access, so session hosts can't "
                      "reach AVD", "./nerdio init --set create_nat_gateway=true")
    if not (ctx.values.get("vnet_id") and ctx.values.get("hosts_subnet")):
        return c.skip("needs input: vnet_id, hosts_subnet")
    data = subnet(ctx, ctx.values["hosts_subnet"])
    if data is None:
        return c.skip("the session host subnet couldn't be read (see Existing subnets)")
    if data.get("natGateway"):
        return c.ok("the session host subnet has a NAT gateway")
    route_table = (data.get("routeTable") or {}).get("id")
    if route_table:
        rt = ctx.az(["network", "route-table", "show", "--ids", route_table, "--query", "routes[].{prefix:addressPrefix, hop:nextHopType}"])
        if rt is None:
            return c.warn("couldn't read the subnet's route table")
        if any(r.get("prefix") == "0.0.0.0/0" and r.get("hop") in ("VirtualAppliance", "VirtualNetworkGateway") for r in rt):
            return c.ok("the session host subnet routes 0.0.0.0/0 to a firewall or gateway")
    if data.get("defaultOutboundAccess") is False:
        return c.fail("the session host subnet has no NAT gateway, no firewall route and no default outbound access, "
                      "so hosts can't reach AVD", "Add a NAT gateway: az network nat gateway create, then attach it to the subnet")
    return c.warn(f"the session host subnet relies on default outbound access, which VNets created after "
                  f"{DEFAULT_OUTBOUND_ENDS} don't get and Microsoft is retiring",
                  "Add a NAT gateway or a 0.0.0.0/0 route to your firewall")
