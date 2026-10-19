"""Run the engine and render its output: what every front door calls."""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Tuple

from . import report, runner
from .context import Ctx
from .model import PRE, Result


def evaluate(values: dict, *, mode: str = "kit", stage: str = PRE, features: Iterable[str] = (),
             only: Iterable[str] = (), skip: Iterable[str] = (), show_names: bool = False,
             az: Optional[Callable] = None, **ctx_kw) -> Tuple[Ctx, List[Result], str]:
    ctx = Ctx(values, az=az, mode=mode, stage=stage, features=features, show_names=show_names, **ctx_kw)
    started = report.now()
    results = runner.run(ctx, runner.select(stage, features, mode, only, skip))
    return ctx, results, started


def region_results(values: dict, subscription_id: str, location: str, *, az: Optional[Callable] = None,
                   mode: str = "kit") -> List[Result]:
    """The checks that change with the region, for one region (`./nerdio preflight --regions`)."""
    ctx = Ctx(dict(values, location=location), az=az, mode=mode)
    ctx.acct = {"id": subscription_id}
    return runner.run(ctx, runner.select(PRE, mode=mode, region_only=True))


def render(ctx: Ctx, results: List[Result], started: str, fmt: str, *, redact: bool = True,
           parameters_version: str = "") -> str:
    doc = report.document(ctx, results, started=started, parameters_version=parameters_version)
    text = report.as_text(doc, results, fmt)
    if not redact:
        return text
    import redact as redactor  # scripts/nerdio/redact.py, bundled beside this package in the zipapp

    return redactor.redact(text, redactor.terms_from(ctx.acct or {}))
