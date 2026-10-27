"""The Nerdio data tier (opt-in, `--nerdio-data`): read-only GETs against Nerdio Manager's REST API.

Nerdio shows the REST client secret once and stores it nowhere, so only the kit has it, in its
secret store (decision 0015). Kit mode reads 02-nerdio-config's platform inputs (no secrets in
them) and the secret from that Key Vault; standalone reads NME_CLIENT_SECRET from the person's own
shell, like the nme provider. The secret stays in this process: it's never printed, written,
logged in ctx.calls or sent anywhere but the sign-in endpoint.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Dict, Optional, Tuple

ENV = ("NME_BASE_URL", "NME_TENANT_ID", "NME_CLIENT_ID", "NME_SCOPE")


class NotConfigured(Exception):
    """The data tier can't sign in: says what's missing, never a value."""


class SignInFailed(NotConfigured):
    """The sign-in endpoint refused the REST client: a wrong ID, scope or secret, not a Nerdio role."""


def kit_settings(env_name: str) -> Dict:
    """Stage 2's inputs from 01-platform (platform.auto.tfvars.json): base URL, tenant, client, scope, vault."""
    import engine

    path = engine.stage_dir(engine.load_schema(), "config", env_name) / "platform.auto.tfvars.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NotConfigured(f"no {path.name} in 02-nerdio-config (written after the platform apply)") from exc
    return {"base_url": data.get("nme_base_url"), "tenant": data.get("nme_tenant_id"),
            "client_id": data.get("nme_client_id"), "scope": data.get("nme_scope"),
            "vault": data.get("nme_key_vault") or {}}


def vault_secret(vault: Dict) -> str:
    """The REST client secret from the kit's Key Vault (needs Key Vault Secrets User on that vault only).
    Run outside Ctx.az on purpose: the default tier's guard refuses every secret read."""
    vault_id, name = vault.get("id") or "", vault.get("secret_name") or ""
    if not vault_id or not name:
        raise NotConfigured("the kit's secret store isn't a Key Vault (nme_secret_store = key_vault)")
    res = subprocess.run(["az", "keyvault", "secret", "show", "--vault-name", vault_id.rstrip("/").split("/")[-1],
                          "--name", name, "--query", "value", "-o", "tsv"], capture_output=True, text=True, check=False)
    if res.returncode != 0 or not res.stdout.strip():
        raise NotConfigured("can't read the REST client secret (needs Key Vault Secrets User on the kit's secret store)")
    return res.stdout.strip()


def settings(mode: str, env: Dict, env_name: str, tenant: str, nerdio_url: str = "") -> Tuple[Dict, str]:
    """(settings, secret) for this run, or NotConfigured."""
    if mode == "kit":
        cfg = kit_settings(env_name)
        secret = env.get("NME_CLIENT_SECRET") or vault_secret(cfg["vault"])
    else:
        cfg = {"base_url": env.get("NME_BASE_URL") or nerdio_url, "tenant": env.get("NME_TENANT_ID") or tenant,
               "client_id": env.get("NME_CLIENT_ID"), "scope": env.get("NME_SCOPE")}
        secret = env.get("NME_CLIENT_SECRET") or ""
    missing = [k for k in ("base_url", "tenant", "client_id", "scope") if not cfg.get(k)]
    if not secret:
        missing.append("secret (set NME_CLIENT_SECRET in your own shell; never paste it into a chat)")
    if missing:
        raise NotConfigured("missing " + ", ".join(missing))
    if not cfg["base_url"].startswith("https://"):
        cfg["base_url"] = "https://" + cfg["base_url"].split("//")[-1]
    return cfg, secret


def _post_form(url: str, form: Dict) -> Tuple[Optional[int], Dict]:
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:  # noqa: S310 (https sign-in endpoint)
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except (urllib.error.URLError, OSError, ValueError):
        return None, {}


def _get(url: str, token: str) -> Tuple[Optional[int], object]:
    req = urllib.request.Request(url, method="GET", headers={"Authorization": f"Bearer {token}",
                                                             "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:  # noqa: S310 (https only)
            body = res.read(1 << 20).decode("utf-8", "replace")
            try:
                return res.status, json.loads(body)
            except ValueError:
                return res.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (urllib.error.URLError, OSError):
        return None, None


class Client:
    """Signs in once with client credentials, then only GETs."""

    def __init__(self, cfg: Dict, secret: str, login: str, *, post: Callable = _post_form, get: Callable = _get):
        self.cfg, self._secret, self.login = cfg, secret, login.rstrip("/")
        self._post, self._get_fn = post, get
        self._token: Optional[str] = None

    def token(self) -> Optional[str]:
        if self._token is None:
            status, data = self._post(f"{self.login}/{self.cfg['tenant']}/oauth2/v2.0/token", {
                "grant_type": "client_credentials", "client_id": self.cfg["client_id"],
                "client_secret": self._secret, "scope": self.cfg["scope"]})
            self._token = data.get("access_token") if status == 200 else ""
        return self._token or None

    def get(self, path: str) -> Tuple[Optional[int], object]:
        if not path.startswith("/api/"):
            raise ValueError("Nerdio data reads are /api/ GETs only")
        token = self.token()
        if not token:
            raise SignInFailed("the REST client couldn't sign in; check NME_CLIENT_ID, NME_SCOPE and the secret")
        return self._get_fn(self.cfg["base_url"].rstrip("/") + path, token)


def connect(ctx) -> Client:
    cfg, secret = settings(ctx.mode, dict(os.environ) if ctx.env is os.environ else ctx.env,
                           ctx.values.get("_env") or "example", (ctx.acct or {}).get("tenantId", ""),
                           ctx.values.get("nerdio_url") or "")
    return Client(cfg, secret, ctx.cloud.login)
