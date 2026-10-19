"""Statuses, results and the check registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

PASS, WARN, FAIL, MANUAL, SKIPPED, NO_ACCESS = "pass", "warn", "fail", "manual", "skipped", "no-access"
STATUSES = (FAIL, WARN, NO_ACCESS, MANUAL, PASS, SKIPPED)  # most to least urgent

STAGES = ("pre-install", "post-install", "post-wizard")
PRE, INSTALLED, WIZARD = STAGES
FEATURES = ("app-mgmt", "app-attach", "insights", "rbac", "self-service", "hardening", "scripted-actions",
            "automation", "ai")
MODES = ("kit", "standalone")

# ID prefix -> domain name, in the order the console report shows them.
DOMAINS = {
    "op": "operator", "id": "identity", "sub": "subscription", "net": "network", "avd": "avd",
    "nme": "nerdio", "hard": "hardening", "app": "app-mgmt", "attach": "app-attach", "ins": "insights",
    "rbac": "rbac", "self": "self-service", "sa": "scripted-actions", "auto": "automation", "ai": "ai",
    "kit": "kit",
}
ID_RE = re.compile(r"^([a-z]+)\.[a-z0-9_]+$")


@dataclass
class Result:
    id: str
    status: str
    title: str
    detail: str
    fix: str = ""
    kb: str = ""
    source: str = ""
    needs: str = ""
    domain: str = ""

    @property
    def check(self) -> str:
        """What the pre-registry preflight called the title; kept for its callers."""
        return self.title


@dataclass
class Check:
    id: str
    title: str
    run: Callable
    needs: str
    kb: str
    source: str
    stages: Tuple[str, ...] = (PRE,)
    features: Tuple[str, ...] = ()
    core: bool = True  # runs without --features; a feature-only check sets False
    reads: Tuple[str, ...] = ()
    writes: bool = False
    modes: Tuple[str, ...] = MODES
    inputs: Tuple[str, ...] = ()  # values it needs; missing ones make it `skipped`
    account: bool = True  # needs a signed-in az account
    region: bool = False  # re-run per region by `./nerdio preflight --regions`

    @property
    def domain(self) -> str:
        return DOMAINS[self.id.split(".")[0]]

    def result(self, status: str, detail: str, fix: str = "", title: Optional[str] = None,
               kb: Optional[str] = None) -> Result:
        return Result(id=self.id, status=status, title=title or self.title, detail=detail, fix=fix,
                      kb=self.kb if kb is None else kb, source=self.source, needs=self.needs, domain=self.domain)

    def ok(self, detail: str, **kw) -> Result:
        return self.result(PASS, detail, **kw)

    def warn(self, detail: str, fix: str = "", **kw) -> Result:
        return self.result(WARN, detail, fix, **kw)

    def fail(self, detail: str, fix: str = "", **kw) -> Result:
        return self.result(FAIL, detail, fix, **kw)

    def manual(self, detail: str, fix: str = "", **kw) -> Result:
        return self.result(MANUAL, detail, fix, **kw)

    def skip(self, detail: str, **kw) -> Result:
        return self.result(SKIPPED, detail, **kw)

    def no_access(self, detail: str, fix: str = "", **kw) -> Result:
        return self.result(NO_ACCESS, detail, fix or f"Needs {self.needs}", **kw)


REGISTRY: Dict[str, Check] = {}


def check(id: str, title: str, *, needs: str, kb: str, source: str, **meta) -> Callable:
    """Register a check. The decorated function takes (ctx, check) and returns a Result or a list."""
    def wrap(fn: Callable) -> Callable:
        if id in REGISTRY:
            raise ValueError(f"duplicate check id {id}")
        if meta.get("features") and "core" not in meta:
            meta["core"] = False
        for key in ("stages", "features", "reads", "modes", "inputs"):
            if key in meta:
                meta[key] = tuple(meta[key])
        REGISTRY[id] = Check(id=id, title=title, run=fn, needs=needs, kb=kb, source=source, **meta)
        return fn
    return wrap


def contract_problems(checks: List[Check]) -> List[str]:
    """What CI insists on for every registered check (spec section 3, check registry)."""
    problems = []
    for c in checks:
        m = ID_RE.match(c.id)
        if not m or m.group(1) not in DOMAINS:
            problems.append(f"{c.id}: id must be <domain>.<name> with a known domain")
        for key in ("needs", "kb", "source", "title"):
            if not getattr(c, key):
                problems.append(f"{c.id}: missing {key}")
        if c.writes:
            problems.append(f"{c.id}: default-tier checks never write")
        if not c.source.startswith("https://"):
            problems.append(f"{c.id}: source must be an https link")
        for s in c.stages:
            if s not in STAGES:
                problems.append(f"{c.id}: unknown stage {s}")
        for f in c.features:
            if f not in FEATURES:
                problems.append(f"{c.id}: unknown feature {f}")
        for mode in c.modes:
            if mode not in MODES:
                problems.append(f"{c.id}: unknown mode {mode}")
        if not c.core and not c.features:
            problems.append(f"{c.id}: a non-core check needs at least one feature")
    return problems
