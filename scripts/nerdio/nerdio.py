"""./nerdio: the kit's engine entry point. Every front door (chat, this CLI, the Actions form) calls it.

  ./nerdio init                 interview, then write the tfvars (Terraform checks them)
  ./nerdio init --advanced      also ask the advanced questions
  ./nerdio init --set k=v ...   answer without prompts (add --non-interactive to never prompt)
  ./nerdio questions --phase discover   the questions as JSON, for the setup chatbot
  ./nerdio show                 the current answers and where each value came from
  ./nerdio preflight            read-only readiness checks (roles, providers, region, quota)
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

import engine
import fix
import form
import preflight
import tfcheck

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


def cmd_init(args) -> int:
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


def cmd_preflight(args) -> int:
    schema = engine.load_schema()
    answers = engine.load_answers()
    engine.ensure_seed(answers)
    resolved = engine.resolve(schema, answers, {"tenant": "", "subscription": ""})
    results = preflight.run(resolved.values)
    if args.json:
        print(preflight.as_json(results))
    else:
        icon = {"pass": "✓", "warn": "!", "fail": "✗", "manual": "?"}
        for r in results:
            print(f"{icon[r.status]} {r.check}: {r.detail}")
            if r.fix and r.status != "pass":
                print(f"    fix: {r.fix}")
        fails = sum(r.status == "fail" for r in results)
        manual = sum(r.status == "manual" for r in results)
        print(f"\n{'NO-GO' if fails else 'GO'}: {fails} to fix, {manual} to confirm yourself.")
    return 1 if any(r.status == "fail" for r in results) else 0


def cmd_fix(args) -> int:
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


def cmd_assistant(args) -> int:
    """Deploy the setup chatbot with Terraform. Run it in Azure Cloud Shell; IDs come from az."""
    stage = engine.ROOT / "environments" / args.env / "00-assistant"
    out = stage / "assistant.auto.tfvars.json"
    tfvars = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    sources = engine.read_sources()
    if not (sources["tenant"] and sources["subscription"]):
        print("✗ Not signed in: run az login (Cloud Shell already is), then try again.", file=sys.stderr)
        return 1
    tfvars.update({"tenant_id": sources["tenant"], "subscription_id": sources["subscription"]})
    for key, value in (("admin_group", args.admin_group), ("location", args.location), ("image", args.image)):
        if value:
            tfvars[key] = value
    if args.foundry_location:
        tfvars.setdefault("foundry", {})["location"] = args.foundry_location
    if not tfvars.get("admin_group"):
        print('✗ Name the Entra group allowed to use the assistant: --admin-group "AVD Admins"', file=sys.stderr)
        return 1
    old = os.umask(0o077)
    try:
        out.write_text(json.dumps(tfvars, indent=2) + "\n", encoding="utf-8")
    finally:
        os.umask(old)
    print(f"Wrote {out.relative_to(engine.ROOT)} (gitignored). Only members of \"{tfvars['admin_group']}\" will be able to sign in.")
    if subprocess.run(["terraform", f"-chdir={stage}", "init", "-input=false"], check=False).returncode:
        return 1
    action = ["plan", "-input=false"] if args.plan else ["apply"]
    code = subprocess.run(["terraform", f"-chdir={stage}", *action], check=False).returncode
    if code == 0 and not args.plan:
        subprocess.run(["terraform", f"-chdir={stage}", "output", "url"], check=False)
        print("Open that URL and sign in. The first visit may take a few seconds while the app wakes up.")
    return code


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="nerdio", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

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
    p.add_argument("--json", action="store_true")
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
    p.add_argument("--foundry-location", help="region for Claude on Foundry, if different")
    p.add_argument("--image", help="container image (default: the kit's published image)")
    p.add_argument("--env", default="example", help="environment folder under environments/")
    p.add_argument("--plan", action="store_true", help="show the plan only")
    p.set_defaults(func=cmd_assistant)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (engine.SchemaError, KeyboardInterrupt, EOFError) as exc:
        print(f"\nstopped: {exc}" if str(exc) else "\nstopped", file=sys.stderr)
        return 130 if isinstance(exc, (KeyboardInterrupt, EOFError)) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
