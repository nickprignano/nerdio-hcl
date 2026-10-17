"""Remember which tenant and subscription each kit environment deploys into, so nobody types them.

`./nerdio use <env>` saves the signed-in `az account show` the first time and checks it every
time after. The profile lives in your home folder (Cloud Shell keeps it), readable only by you,
never in the repo or the chat. IDs aren't secrets, but they identify the tenant, so they stay
out of anything shared.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import engine

ENV_RE = re.compile(r"^[a-z][a-z0-9-]{0,15}$")


def home() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "nerdio-hcl"


def path(env: str) -> Path:
    return home() / "profiles" / f"{env}.json"


def load(env: str) -> dict | None:
    try:
        return json.loads(path(env).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def current() -> str | None:
    try:
        env = (home() / "current").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return env if ENV_RE.match(env) else None


def _write(target: Path, text: str) -> None:
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    old = os.umask(0o077)
    try:
        target.write_text(text, encoding="utf-8")
    finally:
        os.umask(old)


def save(env: str, account: dict) -> dict:
    profile = {
        "tenant_id": account["tenantId"],
        "subscription_id": account["id"],
        "subscription_name": account.get("name", ""),
        "tenant_domain": account.get("tenantDefaultDomain", ""),
    }
    _write(path(env), json.dumps(profile, indent=2) + "\n")
    return profile


def set_current(env: str) -> None:
    _write(home() / "current", env + "\n")


def forget(env: str) -> bool:
    try:
        path(env).unlink()
    except FileNotFoundError:
        return False
    if current() == env:
        (home() / "current").unlink(missing_ok=True)
    return True


def names() -> list[str]:
    folder = home() / "profiles"
    return sorted(p.stem for p in folder.glob("*.json")) if folder.is_dir() else []


def shell_link(profile: dict) -> str:
    domain = profile.get("tenant_domain")
    return f"https://shell.azure.com/{domain}" if domain else "https://shell.azure.com"


def ensure(env: str, account: dict | None = None) -> tuple[bool, str]:
    """Make az point at env's subscription. Switches subscription within the tenant; never signs in."""
    profile = load(env)
    if profile is None:
        return False, f"No profile for {env!r} yet: sign in to its subscription and run ./nerdio use {env}"
    account = account if account is not None else engine.az_json(["account", "show"])
    if not account:
        return False, "Not signed in: run az login (Cloud Shell already is), then try again."
    label = profile.get("subscription_name") or env
    if account.get("tenantId") != profile["tenant_id"]:
        return False, (f"Signed in to a different tenant than {env!r} uses. Open Cloud Shell in that tenant "
                       f"({shell_link(profile)}) and run this again.")
    if account.get("id") != profile["subscription_id"]:
        res = subprocess.run(["az", "account", "set", "--subscription", profile["subscription_id"]],
                             capture_output=True, text=True, check=False)
        if res.returncode:
            return False, f"Couldn't switch to {label!r}; check you still have access to it (az account list)."
        return True, f"Switched to {label!r} for {env}"
    return True, f"Using {label!r} for {env}"


def guard(env: str | None = None) -> tuple[bool, str]:
    """For other commands: check the current profile, if there is one. Pipelines (ARM_*) skip it."""
    if os.environ.get("ARM_SUBSCRIPTION_ID") or os.environ.get("GITHUB_ACTIONS"):
        return True, ""
    env = env or current()
    if not env or load(env) is None:
        return True, ""
    return ensure(env)
