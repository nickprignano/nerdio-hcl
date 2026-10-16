"""Generate the GitHub Actions form (workflow_dispatch inputs) from the schema.

The inputs block in .github/workflows/configure.yml sits between two marker comments and is
written by `./nerdio form --write`. CI runs `./nerdio form --check` so the form can't drift
from the schema.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "configure.yml"
BEGIN = "      # BEGIN GENERATED INPUTS (./nerdio form --write; edit schema/parameters.json instead)"
END = "      # END GENERATED INPUTS"


def _quote(text: str) -> str:
    return json.dumps(text)


def inputs_block(schema: dict) -> str:
    lines = [BEGIN]
    for p in schema["parameters"]:
        if not p.get("form"):
            continue
        lines.append(f"      {p['id']}:")
        default = p.get("default")
        # Templated defaults (like the random prefix ending) are worked out by ./nerdio init.
        templated = not isinstance(default, (bool, int, list)) and (not isinstance(default, str) or "{" in default)
        description = p["question"] + (" Leave blank for the default." if templated else "")
        lines.append(f"        description: {_quote(description)}")
        lines.append(f"        required: {'false' if templated else 'true'}")
        if p["type"] == "bool":
            lines.append("        type: boolean")
            lines.append(f"        default: {'true' if default else 'false'}")
        elif p["type"] == "enum":
            lines.append("        type: choice")
            lines.append("        options:")
            for c in p["choices"]:
                if c.get("supported", True):
                    lines.append(f"          - {c['value']}")
            lines.append(f"        default: {default}")
        elif p["type"] == "int":
            lines.append("        type: number")
            lines.append(f"        default: {default}")
        else:
            lines.append("        type: string")
            lines.append('        default: ""' if templated else f"        default: {_quote(default)}")
    lines.append(END)
    return "\n".join(lines)


def current(path: Path = WORKFLOW) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8")
    start = text.index(BEGIN)
    end = text.index(END) + len(END)
    return text[:start], text[start:end], text[end:]


def write(schema: dict, path: Path = WORKFLOW) -> bool:
    head, block, tail = current(path)
    new = inputs_block(schema)
    if new == block:
        return False
    path.write_text(head + new + tail, encoding="utf-8")
    return True


def in_sync(schema: dict, path: Path = WORKFLOW) -> bool:
    _, block, _ = current(path)
    return block == inputs_block(schema)
