"""The standalone readiness check: `python3 nerdio-preflight.pyz` in Azure Cloud Shell (Bash).

No kit, no tfvars. Inputs come from flags, then --answers FILE (the kit's answer keys), then a
short interview using the kit's own questions for whatever is still missing (--no-input turns
it off). Only parameters tagged with a readiness stage in schema/parameters.json are resolved.
"""

from __future__ import annotations

import argparse
import json
import os
import pkgutil
import sys
from typing import Callable, Dict, List, Optional

from . import __version__, catalogue, main, report, runner
from .model import FEATURES, STAGES

# Planning values the kit derives a default for; a default here would invent a network to check.
EXPLICIT_ONLY = {"address_space", "hub_vnet_id"}
# The standalone path is a manual Marketplace install unless the answers say otherwise.
STANDALONE_DEFAULTS = {"nerdio_install": "marketplace"}
IDENTITY_ALIASES = {"entra": "entra_joined", "entra_joined": "entra_joined", "ad_ds": "ad_ds", "entra_ds": "entra_ds"}
FLAG_KEYS = {"location": "location", "identity_model": "identity_model", "users": "user_count", "vm_size": "vm_size",
             "nerdio_url": "nerdio_url", "resource_group": "resource_group"}


def load_schema() -> Dict:
    """The copy of schema/parameters.json bundled in the zipapp, else the repo's."""
    try:
        data = pkgutil.get_data("readiness", "parameters.json")
    except (OSError, ValueError):
        data = None
    if data:
        return json.loads(data.decode("utf-8"))
    import engine  # running from the repo: scripts/nerdio is on the path

    return engine.load_schema()


def tagged(schema: Dict, stage: str) -> List[Dict]:
    return [p for p in schema["parameters"] if stage in p.get("readiness", [])]


def interview(params: List[Dict], answers: Dict, ask: Callable[[str], str], write: Callable[[str], None]) -> None:
    """Ask the discover-phase questions that are still unanswered, the way ./nerdio init asks them."""
    import engine

    for p in params:
        if p["id"] in answers or p.get("ask", "always") != "always" or p["phase"] != "discover":
            continue
        choices = p.get("choices") or []
        hint = f" [{'/'.join(str(c['value']) for c in choices)}]" if choices else ""
        default = p.get("default")
        shown = f" (default {default})" if isinstance(default, (str, int)) and default != "" else ""
        while True:
            raw = ask(f"{p['question']}{hint}{shown}: ").strip()
            if raw == "":
                break
            try:
                value = engine.parse_input(p, raw)
                if not kit_only_limit(p, value):
                    engine.validate(p, value)
            except engine.AnswerError as exc:
                write(f"  {exc}\n")
                continue
            answers[p["id"]] = value
            break


def resolve(schema: Dict, answers: Dict, stage: str):
    """Values for the tagged parameters: (values, problems). Untagged kit-only parameters are ignored."""
    import engine

    merged = dict(STANDALONE_DEFAULTS)
    merged.update(answers)
    merged.setdefault("_random4", "0000")
    resolved = engine.resolve(schema, merged, engine.read_sources(placeholders=True))
    ids = {p["id"] for p in tagged(schema, stage)} | set(FLAG_KEYS.values())
    values = {k: v for k, v in resolved.values.items() if k in ids and (k not in EXPLICIT_ONLY or k in answers)}
    for k in ("nerdio_url", "resource_group"):
        if answers.get(k):
            values[k] = answers[k]
    params = engine.params_by_id(schema)
    problems = [f"{k}: {v}" for k, v in resolved.errors.items()
                if k in ids and k in answers and not kit_only_limit(params[k], answers[k])]
    return values, problems


