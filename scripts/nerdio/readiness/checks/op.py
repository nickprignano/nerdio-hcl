"""op.*: the operator's tools, cloud, sign-in and Cloud Shell."""

from __future__ import annotations

import json
import sys

from .. import cloud as cloudmod
from ..model import check

KB = "docs/knowledge/nerdio/readiness.md#operator"
CLOUD_SHELL_TOOLS = "https://learn.microsoft.com/azure/cloud-shell/features"


def version_at_least(have: str, want: str) -> bool:
    def parts(v: str):
        return [int(x) for x in v.split("-")[0].split(".")[:3]]
    try:
        return parts(have) >= parts(want)
    except ValueError:
        return False


@check("op.cloud", "Azure cloud", needs="none", kb=KB, account=False,
       reads=["az cloud show"], stages=["pre-install", "post-install", "post-wizard"],
       source="https://learn.microsoft.com/cli/azure/manage-clouds-azure-cli")
def azure_cloud(ctx, c):
    found = cloudmod.detect(ctx.az)
    if found is None:
        return c.warn("couldn't read the active cloud from az; using the commercial cloud's endpoints",
                      "az cloud show")
    ctx.cloud = found
    if found.name == "AzureCloud":
        return c.ok("AzureCloud (commercial)")
    if found.name in cloudmod.KNOWN:
        return c.warn(f"{found.name}: endpoints come from az, but the kit and these checks are only proven on AzureCloud")
    ctx.stopped = f"{found.name} isn't a cloud these checks support"
    return c.fail(f"{found.name} isn't a cloud these checks support", "az cloud set --name AzureCloud")


@check("op.tools", "Tools", needs="none", kb=KB, account=False, reads=["PATH"], source=CLOUD_SHELL_TOOLS)
def tools(ctx, c):
    """Kit mode: terraform 1.11+, az, jq, git. Standalone: az, python3 3.9+ and git only (jq isn't on
    Cloud Shell's documented tool list, and nothing standalone needs terraform)."""
    if ctx.mode == "standalone":
        return standalone_tools(ctx, c)
    out = []
    if not ctx.which("terraform"):
        out.append(c.fail("terraform isn't on PATH",
                          "Cloud Shell includes it; elsewhere see https://developer.hashicorp.com/terraform/install",
                          title="Terraform"))
    else:
        try:
            ver = json.loads(ctx.run_tool(["terraform", "version", "-json"]))["terraform_version"]
        except (ValueError, KeyError, TypeError):
            ver = "unknown"
        if version_at_least(ver, "1.11.0"):
            out.append(c.ok(f"{ver} (the kit needs 1.11 or later)", title="Terraform"))
        else:
            out.append(c.fail(f"{ver} is older than 1.11",
                              "Install a newer one to ~/bin, e.g. NME_TF_VERSION=1.16.6 with the Cloud Shell bootstrap script",
                              title="Terraform"))
    for tool in ("az", "jq", "git"):
        out.append(c.ok("found", title=tool) if ctx.which(tool)
                   else c.fail("not on PATH", f"Install {tool}; Azure Cloud Shell already has it", title=tool))
    return out


def standalone_tools(ctx, c):
    have = ctx.python_version or sys.version_info[:2]
    out = [c.ok(f"{have[0]}.{have[1]}", title="python3") if tuple(have) >= (3, 9)
           else c.fail(f"{have[0]}.{have[1]} is older than 3.9", "Run it from Azure Cloud Shell, which has 3.9 or later",
                       title="python3")]
    for tool in ("az", "git"):
        out.append(c.ok("found", title=tool) if ctx.which(tool)
                   else c.fail("not on PATH", f"Install {tool}; Azure Cloud Shell already has it", title=tool))
    return out


@check("op.cloudshell_storage", "Cloud Shell storage", needs="none", kb=KB, account=False, modes=["kit"],
       reads=["environment", "~/clouddrive"], source="https://learn.microsoft.com/azure/cloud-shell/persisting-shell-storage")
def cloud_shell_storage(ctx, c):
    if not ctx.env.get("AZUREPS_HOST_ENVIRONMENT", "").startswith("cloud-shell") and not ctx.env.get("ACC_CLOUD"):
        return c.skip("not running in Cloud Shell")
    if ctx.isdir(ctx.env.get("HOME", "~") + "/clouddrive"):
        return c.ok("persistent, so Terraform state survives the session")
    return c.fail("this Cloud Shell is ephemeral; Terraform state would be lost when it closes",
                  "Settings > Reset user settings, then reopen Bash and choose Mount storage account")


@check("op.signin", "Azure sign-in", needs="none", kb=KB, account=False, reads=["az account show"],
       stages=["pre-install", "post-install", "post-wizard"],
       source="https://learn.microsoft.com/cli/azure/authenticate-azure-cli")
def signin(ctx, c):
    acct = ctx.az(["account", "show"])
    if not acct:
        return c.fail("az isn't signed in", "az login")
    ctx.acct = acct
    user = acct.get("user", {})
    return c.ok(f"subscription \"{ctx.name('subscription', acct.get('name') or '')}\" as a {user.get('type', 'user')}")
