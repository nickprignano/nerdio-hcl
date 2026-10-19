"""The check catalogue, from the registry: `./nerdio preflight --list` and the KB page's table."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

from . import checks  # noqa: F401  (registers every check)
from .model import REGISTRY, Check

STAGE_LETTER = {"pre-install": "P", "post-install": "I", "post-wizard": "W"}
KB_PAGE = Path(__file__).resolve().parents[3] / "docs" / "knowledge" / "nerdio" / "readiness.md"
BEGIN = "<!-- BEGIN GENERATED: readiness-catalogue (./nerdio preflight --list --write) -->"
END = "<!-- END GENERATED: readiness-catalogue -->"


def entries(checks_: Optional[List[Check]] = None) -> List[dict]:
    return [{"id": c.id, "domain": c.domain, "title": c.title, "stages": list(c.stages), "features": list(c.features),
             "core": c.core, "modes": list(c.modes), "needs": c.needs, "reads": list(c.reads), "writes": c.writes,
             "kb": c.kb, "source": c.source} for c in (checks_ or list(REGISTRY.values()))]


def _cell(text: str) -> str:
    return text.replace("|", "/")


def markdown() -> str:
    rows = ["| ID | Stage | Check | Feature | Right needed | Reads with |", "|---|---|---|---|---|---|"]
    for e in sorted(entries(), key=lambda e: e["id"]):
        stages = ", ".join(STAGE_LETTER[s] for s in e["stages"])
        feat = ", ".join(e["features"]) if e["features"] else "core"
        if e["features"] and e["core"]:
            feat = "core, " + feat
        modes = "" if len(e["modes"]) > 1 else f" ({e['modes'][0]} only)"
        rows.append(f"| `{e['id']}` | {stages} | [{_cell(e['title'])}]({e['source']}){modes} | {feat} | "
                    f"{_cell(e['needs'])} | {_cell(', '.join(e['reads']) or '-')} |")
    return "\n".join(rows)


def console() -> str:
    lines = []
    for e in sorted(entries(), key=lambda e: e["id"]):
        stages = "".join(STAGE_LETTER[s] for s in e["stages"])
        feat = ",".join((["core"] if e["core"] else []) + e["features"])
        lines.append(f"{e['id']:<26} {stages:<4} {feat:<12} {e['title']} (needs {e['needs']})")
    return "\n".join(lines)


def as_text(fmt: str) -> str:
    if fmt in ("json", "legacy"):
        return json.dumps(entries(), indent=2)
    if fmt == "md":
        return markdown() + "\n"
    return console()


def _block() -> str:
    return f"{BEGIN}\n{markdown()}\n{END}"


def page_in_sync(page: Path = KB_PAGE) -> bool:
    text = page.read_text(encoding="utf-8") if page.exists() else ""
    return _block() in text


def write_page(page: Path = KB_PAGE) -> None:
    text = page.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        raise ValueError(f"{page} has no generated catalogue markers")
    page.write_text(pattern.sub(lambda _: _block(), text), encoding="utf-8")
