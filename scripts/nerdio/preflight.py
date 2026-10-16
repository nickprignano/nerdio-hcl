"""Read-only readiness checks for the prepare phase: tools, sign-in, roles, providers, region, quota
(VM vCPUs and the App Service plan Nerdio Manager runs on).

Every check only reads (az ... show/list). Nothing here changes Azure or Entra. Each result
carries the exact command or link that fixes it, so a person or the setup chatbot can act on it.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import asdict, dataclass

from engine import az_json

PASS, WARN, FAIL, MANUAL = "pass", "warn", "fail", "manual"

# Namespaces the kit's resources live in, including what Nerdio's own deployment creates.
PROVIDERS = [
    "Microsoft.DesktopVirtualization",
    "Microsoft.Compute",
    "Microsoft.Network",
    "Microsoft.Storage",
    "Microsoft.Web",
    "Microsoft.Sql",
    "Microsoft.KeyVault",
    "Microsoft.Automation",
    "Microsoft.Insights",
    "Microsoft.OperationalInsights",
]

GLOBAL_ADMIN = "Global Administrator"
# Roles that can create app registrations even when the tenant blocks users from doing so.
APP_CREATORS = {GLOBAL_ADMIN, "Application Administrator", "Cloud Application Administrator", "Application Developer"}
# App Service REST API version for Get Usages in Location.
WEB_API = "2024-11-01"
CONSENT_PAIR = {"Privileged Role Administrator", "Cloud Application Administrator"}


@dataclass
class Result:
    status: str
    check: str
    detail: str
    fix: str = ""
    kb: str = ""


def _version_at_least(have: str, want: str) -> bool:
    def parts(v: str) -> list[int]:
        return [int(x) for x in v.split("-")[0].split(".")[:3]]
    try:
        return parts(have) >= parts(want)
    except ValueError:
        return False


def check_tools() -> list[Result]:
    out = []
    tf = shutil.which("terraform")
    if not tf:
        out.append(Result(FAIL, "Terraform", "terraform isn't on PATH",
                          "Cloud Shell includes it; elsewhere see https://developer.hashicorp.com/terraform/install"))
    else:
        res = subprocess.run(["terraform", "version", "-json"], capture_output=True, text=True, check=False)
        try:
            ver = json.loads(res.stdout)["terraform_version"]
        except (ValueError, KeyError):
            ver = "unknown"
        if _version_at_least(ver, "1.11.0"):
            out.append(Result(PASS, "Terraform", f"{ver} (the kit needs 1.11 or later)"))
        else:
            out.append(Result(FAIL, "Terraform", f"{ver} is older than 1.11",
                              "Install a newer one to ~/bin, e.g. NME_TF_VERSION=1.16.6 with the Cloud Shell bootstrap script"))
    for tool in ("az", "jq", "git"):
        out.append(Result(PASS, tool, "found") if shutil.which(tool)
                   else Result(FAIL, tool, "not on PATH", f"Install {tool}; Azure Cloud Shell already has it"))
    return out


def check_signin() -> tuple[list[Result], dict | None]:
    acct = az_json(["account", "show"])
    if not acct:
        return [Result(FAIL, "Azure sign-in", "az isn't signed in", "az login")], None
    user = acct.get("user", {})
    detail = f"subscription \"{acct.get('name')}\" as a {user.get('type', 'user')}"
    return [Result(PASS, "Azure sign-in", detail)], acct


def check_subscription_owner(acct: dict) -> Result:
    if acct.get("user", {}).get("type") != "user":
        return Result(MANUAL, "Subscription Owner", "signed in as a service principal; check its roles by hand",
                      kb="docs/knowledge/nerdio/platform.md#roles-needed")
    me = az_json(["ad", "signed-in-user", "show", "--query", "id"])
    if not me:
        return Result(WARN, "Subscription Owner", "couldn't read the signed-in user's object ID", "az ad signed-in-user show")
    roles = az_json(["role", "assignment", "list", "--assignee", me, "--scope", f"/subscriptions/{acct['id']}",
                     "--include-inherited", "--include-groups", "--query", "[].roleDefinitionName"])
    if roles is None:
        return Result(WARN, "Subscription Owner", "couldn't list role assignments", "az role assignment list --assignee <you> --all")
    if "Owner" in roles:
        return Result(PASS, "Subscription Owner", "Owner on the subscription",
                      kb="docs/knowledge/nerdio/platform.md#roles-needed")
    return Result(FAIL, "Subscription Owner", "Owner is needed on the subscription (found: " + (", ".join(sorted(set(roles))) or "none") + ")",
                  "Ask a subscription Owner to assign you Owner, or activate it in Privileged Identity Management if it's eligible",
                  kb="docs/knowledge/nerdio/platform.md#roles-needed")


def check_entra_roles(acct: dict, needs_consent: bool) -> Result:
    if not needs_consent:
        return Result(PASS, "Entra admin role", "not needed (admin consent is off, so the wizard asks an admin instead)")
    if acct.get("user", {}).get("type") != "user":
        return Result(MANUAL, "Entra admin role", "signed in as a service principal; it needs Graph app-role grant rights",
                      kb="docs/knowledge/nerdio/entra-app.md")
    data = az_json(["rest", "--method", "get", "--url",
                    "https://graph.microsoft.com/v1.0/me/transitiveMemberOf/microsoft.graph.directoryRole?$select=displayName"])
    if data is None:
        return Result(WARN, "Entra admin role", "couldn't read your directory roles from Microsoft Graph",
                      "Check in the Entra admin center under Roles and administrators")
    roles = {r.get("displayName") for r in data.get("value", [])}
    if GLOBAL_ADMIN in roles or CONSENT_PAIR <= roles:
        return Result(PASS, "Entra admin role", "can grant admin consent", kb="docs/knowledge/nerdio/platform.md#roles-needed")
    return Result(FAIL, "Entra admin role",
                  "admin consent needs Global Administrator, or Privileged Role Administrator plus Cloud Application Administrator "
                  "(active roles only; PIM-eligible roles must be activated first)",
                  "Activate the role in PIM, or answer no to admin consent and let a Global Admin click it in the wizard",
                  kb="docs/knowledge/nerdio/platform.md#roles-needed")


def check_app_registration(acct: dict, creates_app: bool) -> Result:
    """The kit creates the nerdio-nmw-app registration; many tenants stop ordinary users doing that."""
    if not creates_app:
        return Result(PASS, "App registration", "not needed (the kit isn't creating the Entra app)")
    if acct.get("user", {}).get("type") != "user":
        return Result(MANUAL, "App registration", "signed in as a service principal; it needs Application.ReadWrite.OwnedBy or an admin role")
    roles = az_json(["rest", "--method", "get", "--url",
                     "https://graph.microsoft.com/v1.0/me/transitiveMemberOf/microsoft.graph.directoryRole?$select=displayName"])
    if roles is not None and APP_CREATORS & {r.get("displayName") for r in roles.get("value", [])}:
        return Result(PASS, "App registration", "your directory role can create app registrations")
    policy = az_json(["rest", "--method", "get", "--url",
                      "https://graph.microsoft.com/v1.0/policies/authorizationPolicy?$select=defaultUserRolePermissions"])
    if policy is None:
        return Result(WARN, "App registration", "couldn't read the tenant's app registration policy",
                      "Check Entra ID > User settings > 'Users can register applications'")
    if policy.get("defaultUserRolePermissions", {}).get("allowedToCreateApps"):
        return Result(PASS, "App registration", "the tenant lets users register applications")
    return Result(FAIL, "App registration",
                  "this tenant doesn't let users register applications, and you have no active role that can",
                  "Activate Cloud Application Administrator (or Application Developer) in PIM, then az login again",
                  kb="docs/knowledge/nerdio/platform.md#roles-needed")


def check_app_service_quota(subscription_id: str, location: str, sku: str) -> list[Result]:
    """Nerdio Manager runs on a Windows App Service plan (B3 by default). Sandbox and trial
    subscriptions often have a limit of 0 for some tiers, and the apply then fails late with
    "Operation cannot be completed without additional quota"."""
    out = []
    regions = az_json(["appservice", "list-locations", "--sku", sku, "--query", "[].name"])
    wanted = location.replace(" ", "").lower()
    if regions is None:
        out.append(Result(WARN, "App Service SKU", f"couldn't check whether {sku} is offered in {location}"))
    elif wanted in {r.replace(" ", "").lower() for r in regions}:
        out.append(Result(PASS, "App Service SKU", f"{sku} is offered in {location}"))
    else:
        out.append(Result(FAIL, "App Service SKU", f"{sku} isn't offered in {location}",
                          f"az appservice list-locations --sku {sku} -o table, then pick another region or SKU"))
    rows = az_json(["rest", "--method", "get", "--url",
                    f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.Web"
                    f"/locations/{location}/usages?api-version={WEB_API}"])
    request = (f"Portal: Help + support > Create a support request > Service and subscription limits (quotas) > "
               f"App Service; ask for {sku} (Windows) in {location}, new limit 2")
    if rows is None:
        out.append(Result(WARN, "App Service quota", f"couldn't read App Service quota in {location}",
                          "If the apply fails with 'without additional quota': " + request))
        return out
    sku_l = sku.lower()
    row = next((u for u in rows.get("value", [])
                if sku_l in (u.get("name", {}).get("value", "") + " " + u.get("name", {}).get("localizedValue", "")).lower()), None)
    if not row:
        out.append(Result(WARN, "App Service quota", f"no quota row for {sku} in {location}; it may be fine",
                          "If the apply fails with 'without additional quota': " + request))
        return out
    free = int(row.get("limit", 0)) - int(row.get("currentValue", 0))
    if free >= 1:
        out.append(Result(PASS, "App Service quota", f"{sku}: {free} free in {location}, 1 needed"))
    else:
        out.append(Result(FAIL, "App Service quota", f"{sku}: limit {row.get('limit')}, {row.get('currentValue')} used in {location}; 1 needed",
                          request))
    return out


def check_providers() -> Result:
    rows = az_json(["provider", "list", "--query", "[].{ns:namespace, state:registrationState}"])
    if rows is None:
        return Result(WARN, "Resource providers", "couldn't list resource providers", "az provider list -o table")
    state = {r["ns"].lower(): r["state"] for r in rows}
    missing = [ns for ns in PROVIDERS if state.get(ns.lower()) != "Registered"]
    if not missing:
        return Result(PASS, "Resource providers", f"all {len(PROVIDERS)} registered")
    return Result(FAIL, "Resource providers", "not registered: " + ", ".join(missing),
                  " && ".join(f"az provider register -n {ns}" for ns in missing))


def check_region(location: str) -> Result:
    names = az_json(["account", "list-locations", "--query", "[].name"])
    if names is None:
        return Result(WARN, "Region", f"couldn't list regions to check {location}")
    if location in names:
        return Result(PASS, "Region", f"{location} is available to this subscription")
    return Result(FAIL, "Region", f"{location} isn't a region this subscription can use", "az account list-locations -o table")


def check_vm_size_and_quota(location: str, vm_size: str, hosts: int) -> list[Result]:
    skus = az_json(["vm", "list-skus", "-l", location, "--size", vm_size, "--resource-type", "virtualMachines"])
    if skus is None:
        return [Result(WARN, "VM size", f"couldn't look up {vm_size} in {location}")]
    sku = next((s for s in skus if s.get("name", "").lower() == vm_size.lower()), None)
    if not sku:
        return [Result(FAIL, "VM size", f"{vm_size} isn't offered in {location}",
                       f"az vm list-skus -l {location} --size Standard_D -o table")]
    restricted = [r for r in sku.get("restrictions", []) if r.get("reasonCode") == "NotAvailableForSubscription"]
    out = []
    if restricted:
        out.append(Result(FAIL, "VM size", f"{vm_size} is restricted for this subscription in {location}",
                          "Pick another size, or open a support request to lift the restriction"))
    else:
        out.append(Result(PASS, "VM size", f"{vm_size} is offered in {location}"))
    caps = {c["name"]: c["value"] for c in sku.get("capabilities", [])}
    vcpus = int(caps.get("vCPUs", "0") or 0)
    family = sku.get("family")
    need = vcpus * hosts
    usage = az_json(["vm", "list-usage", "-l", location])
    if usage is None or not family:
        out.append(Result(WARN, "vCPU quota", f"couldn't read quota; you need {need} vCPUs of {family or vm_size}"))
        return out
    for key, label in ((family, f"{family} vCPUs"), ("cores", "Total regional vCPUs")):
        row = next((u for u in usage if u.get("name", {}).get("value") == key), None)
        if not row:
            out.append(Result(WARN, "vCPU quota", f"no quota row for {label}"))
            continue
        free = int(row["limit"]) - int(row["currentValue"])
        if free >= need:
            out.append(Result(PASS, "vCPU quota", f"{label}: {free} free, {need} needed for {hosts} hosts at full scale"))
        else:
            out.append(Result(FAIL, "vCPU quota", f"{label}: {free} free, {need} needed for {hosts} hosts at full scale",
                              "Request more in the portal: Quotas > Compute, or lower host_pool_capacity",
                              kb=""))
    return out


def manual_items(values: dict) -> list[Result]:
    items = [
        Result(MANUAL, "Nerdio license", "Nerdio Manager is licensed through its own Marketplace offer; confirm you have one or a trial",
               "https://getnerdio.com", kb="docs/knowledge/nerdio/platform.md#marketplace-deployment"),
        Result(MANUAL, "AVD user licenses", "Users need an eligible license (Microsoft 365 E3/E5, Business Premium and others; check the current list)",
               "https://learn.microsoft.com/azure/virtual-desktop/prerequisites"),
    ]
    if values.get("identity_model") in ("entra_ds", "ad_ds"):
        items.append(Result(MANUAL, "Domain reachability", "session hosts must reach the DNS servers and domain controllers from the AVD network",
                            "Peer to the hub or connect the VNet before deploying"))
    return items


def run(values: dict) -> list[Result]:
    results = check_tools()
    signin, acct = check_signin()
    results += signin
    if acct:
        results.append(check_subscription_owner(acct))
        results.append(check_entra_roles(acct, bool(values.get("create_entra_app")) and bool(values.get("grant_admin_consent"))))
        results.append(check_app_registration(acct, bool(values.get("create_entra_app"))))
        results.append(check_providers())
        results.append(check_region(values["location"]))
        hosts = values.get("host_pool_capacity") or math.ceil(values["user_count"] / values["max_sessions_per_host"])
        results += check_vm_size_and_quota(values["location"], values["vm_size"], hosts)
        if values.get("nerdio_install", "terraform") == "terraform":
            results += check_app_service_quota(acct["id"], values["location"], values.get("app_service_plan_sku") or "B3")
    results += manual_items(values)
    return results


def as_json(results: list[Result]) -> str:
    return json.dumps([asdict(r) for r in results], indent=2)
