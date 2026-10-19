"""./nerdio: the kit's engine entry point. Every front door (chat, this CLI, the Actions form) calls it.

  ./nerdio use trial            remember this tenant and subscription as "trial" (first time), then
                                check and switch to it; other commands then refuse the wrong tenant
  ./nerdio init                 interview, then write the tfvars (Terraform checks them)
  ./nerdio init --advanced      also ask the advanced questions
  ./nerdio init --set k=v ...   answer without prompts (add --non-interactive to never prompt)
  ./nerdio questions --phase discover   the questions as JSON, for the setup chatbot
  ./nerdio show                 the current answers and where each value came from
  ./nerdio preflight            read-only readiness checks (roles, providers, region, quota)
  ./nerdio preflight --list     the check catalogue; --stage, --features, --only and --skip pick checks
  ./nerdio preflight --regions  find regions where the VM size, quota, App Service and SQL all pass
  ./nerdio redact --tail 40     the bootstrap's last output with IDs, IPs and tenant names masked, to share
  ./nerdio fix quota            ask Azure Support for App Service quota (shows it, then asks yes)
  ./nerdio fix vcpu --family F --limit N   raise a VM family's vCPU quota (shows it, then asks yes)
  ./nerdio fix roles            activate eligible PIM roles the kit needs (shows them, then asks yes)
  ./nerdio schema check         check the schema against the Terraform variables (CI)
  ./nerdio form --write|--check generate or check the Actions form from the schema
  ./nerdio assistant --admin-group "AVD Admins"   deploy the setup chatbot into this tenant
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import claude_federation
import engine
import fix
import form
import preflight
import profiles
import redact
import tfcheck
from readiness import catalogue as readiness_catalogue
from readiness import main as readiness_main
from readiness import report as readiness_report
from readiness import runner as readiness_runner
from readiness import standalone as readiness_standalone
from readiness.model import FEATURES as READINESS_FEATURES
from readiness.model import STAGES as READINESS_STAGES

ASKED_PHASES = ["discover", "configure"]
GUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def mask(text: str) -> str:
    return GUID_RE.sub(lambda m: m.group(0)[:4] + "…" if m.group(0) != "00000000-0000-0000-0000-000000000000" else m.group(0), text)


def askable(param: dict, advanced: bool) -> bool:
    ask = param.get("ask", "always")
    return ask == "always" or (ask == "advanced" and advanced)


def apply_sets(schema: dict, answers: dict, sets: list[str]) -> list[str]:
    params = engine.params_by_id(schema)
    problems = []
    for item in sets:
        key, sep, raw = item.partition("=")
        key = key.strip()
        if not sep or key not in params:
            problems.append(f"--set {item}: unknown parameter {key!r}")
            continue
        if "source" in params[key]:
            problems.append(f"--set {key}: read from the signed-in account (ARM_* or az), not set by hand")
            continue
        if raw.strip() == "":
            answers.pop(key, None)  # blank means "use the default" (Actions sends blanks)
            continue
        try:
            value = engine.parse_input(params[key], raw)
            engine.validate(params[key], value)
        except engine.AnswerError as exc:
            problems.append(f"{key}: {exc}")
            continue
        answers[key] = value
    return problems


def show_value(value) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(value) if value else "(none)"
    return str(value)


def prompt(param: dict, current, position: str):
    """Ask one question on the terminal. Returns a typed value, or None to keep the current one."""
    print(f"\n[{position}] {param['question']}")
    print(textwrap.indent(textwrap.fill(param["help"], 92), "  "))
    if param["type"] == "enum":
        for i, c in enumerate(param["choices"], 1):
            note = "" if c.get("supported", True) else "  (not supported yet)"
            print(f"    {i}. {c.get('label', c['value'])}{note}")
    while True:
        hint = "Y/n" if current is True else "y/N" if current is False else show_value(current)
        raw = input(f"  [{hint}] (? for sources) > ").strip()
        if raw == "":
            return None
        if raw == "?":
            refs = param.get("kb", []) + param.get("sources", [])
            print(textwrap.indent("\n".join(refs) if refs else "No sources listed for this one.", "    "))
            continue
        if param["type"] == "enum" and raw.isdigit() and 1 <= int(raw) <= len(param["choices"]):
            raw = param["choices"][int(raw) - 1]["value"]
        try:
            value = engine.parse_input(param, raw)
            engine.validate(param, value)
            return value
        except engine.AnswerError as exc:
            print(f"  ✗ {exc}")


def interview(schema: dict, answers: dict, sources: dict, phases: list[str], advanced: bool) -> None:
    asked = 0
    for p in schema["parameters"]:
        if p["phase"] not in phases:
            continue
        resolved = engine.resolve(schema, answers, sources)
        if p["id"] not in resolved.active or not askable(p, advanced):
            continue
        asked += 1
        value = prompt(p, resolved.values.get(p["id"]), f"{p['phase']} · {asked}")
        if value is not None:
            answers[p["id"]] = value


def fix_errors_interactively(schema: dict, answers: dict, sources: dict) -> engine.Resolved:
    params = engine.params_by_id(schema)
    for _ in range(5):
        resolved = engine.resolve(schema, answers, sources)
        fixable = {k: v for k, v in resolved.errors.items() if "source" not in params[k]}
        if not fixable:
            return resolved
        for pid, err in fixable.items():
            print(f"\n✗ {pid}: {err}")
            value = prompt(params[pid], resolved.values.get(pid), "fix")
            if value is not None:
                answers[pid] = value
    return engine.resolve(schema, answers, sources)


def check_profile() -> bool:
    ok, message = profiles.guard()
    if message:  # stderr, so --json output stays clean
        print(("" if ok else "✗ ") + message, file=sys.stderr)
    return ok


def cmd_use(args) -> int:
    """Save the signed-in tenant and subscription for a kit environment once; check it after that."""
    if not args.env:
        cur = profiles.current()
        for env in profiles.names():
            prof = profiles.load(env) or {}
            print(f"{'*' if env == cur else ' '} {env:<16} {prof.get('subscription_name', '')}")
        if not profiles.names():
            print("No profiles yet. Sign in to the subscription and run ./nerdio use <env>, e.g. ./nerdio use trial")
        return 0
    if not profiles.ENV_RE.match(args.env):
        print("✗ Use a short lowercase name: letters, digits and dashes, starting with a letter (e.g. trial, prod)", file=sys.stderr)
        return 1
    if args.forget:
        print(f"Forgot {args.env}" if profiles.forget(args.env) else f"No profile named {args.env}")
        return 0
    if profiles.load(args.env) is None:
        account = engine.az_json(["account", "show"])
        if not account:
            print("✗ Not signed in: run az login (Cloud Shell already is), then try again.", file=sys.stderr)
            return 1
        where = account.get("tenantDisplayName") or account.get("tenantDefaultDomain") or "this tenant"
        print(f"Save subscription {account.get('name', '?')!r} in {where} as {args.env!r}?")
        if not args.yes and input("Type yes to save: ").strip().lower() != "yes":
            print("Nothing saved.")
            return 1
        profiles.save(args.env, account)
        print(f"Saved to {profiles.path(args.env)} (only you can read it; it's not in the repo).")
    ok, message = profiles.ensure(args.env)
    print(("" if ok else "✗ ") + message, file=sys.stdout if ok else sys.stderr)
    if not ok:
        return 1
    profiles.set_current(args.env)
    return 0


def cmd_init(args) -> int:
    if not args.placeholder_ids and not check_profile():
        return 1
    schema = engine.load_schema()
    answers = engine.load_answers()
    engine.ensure_seed(answers)
    sets = list(args.set or [])
    if args.inputs_env:
        # The Actions form hands its inputs over as one JSON env var, never interpolated into shell.
        raw = json.loads(os.environ.get(args.inputs_env) or "{}")
        sets += [f"{k}={'true' if v is True else 'false' if v is False else v}" for k, v in raw.items()]
    problems = apply_sets(schema, answers, sets)
    if problems:
        print("\n".join("✗ " + p for p in problems), file=sys.stderr)
        return 1
    sources = engine.read_sources(args.placeholder_ids)
    phases = [args.phase] if args.phase else ASKED_PHASES
    interactive = not args.non_interactive and not sets and sys.stdin.isatty()
    if interactive:
        print("Answer each question, or press Enter to keep the value in brackets.")
        interview(schema, answers, sources, phases, args.advanced)
        resolved = fix_errors_interactively(schema, answers, sources)
    else:
        resolved = engine.resolve(schema, answers, sources)
    engine.save_answers(answers)
    if args.phase:
        in_phase = {p["id"] for p in schema["parameters"] if p["phase"] == args.phase}
        resolved.errors = {k: v for k, v in resolved.errors.items() if k in in_phase}
    if resolved.errors:
        for pid, err in resolved.errors.items():
            print(f"✗ {pid}: {err}", file=sys.stderr)
        print("\nNothing written. Fix the values above (./nerdio init --set name=value) and run it again.", file=sys.stderr)
        return 1
    if args.phase == "discover":
        print("Discovery answers saved to .nerdio/answers.json. Next: ./nerdio preflight, then ./nerdio init --phase configure")
        return 0

    rendered, problems = engine.render(schema, resolved, args.placeholder_ids)
    if problems:
        print("\n".join("✗ " + p for p in problems), file=sys.stderr)
        print("\nNothing written.", file=sys.stderr)
        return 1
    ok = True
    for stage, tfvars in rendered.items():
        good, message = tfcheck.check_stage(engine.stage_dir(schema, stage, args.env), tfvars)
        print(("✓ " if good else "✗ ") + message)
        ok = ok and good
    if not ok:
        print("\nNothing written: Terraform didn't accept the values. This is a kit bug if the questions all passed; please report it.", file=sys.stderr)
        return 2
    written = engine.write_tfvars(schema, rendered, args.env)
    for path in written:
        print(f"Wrote {path.relative_to(engine.ROOT)} (gitignored)")
    text = json.dumps(rendered, indent=2)
    print("\n" + (text if args.show_ids else mask(text)))
    print("\nNext: ./nerdio preflight, then the Cloud Shell bootstrap script runs the plan.")
    return 0


def cmd_questions(args) -> int:
    """Everything the setup chatbot needs to ask the same questions as the CLI, as JSON."""
    schema = engine.load_schema()
    answers = engine.load_answers()
    engine.ensure_seed(answers)
    engine.save_answers(answers)
    resolved = engine.resolve(schema, answers, {"tenant": "", "subscription": ""})
    out = []
    for p in schema["parameters"]:
        if args.phase and p["phase"] != args.phase:
            continue
        if p["id"] not in resolved.active or not askable(p, args.advanced):
            continue
        item = {k: p[k] for k in ("id", "phase", "type", "question", "help") if k in p}
        for key in ("choices", "pattern", "min", "max", "kb", "sources", "form"):
            if key in p:
                item[key] = p[key]
        item["current"] = resolved.values.get(p["id"])
        item["answered"] = p["id"] in answers
        if p["id"] in resolved.errors:
            item["error"] = resolved.errors[p["id"]]
        out.append(item)
    print(json.dumps(out, indent=2))
    return 0


def cmd_show(args) -> int:
    schema = engine.load_schema()
    answers = engine.load_answers()
    resolved = engine.resolve(schema, answers, engine.read_sources(args.placeholder_ids))
    for p in schema["parameters"]:
        if p["id"] not in resolved.active:
            continue
        origin = "az/ARM_*" if "source" in p else "answer" if p["id"] in answers else "default"
        value = mask(show_value(resolved.values.get(p["id"], "?")))
        line = f"{p['id']:<30} {value:<40} {origin}"
        if p["id"] in resolved.errors:
            line += f"   ✗ {resolved.errors[p['id']]}"
        print(line)
    return 1 if resolved.errors else 0


def scan_regions(values: dict, regions: str, as_json: bool) -> int:
    sub = engine.az_json(["account", "show", "--query", "id"])
    if not sub:
        print("stopped: sign in with az login first", file=sys.stderr)
        return 1
    names = [r.strip() for r in regions.split(",") if r.strip()] or preflight.nearby_regions(values["location"])
    found = preflight.scan_regions(values, sub, names, None if as_json else
                                   lambda r: print(f"checking {r} ...", file=sys.stderr))
    if as_json:
        print(json.dumps({r: readiness_report.legacy(res) for r, res in found.items()}, indent=2))
    else:
        print(f"\n{values['vm_size']}, {values.get('app_service_plan_sku') or 'B3'} App Service, Azure SQL:\n")
        for region, res in found.items():
            bad = [x for x in res if x.status == "fail"]
            unsure = [x for x in res if x.status == "warn"]
            # vCPU quota is the one fix that's self-service (Azure Quota API, usually minutes).
            only_vcpu = bad and all(x.check == "vCPU quota" for x in bad)
            mark = "~" if only_vcpu else "✗" if bad else "!" if unsure else "✓"
            why = "; ".join(f"{x.check}: " + re.sub(r" for this subscription: .*", "", x.detail)
                            for x in bad + unsure) or "everything checked passes"
            print(f"{mark} {region:<20} {why}")
        good = [r for r, res in found.items() if not any(x.status == "fail" for x in res)]
        near = [r for r, res in found.items()
                if any(x.status == "fail" for x in res) and all(x.check == "vCPU quota" for x in res if x.status == "fail")]
        if good:
            print("\n✓ passes. Use one with ./nerdio init --set location=<region>")
        elif near:
            print(f"\n~ needs only vCPU quota, which is self-service: ./nerdio fix vcpu --location {near[0]} "
                  "--family <family> --limit <vCPUs>")
        else:
            print("\nNo region passes as is. Quota fixes (./nerdio fix ...) apply per region; "
                  "try another size with --set vm_size=<size>.")
    return 0


LAST_LOG = engine.ROOT / ".nerdio" / "logs" / "last.log"


def cmd_redact(args) -> int:
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8", errors="replace")
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    elif LAST_LOG.exists():
        text = LAST_LOG.read_text(encoding="utf-8", errors="replace")
    else:
        print("nothing to redact: pipe output in, name a file, or run the bootstrap script first", file=sys.stderr)
        return 1
    lines = redact.redact(text, redact.account_terms()).splitlines()
    print("\n".join(lines[-args.tail:] if args.tail else lines))
    return 0


def cmd_preflight(args) -> int:
    try:
        features = readiness_runner.parse_features(args.features)
        only = readiness_runner.parse_ids(args.only)
        skip = readiness_runner.parse_ids(args.skip)
    except readiness_runner.UsageError as exc:
        print(f"stopped: {exc}", file=sys.stderr)
        return readiness_report.USAGE
    fmt = "json" if args.json else args.format
    if args.list:
        if args.write:
            readiness_catalogue.write_page()
            print(f"Wrote the catalogue into {readiness_catalogue.KB_PAGE.relative_to(engine.ROOT)}")
            return 0
        print(readiness_catalogue.as_text(fmt))
        return 0
    if args.no_redact and not (args.out or args.save):
        print("stopped: --no-redact writes only to a private file; add --out FILE or --save DIR", file=sys.stderr)
        return readiness_report.USAGE
    if args.probe:
        from readiness import probe

        return probe.main(args.probe, args.vm, env=dict(os.environ), interactive=sys.stdin.isatty(), ask=input,
                          out=sys.stdout, err=sys.stderr)
    if not check_profile():
        return 1
    schema = engine.load_schema()
    answers = engine.load_answers()
    engine.ensure_seed(answers)
    # Inputs only the readiness check has (resource_group, intune_devices, ...) apply to this run only.
    extras, sets = {}, []
    for item in args.set or []:
        key, sep, raw = item.partition("=")
        if sep and key.strip() in readiness_standalone.EXTRA_INPUTS:
            try:
                extras[key.strip()] = readiness_standalone.extra_value(key.strip(), raw)
            except ValueError as exc:
                print(f"--set {key.strip()}: {exc}", file=sys.stderr)
                return readiness_report.USAGE
        else:
            sets.append(item)
    problems = apply_sets(schema, answers, sets)  # tried for this run only, not saved
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return readiness_report.USAGE
    resolved = engine.resolve(schema, answers, {"tenant": "", "subscription": ""})
    if args.regions is not None:
        return scan_regions(resolved.values, args.regions, args.json)
    resolved.values.update(extras, _env=args.env)
    ctx, results, started = readiness_main.evaluate(
        resolved.values, az=engine.az_json, stage=args.stage, features=features, only=only, skip=skip,
        show_names=args.names, nerdio_data=args.nerdio_data)
    version = str(schema.get("version", ""))
    redact_on = not args.no_redact

    def text(kind: str) -> str:
        return readiness_main.render(ctx, results, started, kind, redact=redact_on, parameters_version=version)

    if args.save:
        out_dir = Path(args.save)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, kind in (("readiness.json", "json"), ("readiness.md", "md")):
            readiness_report.write_private(str(out_dir / name), text(kind))
    if args.out:
        readiness_report.write_private(args.out, text(fmt))
    elif not args.no_redact:
        print(text(fmt))
    doc = readiness_report.document(ctx, results, started=started)
    return readiness_report.exit_code(doc["verdict"], results, args.strict)


def cmd_fix(args) -> int:
    if not check_profile():
        return 1
    schema = engine.load_schema()
    answers = engine.load_answers()
    engine.ensure_seed(answers)
    values = engine.resolve(schema, answers, {"tenant": "", "subscription": ""}).values
    try:
        sub = fix.az(["account", "show", "--query", "id"])
        if args.what == "quota":
            if args.status:
                return fix.quota_status(sub)
            return fix.fix_quota(sub, args.location or values["location"], args.sku, args.limit,
                                 args.country, args.email, args.timezone or values.get("timezone_id") or "UTC", args.yes)
        if args.what == "vcpu":
            if not args.family:
                print("stopped: --family is needed, e.g. --family standardDSv5Family (preflight's vCPU line names it)", file=sys.stderr)
                return 1
            return fix.fix_vcpu(sub, args.location or values["location"], args.family, args.limit, args.yes)
        return fix.fix_roles(sub, bool(values.get("create_entra_app")) and bool(values.get("grant_admin_consent")),
                             args.hours, args.yes)
    except fix.FixError as exc:
        print(f"stopped: {exc}", file=sys.stderr)
        return 1


def cmd_schema(args) -> int:
    schema = engine.load_schema()
    problems = engine.check_schema(schema)
    params = engine.params_by_id(schema)
    # Every example answer set must resolve, render and pass Terraform's own checks.
    examples = sorted((engine.ROOT / "schema" / "examples").glob("*.json"))
    for example in examples:
        answers = json.loads(example.read_text(encoding="utf-8"))
        resolved = engine.resolve(schema, answers, engine.read_sources(placeholders=True))
        problems += [f"{example.name}: {k}: {v}" for k, v in resolved.errors.items()]
        unknown = set(answers) - set(params) - {"_random4"}
        problems += [f"{example.name}: unknown parameter {k}" for k in sorted(unknown)]
        if resolved.errors:
            continue
        rendered, issues = engine.render(schema, resolved, placeholders=True)
        problems += [f"{example.name}: {i}" for i in issues]
        for stage, tfvars in rendered.items():
            good, message = tfcheck.check_stage(engine.stage_dir(schema, stage, "example"), tfvars)
            print(("✓ " if good else "✗ ") + f"{example.name}: {message}")
            if not good:
                problems.append(f"{example.name}: {message}")
    if not form.in_sync(schema):
        problems.append("the Actions form is out of date; run ./nerdio form --write")
    if not readiness_catalogue.page_in_sync():
        problems.append("the readiness catalogue in the KB is out of date; run ./nerdio preflight --list --write")
    for p in problems:
        print("✗ " + p)
    if not problems:
        print(f"✓ schema: {len(schema['parameters'])} parameters, {len(examples)} examples, form in sync")
    return 1 if problems else 0


def cmd_form(args) -> int:
    schema = engine.load_schema()
    if args.check:
        if form.in_sync(schema):
            print("✓ form matches the schema")
            return 0
        print("✗ form is out of date; run ./nerdio form --write", file=sys.stderr)
        return 1
    if args.write:
        print("Updated the form" if form.write(schema) else "Form already up to date")
        return 0
    print(form.inputs_block(schema))
    return 0


def pipeline_link(pipeline_stage: Path) -> tuple[dict, str]:
    """The assistant's pipeline settings, from 00-pipeline's outputs and this checkout's origin."""
    res = subprocess.run(["terraform", f"-chdir={pipeline_stage}", "output", "-json"], capture_output=True, text=True, check=False)
    try:
        outputs = {k: v["value"] for k, v in json.loads(res.stdout or "{}").items()}
    except (ValueError, KeyError, TypeError):
        outputs = {}
    if not outputs.get("storage_account_id"):
        return {}, "No deploy pipeline here yet: run ./scripts/pipeline/bootstrap.sh first."
    remote = subprocess.run(["git", "-C", str(engine.ROOT), "remote", "get-url", "origin"],
                            capture_output=True, text=True, check=False).stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
    if not m:
        return {}, "Couldn't tell the GitHub repository from this checkout's origin remote."
    return {"storage_account_id": outputs["storage_account_id"], "environment": outputs.get("environment", "sandbox"),
            "github": {"repository": m.group(1)}}, ""


