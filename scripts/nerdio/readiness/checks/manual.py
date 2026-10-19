"""Things only a person can confirm: licenses and domain reachability."""

from __future__ import annotations

from ..model import check

AVD_PREREQS = "https://learn.microsoft.com/azure/virtual-desktop/prerequisites"


@check("sub.nerdio_license", "Nerdio license", needs="none", kb="docs/knowledge/nerdio/platform.md#marketplace-deployment",
       account=False, source="https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps")
def nerdio_license(ctx, c):
    return c.manual("Nerdio Manager is licensed through its own Marketplace offer; confirm you have one or a trial",
                    "https://getnerdio.com")


@check("avd.licenses", "AVD user licenses", needs="none", kb="docs/knowledge/nerdio/readiness.md#avd", account=False,
       source=AVD_PREREQS)
def avd_licenses(ctx, c):
    return c.manual("Users need an eligible license (Microsoft 365 E3/E5, Business Premium and others; check the current list)",
                    AVD_PREREQS)


@check("id.domain_join_account", "Domain reachability", needs="nothing in Azure; a person confirms it", kb="docs/knowledge/nerdio/readiness.md#identity",
       account=False, inputs=["identity_model"], source=AVD_PREREQS)
def domain_reachability(ctx, c):
    if ctx.values.get("identity_model") not in ("entra_ds", "ad_ds"):
        return c.skip("Entra-joined hosts don't join a domain")
    return c.manual("session hosts must reach the DNS servers and domain controllers from the AVD network",
                    "Peer to the hub or connect the VNet before deploying")
