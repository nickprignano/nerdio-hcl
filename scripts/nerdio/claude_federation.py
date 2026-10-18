"""Connect the setup chat to the Claude API with workload identity federation. No API key exists.

The chat's managed identity gets an Entra token; the Claude API trusts it because of three things
made once in your Anthropic organization, which this module creates through the Admin API:

- a federation issuer for this tenant's Entra v2.0 issuer (discovery JWKS, 24-hour token
  lifetime, because Azure hands managed identities tokens that live that long),
- a service account with the developer organization role, a plain member of one workspace,
- a rule that accepts only this app's managed identity (exact object ID, tenant and audience),
  minting inference-only tokens that last ten minutes.

The Admin API takes only an OAuth token with the org:admin scope, from an Anthropic organization
admin's own login (`ant auth login --profile nerdio-admin --scope org:admin`). The token is read
from the ant CLI or ANTHROPIC_AUTH_TOKEN, sent only to api.anthropic.com and never printed or saved.
The IDs this returns aren't secrets; they go in the stage's gitignored tfvars.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.anthropic.com"
ADMIN_PROFILE = "nerdio-admin"
SCOPE = "workspace:inference"  # Messages, token counting and models only; nothing else in the workspace
TOKEN_LIFETIME = 600
MAX_JWT_LIFETIME = 86400
WORKSPACE_ROLE = "workspace_user"
LOGIN_HINT = (f"Sign in as an Anthropic organization admin first (Cloud Shell has no browser, so paste the code back):\n"
              f"  ant auth login --no-browser --profile {ADMIN_PROFILE} --scope org:admin\n"
              f"No ant CLI yet? Run scripts/install-ant-cli.sh. Or connect in the Claude Console instead: "
              f"./nerdio assistant --connect-claude --console")


class FederationError(RuntimeError):
    pass


def admin_token() -> str:
    """An org:admin OAuth token from the environment or the ant CLI. Never printed."""
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    if token:
        return token
    if not shutil.which("ant"):
        raise FederationError(LOGIN_HINT)
    res = subprocess.run(["ant", "auth", "print-credentials", "--profile", ADMIN_PROFILE, "--access-token"],
                         capture_output=True, text=True, check=False)
    token = res.stdout.strip()
    if res.returncode or not token:
        raise FederationError(LOGIN_HINT)
    return token


class Admin:
    """The few Admin API calls the setup needs, standard library only."""

    def __init__(self, token: str, opener=urllib.request.urlopen):
        self._token = token
        self._open = opener

    def call(self, method: str, path: str, body: dict | None = None, query: dict | None = None) -> dict:
        url = API + path + ("?" + urllib.parse.urlencode(query) if query else "")
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "authorization": f"Bearer {self._token}",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        })
        try:
            with self._open(req, timeout=30) as res:
                return json.loads(res.read() or b"{}")
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read()).get("error", {}).get("message", "")
            except ValueError:
                detail = ""
            hint = " (is the admin sign-in still valid? " + LOGIN_HINT.splitlines()[1].strip() + ")" if exc.code in (401, 403) else ""
            raise FederationError(f"{method} {path} failed: HTTP {exc.code} {detail}{hint}".strip()) from None
        except urllib.error.URLError as exc:
            raise FederationError(f"Couldn't reach {API}: {exc.reason}") from None

    def items(self, path: str, **query) -> list[dict]:
        """Every item of a list endpoint; handles both of the Admin API's cursor styles."""
        out, query = [], {"limit": 100, **query}
        for _ in range(50):
            page = self.call("GET", path, query=query)
            out += page.get("data", [])
            if page.get("next_page"):
                query["page"] = page["next_page"]
            elif page.get("has_more") and page.get("last_id"):
                query["after_id"] = page["last_id"]
            else:
                break
        return out


def plan(name: str, federation: dict) -> dict:
    """What gets created, by name. Names are unique per organization, so reruns find them again."""
    return {
        "workspace": name,
        "issuer": {"name": f"entra-{federation['tenant_id'][:8]}", "issuer_url": federation["issuer_url"],
                   "jwks": {"type": "discovery"}, "max_jwt_lifetime_seconds": MAX_JWT_LIFETIME},
        "service_account": {"name": f"{name}-chat", "organization_role": "developer",
                            "description": "Nerdio setup chat (nerdio-hcl). Federated from its Azure managed identity."},
        "rule": {
            "name": f"{name}-chat",
            "match": {
                "audience": federation["audience"],
                # The full object ID, so it matches exactly this identity (Entra subjects are GUIDs).
                "subject_prefix": federation["object_id"],
                "claims": {"oid": federation["object_id"], "tid": federation["tenant_id"]},
            },
            "oauth_scope": SCOPE,
            "token_lifetime_seconds": TOKEN_LIFETIME,
        },
    }


