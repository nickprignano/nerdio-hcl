"""kit.*: what the kit's own Terraform checks last reported (kit mode, after the install)."""

from __future__ import annotations

import json

from ..model import INSTALLED, WIZARD, check

KB = "docs/knowledge/nerdio/readiness.md#kit"
STAGES = ("platform", "config")


@check("kit.terraform_checks", "Terraform checks", needs="read access to the Terraform state (it holds sensitive values)", kb=KB,
       stages=[INSTALLED, WIZARD], modes=["kit"], account=False,
       source="https://developer.hashicorp.com/terraform/language/checks", reads=["terraform state pull"])
def terraform_checks(ctx, c):
    """`check` blocks (nerdio_health and others) as of the last plan or apply, from each stage's state.
    The state holds sensitive values, so this is the one default check that loads them: only
    check_results is kept, and nothing else from the state leaves this function."""
    import engine

    env = ctx.values.get("_env") or "example"
    schema = engine.load_schema()
    out, seen = [], 0
    for stage in STAGES:
        folder = engine.stage_dir(schema, stage, env)
        if not ctx.isdir(str(folder / ".terraform")):
            continue
        try:
            results = json.loads(ctx.run_tool(["terraform", f"-chdir={folder}", "state", "pull"]) or "{}").get("check_results")
        except (ValueError, AttributeError):
            out.append(c.warn(f"couldn't read the {stage} stage's state"))
            continue
        for item in results or []:
            seen += 1
            if item.get("status") in ("fail", "error"):
                messages = [m for o in item.get("objects") or [] for m in o.get("failure_messages") or []]
                out.append(c.fail(f"{item.get('config_addr')} ({stage}): " + ("; ".join(messages) or item["status"]),
                                  f"./nerdio plan --env {env}, then fix what the check names"))
    if not seen and not out:
        return c.skip("no initialised stage with check results here (run in the pipeline's verify job)")
    return out or [c.ok(f"all {seen} Terraform checks passed at the last plan or apply")]
