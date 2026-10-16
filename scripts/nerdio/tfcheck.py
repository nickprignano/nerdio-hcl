"""Let Terraform itself judge the rendered tfvars.

Copies only the `variable` blocks the tfvars set out of a stage's variables.tf into a scratch
directory and runs `terraform plan` there. With no resources and no providers, that needs no
credentials or downloads, yet it applies Terraform's own type conversion and validation blocks
to the values, so the schema can't drift from the real variables unnoticed.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

VAR_RE = re.compile(r'^variable\s+"([^"]+)"\s*\{', re.M)


def variable_blocks(variables_tf: str) -> dict[str, str]:
    """Top-level variable blocks by name, found by brace matching (strings and heredocs included)."""
    blocks = {}
    for m in VAR_RE.finditer(variables_tf):
        depth, i = 0, m.end() - 1
        in_str = False
        while i < len(variables_tf):
            ch = variables_tf[i]
            if in_str:
                if ch == "\\":
                    i += 1
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blocks[m.group(1)] = variables_tf[m.start(): i + 1]
                    break
            i += 1
    return blocks


def attribute_declared(block: str, attr: str) -> bool:
    """Whether an object attribute name appears in a variable's type (a cheap guard against typos)."""
    return re.search(rf"(?m)^\s*{re.escape(attr)}\s*=", block) is not None


def declared_variables(stage_dir: Path) -> dict[str, str]:
    blocks = {}
    for tf in sorted(stage_dir.glob("*.tf")):
        blocks.update(variable_blocks(tf.read_text(encoding="utf-8")))
    return blocks


def terraform_available() -> bool:
    return shutil.which("terraform") is not None


def check_stage(stage_dir: Path, tfvars: dict) -> tuple[bool, str]:
    """Return (ok, message). Unknown variable names are reported without running Terraform."""
    declared = declared_variables(stage_dir)
    unknown = sorted(set(tfvars) - set(declared))
    if unknown:
        return False, f"{stage_dir.name}: not declared in variables.tf: {', '.join(unknown)}"
    if not terraform_available():
        return True, f"{stage_dir.name}: variable names match (terraform not found, so types weren't checked)"
    with tempfile.TemporaryDirectory(prefix="nerdio-tfcheck-") as tmp:
        work = Path(tmp)
        (work / "variables.tf").write_text("\n\n".join(declared[name] for name in sorted(tfvars)) + "\n", encoding="utf-8")
        (work / "check.auto.tfvars.json").write_text(json.dumps(tfvars), encoding="utf-8")
        for args in (["init", "-backend=false", "-input=false"], ["plan", "-input=false", "-lock=false", "-refresh=false"]):
            res = subprocess.run(["terraform", f"-chdir={work}", *args, "-no-color"], capture_output=True, text=True, check=False)
            if res.returncode != 0:
                detail = "\n".join(line for line in (res.stderr or res.stdout).splitlines() if line.strip())
                return False, f"{stage_dir.name}: Terraform rejected the values:\n{detail}"
    return True, f"{stage_dir.name}: Terraform accepted all {len(tfvars)} variables"