def _tf_output(stage: Path, name: str):
    res = subprocess.run(["terraform", f"-chdir={stage}", "output", "-json", name],
                         capture_output=True, text=True, check=False)
    try:
        return json.loads(res.stdout) if res.returncode == 0 else None
    except ValueError:
        return None


def _write_private(path: Path, data: dict) -> None:
    old = os.umask(0o077)
    try:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    finally:
        os.umask(old)


def _terraform(stage: Path, *action: str) -> int:
    return subprocess.run(["terraform", f"-chdir={stage}", *action], check=False).returncode


def connect_claude(stage: Path, tfvars: dict, console: bool) -> dict | None:
    """Make (or show) the Claude API side of the chat's federation; returns the claude_api IDs."""
    federation = _tf_output(stage, "claude_federation")
    if not federation:
        print("✗ The chat isn't deployed with the Claude API yet, so there's no identity to trust. "
              "Run ./nerdio assistant --model-provider claude-api first.", file=sys.stderr)
        return None
    name = tfvars.get("name", "nme-assistant")
    if console:
        print(claude_federation.console_steps(name, federation))
        return None
    print("Connecting the chat to the Claude API (workload identity federation, no API key):")
    try:
        ids = claude_federation.connect(claude_federation.Admin(claude_federation.admin_token()), name, federation)
    except claude_federation.FederationError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return None
    return ids


