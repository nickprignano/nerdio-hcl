"""The run context: inputs, the az runner, the read-only guard, caches and name masking.

Every check reaches Azure only through Ctx.az and Ctx.get, so tests swap in recorded answers and
the guard below makes a write impossible from a default-tier check.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional

from . import cloud as cloudmod

# az subcommands whose last word is one of these only read.
READ_VERBS = {"show", "list", "exists", "check-name"}
READ_PREFIXES = ("list-",)
# The evaluate-only POSTs a default check may make: name availability (nothing is reserved). The
# path must end in checkNameAvailability, so a URL that merely contains it doesn't pass.
EVALUATE_ONLY = re.compile(r"^https://[^/?#]+/[^?#]*/checkNameAvailability\?[^/#]*$", re.I)
# Command words that read secret values, keys or credentials; no default-tier check may make them,
# even when the verb is show or list (`storage account keys list`, `webapp config appsettings list`).
SECRET_WORDS = {"secret", "secrets", "key", "keys", "credential", "credentials", "appsettings", "connection-string",
                "list-publishing-profiles", "list-publishing-credentials", "list-keys", "list-connection-strings",
                "show-connection-string", "list-secrets"}
# ARM or data-plane URL parts that return secrets, refused for az rest even as a GET.
SECRET_URL = re.compile(r"(\.vault(core)?\.|/secrets(/|\?|$)|/list[A-Za-z]*(keys|secrets|credentials)|/appsettings"
                        r"|/connectionstrings|/publishxml|/publishingcredentials)", re.I)
# What Ctx.calls records besides az argument lists.
NOT_AZ = ("GET", "NERDIO")


class WriteRefused(Exception):
    """A check tried to call something that isn't a read."""


def option(args: List[str], *names: str) -> Optional[str]:
    """An option's value, written as `--name value` or `--name=value`; None when absent."""
    for i, a in enumerate(args):
        key, eq, value = a.partition("=")
        if key.lower() in names:
            return value if eq else (args[i + 1] if i + 1 < len(args) else "")
    return None


def is_read_only(args: List[str]) -> bool:
    """True when an az command line only reads and returns no secret: `az ... show|list|list-*`,
    or `az rest` GET (or the evaluate-only name availability POST)."""
    words = []
    for a in args:
        if a.startswith("-"):
            break
        words.append(a)
    if not words or SECRET_WORDS & {w.lower() for w in words}:
        return False
    if words[0] == "rest":
        method = (option(args, "--method", "-m") or "get").lower()  # az rest defaults to GET
        url = option(args, "--url", "--uri", "-u") or ""
        if SECRET_URL.search(url):
            return False
        if method == "post" and EVALUATE_ONLY.match(url):
            return True
        if option(args, "--body", "-b") is not None:
            return False
        return method == "get"
    if words == ["cloud", "show"]:
        return True
    last = words[-1]
    return last in READ_VERBS or last.startswith(READ_PREFIXES)


def run_az(args: List[str]):
    """az with JSON output; None when az is missing, fails or prints something that isn't JSON."""
    try:
        res = subprocess.run(["az", *args, "-o", "json"], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def http_get(url: str):
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "nerdio-readiness"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:  # noqa: S310 (https only, checked above)
            return res.status, res.read(65536).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, OSError) as exc:
        # The class only: a TLS error's text names the host, which can be a customer's domain.
        reason = getattr(exc, "reason", exc)
        return None, type(reason).__name__ if isinstance(reason, BaseException) else type(exc).__name__


