"""The probe tier: opt-in checks that change something, because some answers can't be read.

Each probe says exactly what it does, needs a typed yes at a terminal, and never runs in the
deploy pipeline or for the setup chat. Probes call az directly, outside Ctx and its read-only
guard: the guard is what keeps every other check from doing this.
"""

from __future__ import annotations

import sys
from typing import Callable, Dict, List, Optional, TextIO

from . import context

# Our own script (not Microsoft's tool): find the newest AVD agent and run the Required URL Check
# tool that ships with it, WVDAgentUrlTool.exe.
URL_CHECK_SCRIPT = (
    "$root = 'C:\\Program Files\\Microsoft RDInfra'; "
    "$agent = Get-ChildItem $root -Directory -Filter 'RDAgent_*' -ErrorAction SilentlyContinue | "
    "Sort-Object { [version]($_.Name -replace '^RDAgent_', '') } -Descending | Select-Object -First 1; "
    "if (-not $agent) { 'NERDIO-PROBE: no AVD agent'; exit 0 }; "
    "$tool = Join-Path $agent.FullName 'WVDAgentUrlTool.exe'; "
    "if (-not (Test-Path $tool)) { 'NERDIO-PROBE: no URL tool'; exit 0 }; "
    "& $tool"
)
PROBES = {
    "url-check": {
        "needs": "Virtual Machine Contributor on that VM",
        "what": "runs Microsoft's Required URL Check tool (WVDAgentUrlTool.exe, installed with the AVD agent) on "
                "one session host through Run Command. Run Command runs the script as SYSTEM on that VM. It creates "
                "no Azure resource; Azure keeps a record of the run in the VM's activity log.",
    },
}
# Where nobody can answer the question: the deploy pipeline. (The setup chat never offers probes.)
NO_PROBES = ("GITHUB_ACTIONS", "TF_IN_AUTOMATION")


class ProbeRefused(Exception):
    """The probe can't run here, or the person didn't say yes."""


def describe(name: str, target: str) -> str:
    p = PROBES[name]
    return f"Probe {name}: {p['what']}\nTarget: {target}\nNeeds: {p['needs']}\n"


def url_check_lines(message: str) -> Dict:
    """What the tool printed, split into a status. Its output format is unverified, so anything
    that isn't plainly fine is a `warn` with the lines shown."""
    lines = [ln.strip() for ln in (message or "").splitlines() if ln.strip()]
    text = "\n".join(lines).lower()
    if "nerdio-probe: no avd agent" in text or "nerdio-probe: no url tool" in text:
        return {"status": "warn", "detail": "the host has no AVD agent or URL tool", "lines": lines}
    bad = [ln for ln in lines if "not accessible" in ln.lower() or "unaccessible" in ln.lower()]
    if bad:
        return {"status": "fail", "detail": f"{len(bad)} required URLs aren't reachable", "lines": lines}
    if "accessible" in text:
        return {"status": "pass", "detail": "every required URL is reachable", "lines": lines}
    return {"status": "warn", "detail": "couldn't read the tool's output", "lines": lines}


def run(name: str, *, vm: Optional[str], env: Dict, interactive: bool, ask: Callable[[str], str],
        out: TextIO, az: Optional[Callable] = None, masked: Callable[[str], str] = lambda s: s) -> Dict:
    if name not in PROBES:
        raise ProbeRefused(f"unknown probe {name}")
    if any(env.get(k) for k in NO_PROBES) or not interactive:
        raise ProbeRefused("probes change something, so they only run at a terminal where you can answer; "
                           "never in the pipeline or for the chat")
    if not vm or "/providers/Microsoft.Compute/virtualMachines/" not in vm:
        raise ProbeRefused("--vm takes the session host's resource ID (az vm show -g <group> -n <name> --query id)")
    out.write(describe(name, masked(vm)))
    if ask("Type yes to run it: ").strip().lower() != "yes":
        raise ProbeRefused("not run: you didn't type yes")
    az = az or run_az_write
    data = az(["vm", "run-command", "invoke", "--ids", vm, "--command-id", "RunPowerShellScript",
               "--scripts", URL_CHECK_SCRIPT])
    if data is None:
        return {"status": "no-access", "detail": f"Run Command failed (needs {PROBES[name]['needs']})", "lines": []}
    message = "\n".join(v.get("message", "") for v in (data.get("value") or []) if isinstance(v, dict))
    return url_check_lines(message)


def run_az_write(args: List[str]):
    """az for a probe, after the person said yes. Only probe.run calls it."""
    return context.run_az(args)


def main(name: str, vm: Optional[str], *, env: Dict, interactive: bool, ask: Callable[[str], str],
         out: TextIO, err: TextIO, az: Optional[Callable] = None) -> int:
    """`--probe NAME`: run it and print the masked result. Exit 0 pass or warn, 1 fail, 2 refused."""
    import redact as redactor

    def masked(text: str) -> str:
        return redactor.redact(text, [])
    try:
        result = run(name, vm=vm, env=env, interactive=interactive, ask=ask, out=out, az=az, masked=masked)
    except ProbeRefused as exc:
        err.write(f"stopped: {exc}\n")
        return 2
    return report(result, out, masked)


def report(result: Dict, out: TextIO = sys.stdout, masked: Callable[[str], str] = lambda s: s) -> int:
    out.write(f"{result['status']}: {result['detail']}\n")
    for ln in result.get("lines", [])[:60]:
        out.write(f"  {masked(ln)}\n")
    return 1 if result["status"] == "fail" else 0
