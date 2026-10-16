#!/usr/bin/env python3
"""List knowledge base pages that need a look: stale, unverified, or reported broken.

    python3 scripts/kb/freshness.py --max-age-days 90 --output freshness.md

Flags:
  - pages whose last_reviewed is older than --max-age-days
  - pages with status unverified or partial, with the count of claims marked *unverified* inline
  - pages with unresolved "broke" or "outdated" field reports
  - known errors whose fix is still unverified

Writes a Markdown checklist and, under GitHub Actions, items=<count> to GITHUB_OUTPUT.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kblib  # noqa: E402
from kblib import rel  # noqa: E402

INLINE_UNVERIFIED = re.compile(r"\*(?:unverified|not verified)\b|not yet reviewed", re.I)


def collect(max_age_days: int, today: date) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"Reported broken or outdated": [], "Stale": [],
                                      "Unverified claims": [], "Unverified known-error fixes": []}
    reports = (kblib.load_yaml(kblib.FIELD_REPORTS) or {}).get("reports", [])
    open_reports: dict[str, list[dict]] = {}
    for r in reports:
        if r["outcome"] in ("broke", "outdated") and not r.get("resolved"):
            open_reports.setdefault(r["page"], []).append(r)

    for p in kblib.topic_pages():
        fm, body = kblib.split_front_matter(p.read_text(encoding="utf-8"))
        if not fm:
            continue
        page = rel(p)
        link = f"`docs/knowledge/{page}`"
        for r in open_reports.get(page, []):
            sections["Reported broken or outdated"].append(
                f"{link}: {r['outcome']} ({r['date']}, #{r['issue']}): {r['summary']}")
        age = (today - date.fromisoformat(fm["last_reviewed"])).days
        if age > max_age_days and fm["status"] != "plan":
            sections["Stale"].append(f"{link}: last reviewed {fm['last_reviewed']} ({age} days ago)")
        if fm["status"] in ("unverified", "partial"):
            n = len(INLINE_UNVERIFIED.findall(kblib.strip_code(body)))
            detail = f"{n} claim(s) marked unverified" if n else "no inline markers; re-check and update the status"
            sections["Unverified claims"].append(f"{link}: status {fm['status']}, {detail}")

    for e in (kblib.load_yaml(kblib.KNOWN_ERRORS) or {}).get("errors", []):
        if e["status"] == "unverified":
            sections["Unverified known-error fixes"].append(f"`{e['id']}`: {e['symptom'][:80]}")
    return sections


def render(sections: dict[str, list[str]], max_age_days: int) -> str:
    total = sum(len(v) for v in sections.values())
    lines = [
        f"Pages that need a look. Stale means not reviewed in {max_age_days} days.",
        "",
        "For each item: re-check the claim against a primary source or a real run, update the page,",
        "set `last_reviewed` (and `status` if it changed), and mark any field report `resolved: true`.",
        "",
    ]
    for title, items in sections.items():
        if items:
            lines += [f"## {title}", ""] + [f"- [ ] {i}" for i in items] + [""]
    if not total:
        lines.append("Nothing to review.")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-age-days", type=int, default=90)
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD), for testing")
    ap.add_argument("--output", help="write the report here instead of stdout")
    args = ap.parse_args()

    today = date.fromisoformat(args.today) if args.today else date.today()
    sections = collect(args.max_age_days, today)
    report = render(sections, args.max_age_days)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    else:
        print(report)
    if gh_out := os.environ.get("GITHUB_OUTPUT"):
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"items={sum(len(v) for v in sections.values())}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