def tool_version(cmd: List[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return res.stdout


class Ctx:
    def __init__(self, values: Dict, *, az: Optional[Callable] = None, mode: str = "kit", stage: str = "pre-install",
                 features=(), show_names: bool = False, env: Optional[Dict] = None,
                 which: Optional[Callable] = None, run_tool: Optional[Callable] = None,
                 isdir: Optional[Callable] = None, python_version=None, http: Optional[Callable] = None,
                 nerdio_data: bool = False, nerdio_client=None):
        self.values = values
        self.mode = mode
        self.stage = stage
        self.features = tuple(features)
        self.show_names = show_names
        self.env = os.environ if env is None else env
        self.which = which or shutil.which
        self.run_tool = run_tool or tool_version
        self.isdir = isdir or os.path.isdir
        self.python_version = python_version
        self._az = az or run_az
        self._http = http or http_get
        self.nerdio_data = nerdio_data  # the opt-in Nerdio REST tier (--nerdio-data)
        self._nerdio = nerdio_client
        self.acct: Optional[Dict] = None
        self.cloud: cloudmod.Cloud = cloudmod.COMMERCIAL
        self.stopped = ""  # set by a check that makes the rest pointless (unsupported cloud)
        self.rights: set = set()
        self.calls: List[List[str]] = []
        self._cache: Dict = {}
        self._names: Dict = {}

    # --- Azure -------------------------------------------------------------------------------

    def az(self, args: List[str]):
        if not is_read_only(args):
            raise WriteRefused("readiness checks only read; refused: az " + " ".join(args[:4]))
        self.calls.append(list(args))
        return self._az(list(args))

    def get(self, url: str):
        return self.az(["rest", "--method", "get", "--url", url])

    def arm(self, path: str) -> str:
        return self.cloud.arm + path

    def graph(self, path: str) -> str:
        return self.cloud.graph_v1 + path

    def cached(self, key, fn: Callable):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    @property
    def subscription_id(self) -> str:
        return (self.acct or {}).get("id", "")

    @property
    def is_user(self) -> bool:
        return (self.acct or {}).get("user", {}).get("type") == "user"

    def me_id(self) -> Optional[str]:
        return self.cached("me", lambda: self.az(["ad", "signed-in-user", "show", "--query", "id"]))

    def directory_roles(self) -> Optional[set]:
        """Active directory roles of the signed-in user, or None when Graph won't say."""
        def read():
            data = self.get(self.graph("/me/transitiveMemberOf/microsoft.graph.directoryRole?$select=displayName"))
            return None if data is None else {r.get("displayName") for r in data.get("value", [])}
        roles = self.cached("directory_roles", read)
        if roles:
            self.rights |= roles
        return roles

    def assignments_at(self, scope: str) -> Optional[List[Dict]]:
        """The signed-in user's role assignments at a scope (inherited and through groups included),
        each as {"role": name, "condition": text or None}."""
        def read():
            me = self.me_id()
            if not me:
                return None
            rows = self.az(["role", "assignment", "list", "--assignee", me, "--scope", scope,
                            "--include-inherited", "--include-groups", "--query",
                            "[].{role:roleDefinitionName, condition:condition}"])
            if rows is None:
                return None
            return [r if isinstance(r, dict) else {"role": r, "condition": None} for r in rows]
        return self.cached(("roles", scope.lower()), read)

    def roles_at(self, scope: str) -> Optional[List[str]]:
        """Role names the signed-in user holds at a scope."""
        rows = self.assignments_at(scope)
        return None if rows is None else [r.get("role") for r in rows]

    def http_get(self, url: str):
        """An unauthenticated HTTPS GET (Nerdio's health page): (status, body text), or (None, reason)."""
        if not url.startswith("https://"):
            raise WriteRefused("only https GETs")
        self.calls.append(["GET", url])
        return self._http(url)

    def nerdio_get(self, path: str):
        """A GET of Nerdio Manager's REST API: (status, body). Only with --nerdio-data; raises
        nerdio_api.NotConfigured when it can't sign in. The secret never enters ctx.calls."""
        from . import nerdio_api

        if not self.nerdio_data:
            raise nerdio_api.NotConfigured("the Nerdio data tier is off (add --nerdio-data)")
        if self._nerdio is None:
            self._nerdio = nerdio_api.connect(self)
        self.calls.append(["NERDIO", "GET", path])
        return self._nerdio.get(path)

    def post_check(self, url: str, body: Dict):
        """An evaluate-only POST (name availability); the guard refuses any other POST."""
        return self.az(["rest", "--method", "post", "--url", url, "--body", json.dumps(body)])

    # --- Output ------------------------------------------------------------------------------

    def name(self, kind: str, value: str) -> str:
        """A resource, group or network name for a detail line: masked unless --names, the same
        placeholder every time for the same name. Names can identify a customer."""
        if self.show_names or not value:
            return value
        key = (kind, value.lower())
        if key not in self._names:
            n = sum(1 for k in self._names if k[0] == kind) + 1
            self._names[key] = f"<{kind}-{n}>"
        return self._names[key]

    def account_terms(self) -> List[str]:
        """Names from az account show that would identify the tenant or the person."""
        acct = self.acct or {}
        terms = [acct.get("name"), (acct.get("user") or {}).get("name"), acct.get("tenantDefaultDomain"),
                 acct.get("tenantDisplayName")]
        return sorted({t for t in terms if t and len(t) > 3}, key=len, reverse=True)
