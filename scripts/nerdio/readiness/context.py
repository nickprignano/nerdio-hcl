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
from typing import Callable, Dict, List, Optional

from . import cloud as cloudmod

# az subcommands whose last word is one of these only read.
READ_VERBS = {"show", "list", "exists", "check-name"}
READ_PREFIXES = ("list-",)
# The evaluate-only POSTs a default check may make: name availability (nothing is reserved).
EVALUATE_ONLY = re.compile(r"/checkNameAvailability\?", re.I)


class WriteRefused(Exception):
    """A check tried to call something that isn't a read."""


def is_read_only(args: List[str]) -> bool:
    """True when an az command line only reads: `az ... show|list|list-*`, or `az rest --method get`."""
    words = []
    for a in args:
        if a.startswith("-"):
            break
        words.append(a)
    if not words:
        return False
    if words[0] == "rest":
        lowered = [a.lower() for a in args]
        try:
            method = lowered[lowered.index("--method") + 1]
        except (ValueError, IndexError):
            method = "get"  # az rest defaults to GET
        try:
            url = args[lowered.index("--url") + 1]
        except (ValueError, IndexError):
            url = ""
        if method == "post" and EVALUATE_ONLY.search(url):
            return True
        if "--body" in lowered or "-b" in lowered:
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


def tool_version(cmd: List[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return res.stdout


class Ctx:
    def __init__(self, values: Dict, *, az: Optional[Callable] = None, mode: str = "kit", stage: str = "pre-install",
                 features=(), show_names: bool = False, env: Optional[Dict] = None,
                 which: Optional[Callable] = None, run_tool: Optional[Callable] = None,
                 isdir: Optional[Callable] = None, python_version=None):
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
