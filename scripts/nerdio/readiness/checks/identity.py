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
    rows = ctx.assignments_at(f"/subscriptions/{ctx.subscription_id}")
    if rows is None:
        return c.warn("couldn't list role assignments", "az role assignment list --assignee <you> --all")
    roles = {r["role"] for r in rows}
    ctx.rights |= roles
    free = {r["role"] for r in rows if not r.get("condition")}
    if "Owner" in free:
        return c.ok("Owner on the subscription")
    if "Contributor" in roles and RBAC_WRITERS & free:
        return c.ok("Contributor plus a role that can assign roles, which covers what the kit needs")
    # A condition (the portal's default "all roles except privileged") blocks the role
    # assignments Nerdio and the kit make (docs/access.md), so it isn't a pass.
    if "Owner" in roles or ("Contributor" in roles and RBAC_WRITERS & roles):
        return c.warn("your Owner or role-assigning role carries a condition, which can block the role assignments "
                      "Nerdio's install and the kit make (the subscription's Reader, Backup Reader and Contributor grants)",
                      "Ask for an assignment whose condition allows the roles in docs/access.md, or one without a condition")
    return c.fail("Owner is needed on the subscription (found: " + (", ".join(sorted(roles)) or "none") + ")",
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


@check("id.pim_eligible", "PIM roles", needs="your own PIM eligibility (read)", kb=ROLES_KB,
       source="https://learn.microsoft.com/rest/api/authorization/role-eligibility-schedule-instances/list-for-scope",
       reads=["ARM roleEligibilityScheduleInstances asTarget()", "Graph roleEligibilityScheduleInstances"])
def pim_eligible(ctx, c):
    """A role that's eligible but not active is a guaranteed failure at install or apply time."""
    if not ctx.is_user:
        return c.skip("service principals don't use PIM")
    roles = ctx.roles_at(f"/subscriptions/{ctx.subscription_id}") or []
    active_dir = ctx.directory_roles() or set()
    wanted_dir = set() if GLOBAL_ADMIN in active_dir else (CONSENT_PAIR - active_dir)
    out, eligible = [], []
    if "Owner" not in roles:
        rows = ctx.get(ctx.arm(f"/subscriptions/{ctx.subscription_id}/providers/Microsoft.Authorization"
                               "/roleEligibilityScheduleInstances?api-version=2020-10-01&$filter=asTarget()"))
        if rows is None:
            out.append(c.no_access("couldn't read your Azure PIM eligibility", "./nerdio fix roles reads it with your sign-in",
                                   title="PIM roles (Azure)"))
        else:
            names = {r.get("properties", {}).get("expandedProperties", {}).get("roleDefinition", {}).get("displayName")
                     for r in rows.get("value", [])}
            eligible += sorted(n for n in names & {"Owner", "Role Based Access Control Administrator",
                                                    "User Access Administrator"} if n)
    if wanted_dir:
        me = ctx.me_id()
        rows = ctx.get(ctx.graph(f"/roleManagement/directory/roleEligibilityScheduleInstances?$filter=principalId eq '{me}'"
                                 "&$expand=roleDefinition")) if me else None
        if rows is None:
            # The az CLI's Graph token usually lacks RoleManagement scopes, whatever role you hold.
            out.append(c.no_access("az's Graph token can't read Entra PIM eligibility in most tenants",
                                   "./nerdio fix roles checks it with its own Graph sign-in", title="PIM roles (Entra)"))
        else:
            names = {(r.get("roleDefinition") or {}).get("displayName") for r in rows.get("value", [])
                     if r.get("directoryScopeId") == "/"}
            eligible += sorted(n for n in names & (wanted_dir | {GLOBAL_ADMIN}) if n)
    if eligible:
        out.insert(0, c.warn("eligible in PIM but not active: " + ", ".join(eligible)
                             + " (the install and an apply fail until they are)", "./nerdio fix roles, then az login again"))
    elif not out:
        out.append(c.ok("nothing the install needs is waiting on PIM activation"))
    return out


@check("id.tenant_match", "Home tenant", needs="your own default directory read rights", kb=ROLES_KB,
       source="https://learn.microsoft.com/entra/external-id/user-properties",
       reads=["az account show", "Graph /me"], stages=["pre-install", "post-install", "post-wizard"])
def tenant_match(ctx, c):
    """Guests (B2B) and accounts signed in to a tenant other than their home one hit consent and app
    registration limits that members don't."""
    acct = ctx.acct or {}
    home, tenant = acct.get("homeTenantId"), acct.get("tenantId")
    if not ctx.is_user:
        return c.skip("signed in as a service principal")
    me = ctx.get(ctx.graph("/me?$select=userType"))
    guest = (me or {}).get("userType") == "Guest"
    if (home and tenant and home != tenant) or guest:
        return c.warn("you're signed in as a guest in this tenant; guests often can't register apps or grant consent, "
                      "and Nerdio's install should run as a member of the tenant",
                      "Sign in with an account from this tenant: az login --tenant <tenant>")
    if me is None and not home:
        return c.warn("couldn't tell whether you're a member or a guest here")
    return c.ok("signed in as a member of the subscription's tenant")


@check("id.leftover_app", "Earlier Nerdio app", needs="your own default directory read rights",
       kb="docs/knowledge/nerdio/entra-app.md", source=NERDIO_PREP, reads=["Graph /applications"])
def leftover_app(ctx, c):
    rows = ctx.get(ctx.graph("/applications?$filter=startswith(displayName,'nerdio-nmw-app')&$select=displayName,createdDateTime"))
    if rows is None:
        return c.warn("couldn't list app registrations to look for an earlier Nerdio install")
    found = rows.get("value", [])
    if not found:
        return c.ok("no nerdio-nmw-app registration from an earlier install")
    when = ", ".join(sorted((a.get("createdDateTime") or "?")[:10] for a in found))
    return c.warn(f"{len(found)} nerdio-nmw-app registration(s) already exist (created {when}); a new install makes "
                  "another one unless you reuse it",
                  "If it's left from a removed install (not this kit's own), delete it: az ad app list --display-name "
                  "nerdio-nmw-app --query '[].appId', then az ad app delete --id <appId>")