def cmd_assistant(args) -> int:
    """Deploy the setup chatbot with Terraform. Run it in Azure Cloud Shell; IDs come from az."""
    stage = engine.ROOT / "environments" / args.env / "00-assistant"
    out = stage / "assistant.auto.tfvars.json"
    if not check_profile():
        return 1
    tfvars = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    sources = engine.read_sources()
    if not (sources["tenant"] and sources["subscription"]):
        print("✗ Not signed in: run az login (Cloud Shell already is), then try again.", file=sys.stderr)
        return 1
    tfvars.update({"tenant_id": sources["tenant"], "subscription_id": sources["subscription"]})
    for key, value in (("admin_group", args.admin_group), ("location", args.location), ("image", args.image),
                       ("model_provider", args.model_provider)):
        if value:
            tfvars[key] = value
    if args.foundry_location:
        tfvars.setdefault("foundry", {})["location"] = args.foundry_location
    if args.claude_ids:
        try:
            tfvars.setdefault("claude_api", {}).update(claude_federation.parse_ids(args.claude_ids))
        except claude_federation.FederationError as exc:
            print(f"✗ {exc}", file=sys.stderr)
            return 1
    if args.pipeline:
        link, problem = pipeline_link(stage.parent / "00-pipeline")
        if problem:
            print(f"✗ {problem}", file=sys.stderr)
            return 1
        tfvars["pipeline"] = link
    if not tfvars.get("admin_group"):
        print('✗ Name the Entra group allowed to use the assistant: --admin-group "AVD Admins"', file=sys.stderr)
        return 1
    if args.connect_claude and args.plan:
        print("✗ --connect-claude changes your Anthropic organization; run it without --plan.", file=sys.stderr)
        return 1
    _write_private(out, tfvars)
    print(f"Wrote {out.relative_to(engine.ROOT)} (gitignored). Only members of \"{tfvars['admin_group']}\" will be able to sign in.")
    if _terraform(stage, "init", "-input=false"):
        return 1
    if args.connect_claude:
        # The rule needs the chat's identity, so it must exist first; the first apply makes it.
        if not _tf_output(stage, "claude_federation") and not args.console:
            print("First, deploy the chat so it has an identity for the Claude API to trust:")
            if _terraform(stage, "apply"):
                return 1
        ids = connect_claude(stage, tfvars, args.console)
        if ids is None:
            return 0 if args.console else 1
        tfvars.setdefault("claude_api", {}).update(ids)
        _write_private(out, tfvars)
        print("Saved the Claude API IDs (not secrets). Applying so the chat uses them.")
        print(f"After this, drop the admin sign-in: ant auth logout --profile {claude_federation.ADMIN_PROFILE}")
    action = ["plan", "-input=false"] if args.plan else ["apply"]
    code = _terraform(stage, *action)
    if code == 0 and not args.plan:
        _terraform(stage, "output", "url")
        federation = _tf_output(stage, "claude_federation")
        if federation and not federation.get("connected"):
            print("Next, once: connect the chat to the Claude API. As an Anthropic organization admin, run")
            print(f"  ant auth login --no-browser --profile {claude_federation.ADMIN_PROFILE} --scope org:admin")
            print("  ./nerdio assistant --connect-claude")
            print("(or ./nerdio assistant --connect-claude --console for the Claude Console steps).")
        else:
            print("Open that URL and sign in. The first visit may take a few seconds while the app wakes up.")
        if tfvars.get("pipeline"):
            print("Then, once, open this to give the chat its GitHub App (one click on GitHub, then install it):")
            _terraform(stage, "output", "-raw", "github_setup_url")
            print()
    return code


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="nerdio", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("use", help="remember or switch to a kit environment's tenant and subscription")
    p.add_argument("env", nargs="?", help="kit environment name, e.g. trial or prod (omit to list them)")
    p.add_argument("--forget", action="store_true", help="delete this environment's saved profile")
    p.add_argument("--yes", action="store_true", help="save without asking")
    p.set_defaults(func=cmd_use)

    p = sub.add_parser("init", help="interview and write the tfvars")
    p.add_argument("--env", default="example", help="environment folder under environments/ (default: example)")
    p.add_argument("--phase", choices=ASKED_PHASES, help="only ask one phase's questions")
    p.add_argument("--advanced", action="store_true", help="also ask the advanced questions")
    p.add_argument("--set", action="append", metavar="NAME=VALUE", help="answer a question (repeatable)")
    p.add_argument("--inputs-env", metavar="VAR", help="read answers from a JSON object in this env var (the Actions form)")
    p.add_argument("--non-interactive", action="store_true", help="never prompt; fail on missing or bad values")
    p.add_argument("--placeholder-ids", action="store_true", help="use zero GUIDs instead of reading az (dry runs and CI)")
    p.add_argument("--show-ids", action="store_true", help="print IDs in full in the summary")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("questions", help="print the questions as JSON for the setup chatbot")
    p.add_argument("--phase", choices=ASKED_PHASES)
    p.add_argument("--advanced", action="store_true")
    p.set_defaults(func=cmd_questions)

    p = sub.add_parser("show", help="show current values and where each came from")
    p.add_argument("--placeholder-ids", action="store_true", help="don't read IDs from az")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("preflight", help="read-only readiness checks")
    p.add_argument("--env", default="example", help="environment folder under environments/ (post-install Terraform checks)")
    p.add_argument("--stage", choices=READINESS_STAGES, default="pre-install",
                   help="when you are: before the install (default), after it, or after Nerdio's wizard")
    p.add_argument("--features", default="", metavar="A,B,...",
                   help="also check these features: " + ", ".join(READINESS_FEATURES) + ", or all")
    p.add_argument("--format", choices=["console", "json", "md", "legacy"], default="console",
                   help="json: readiness.json (nerdio-readiness/1); md: a report to paste; legacy: the old bare list")
    p.add_argument("--json", action="store_true", help="same as --format json")
    p.add_argument("--strict", action="store_true", help="exit 1 on warnings too (the pipeline uses this)")
    p.add_argument("--save", metavar="DIR", help="also write readiness.json and readiness.md here (mode 600)")
    p.add_argument("--out", metavar="FILE", help="write the chosen format to this file (mode 600) instead of the screen")
    p.add_argument("--names", action="store_true", help="show resource, group and network names instead of masking them")
    p.add_argument("--no-redact", action="store_true",
                   help="keep IDs, emails and names; only with --out or --save, to a mode-600 file")
    p.add_argument("--list", action="store_true", help="print the check catalogue (add --write to update its KB page)")
    p.add_argument("--write", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--only", default="", metavar="ID,...", help="run only these checks")
    p.add_argument("--skip", default="", metavar="ID,...", help="leave these checks out")
    p.add_argument("--set", action="append", metavar="NAME=VALUE",
                   help="try a different answer for this run (not saved); also resource_group, nerdio_url, intune_devices, "
                        "app_attach_storage and the other inputs only the readiness check has")
    p.add_argument("--nerdio-data", action="store_true",
                   help="also read Nerdio's own REST API, with the REST client secret from the kit's Key Vault")
    p.add_argument("--probe", choices=["url-check"], help="run one opt-in probe that changes something (asks first)")
    p.add_argument("--vm", metavar="ID", help="with --probe url-check: the session host's resource ID")
    p.add_argument("--regions", nargs="?", const="", metavar="A,B,...",
                   help="check the region-specific items across regions (default: the configured region's geography)")
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("fix", help="request quota or activate PIM roles that preflight found missing")
    p.add_argument("what", choices=["quota", "vcpu", "roles"])
    p.add_argument("--family", help="vcpu: VM family quota name, e.g. standardDSv5Family")
    p.add_argument("--sku", default="B3", help="quota: App Service SKU (default B3, what Nerdio uses)")
    p.add_argument("--limit", type=int, default=2, help="quota/vcpu: new limit to ask for (default 2; give vcpu its own)")
    p.add_argument("--location", help="quota: region (default: your answers, else eastus2)")
    p.add_argument("--country", help="quota: 3-letter country for the support contact, if Entra doesn't have it")
    p.add_argument("--email", help="quota: where Azure Support replies (default: your account's mail)")
    p.add_argument("--timezone", help="quota: your time zone for the support contact")
    p.add_argument("--status", action="store_true", help="quota: list the kit's quota requests and their status")
    p.add_argument("--hours", type=int, default=4, help="roles: activation length in hours (default 4)")
    p.add_argument("--yes", action="store_true", help="don't ask before sending (for pipelines)")
    p.set_defaults(func=cmd_fix)

    p = sub.add_parser("redact", help="mask IDs, IPs, emails and tenant names in output before sharing it")
    p.add_argument("file", nargs="?", help="file to read (default: stdin, else the bootstrap's last log)")
    p.add_argument("--tail", type=int, metavar="N", help="only the last N lines")
    p.set_defaults(func=cmd_redact)

    p = sub.add_parser("schema", help="check the schema against the Terraform variables")
    p.add_argument("action", choices=["check"])
    p.set_defaults(func=cmd_schema)

    p = sub.add_parser("form", help="generate the Actions form from the schema")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    p.set_defaults(func=cmd_form)

    p = sub.add_parser("assistant", help="deploy the setup chatbot into this tenant with Terraform")
    p.add_argument("--admin-group", help="display name of the Entra group allowed to use it")
    p.add_argument("--location", help="region for the app (default eastus2)")
    p.add_argument("--model-provider", choices=["claude-api", "foundry"],
                   help="where the chat gets Claude (default claude-api: the Claude API, keyless)")
    p.add_argument("--foundry-location", help="region for Claude on Foundry, if different")
    p.add_argument("--connect-claude", action="store_true",
                   help="once: trust the chat's managed identity in your Anthropic organization (needs an org admin sign-in)")
    p.add_argument("--console", action="store_true", help="with --connect-claude: print the Claude Console steps instead")
    p.add_argument("--claude-ids", metavar="org=…,rule=…,account=…[,workspace=…]",
                   help="the Claude API IDs from the Console, if you connected there")
    p.add_argument("--image", help="container image (default: the kit's published image)")
    p.add_argument("--env", default="example", help="environment folder under environments/")
    p.add_argument("--plan", action="store_true", help="show the plan only")
    p.add_argument("--pipeline", action="store_true",
                   help="connect it to the deploy pipeline from scripts/pipeline/bootstrap.sh")
    p.set_defaults(func=cmd_assistant)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (engine.SchemaError, KeyboardInterrupt, EOFError) as exc:
        print(f"\nstopped: {exc}" if str(exc) else "\nstopped", file=sys.stderr)
        return 130 if isinstance(exc, (KeyboardInterrupt, EOFError)) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
