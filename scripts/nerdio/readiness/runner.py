"""Pick the checks that apply and run them."""

from __future__ import annotations

from typing import Iterable, List, Optional

from . import checks  # noqa: F401  (registers every check)
from .context import Ctx, WriteRefused
from .model import FEATURES, INSTALLED, REGISTRY, WIZARD, Check, Result


class UsageError(Exception):
    """Bad --stage, --features, --only or --skip."""


def parse_features(text: str) -> List[str]:
    items = [f.strip() for f in (text or "").split(",") if f.strip()]
    if "all" in items:
        return list(FEATURES)
    unknown = [f for f in items if f not in FEATURES]
    if unknown:
        raise UsageError("unknown feature " + ", ".join(unknown) + "; pick from " + ", ".join(FEATURES) + " or all")
    return items


def parse_ids(text: str) -> List[str]:
    items = [i.strip() for i in (text or "").split(",") if i.strip()]
    unknown = [i for i in items if i not in REGISTRY]
    if unknown:
        raise UsageError("unknown check " + ", ".join(unknown) + "; ./nerdio preflight --list shows them")
    return items


def applies(c: Check, stage: str) -> bool:
    """A check runs in its own stages; post-wizard also re-runs the post-install checks, since an
    installed Nerdio Manager has to stay healthy through and after its wizard."""
    return stage in c.stages or (stage == WIZARD and INSTALLED in c.stages)


def select(stage: str, features: Iterable[str] = (), mode: str = "kit", only: Iterable[str] = (),
           skip: Iterable[str] = (), region_only: bool = False) -> List[Check]:
    features, only, skip = set(features), set(only), set(skip)
    out = []
    for c in REGISTRY.values():
        if only and c.id not in only:
            continue
        if c.id in skip or mode not in c.modes:
            continue
        if region_only and not c.region:
            continue
        if not only and not applies(c, stage):
            continue
        if not only and not c.core and not features & set(c.features):
            continue
        out.append(c)
    return out


def missing_input(ctx: Ctx, c: Check) -> Optional[str]:
    gone = [k for k in c.inputs if ctx.values.get(k) in (None, "", [])]
    return ", ".join(gone) if gone else None


def run_check(ctx: Ctx, c: Check) -> List[Result]:
    if ctx.stopped:
        return [c.skip(f"stopped: {ctx.stopped}")]
    if c.account and not ctx.acct:
        return [c.skip("needs a signed-in az account")]
    gone = missing_input(ctx, c)
    if gone:
        return [c.skip(f"needs input: {gone}")]
    try:
        got = c.run(ctx, c)
    except WriteRefused:
        raise
    except Exception as exc:  # a broken check must never turn into a pass or end the run
        return [c.warn(f"the check stopped unexpectedly ({type(exc).__name__})",
                       "Rerun; if it repeats, report it with ./nerdio redact")]
    return [got] if isinstance(got, Result) else list(got or [])


def run(ctx: Ctx, selected: List[Check]) -> List[Result]:
    results: List[Result] = []
    for c in selected:
        results += run_check(ctx, c)
    return results

