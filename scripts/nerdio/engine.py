"""Load the parameter schema, resolve answers against it, and render tfvars.

Standard library only, so it runs in Azure Cloud Shell, CI and a plain laptop alike.
The schema format is documented in schema/README.md.
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
import re
import secrets
import string
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schema" / "parameters.json"
ANSWERS_PATH = ROOT / ".nerdio" / "answers.json"

TYPES = {"string", "int", "bool", "enum", "uuid", "cidr", "ipv4_list", "group_list", "principal_list"}
ASK = {"always", "advanced", "never"}
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
TEMPLATE_RE = re.compile(r"\{([a-z0-9_]+)(?:\|([a-z_]+)(?::(\d+))?)?\}")
ROLES = ["nerdio", "network", "hostpools", "storage", "monitoring"]


class SchemaError(Exception):
    """The schema file itself is wrong."""


class AnswerError(Exception):
    """A value the user gave doesn't pass validation."""


def load_schema(path: Path = SCHEMA_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def params_by_id(schema: dict) -> dict:
    return {p["id"]: p for p in schema["parameters"]}


def load_answers(path: Path = ANSWERS_PATH) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_answers(answers: dict, path: Path = ANSWERS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = os.umask(0o077)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(answers, f, indent=2, sort_keys=True)
            f.write("\n")
    finally:
        os.umask(old)


# ---------------------------------------------------------------------------
# Value parsing and validation


def parse_input(param: dict, raw):
    """Turn user input (a string from a prompt, a form or --set, or a JSON value) into a typed value."""
    kind = param["type"]
    if isinstance(raw, str):
        text = raw.strip()
        if kind == "int":
            try:
                return int(text)
            except ValueError as exc:
                raise AnswerError("enter a whole number") from exc
        if kind == "bool":
            low = text.lower()
            if low in ("y", "yes", "true", "1", "on"):
                return True
            if low in ("n", "no", "false", "0", "off"):
                return False
            raise AnswerError("answer yes or no")
        if kind in ("ipv4_list", "group_list", "principal_list"):
            return [item.strip() for item in text.split(",") if item.strip()]
        return text
    return raw


def validate(param: dict, value) -> None:
    """Raise AnswerError when value doesn't fit the parameter. Mirrors the Terraform validation."""
    kind = param["type"]
    if kind == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            raise AnswerError("must be a whole number")
        if "min" in param and value < param["min"]:
            raise AnswerError(f"must be at least {param['min']}")
        if "max" in param and value > param["max"]:
            raise AnswerError(f"must be at most {param['max']}")
    elif kind == "bool":
        if not isinstance(value, bool):
            raise AnswerError("must be yes or no")
    elif kind == "enum":
        choices = {c["value"]: c for c in param["choices"]}
        if value not in choices:
            raise AnswerError("pick one of: " + ", ".join(str(v) for v in choices))
        if choices[value].get("supported") is False:
            raise AnswerError(choices[value].get("reason", "not supported by the kit yet"))
    elif kind == "uuid":
        if not isinstance(value, str) or not UUID_RE.match(value):
            raise AnswerError("must be a GUID")
    elif kind == "cidr":
        try:
            net = ipaddress.IPv4Network(value, strict=True)
        except (ValueError, TypeError) as exc:
            raise AnswerError("must be an IPv4 range like 10.50.0.0/20, with no host bits set") from exc
        if not net.is_private:
            raise AnswerError("must be a private range (10.x, 172.16-31.x or 192.168.x)")
        if "min_prefix" in param and net.prefixlen < param["min_prefix"]:
            raise AnswerError(f"must be /{param['min_prefix']} or smaller")
        if "max_prefix" in param and net.prefixlen > param["max_prefix"]:
            raise AnswerError(f"must be /{param['max_prefix']} or larger")
    elif kind in ("ipv4_list", "group_list", "principal_list"):
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise AnswerError("must be a comma-separated list")
        if kind == "ipv4_list":
            for v in value:
                try:
                    ipaddress.IPv4Address(v)
                except ValueError as exc:
                    raise AnswerError(f"{v} isn't an IPv4 address") from exc
        if len(value) < param.get("min_items", 0):
            raise AnswerError(f"needs at least {param['min_items']} entry")
    elif kind == "string":
        if not isinstance(value, str):
            raise AnswerError("must be text")
    if "pattern" in param and isinstance(value, str) and not re.fullmatch(param["pattern"], value):
        raise AnswerError(f"doesn't match {param['pattern']}")


# ---------------------------------------------------------------------------
# Resolution: answers + defaults + derivations -> a full set of values


def _filter(value: str, name: str | None, arg: str | None) -> str:
    if name is None:
        return value
    if name == "compact":
        out = re.sub(r"[^a-z0-9]", "", value.lower())
        return out[: int(arg)] if arg else out
    if name == "underscore":
        return re.sub(r"[^A-Za-z0-9]", "_", value)
    raise SchemaError(f"unknown filter {name}")


def expand(template: str, values: dict, extra: dict | None = None) -> str:
    ctx = dict(values)
    ctx.update(extra or {})

    def sub(m: re.Match) -> str:
        key, flt, arg = m.groups()
        if key not in ctx:
            raise SchemaError(f"template {template!r} refers to {key}, which isn't resolved yet")
        return _filter(str(ctx[key]), flt, arg)

    return TEMPLATE_RE.sub(sub, template)


def _quarters(cidr: str) -> list[ipaddress.IPv4Network]:
    net = ipaddress.IPv4Network(cidr)
    return list(net.subnets(prefixlen_diff=2))


DERIVATIONS = {
    "subnet_session_hosts": lambda v: str(_quarters(v["address_space"])[0]),
    "subnet_private_endpoints": lambda v: str(list(_quarters(v["address_space"])[1].subnets(new_prefix=27))[0]),
    "subnet_app_integration": lambda v: str(list(_quarters(v["address_space"])[1].subnets(new_prefix=27))[1]),
    "subnet_openbao": lambda v: str(list(_quarters(v["address_space"])[1].subnets(new_prefix=28))[4]),
    "host_capacity": lambda v: max(1, math.ceil(v["user_count"] / v["max_sessions_per_host"])),
}


def when_ok(param: dict, values: dict) -> bool:
    for key, allowed in param.get("when", {}).items():
        if values.get(key) not in allowed:
            return False
    return True


def default_for(param: dict, values: dict, answers: dict):
    default = param.get("default")
    if isinstance(default, dict) and "map" in default:
        return default["values"][values[default["map"]]]
    if isinstance(default, dict) and "derive" in default:
        return DERIVATIONS[default["derive"]](values)
    if isinstance(default, str):
        return expand(default, values, {"random4": answers.get("_random4", ""), "role": "{role}"})
    if isinstance(default, list):
        return list(default)
    return default


def ensure_seed(answers: dict) -> None:
    """A random four-character ending, generated once and kept, so default names stay stable across runs."""
    if not answers.get("_random4"):
        alphabet = string.ascii_lowercase + string.digits
        answers["_random4"] = "".join(secrets.choice(alphabet) for _ in range(4))


@dataclass
class Resolved:
    values: dict = field(default_factory=dict)
    active: list = field(default_factory=list)  # parameter ids whose `when` holds
    errors: dict = field(default_factory=dict)


def resolve(schema: dict, answers: dict, sources: dict | None = None) -> Resolved:
    """Walk the parameters in order, taking the answer, else the source, else the default."""
    sources = sources or {}
    out = Resolved()
    for p in schema["parameters"]:
        pid = p["id"]
        if not when_ok(p, out.values):
            continue
        out.active.append(pid)
        if "source" in p:
            value = sources.get(p["source"])
            if value is None:
                out.errors[pid] = f"couldn't read the {p['source']} ID (sign in with az, or set ARM_{p['source'].upper()}_ID)"
                continue
        elif pid in answers:
            value = answers[pid]
        else:
            try:
                value = default_for(p, out.values, answers)
            except (KeyError, SchemaError, ValueError) as exc:
                out.errors[pid] = f"no default could be worked out: {exc}"
                continue
        try:
            validate(p, value)
        except AnswerError as exc:
            out.errors[pid] = str(exc)
        out.values[pid] = value
    out.errors.update(cross_checks(schema, out.values))
    return out


def cross_checks(schema: dict, values: dict) -> dict:
    errors = {}
    for p in schema["parameters"]:
        for check in p.get("checks", []):
            if check == "subnets_in_address_space":
                errors.update(_check_subnets(values))
            elif check == "entra_app_for_terraform_install":
                if values.get("nerdio_install") == "terraform" and values.get("create_entra_app") is False:
                    errors["create_entra_app"] = ("the Terraform install builds Nerdio's Entra app itself, so this must be yes "
                                                  "(or pick the Marketplace install)")
            else:
                raise SchemaError(f"unknown check {check}")
    return errors


def _check_subnets(values: dict) -> dict:
    try:
        space = ipaddress.IPv4Network(values["address_space"])
        subnets = {k: ipaddress.IPv4Network(values[k]) for k in
                   ("session_hosts_subnet", "private_endpoints_subnet", "app_integration_subnet")}
        if "openbao_subnet" in values:
            subnets["openbao_subnet"] = ipaddress.IPv4Network(values["openbao_subnet"])
    except (KeyError, ValueError, TypeError):
        return {}
    errors = {}
    for key, net in subnets.items():
        if not net.subnet_of(space):
            errors[key] = f"{net} isn't inside the address range {space}"
    names = list(subnets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if subnets[a].overlaps(subnets[b]):
                errors[b] = f"{subnets[b]} overlaps {a.replace('_subnet', '')} ({subnets[a]})"
    if subnets["private_endpoints_subnet"].prefixlen > 28 or subnets["app_integration_subnet"].prefixlen > 28:
        errors.setdefault("private_endpoints_subnet", "private endpoint and app integration subnets need at least a /28")
    return errors


# ---------------------------------------------------------------------------
# Lookups the CLI does at render time, so IDs never pass through chat


def az_json(args: list[str]):
    try:
        res = subprocess.run(["az", *args, "-o", "json"], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def read_sources(placeholders: bool = False) -> dict:
    """Tenant and subscription: ARM_* env vars first (what Terraform's azurerm provider reads), then az."""
    if placeholders:
        zero = "00000000-0000-0000-0000-000000000000"
        return {"tenant": zero, "subscription": zero}
    tenant = os.environ.get("ARM_TENANT_ID")
    sub = os.environ.get("ARM_SUBSCRIPTION_ID")
    if not (tenant and sub):
        acct = az_json(["account", "show"]) or {}
        tenant = tenant or acct.get("tenantId")
        sub = sub or acct.get("id")
    return {"tenant": tenant, "subscription": sub}


def resolve_principals(names: list[str], placeholders: bool = False) -> tuple[list[str], list[str]]:
    """Group names (or "me") to object IDs. GUIDs pass straight through."""
    ids, problems = [], []
    for name in names:
        if UUID_RE.match(name):
            ids.append(name)
            continue
        if placeholders:
            ids.append("00000000-0000-0000-0000-000000000000")
            continue
        if name.lower() == "me":
            me = az_json(["ad", "signed-in-user", "show", "--query", "id"])
            if me:
                ids.append(me)
            else:
                problems.append('"me" needs a signed-in user (az login as a person, not a service principal)')
            continue
        found = az_json(["ad", "group", "list", "--filter", f"displayName eq '{name.replace(chr(39), chr(39) * 2)}'", "--query", "[].id"])
        if not found:
            problems.append(f"no Entra group named {name!r}")
        elif len(found) > 1:
            problems.append(f"{len(found)} groups are named {name!r}; use its object ID instead")
        else:
            ids.append(found[0])
    return ids, problems


# ---------------------------------------------------------------------------
# Rendering to tfvars


def _set_path(tree: dict, path: list[str], value) -> None:
    node = tree
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value


def render(schema: dict, resolved: Resolved, placeholders: bool = False) -> tuple[dict, list[str]]:
    """Return ({stage: tfvars dict}, problems). Lookups for group names happen here."""
    values = resolved.values
    stages: dict[str, dict] = {s: {} for s in schema["stages"]}
    problems: list[str] = []
    for const in schema.get("constants", []):
        _set_path(stages[const["stage"]], const["path"].split("."), const["value"])
    for p in schema["parameters"]:
        if p["id"] not in resolved.active or p["id"] not in values:
            continue
        for target in p.get("tfvars", []):
            value = values[p["id"]]
            if "value" in target:
                value = expand(target["value"], values)
            how = target.get("render")
            if how == "list":
                value = [value]
            elif how == "resource_groups":
                value = {role: expand(value, values, {"role": role}) for role in ROLES}
            if p["type"] in ("group_list", "principal_list"):
                value, issues = resolve_principals(value, placeholders)
                problems += [f"{p['id']}: {i}" for i in issues]
            if target.get("omit_empty") and value in ("", None, []):
                continue
            path = expand(target["path"], values).split(".")
            _set_path(stages[target["stage"]], path, value)
    for root in schema.get("roots", []):
        if not all(values.get(k) == v for k, v in root["null_unless"].items()):
            stages[root["stage"]][root["path"]] = None
    return stages, problems


def stage_dir(schema: dict, stage: str, env: str) -> Path:
    return ROOT / schema["stages"][stage].format(env=env)


def write_tfvars(schema: dict, rendered: dict, env: str) -> list[Path]:
    written = []
    old = os.umask(0o077)
    try:
        for stage, tfvars in rendered.items():
            path = stage_dir(schema, stage, env) / schema["output_file"]
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(tfvars, indent=2) + "\n")
            written.append(path)
    finally:
        os.umask(old)
    return written


# ---------------------------------------------------------------------------
# Schema self-check (run in CI)


def check_schema(schema: dict) -> list[str]:
    problems = []
    ids = set()
    phases = {ph["id"] for ph in schema["phases"]}
    for p in schema["parameters"]:
        pid = p.get("id", "?")
        if pid in ids:
            problems.append(f"{pid}: duplicate id")
        ids.add(pid)
        for key in ("phase", "type", "question", "help"):
            if key not in p:
                problems.append(f"{pid}: missing {key}")
        if p.get("type") not in TYPES:
            problems.append(f"{pid}: unknown type {p.get('type')}")
        if p.get("phase") not in phases:
            problems.append(f"{pid}: unknown phase {p.get('phase')}")
        if p.get("ask", "always") not in ASK:
            problems.append(f"{pid}: ask must be one of {sorted(ASK)}")
        if p.get("type") == "enum" and not p.get("choices"):
            problems.append(f"{pid}: enum needs choices")
        if p.get("form") and p.get("ask") in ("never", "advanced"):
            problems.append(f"{pid}: a form input should be a question everyone answers")
        if "source" in p and p.get("ask") != "never":
            problems.append(f"{pid}: sourced values are never asked")
        for target in p.get("tfvars", []):
            if target.get("stage") not in schema["stages"]:
                problems.append(f"{pid}: unknown stage {target.get('stage')}")
        for key in p.get("when", {}):
            if key not in ids:
                problems.append(f"{pid}: `when` refers to {key}, which must come earlier")
        for ref in p.get("kb", []):
            if not (ROOT / ref.split("#")[0]).exists():
                problems.append(f"{pid}: KB page {ref} doesn't exist")
    form_count = sum(1 for p in schema["parameters"] if p.get("form"))
    if form_count > 10:
        problems.append(f"{form_count} form inputs; keep workflow_dispatch forms to 10 or fewer")
    return problems