def connect(admin: Admin, name: str, federation: dict, say=print) -> dict:
    """Create or reuse the workspace, issuer, service account and rule. Returns the claude_api IDs."""
    want = plan(name, federation)
    org = admin.call("GET", "/v1/organizations/me")["id"]

    workspace = next((w for w in admin.items("/v1/organizations/workspaces")
                      if w.get("name") == want["workspace"] and not w.get("archived_at")), None)
    if workspace is None:
        workspace = admin.call("POST", "/v1/organizations/workspaces", {"name": want["workspace"]})
        say(f"✓ Created workspace {want['workspace']!r} (its own spend limits and usage)")
    else:
        say(f"✓ Using workspace {want['workspace']!r}")

    issuer_body = want["issuer"]
    issuer = next((i for i in admin.items("/v1/organizations/federation_issuers")
                   if i.get("issuer_url") == issuer_body["issuer_url"]), None)
    if issuer is None:
        issuer = admin.call("POST", "/v1/organizations/federation_issuers", issuer_body)
        say("✓ Registered this tenant's Entra issuer")
    else:
        if (issuer.get("max_jwt_lifetime_seconds") or 0) < MAX_JWT_LIFETIME:
            admin.call("POST", f"/v1/organizations/federation_issuers/{issuer['id']}",
                       {"max_jwt_lifetime_seconds": MAX_JWT_LIFETIME})
        say("✓ Using this tenant's Entra issuer")

    account_body = want["service_account"]
    account = next((a for a in admin.items("/v1/organizations/service_accounts")
                    if a.get("name") == account_body["name"]), None)
    if account is None:
        account = admin.call("POST", "/v1/organizations/service_accounts", account_body)
        say(f"✓ Created service account {account_body['name']!r} (developer role)")
    else:
        say(f"✓ Using service account {account_body['name']!r}")
    admin.call("POST", f"/v1/organizations/service_accounts/{account['id']}/workspaces",
               {"workspace_id": workspace["id"], "workspace_role": WORKSPACE_ROLE})

    rule_body = dict(want["rule"], issuer_id=issuer["id"],
                     target={"type": "service_account", "service_account_id": account["id"]},
                     workspace_id=workspace["id"])
    rule = next((r for r in admin.items("/v1/organizations/federation_rules", issuer_id=issuer["id"])
                 if r.get("name") == rule_body["name"]), None)
    if rule is None:
        rule = admin.call("POST", "/v1/organizations/federation_rules", rule_body)
        say("✓ Created the rule: only this chat's managed identity, inference only, 10-minute tokens")
    else:
        # The identity may have been recreated since; keep the rule pointed at the current one.
        update = {k: rule_body[k] for k in ("match", "target", "oauth_scope", "token_lifetime_seconds")
                  if rule.get(k) != rule_body[k]}
        if update:
            rule = admin.call("POST", f"/v1/organizations/federation_rules/{rule['id']}", update)
            say("✓ Updated the rule to match this chat's managed identity")
        else:
            say("✓ Using the rule for this chat's managed identity")

    return {"organization_id": org, "federation_rule_id": rule["id"],
            "service_account_id": account["id"], "workspace_id": workspace["id"]}


def console_steps(name: str, federation: dict) -> str:
    """The same setup by hand, for organizations where the Admin API isn't an option."""
    want = plan(name, federation)
    rule = want["rule"]
    return "\n".join([
        "In the Claude Console (platform.claude.com/settings/workload-identity-federation), choose",
        "Connect workload, then Microsoft Entra, and enter:",
        "  Token issuer:        v2.0 (login.microsoftonline.com)",
        f"  Issuer URL:          {federation['issuer_url']}",
        f"  Audience:            {federation['audience']}",
        f"  Object ID (oid):     {federation['object_id']}",
        f"  Tenant ID (tid):     {federation['tenant_id']}",
        f"  Service account:     {want['service_account']['name']} (developer)",
        f"  Rule:                {rule['name']}, scope {SCOPE}, token lifetime {TOKEN_LIFETIME}s",
        f"  Workspace:           {want['workspace']} (create it first, or pick one)",
        f"Then, on the Issuers tab, edit the issuer and set the maximum JWT lifetime to {MAX_JWT_LIFETIME}",
        "(Azure managed identity tokens live up to 24 hours; the wizard's default rejects them).",
        "Finally give the chat the IDs the wizard shows (none of them are secrets):",
        "  ./nerdio assistant --claude-ids org=<organization UUID>,rule=fdrl_...,account=svac_...,workspace=wrkspc_...",
    ])


def parse_ids(text: str) -> dict:
    keys = {"org": "organization_id", "rule": "federation_rule_id", "account": "service_account_id",
            "workspace": "workspace_id"}
    out = {}
    for part in filter(None, (p.strip() for p in text.split(","))):
        key, sep, value = part.partition("=")
        if not sep or key not in keys or not value:
            raise FederationError(f"Unknown --claude-ids part {part!r}; use org=,rule=,account= and optionally workspace=")
        out[keys[key]] = value
    missing = [k for k in ("org", "rule", "account") if keys[k] not in out]
    if missing:
        raise FederationError("--claude-ids also needs " + ", ".join(f"{k}=" for k in missing))
    return out
