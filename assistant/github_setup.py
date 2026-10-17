"""One-click registration of the chatbot's GitHub App, with GitHub's App manifest flow.

GitHub only accepts a manifest as a form POST from the browser, so the chatbot hosts that form:
1. /setup/github posts a manifest (Actions read and write, no webhook, private) to GitHub, and
   the admin clicks GitHub's "Create GitHub App" button.
2. GitHub redirects back to /setup/github/callback with a one-time code. The app trades it for
   the new app's private key and imports the key straight into its Key Vault as a non-exportable,
   sign-only key, tagged with the app's client ID. The key is never written to disk, logged or
   shown, and nobody downloads or pastes a .pem.
3. The admin lands on GitHub's install page and installs the app on the kit's repository.

Both pages sit behind the chatbot's Entra sign-in. A state cookie ties the callback to the form
this browser posted.
"""

from __future__ import annotations

import base64
import html
import json
import re
import secrets

from pipeline import GITHUB_API, Pipeline, PipelineError, _b64url

STATE_COOKIE = "nerdio_gh_state"
PEM_RE = re.compile(r"-----BEGIN (RSA )?PRIVATE KEY-----(.+?)-----END (RSA )?PRIVATE KEY-----", re.S)


# -- the key: PEM to the JWK Key Vault imports ------------------------------------------------

def _der(data: bytes, pos: int) -> tuple[int, int, int]:
    """(tag, start of contents, end of contents) of the DER element at pos."""
    tag, length = data[pos], data[pos + 1]
    pos += 2
    if length & 0x80:
        count = length & 0x7F
        length = int.from_bytes(data[pos:pos + count], "big")
        pos += count
    return tag, pos, pos + length


def _children(data: bytes, start: int, end: int) -> list[tuple[int, int, int]]:
    out, pos = [], start
    while pos < end:
        tag, s, e = _der(data, pos)
        out.append((tag, s, e))
        pos = e
    return out


def pem_to_jwk(pem: str) -> dict:
    """An RSA private key (PKCS#1 as GitHub issues it, or PKCS#8) as a sign-only JWK."""
    m = PEM_RE.search(pem)
    if not m:
        raise PipelineError("GitHub didn't return a private key.")
    der = base64.b64decode("".join(m.group(2).split()))
    _, s, e = _der(der, 0)
    fields = _children(der, s, e)
    if fields[1][0] == 0x30:  # PKCS#8: version, algorithm, OCTET STRING holding the PKCS#1 key
        _, s, e = fields[2]
        der = der[s:e]
        _, s, e = _der(der, 0)
        fields = _children(der, s, e)
    ints = [der[s:e].lstrip(b"\x00") for tag, s, e in fields if tag == 0x02]
    names = ["version", "n", "e", "d", "p", "q", "dp", "dq", "qi"]
    if len(ints) < len(names):
        raise PipelineError("The private key isn't an RSA key.")
    jwk = {name: _b64url(value) for name, value in zip(names[1:], ints[1:])}
    return {"kty": "RSA", "key_ops": ["sign"], **jwk}


# -- the flow ---------------------------------------------------------------------------------

def owner_kind(pipeline: Pipeline) -> str:
    owner = pipeline.repository.split("/", 1)[0]
    status, raw = pipeline._request("GET", f"{GITHUB_API}/users/{owner}", {"Accept": "application/vnd.github+json"})
    return json.loads(raw).get("type", "User") if status == 200 else "User"


def manifest(pipeline: Pipeline, base_url: str) -> dict:
    return {
        "name": f"nerdio-chat-{secrets.token_hex(3)}",
        "url": f"https://github.com/{pipeline.repository}",
        "description": "Starts the Nerdio kit's deploy workflow for its setup chatbot. Can't approve applies.",
        "redirect_url": f"{base_url}/setup/github/callback",
        "setup_url": f"{base_url}/setup/github/installed",
        "public": False,
        "hook_attributes": {"url": base_url, "active": False},
        "default_permissions": {"actions": "write", "metadata": "read"},
        "default_events": [],
    }


def form_page(pipeline: Pipeline, base_url: str, state: str) -> str:
    owner = pipeline.repository.split("/", 1)[0]
    if owner_kind(pipeline) == "Organization":
        action = f"https://github.com/organizations/{owner}/settings/apps/new?state={state}"
    else:
        action = f"https://github.com/settings/apps/new?state={state}"
    data = html.escape(json.dumps(manifest(pipeline, base_url)), quote=True)
    return page("Connect the chat to GitHub", f"""
<p>This creates a private GitHub App for this chat. It can start the deploy workflow on
<b>{html.escape(pipeline.repository)}</b> and read its runs, and nothing else. It can't approve an apply.</p>
<p>On GitHub, click <b>Create GitHub App</b>, then install it on that repository.</p>
<form id="manifest" method="post" action="{html.escape(action, quote=True)}">
  <input type="hidden" name="manifest" value="{data}">
  <button type="submit">Continue to GitHub</button>
</form>
<script src="/static/github-setup.js"></script>""")


def convert_and_import(pipeline: Pipeline, code: str) -> dict:
    """Trade the one-time code for the app, and put its private key straight into Key Vault."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", code or ""):
        raise PipelineError("GitHub sent back an unexpected code. Start again from /setup/github.")
    # No credential needed: the code itself proves the admin just created this app.
    status, raw = pipeline._request("POST", f"{GITHUB_API}/app-manifests/{code}/conversions",
                                    {"Accept": "application/vnd.github+json"}, b"")
    if status != 201:
        raise PipelineError("GitHub didn't hand over the new app. The code lasts an hour; start again from /setup/github.")
    app = json.loads(raw)
    jwk = pem_to_jwk(app.pop("pem", ""))
    for secret in ("client_secret", "webhook_secret"):
        app.pop(secret, None)
    pipeline.import_app_key(jwk, {"client_id": app["client_id"], "app_id": str(app["id"]), "slug": app["slug"]})
    return {"slug": app["slug"], "install_url": f"https://github.com/apps/{app['slug']}/installations/new"}


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><link rel="stylesheet" href="/static/app.css"></head>
<body><main class="setup"><h1>{html.escape(title)}</h1>{body}</main></body></html>"""
