"""id.*: the installer's Azure and Entra rights."""

from __future__ import annotations

from ..model import check

ROLES_KB = "docs/knowledge/nerdio/platform.md#roles-needed"
NERDIO_PREP = "https://nmehelp.getnerdio.com/hc/en-us/articles/44411071090317-Nerdio-Manager-Installation-Preparation-Steps"

GLOBAL_ADMIN = "Global Administrator"
CONSENT_PAIR = {"Privileged Role Administrator", "Cloud Application Administrator"}
# Roles that can create app registrations even when the tenant blocks users from doing so.
APP_CREATORS = {GLOBAL_ADMIN, "Application Administrator", "Cloud Application Administrator", "Application Developer"}
# Owner, or Contributor plus one of these, can create the resources and the role assignments the kit makes.
RBAC_WRITERS = {"User Access Administrator", "Role Based Access Control Administrator"}



def list_my_roles(ctx) -> str:
    return (f"az rest --url '{ctx.graph('/me/transitiveMemberOf/microsoft.graph.directoryRole')}' "
            "--query 'value[].displayName'")


def read_app_policy(ctx) -> str:
    return (f"az rest --url '{ctx.graph('/policies/authorizationPolicy')}' "
            "--query defaultUserRolePermissions.allowedToCreateApps")


@check("id.sub_owner", "Subscription Owner", needs="Reader on the subscription", kb=ROLES_KB, source=NERDIO_PREP,
       reads=["az ad signed-in-user show", "az role assignment list"])
def subscription_owner(ctx, c):
    if not ctx.is_user:
        return c.manual("signed in as a service principal; check its roles by hand")
    if not ctx.me_id():
        return c.warn("couldn't read the signed-in user's object ID", "az ad signed-in-user show")
    roles = ctx.roles_at(f"/subscriptions/{ctx.subscription_id}")
    if roles is None:
        return c.warn("couldn't list role assignments", "az role assignment list --assignee <you> --all")
    ctx.rights |= set(roles)
    if "Owner" in roles:
        return c.ok("Owner on the subscription")
    if "Contributor" in roles and RBAC_WRITERS & set(roles):
        return c.ok("Contributor plus a role that can assign roles, which covers what the kit needs")
    return c.fail("Owner is needed on the subscription (found: " + (", ".join(sorted(set(roles))) or "none") + ")",
                  "./nerdio fix roles if Owner is eligible in PIM; otherwise ask a subscription Owner to assign it")


@check("id.entra_roles", "Entra admin role", needs="your own default directory read rights", kb=ROLES_KB,
       source=NERDIO_PREP, reads=["Graph /me/transitiveMemberOf"])
def entra_roles(ctx, c):
    v = ctx.values
    if not (bool(v.get("create_entra_app")) and bool(v.get("grant_admin_consent"))):
        return c.ok("not needed (admin consent is off, so the wizard asks an admin instead)")
    if not ctx.is_user:
        return c.manual("signed in as a service principal; it needs Graph app-role grant rights",
                        kb="docs/knowledge/nerdio/entra-app.md")
    roles = ctx.directory_roles()
    if roles is None:
        return c.warn("couldn't read your directory roles from Microsoft Graph", list_my_roles(ctx))
    if GLOBAL_ADMIN in roles or CONSENT_PAIR <= roles:
        return c.ok("can grant admin consent")
    return c.fail("admin consent needs Global Administrator, or Privileged Role Administrator plus Cloud Application "
                  "Administrator (active roles only; PIM-eligible roles must be activated first)",
                  "./nerdio fix roles (activates eligible PIM roles), or answer no to admin consent and let a Global "
                  "Admin grant it in the wizard")


@check("id.app_registration", "App registration", needs="your own default directory read rights", kb=ROLES_KB,
       source="https://learn.microsoft.com/graph/api/resources/authorizationpolicy",
       reads=["Graph /me/transitiveMemberOf", "Graph /policies/authorizationPolicy"])
def app_registration(ctx, c):
    """The kit creates the nerdio-nmw-app registration; many tenants stop ordinary users doing that."""
    if not ctx.values.get("create_entra_app"):
        return c.ok("not needed (the kit isn't creating the Entra app)")
    if not ctx.is_user:
        return c.manual("signed in as a service principal; it needs Application.ReadWrite.OwnedBy or an admin role")
    roles = ctx.directory_roles()
    if roles is not None and APP_CREATORS & roles:
        return c.ok("your directory role can create app registrations")
    policy = ctx.get(ctx.graph("/policies/authorizationPolicy?$select=defaultUserRolePermissions"))
    if policy is None:
        return c.warn("couldn't read the tenant's app registration policy", read_app_policy(ctx))
    if policy.get("defaultUserRolePermissions", {}).get("allowedToCreateApps"):
        return c.ok("the tenant lets users register applications")
    return c.fail("this tenant doesn't let users register applications, and you have no active role that can",
                  "./nerdio fix roles (activates eligible PIM roles), then az login again")
