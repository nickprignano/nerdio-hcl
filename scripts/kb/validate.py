#!/usr/bin/env python3
"""Validate the knowledge base: front matter, decision records, YAML data, links and leak patterns.

    python3 scripts/kb/validate.py

Checks:
  - every topic page has front matter matching schema/page.schema.json, and its title matches the H1
  - every decision record has MADR front matter (schema/decision.schema.json) and the MADR sections
  - known-errors.yaml, upstream.yaml and field-reports.yaml match their schemas, ids are unique,
    and KB paths they reference exist
  - relative links and #anchors in KB pages and llms.txt resolve
  - no email addresses or public IPv4 addresses (the no-leak rule; gitleaks covers secrets)

Prints GitHub Actions ::error annotations and exits 1 on any error.
"""

from __future__ import annotations

import ipaddress
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kblib  # noqa: E402
from kblib import KB_DIR, ROOT, SCHEMA_DIR, rel  # noqa: E402

MADR_SECTIONS = ["## Context and Problem Statement", "## Considered Options", "## Decision Outcome"]
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# Documented placeholder addresses are allowed.
ALLOWED_EMAIL_DOMAINS = ("example.com", "contoso.com", "users.noreply.github.com")

errors: list[str] = []


def error(path: Path, msg: str, line: int | None = None) -> None:
    loc = f"file={path.relative_to(ROOT).as_posix()}" + (f",line={line}" if line else "")
    errors.append(f"::error {loc}::{msg}")


def schema(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8")))


def check_schema(validator: Draft202012Validator, data, path: Path, what: str) -> None:
    for e in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in e.path) or "(root)"
        error(path, f"{what} {where}: {e.message}")


def check_pages() -> None:
    v = schema("page.schema.json")
    for p in kblib.topic_pages():
        fm, body = kblib.split_front_matter(p.read_text(encoding="utf-8"))
        if fm is None:
            error(p, "missing YAML front matter (see docs/knowledge/schema/page.schema.json)", 1)
            continue
        check_schema(v, fm, p, "front matter")
        if fm.get("title") and kblib.h1(body) != fm["title"]:
            error(p, f"front matter title {fm['title']!r} doesn't match the H1 {kblib.h1(body)!r}")


def check_decisions() -> None:
    v = schema("decision.schema.json")
    for p in kblib.decision_records():
        fm, body = kblib.split_front_matter(p.read_text(encoding="utf-8"))
        if fm is None:
            error(p, "missing MADR front matter (status, date)", 1)
            continue
        check_schema(v, fm, p, "front matter")
        title = kblib.h1(body) or ""
        if not title.startswith(p.name[:4] + ". "):
            error(p, f"H1 should start with '{p.name[:4]}. '")
        for s in MADR_SECTIONS:
            if s not in body:
                error(p, f"missing MADR section '{s}'")


def kb_path_exists(target: str) -> bool:
    if target.startswith("https://"):
        return True
    return (KB_DIR / target.split("#")[0]).is_file()


def check_data() -> None:
    files = [
        (kblib.KNOWN_ERRORS, "known-errors.schema.json"),
        (kblib.UPSTREAM, "upstream.schema.json"),
        (kblib.FIELD_REPORTS, "field-reports.schema.json"),
    ]
    for path, schema_name in files:
        data = kblib.load_yaml(path)
        check_schema(schema(schema_name), data, path, "data")
        if not isinstance(data, dict):
            continue
        ids = [e.get("id") for lst in data.values() if isinstance(lst, list) for e in lst if isinstance(e, dict)]
        dupes = {i for i in ids if i and ids.count(i) > 1}
        for d in sorted(dupes):
            error(path, f"duplicate id {d!r}")
    for e in (kblib.load_yaml(kblib.KNOWN_ERRORS) or {}).get("errors", []):
        if not kb_path_exists(str(e.get("source", ""))):
            error(kblib.KNOWN_ERRORS, f"{e.get('id')}: source {e.get('source')!r} doesn't exist")
    for r in (kblib.load_yaml(kblib.FIELD_REPORTS) or {}).get("reports", []):
        if not kb_path_exists(str(r.get("page", ""))):
            error(kblib.FIELD_REPORTS, f"issue {r.get('issue')}: page {r.get('page')!r} doesn't exist")


def check_links(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    _, body = kblib.split_front_matter(text)
    searchable = kblib.strip_code(body)
    for m in LINK.finditer(searchable):
        target = m.group(1)
        if re.match(r"^[a-z]+:", target):
            continue
        file_part, _, anchor = target.partition("#")
        dest = (path.parent / file_part).resolve() if file_part else path
        line = text[: text.find(m.group(0))].count("\n") + 1 if m.group(0) in text else None
        if not dest.exists():
            error(path, f"broken link {target!r}", line)
            continue
        if anchor and dest.suffix == ".md":
            _, dest_body = kblib.split_front_matter(dest.read_text(encoding="utf-8"))
            if anchor not in kblib.anchors(dest_body):
                error(path, f"link {target!r}: no heading with anchor #{anchor}", line)


def check_leaks(path: Path) -> None:
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for m in EMAIL.finditer(line):
            if not m.group(0).lower().endswith(ALLOWED_EMAIL_DOMAINS):
                error(path, "email address; use a placeholder such as user@contoso.com", n)
        for m in IPV4.finditer(line):
            try:
                ip = ipaddress.ip_address(m.group(0))
            except ValueError:
                continue
            doc_ranges = ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
            if ip.is_global and not any(ip in ipaddress.ip_network(r) for r in doc_ranges):
                error(path, f"public IP {ip}; use a 10.x or RFC 5737 documentation address", n)


def main() -> int:
    check_pages()
    check_decisions()
    check_data()
    md_files = sorted(KB_DIR.rglob("*.md")) + [kblib.LLMS_TXT]
    for p in md_files:
        check_links(p)
    for p in md_files + sorted(KB_DIR.rglob("*.yaml")):
        check_leaks(p)
    print("\n".join(errors))
    print(f"{len(errors)} error(s) in the knowledge base" if errors else "knowledge base is valid")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
