"""rbac.* and self.*: who can use Nerdio Manager, through its app roles (--features rbac, self-service)."""

from __future__ import annotations

from ..model import PRE, WIZARD, check
from .nerdio import graph_list, nerdio_app

KB = "docs/knowledge/nerdio/entra-app.md"
RBAC_DOC = "https://nmehelp.getnerdio.com/hc/en-us/articles/26124313324173"
OTHER_ROLES = ("DesktopAdmin", "HelpDesk", "Reviewer", "EndUser")


def holders(ctx):
    """{role value: [assignments]} for Nerdio's app roles; {} with no app; None when unreadable."""
    def read():
        found = nerdio_app(ctx)
        if found is None:
            return None
        if not found or not found.get("sp"):
            return {}
        names = {r.get("id"): r.get("value") for r in found["sp"].get("appRoles") or []}
        rows = graph_list(ctx, f"/servicePrincipals/{found['sp']['id']}/appRoleAssignedTo")
        if rows is None:
            return None
        out = {}
        for r in rows:
            out.setdefault(names.get(r.get("appRoleId"), "?"), []).append(r)
        return out
    return ctx.cached("nerdio_role_holders", read)


def holders_or_skip(ctx, c):
    found = holders(ctx)
    if found is None:
        return None, c.no_access("can't read who holds Nerdio's roles")
    if not (nerdio_app(ctx) or {}).get("sp"):
        return None, c.skip("needs Nerdio's service principal (see Nerdio's Entra app)")
    return found, None


@check("rbac.admins", "Nerdio admins", needs="Directory Readers", kb=KB, stages=[WIZARD], features=["rbac"],
       source=RBAC_DOC, reads=["Graph /servicePrincipals/{id}/appRoleAssignedTo"])
def admins(ctx, c):
    """At least two holders of the Admin role (WvdAdmin), one of them a person assigned directly:
    Entra gives the enterprise app's owner role only to directly assigned users, not to groups."""
    found, skipped = holders_or_skip(ctx, c)
    if skipped:
        return skipped
    rows = found.get("WvdAdmin", [])
    if not any(r.get("principalType") == "User" for r in rows):
        return c.fail("no person is assigned Nerdio's Admin role directly (a group alone isn't enough)",
                      "Assign at least one admin directly to the WvdAdmin role on Nerdio's enterprise app")
    if len(rows) < 2:
        return c.warn("only one Admin assignment; keep a second (break-glass) admin",
                      "Assign a second admin to the WvdAdmin role")
    return c.ok(f"{len(rows)} Admin assignments, at least one direct")


@check("rbac.groups", "Nerdio role groups", needs="Directory Readers", kb=KB, stages=[WIZARD], features=["rbac"],
       source=RBAC_DOC, reads=["Graph /servicePrincipals/{id}/appRoleAssignedTo", "Graph /groups/{id}/members"])
def groups(ctx, c):
    """Desktop Admin, Help Desk, Reviewer and End User go to groups that exist and aren't empty."""
    found, skipped = holders_or_skip(ctx, c)
    if skipped:
        return skipped
    out, unused = [], []
    for role in OTHER_ROLES:
        rows = [r for r in found.get(role, []) if r.get("principalType") == "Group"]
        if not rows:
            unused.append(role)
            continue
        for r in rows:
            members = graph_list(ctx, f"/groups/{r.get('principalId')}/members?$top=1&$select=id")
            if members is None:
                out.append(c.no_access(f"can't read the members of the group holding {role}"))
            elif not members:
                out.append(c.warn(f"the group holding {role} is empty"))
    if unused:
        out.append(c.warn("no group holds " + ", ".join(unused) + "; assign groups so access follows membership",
                          "Assign a group to each role on Nerdio's enterprise app"))
    return out or [c.ok("every Nerdio role is held by a group with members")]


@check("rbac.azure_side", "Azure rights for Nerdio admins", needs="Reader on the subscription", kb=KB, stages=[PRE],
       features=["rbac"], source=RBAC_DOC, reads=["az role assignment list"])
def azure_side(ctx, c):
    """Nerdio's admins also need Azure roles for some actions: Owner on a resource group to link
    it, Owner or User Access Administrator on a VNet's group to link the network."""
    sub = f"/subscriptions/{ctx.subscription_id}"
    roles = ctx.roles_at(sub) if ctx.is_user else None
    if roles is None:
        return c.manual("confirm the people who link resource groups and networks in Nerdio hold Owner on those "
                        "groups, and Owner or User Access Administrator on the network's group")
    if "Owner" in roles:
        return c.ok("you hold Owner on the subscription, which covers linking groups and networks")
    return c.manual("you don't hold Owner on the subscription; whoever links resource groups and networks in Nerdio "
                    "needs Owner on those groups, and Owner or User Access Administrator on the network's group")


@check("self.end_user_role", "Self-service users", needs="Directory Readers", kb=KB, stages=[WIZARD],
       features=["self-service"], source=RBAC_DOC, reads=["Graph /servicePrincipals/{id}/appRoleAssignedTo"])
def end_user_role(ctx, c):
    found, skipped = holders_or_skip(ctx, c)
    if skipped:
        return skipped
    if not found.get("EndUser"):
        return c.fail("nobody holds Nerdio's End User role, so the self-service portal has no users",
                      "Assign the AVD users' group to the EndUser role on Nerdio's enterprise app")
    return c.ok(f"{len(found['EndUser'])} principals hold the End User role")


@check("self.consent", "Self-service sign-in", needs="Directory Readers", kb=KB, stages=[WIZARD],
       features=["self-service"], source="https://learn.microsoft.com/entra/identity/enterprise-apps/what-is-access-management",
       reads=["Graph /servicePrincipals", "Graph /oauth2PermissionGrants"])
def consent(ctx, c):
    """End users can sign in: the app is enabled, and its delegated permissions have tenant-wide
    consent so people aren't asked to consent themselves. Conditional Access is `manual`."""
    found = nerdio_app(ctx)
    if found is None:
        return c.no_access("can't read Nerdio's service principal")
    if not found or not found.get("sp"):
        return c.skip("needs Nerdio's service principal")
    sp = found["sp"]
    if sp.get("accountEnabled") is False:
        return c.fail("Nerdio Manager's enterprise app is disabled for sign-in", "Enable it on the enterprise app")
    grants = graph_list(ctx, f"/oauth2PermissionGrants?$filter=clientId eq '{sp['id']}'")
    if grants is None:
        return c.no_access("can't read the app's consent grants")
    if not any(g.get("consentType") == "AllPrincipals" for g in grants):
        return c.fail("users would be asked to consent to Nerdio Manager themselves",
                      "Grant tenant-wide consent (the wizard's second consent)")
    return c.manual("the app is enabled and consented; confirm Conditional Access lets end users reach it")
