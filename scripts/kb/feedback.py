#!/usr/bin/env python3
"""Turn an accepted KB or drift issue into a pull request change.

Run by .github/workflows/kb-feedback.yml when a maintainer labels an issue kb-accepted. It reads
the issue and applies the change:
  - kb-feedback: appends a field report to docs/knowledge/field-reports.yaml
  - kb-known-error: appends a known error to docs/knowledge/troubleshooting/known-errors.yaml
  - kb-source: appends an expert nomination to docs/knowledge/experts.yaml
  - kb-digest: adds ticked (- [x]) digest items to their target KB pages and updates last_reviewed
  - settings-drift: syncs github/main.tf merge and topic settings with the live repository
and writes the branch name, PR title and PR body for the workflow to open a pull request.

    python3 scripts/kb/feedback.py --event "$GITHUB_EVENT_PATH"
    python3 scripts/kb/feedback.py --issue-json issue.json      # {"number", "title", "body", "labels"}

Issue text is untrusted: it's only parsed into fields, written as YAML data, then checked by
validate.py and reviewed in the pull request. Nothing from it is executed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kblib  # noqa: E402
from kblib import KB_DIR  # noqa: E402

OUTCOMES = {
    "Worked as described": "worked",
    "Broke or gave the wrong result": "broke",
    "Outdated (something changed upstream)": "outdated",
    "Missing (the KB should cover this)": "missing",
}
MAX_FIELD = 2000


class FeedbackError(Exception):
    pass


def parse_form(body: str) -> dict[str, str]:
    """Parse a rendered GitHub issue form ("### Label" headings followed by the answer)."""
    fields: dict[str, str] = {}
    parts = re.split(r"^### (.+?)\s*$", body.replace("\r\n", "\n"), flags=re.M)
    for label, value in zip(parts[1::2], parts[2::2]):
        value = value.strip()
        fields[label.strip()] = "" if value == "_No response_" else value
    return fields


def clean(value: str, field: str, required: bool = True) -> str:
    value = value.strip()
    if required and not value:
        raise FeedbackError(f"'{field}' is empty")
    if len(value) > MAX_FIELD:
        raise FeedbackError(f"'{field}' is longer than {MAX_FIELD} characters")
    return value


def kb_target(value: str, field: str, allow_url: bool = False) -> str:
    """Normalise a KB path (or URL) and check it exists."""
    value = value.strip().strip("`")
    if allow_url and value.startswith("https://"):
        return value
    value = value.removeprefix("/").removeprefix("docs/knowledge/")
    if not (KB_DIR / value.split("#")[0]).is_file():
        raise FeedbackError(f"'{field}' must be an existing path under docs/knowledge/"
                            + (" or an https:// link" if allow_url else "") + f", got {value!r}")
    return value


def public_safe(fields: dict[str, str]) -> None:
    if not re.search(r"^- \[[xX]\]", fields.get("Public-safe", ""), re.M):
        raise FeedbackError("the public-safe box isn't ticked")


def slug(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower().replace("`", "")).strip("-")
    return text[:50].rstrip("-") or "entry"


def add_field_report(issue: dict, fields: dict[str, str], today: str) -> tuple[str, str]:
    outcome = OUTCOMES.get(fields.get("Outcome", ""))
    if not outcome:
        raise FeedbackError(f"unknown outcome {fields.get('Outcome')!r}")
    report = {
        "date": today,
        "page": kb_target(fields.get("Page", ""), "Page"),
        "outcome": outcome,
        "summary": clean(fields.get("What happened", ""), "What happened"),
        "versions": clean(fields.get("Versions", ""), "Versions", required=False),
        "evidence": clean(fields.get("Evidence", ""), "Evidence", required=False),
        "issue": issue["number"],
    }
    report = {k: v for k, v in report.items() if v != ""}
    data = kblib.load_yaml(kblib.FIELD_REPORTS) or {"reports": []}
    if any(r.get("issue") == issue["number"] for r in data["reports"]):
        raise FeedbackError(f"issue #{issue['number']} is already in field-reports.yaml")
    data["reports"].append(report)
    write(kblib.FIELD_REPORTS, data)
    title = f"KB field report: {outcome} on {report['page']} (#{issue['number']})"
    todo = ("Update the page to match, then set the report's `resolved: true`."
            if outcome in ("broke", "outdated", "missing") else
            "If this confirms a claim marked *unverified*, update the page and its `status`.")
    return title, f"Adds a field report from #{issue['number']} to `docs/knowledge/field-reports.yaml`.\n\n{todo}"


def add_known_error(issue: dict, fields: dict[str, str], today: str) -> tuple[str, str]:
    symptom = clean(fields.get("Symptom", ""), "Symptom")
    data = kblib.load_yaml(kblib.KNOWN_ERRORS) or {"errors": []}
    if any(e.get("issue") == issue["number"] for e in data["errors"]):
        raise FeedbackError(f"issue #{issue['number']} is already in known-errors.yaml")
    ids = {e["id"] for e in data["errors"]}
    entry_id = slug(symptom)
    if entry_id in ids:
        entry_id = f"{entry_id}-{issue['number']}"
    entry = {
        "id": entry_id,
        "symptom": symptom,
        "cause": clean(fields.get("Cause", ""), "Cause"),
        "fix": clean(fields.get("Fix", ""), "Fix"),
        "source": kb_target(fields.get("Source", ""), "Source", allow_url=True),
        "applies_to": clean(fields.get("Versions", ""), "Versions", required=False),
        "status": "verified" if fields.get("Confidence", "").startswith("Fix confirmed") else "unverified",
        "added": today,
        "issue": issue["number"],
    }
    data["errors"].append({k: v for k, v in entry.items() if v != ""})
    write(kblib.KNOWN_ERRORS, data)
    return (f"Known error: {symptom[:60]} (#{issue['number']})",
            f"Adds known error `{entry_id}` from #{issue['number']} to "
            "`docs/knowledge/troubleshooting/known-errors.yaml` and regenerates the catalog page.")


def https_or_empty(value: str, field: str) -> str:
    value = clean(value, field, required=False)
    if value and not value.startswith("https://"):
        raise FeedbackError(f"'{field}' must be an https:// link")
    return value


def add_nomination(issue: dict, fields: dict[str, str], today: str) -> tuple[str, str]:
    name = clean(fields.get("Name", ""), "Name")
    if len(name) > 80:
        raise FeedbackError("'Name' is longer than 80 characters")
    links = {
        "blog": https_or_empty(fields.get("Blog", ""), "Blog"),
        "youtube": https_or_empty(fields.get("YouTube channel", ""), "YouTube channel"),
        "github": clean(fields.get("GitHub username", ""), "GitHub username", required=False).lstrip("@"),
    }
    if links["github"] and not re.fullmatch(r"[A-Za-z0-9-]{1,39}", links["github"]):
        raise FeedbackError("'GitHub username' isn't a valid GitHub username")
    links = {k: v for k, v in links.items() if v}
    if not links:
        raise FeedbackError("give at least one of Blog, YouTube channel or GitHub username")
    data = kblib.load_yaml(kblib.EXPERTS)
    if any(e.get("issue") == issue["number"] for e in data["experts"]):
        raise FeedbackError(f"issue #{issue['number']} is already in experts.yaml")
    ids = {e["id"] for e in data["experts"]}
    entry_id = slug(name)
    if entry_id in ids:
        raise FeedbackError(f"{name} is already in experts.yaml as '{entry_id}'")
    data["experts"].append({
        "id": entry_id,
        "name": name,
        "affiliation": "unknown",
        "status": "nominated",
        "found_via": [f"nomination (#{issue['number']}, {today})"],
        "links": links,
        "notes": clean(fields.get("Why follow them", ""), "Why follow them")[:300],
        "issue": issue["number"],
    })
    write(kblib.EXPERTS, data)
    return (f"KB source nomination: {name} (#{issue['number']})",
            f"Adds {name} to `docs/knowledge/experts.yaml` as nominated, from #{issue['number']}.\n\n"
            "Before merging, score them with the method in `docs/knowledge/experts.md`: add `gates`, "
            "`scores`, `reviewed` and evidence, set the status the scores give, and add a source to "
            "`sources.toml` with `expert = \"" + entry_id + "\"` if they're tracked. Or merge as is and the "
            "freshness check will list them as waiting.")


def write(path: Path, data) -> None:
    path.write_text(kblib.yaml_header(path) + kblib.dump_yaml(data), encoding="utf-8")


DIGEST_SECTION = re.compile(r"^### (.+?)(?:\s*→\s*`?([^`\s]+)`?)?\s*$")
DIGEST_TICKED = re.compile(
    r"^- \[[xX]\] \[([^\]]+)\]\((https://[^)\s]+)\)(?:\s*·\s*(\d{4}-\d{2}-\d{2}))?(.*)$"
)
PAGE_OVERRIDE = re.compile(r"→\s*`?([^`\s]+\.md)`?")


def add_digest(issue: dict, today: str) -> tuple[str, str]:
    body = (issue.get("body") or "").replace("\r\n", "\n")
    current_source = "Digest"
    current_page: str | None = None
    grouped: dict[str, list[tuple[str, str, str, str, str]]] = {}

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if m := DIGEST_SECTION.match(line):
            current_source = m.group(1).strip()
            current_page = m.group(2).strip() if m.group(2) else None
            continue
        if m := DIGEST_TICKED.match(line):
            title, url, item_date, rest = m.group(1).strip(), m.group(2).strip(), m.group(3) or today, m.group(4).strip()
            target_raw = current_page
            if pm := PAGE_OVERRIDE.search(rest):
                target_raw = pm.group(1)
                rest = PAGE_OVERRIDE.sub("", rest).strip()
            if not target_raw:
                raise FeedbackError(f"ticked item {title!r} has no target KB page; add '→ `docs/knowledge/<page>.md`'")
            page = kb_target(target_raw, "kb_page")
            rest = re.sub(r"^\([^)]*\)\s*", "", rest).lstrip("—:- ").strip()
            grouped.setdefault(page, []).append((title, url, item_date, current_source, rest))

    if not grouped:
        raise FeedbackError("no digest items are ticked (- [x])")

    added_count = 0
    touched_pages: list[str] = []
    for page, items in grouped.items():
        path = KB_DIR / page.split("#")[0]
        text = path.read_text(encoding="utf-8")
        new_bullets = []
        for title, url, item_date, source_name, note in items:
            if url in text:
                continue
            suffix = f": {note}" if note else ""
            new_bullets.append(f"- [{title}]({url}) ({source_name}, {item_date}){suffix}")
            added_count += 1
        text = re.sub(r"(?m)^last_reviewed:\s*\S+", f"last_reviewed: {today}", text, count=1)
        if new_bullets:
            block = "\n".join(new_bullets)
            if "\n## Recent upstream updates\n" in text:
                idx = text.index("\n## Recent upstream updates\n") + len("\n## Recent upstream updates\n")
                if idx < len(text) and text[idx] == "\n":
                    idx += 1
                text = text[:idx] + block + "\n" + text[idx:]
            elif "\n## Sources\n" in text:
                idx = text.index("\n## Sources\n")
                text = text[:idx] + "\n## Recent upstream updates\n\n" + block + "\n" + text[idx:]
            else:
                text = text.rstrip() + "\n\n## Recent upstream updates\n\n" + block + "\n"
        path.write_text(text, encoding="utf-8")
        touched_pages.append(f"`docs/knowledge/{page}`")

    if added_count == 0:
        raise FeedbackError("all ticked digest URLs are already linked in their target KB pages")

    title = f"KB digest: add {added_count} item(s) from #{issue['number']}"
    summary = (f"Adds {added_count} ticked item(s) from digest #{issue['number']} to "
               + ", ".join(touched_pages) + " and updates `last_reviewed`.")
    return title, summary


def add_settings_drift(issue: dict, today: str, repo_data: dict | None = None) -> tuple[str, str]:
    if repo_data is None:
        from sources import github
        repo_slug = os.environ.get("GITHUB_REPOSITORY", "nickprignano/nerdio-hcl")
        repo_data = github(f"/repos/{repo_slug}")
    main_tf = kblib.ROOT / "github" / "main.tf"
    if not main_tf.is_file():
        raise FeedbackError("github/main.tf not found")
    text = main_tf.read_text(encoding="utf-8")
    topics = json.dumps(sorted(repo_data.get("topics") or []))
    merge_keys = (
        "allow_merge_commit",
        "allow_squash_merge",
        "allow_rebase_merge",
        "allow_auto_merge",
        "allow_update_branch",
        "delete_branch_on_merge",
    )
    merge_lines = ["  merge = {"]
    for k in merge_keys:
        if k in repo_data and isinstance(repo_data[k], bool):
            val = "true" if repo_data[k] else "false"
            merge_lines.append(f"    {k:<22} = {val}")
    merge_lines.append("  }")
    merge_block = "\n".join(merge_lines)

    new_text = re.sub(r"(?m)^(\s*topics\s*=\s*)\[[^\]]*\].*$", rf"\g<1>{topics}", text, count=1)
    new_text = re.sub(r"(?ms)^  merge\s*=\s*\{[^}]*\}", merge_block, new_text, count=1)
    if new_text == text:
        raise FeedbackError("github/main.tf already matches the repository's current merge and topic settings")
    main_tf.write_text(new_text, encoding="utf-8")
    return (f"Sync github/main.tf with repository settings (#{issue['number']})",
            f"Updates `github/main.tf` (`merge` and `topics`) to match the live repository settings "
            f"reported in #{issue['number']}.")


def handle(issue: dict, today: str, repo_data: dict | None = None) -> tuple[str, str]:
    labels = {lbl["name"] if isinstance(lbl, dict) else lbl for lbl in issue.get("labels", [])}
    if "kb-digest" in labels:
        return add_digest(issue, today)
    if "settings-drift" in labels:
        return add_settings_drift(issue, today, repo_data=repo_data)
    fields = parse_form(issue.get("body") or "")
    public_safe(fields)
    if "kb-known-error" in labels:
        return add_known_error(issue, fields, today)
    if "kb-source" in labels:
        return add_nomination(issue, fields, today)
    if "kb-feedback" in labels:
        return add_field_report(issue, fields, today)
    raise FeedbackError(
        "the issue has none of the kb-feedback, kb-known-error, kb-source, kb-digest or settings-drift labels"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--event", help="GitHub event payload (issues event)")
    src.add_argument("--issue-json", help="a JSON file with number, title, body and labels")
    ap.add_argument("--body-file", default="pr-body.md", help="where to write the PR body")
    args = ap.parse_args()

    if args.event:
        issue = json.loads(Path(args.event).read_text(encoding="utf-8"))["issue"]
    else:
        issue = json.loads(Path(args.issue_json).read_text(encoding="utf-8"))

    try:
        title, body = handle(issue, date.today().isoformat())
    except FeedbackError as e:
        print(f"::error::Issue #{issue.get('number')}: {e}")
        Path("feedback-error.txt").write_text(str(e), encoding="utf-8")
        return 1

    body += f"\n\nCloses #{issue['number']}.\n"
    Path(args.body_file).write_text(body, encoding="utf-8")
    if gh_out := os.environ.get("GITHUB_OUTPUT"):
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"branch=kb-feedback/issue-{issue['number']}\n")
            f.write("title=" + " ".join(title.split()) + "\n")
    print(title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
