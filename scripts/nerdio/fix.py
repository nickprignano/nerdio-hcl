"""Fixes for preflight failures that need a request rather than code: quota and role activation.

Both run from Cloud Shell with the signed-in az account, so nobody has to click through the
portal. Each shows exactly what it will send and changes nothing until the person types yes.
The portal path is printed only if the API refuses.

  ./nerdio fix quota     open an App Service quota request with Azure Support
  ./nerdio fix vcpu      raise a VM family's vCPU quota through the Azure Quota API
  ./nerdio fix roles     activate the Entra and Azure roles you're eligible for in PIM
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import uuid

SUPPORT_API = "2024-04-01"
PIM_ARM_API = "2020-10-01"
QUOTA_API = "2023-02-01"
ARM = "https://management.azure.com"
GRAPH = "https://graph.microsoft.com/v1.0"
QUOTA_SERVICE = "service and subscription limits (quotas)"
TICKET_PREFIX = "Nerdio kit:"
# usageLocation in Entra is ISO 3166-1 alpha-2; Azure Support wants alpha-3.
COUNTRIES = {"US": "USA", "CA": "CAN", "GB": "GBR", "IE": "IRL", "AU": "AUS", "NZ": "NZL", "DE": "DEU",
             "FR": "FRA", "NL": "NLD", "BE": "BEL", "ES": "ESP", "IT": "ITA", "SE": "SWE", "NO": "NOR",
             "DK": "DNK", "FI": "FIN", "CH": "CHE", "AT": "AUT", "IN": "IND", "SG": "SGP", "JP": "JPN",
             "ZA": "ZAF", "BR": "BRA", "MX": "MEX"}
ENTRA_NEEDED = ["Cloud Application Administrator", "Privileged Role Administrator"]
GLOBAL_ADMIN = "Global Administrator"


class FixError(Exception):
    pass


def az(args: list[str]):
    """Run az and return parsed JSON; raise FixError with az's own message on failure."""
    try:
        res = subprocess.run(["az", *args, "-o", "json"], capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise FixError("az isn't installed; run this from Azure Cloud Shell") from exc
    if res.returncode != 0:
        msg = res.stderr.strip().splitlines()
        raise FixError(msg[-1] if msg else f"az {' '.join(args[:2])} failed")
    out = res.stdout.strip()
    return json.loads(out) if out else None


def rest(method: str, url: str, body: dict | None = None):
    args = ["rest", "--method", method, "--url", url]
    if body is not None:
        args += ["--body", json.dumps(body), "--headers", "Content-Type=application/json"]
    return az(args)


def confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    try:
        return input(f"{prompt} Type yes to go ahead: ").strip().lower() == "yes"
    except EOFError:
        return False


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# --- App Service quota ---------------------------------------------------------------------------

def pick_classification(rows: list[dict]) -> dict | None:
    """The quota service's classification for App Service. Names vary, so match loosely."""
    for want in ("app service", "web app"):
        for r in rows:
            if want in (r.get("properties", {}).get("displayName") or r.get("displayName") or "").lower():
                return r
    return None


def contact_from_me(me: dict, country: str | None, timezone: str) -> dict:
    code = country or COUNTRIES.get((me.get("usageLocation") or "").upper())
    if not code:
        raise FixError("couldn't work out your country for the support contact; pass --country with a "
                       "3-letter code, e.g. --country USA")
    email = me.get("mail") or me.get("userPrincipalName")
    if not email or "#EXT#" in email:
        raise FixError("your account has no usable email for Azure Support to reply to; pass --email")
    return {
        "firstName": me.get("givenName") or email.split("@")[0],
        "lastName": me.get("surname") or "-",
        "preferredContactMethod": "email",
        "primaryEmailAddress": email,
        "preferredTimeZone": timezone,
        "country": code.upper(),
        "preferredSupportLanguage": "en-US",
    }


def quota_ticket(service_id: str, classification_id: str, contact: dict, sku: str, location: str,
                 limit: int, current: str) -> dict:
    return {"properties": {
        "title": f"{TICKET_PREFIX} App Service {sku} quota in {location}",
        "description": (f"Please raise this subscription's App Service quota for {sku} (Windows) in {location} "
                        f"to {limit}. The current limit is {current}. It is needed for one App Service plan that "
                        "hosts Nerdio Manager for Enterprise. Opened by the nerdio-hcl kit's ./nerdio fix quota."),
        "serviceId": service_id,
        "problemClassificationId": classification_id,
        "severity": "minimal",
        "advancedDiagnosticConsent": "No",
        "contactDetails": contact,
    }}


def fix_quota(subscription_id: str, location: str, sku: str, limit: int, country: str | None,
              email: str | None, timezone: str, assume_yes: bool) -> int:
    services = rest("get", f"{ARM}/providers/Microsoft.Support/services?api-version={SUPPORT_API}") or {}
    svc = next((s for s in services.get("value", [])
                if (s.get("properties", {}).get("displayName") or "").lower() == QUOTA_SERVICE), None)
    if not svc:
        raise FixError("Azure Support didn't list the quota service for this account")
    classes = rest("get", f"{ARM}{svc['id']}/problemClassifications?api-version={SUPPORT_API}") or {}
    pc = pick_classification(classes.get("value", []))
    if not pc:
        names = sorted(c.get("properties", {}).get("displayName", "") for c in classes.get("value", []))
        raise FixError("no App Service entry under the quota service; it lists: " + ", ".join(names))
    me = rest("get", f"{GRAPH}/me?$select=givenName,surname,mail,userPrincipalName,usageLocation") or {}
    if email:
        me["mail"] = email
    contact = contact_from_me(me, country, timezone)
    current = "unknown"
    try:
        usages = rest("get", f"{ARM}/subscriptions/{subscription_id}/providers/Microsoft.Web/locations/{location}"
                             f"/usages?api-version=2024-11-01") or {}
        row = next((u for u in usages.get("value", []) if sku.lower() in json.dumps(u.get("name", {})).lower()), None)
        if row:
            current = str(row.get("limit"))
    except FixError:
        pass
    body = quota_ticket(svc["id"], pc["id"], contact, sku, location, limit, current)
    p = body["properties"]
    print(f"Azure Support request for subscription {subscription_id[:8]}...:\n"
          f"  {p['title']}\n  {p['description']}\n"
          f"  Replies go to {contact['primaryEmailAddress']} (severity: minimal; no support plan needed for quota).")
    if not confirm("Open this request?", assume_yes):
        print("Nothing sent.")
        return 1
    name = f"nerdio-kit-quota-{dt.datetime.now(dt.timezone.utc):%Y%m%d%H%M%S}"
    url = f"{ARM}/subscriptions/{subscription_id}/providers/Microsoft.Support/supportTickets/{name}?api-version={SUPPORT_API}"
    try:
        made = rest("put", url, body) or {}
    except FixError as exc:
        raise FixError(f"Azure Support refused the request: {exc}\n  Last resort, in the portal: Help + support > "
                       f"Create a support request > Service and subscription limits (quotas) > App Service, "
                       f"{sku} (Windows) in {location}, new limit {limit}") from exc
    number = made.get("properties", {}).get("supportTicketId", name)
    print(f"Opened support request {number}. Check it with: ./nerdio fix quota --status")
    return 0


def quota_status(subscription_id: str) -> int:
    rows = rest("get", f"{ARM}/subscriptions/{subscription_id}/providers/Microsoft.Support/supportTickets"
                       f"?api-version={SUPPORT_API}") or {}
    mine = [r["properties"] for r in rows.get("value", []) if (r.get("properties", {}).get("title") or "").startswith(TICKET_PREFIX)]
    if not mine:
        print("No quota requests opened by the kit on this subscription.")
    for t in mine:
        print(f"{t.get('supportTicketId')}  {t.get('status')}  {t.get('title')}")
    return 0


# --- VM vCPU quota (Azure Quota API; usually approved in minutes, no ticket) ----------------------

def fix_vcpu(subscription_id: str, location: str, family: str, limit: int, assume_yes: bool) -> int:
    scope = f"{ARM}/subscriptions/{subscription_id}/providers/Microsoft.Compute/locations/{location}"
    url = f"{scope}/providers/Microsoft.Quota/quotas/{family}?api-version={QUOTA_API}"
    try:
        current = (rest("get", url) or {}).get("properties", {}).get("limit", {}).get("value", "unknown")
    except FixError:
        current = "unknown"
    print(f"Raise {family} vCPU quota in {location} from {current} to {limit} (Azure Quota API).")
    if not confirm("Send this quota request?", assume_yes):
        print("Nothing sent.")
        return 1
    body = {"properties": {"limit": {"limitObjectType": "LimitValue", "value": limit}, "name": {"value": family}}}
    try:
        rest("put", url, body)
    except FixError as exc:
        raise FixError(f"the Quota API refused it: {exc}\n  Last resort, in the portal: Quotas > Compute, "
                       f"{family} in {location}, new limit {limit}") from exc
    print("Requested. Most increases apply within minutes; rerun ./nerdio preflight to check.")
    return 0


# --- PIM role activation -------------------------------------------------------------------------

def entra_plan(active: set[str], eligible: dict[str, str], needs_consent: bool) -> list[tuple[str, str]]:
    """Which eligible Entra roles to activate: the specific roles first, Global Admin only as a fallback."""
    needed = ENTRA_NEEDED if needs_consent else ENTRA_NEEDED[:1]
    if GLOBAL_ADMIN in active or set(needed) <= active:
        return []
    missing = [r for r in needed if r not in active]
    if all(r in eligible for r in missing):
        return [(r, eligible[r]) for r in missing]
    if GLOBAL_ADMIN in eligible:
        return [(GLOBAL_ADMIN, eligible[GLOBAL_ADMIN])]
    return [(r, eligible[r]) for r in missing if r in eligible]


def fix_roles(subscription_id: str, needs_consent: bool, hours: int, assume_yes: bool) -> int:
    me = az(["ad", "signed-in-user", "show", "--query", "id"])
    roles = rest("get", f"{GRAPH}/me/transitiveMemberOf/microsoft.graph.directoryRole?$select=displayName") or {}
    active = {r.get("displayName") for r in roles.get("value", [])}
    elig = rest("get", f"{GRAPH}/roleManagement/directory/roleEligibilityScheduleInstances"
                       f"?$filter=principalId eq '{me}'&$expand=roleDefinition") or {}
    eligible = {e["roleDefinition"]["displayName"]: e["roleDefinitionId"] for e in elig.get("value", [])
                if e.get("roleDefinition") and e.get("directoryScopeId") == "/"}
    entra = entra_plan(active, eligible, needs_consent)

    scope = f"/subscriptions/{subscription_id}"
    owner_active = "Owner" in (az(["role", "assignment", "list", "--assignee", me, "--scope", scope,
                                   "--include-inherited", "--include-groups", "--query", "[].roleDefinitionName"]) or [])
    azure = []
    if not owner_active:
        rows = rest("get", f"{ARM}{scope}/providers/Microsoft.Authorization/roleEligibilityScheduleInstances"
                           f"?api-version={PIM_ARM_API}&$filter=asTarget()") or {}
        for r in rows.get("value", []):
            props = r.get("properties", {})
            name = props.get("expandedProperties", {}).get("roleDefinition", {}).get("displayName")
            if name == "Owner":
                azure.append((props["scope"], props["roleDefinitionId"], props.get("roleEligibilityScheduleId")))
                break

    if not entra and not azure:
        print("Nothing to activate: you already have the roles the kit needs, or none are eligible in PIM.")
        print("Run ./nerdio preflight to see which role is still missing.")
        return 0
    print(f"Activate for {hours} hours through Privileged Identity Management:")
    for name, _ in entra:
        print(f"  Entra: {name}")
    for sc, _, _ in azure:
        print(f"  Azure: Owner on {'this subscription' if sc == scope else sc}")
    if not confirm("Activate these roles?", assume_yes):
        print("Nothing activated.")
        return 1

    when = {"startDateTime": _now(), "expiration": {"type": "AfterDuration", "duration": f"PT{hours}H"}}
    failed = []
    for name, role_id in entra:
        try:
            rest("post", f"{GRAPH}/roleManagement/directory/roleAssignmentScheduleRequests", {
                "action": "selfActivate", "principalId": me, "roleDefinitionId": role_id, "directoryScopeId": "/",
                "justification": "Deploying Nerdio Manager with the nerdio-hcl kit", "scheduleInfo": when})
            print(f"  activated {name}")
        except FixError as exc:
            failed.append(f"{name}: {exc}")
    for sc, role_id, sched in azure:
        try:
            rest("put", f"{ARM}{sc}/providers/Microsoft.Authorization/roleAssignmentScheduleRequests/{uuid.uuid4()}"
                        f"?api-version={PIM_ARM_API}", {"properties": {
                            "principalId": me, "roleDefinitionId": role_id, "requestType": "SelfActivate",
                            "linkedRoleEligibilityScheduleId": sched,
                            "justification": "Deploying Nerdio Manager with the nerdio-hcl kit", "scheduleInfo": when}})
            print("  activated Owner")
        except FixError as exc:
            failed.append(f"Owner: {exc}")
    if failed:
        print("Some activations were refused (approval, MFA or ticket rules in PIM can require the portal):")
        for f in failed:
            print(f"  {f}")
        print("  Last resort, in the portal: Entra ID > Privileged Identity Management > My roles > Activate")
    print("Then run az login again so your token carries the new roles, and rerun ./nerdio preflight.")
    return 1 if failed else 0
