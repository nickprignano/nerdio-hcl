"""Read-only readiness checks for the prepare phase.

A thin shim over the readiness engine (`readiness/`, decision 0026), kept so the callers that
used this module before the engine existed keep working. New checks go in readiness/checks/.
"""

from __future__ import annotations

import json

from engine import az_json
from readiness import main, report
from readiness.checks.subscription import PROVIDERS  # noqa: F401  (re-exported for callers)
from readiness.model import FAIL, MANUAL, PASS, WARN, Result  # noqa: F401


def run(values: dict, az=None, **kw) -> list[Result]:
    """Today's pre-install checks in kit mode, as a list of results."""
    _, results, _ = main.evaluate(values, az=az or az_json, **kw)
    return [r for r in results if r.status != "skipped"]


def nearby_regions(location: str, az=None) -> list[str]:
    """Physical regions in the same geography group as the configured one (US, Europe, ...)."""
    rows = (az or az_json)(["account", "list-locations", "--query",
                            "[?metadata.regionType=='Physical'].{name:name, group:metadata.geographyGroup}"]) or []
    group = next((r.get("group") for r in rows if r.get("name") == location), None)
    # Skip canary (euap) and staging regions; they're listed but not for general use.
    names = [r["name"] for r in rows if group and r.get("group") == group
             and not r["name"].endswith(("euap", "stg"))]
    return sorted(set(names) | {location})


def scan_regions(values: dict, subscription_id: str, regions: list[str], progress=None, az=None) -> dict[str, list[Result]]:
    out = {}
    for region in regions:
        if progress:
            progress(region)
        out[region] = [r for r in main.region_results(values, subscription_id, region, az=az or az_json)
                       if r.status != "skipped"]
    return out


def as_json(results: list[Result]) -> str:
    """The bare list this module printed before the engine (`./nerdio preflight --format legacy`)."""
    return json.dumps(report.legacy(results), indent=2)