def kit_only_limit(param: Dict, value) -> bool:
    """A choice the kit can't build yet (`supported: false`) is still a valid Nerdio deployment to check."""
    return any(c["value"] == value and c.get("supported") is False for c in param.get("choices", []))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nerdio-preflight.pyz", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"nerdio readiness {__version__}")
    p.add_argument("--stage", choices=STAGES, default="pre-install")
    p.add_argument("--features", default="", metavar="A,B,...", help="also check: " + ", ".join(FEATURES) + ", or all")
    p.add_argument("--location", help="Azure region short name, e.g. eastus2")
    p.add_argument("--identity-model", choices=sorted(IDENTITY_ALIASES), help="how session hosts join a directory")
    p.add_argument("--users", type=int, help="how many people will use AVD")
    p.add_argument("--vm-size", help="session host size, e.g. Standard_D8s_v5")
    p.add_argument("--nerdio-url", help="after the install: Nerdio Manager's URL")
    p.add_argument("--resource-group", help="after the install: the resource group Nerdio Manager is in")
    p.add_argument("--answers", metavar="FILE", help="answers in the kit's format (same keys as schema/parameters.json)")
    p.add_argument("--set", action="append", default=[], metavar="NAME=VALUE", help="answer one question (repeatable)")
    p.add_argument("--no-input", action="store_true", help="never ask; missing inputs make their checks skipped")
    p.add_argument("--format", choices=["console", "json", "md"], default="console")
    p.add_argument("--json", action="store_true", help="same as --format json")
    p.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    p.add_argument("--save", metavar="DIR", help="also write readiness.json and readiness.md here (mode 600)")
    p.add_argument("--out", metavar="FILE", help="write the chosen format to this file (mode 600)")
    p.add_argument("--names", action="store_true", help="show resource, group and network names")
    p.add_argument("--no-redact", action="store_true", help="keep IDs and names; only with --out or --save")
    p.add_argument("--list", action="store_true", help="print the check catalogue")
    p.add_argument("--only", default="", metavar="ID,...")
    p.add_argument("--skip", default="", metavar="ID,...")
    return p


def collect_answers(args, schema: Dict) -> Dict:
    import engine

    answers: Dict = {}
    if args.answers:
        with open(args.answers, encoding="utf-8") as f:
            answers.update(json.load(f))
    params = engine.params_by_id(schema)
    for item in args.set:
        key, sep, raw = item.partition("=")
        if not sep or key.strip() not in params:
            raise runner.UsageError(f"--set {item}: unknown parameter")
        try:
            answers[key.strip()] = engine.parse_input(params[key.strip()], raw)
        except engine.AnswerError as exc:
            raise runner.UsageError(f"--set {key.strip()}: {exc}") from exc
    for flag, key in FLAG_KEYS.items():
        value = getattr(args, flag)
        if value is not None:
            answers[key] = IDENTITY_ALIASES[value] if flag == "identity_model" else value
    return answers


def run(argv: List[str], *, az: Optional[Callable] = None, ask: Callable[[str], str] = input,
        stdout=None, stderr=None, interactive: Optional[bool] = None, **ctx_kw) -> int:
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    args = parser().parse_args(argv)
    fmt = "json" if args.json else args.format
    try:
        features = runner.parse_features(args.features)
        only, skip = runner.parse_ids(args.only), runner.parse_ids(args.skip)
        if args.list:
            stdout.write(catalogue.as_text(fmt) + "\n")
            return 0
        if args.no_redact and not (args.out or args.save):
            raise runner.UsageError("--no-redact writes only to a private file; add --out FILE or --save DIR")
        schema = load_schema()
        answers = collect_answers(args, schema)
    except (runner.UsageError, ValueError, OSError) as exc:
        stderr.write(f"stopped: {exc}\n")
        return report.USAGE
    if interactive is None:
        interactive = not args.no_input and sys.stdin.isatty()
    if interactive:
        interview(tagged(schema, args.stage), answers, ask, stderr.write)
    values, problems = resolve(schema, answers, args.stage)
    if problems:
        stderr.write("stopped: " + "; ".join(problems) + "\n")
        return report.USAGE
    ctx, results, started = main.evaluate(values, mode="standalone", stage=args.stage, features=features, only=only,
                                          skip=skip, show_names=args.names, az=az, **ctx_kw)
    version = str(schema.get("version", ""))

    def text(kind: str) -> str:
        return main.render(ctx, results, started, kind, redact=not args.no_redact, parameters_version=version)

    if args.save:
        os.makedirs(args.save, exist_ok=True)
        for name, kind in (("readiness.json", "json"), ("readiness.md", "md")):
            report.write_private(os.path.join(args.save, name), text(kind))
    if args.out:
        report.write_private(args.out, text(fmt))
    elif not args.no_redact:
        stdout.write(text(fmt) + "\n")
    doc = report.document(ctx, results, started=started)
    return report.exit_code(doc["verdict"], results, args.strict)


def main_entry() -> None:
    sys.exit(run(sys.argv[1:]))
